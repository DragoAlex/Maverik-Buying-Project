"""
Maverick Buying Analyzer v2
============================
Mehrstufiger Prüfprozess zur systematischen Identifikation von Maverick Buying.
Jede Stufe scheidet Transaktionen aus oder eskaliert sie.

Prüfreihenfolge:
  1. Sortierung & Aggregation nach Lieferant
  2. Gremienprüfungs-Ausschluss (oberhalb Schwellenwert → raus)
  3. Zeitlicher Abstand (> 3 Wochen → kein Maverick)
  4. Materialbeschreibung (generisch vs. klar unterschiedlich)
  5a. Rahmenvertrag / automatische Bestellung prüfen
  5b. Einkäufer-Klärung (Genehmigung nachweisen)
  6. Täuschung / bewusstes Umgehen vs. Prozessfehler
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
import warnings
warnings.filterwarnings("ignore")


# ─────────────────────────────────────────────────────────────────────────────
# KONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────
CONFIG = {
    # ── Spaltennamen (an eigene Daten anpassen) ──────────────────────────────
    "col_order_id":          "Bestellnummer",
    "col_supplier":          "Lieferant",
    "col_amount":            "Betrag",
    "col_category":          "Warengruppe",
    "col_cost_center":       "Kostenstelle",
    "col_buyer_id":          "Einkäufernummer",
    "col_contract_flag":     "Rahmenvertrag",     # 'Ja'/'Nein' oder 1/0
    "col_auto_order_flag":   "AutoBestellung",    # optional: automatisierte Bestellung
    "col_order_date":        "Bestelldatum",
    "col_delivery_date":     "Lieferdatum",
    "col_quantity":          "Menge",
    "col_unit_price":        "Preis",
    "col_item_description":  "Artikelbeschreibung",
    "col_approval_doc":      "Genehmigungsnachweis",  # optional

    # ── Stufe 2: Gremien-Schwellenwert ───────────────────────────────────────
    # Bestellungen >= dieser Grenze werden durch Gremium geprüft → aus Maverick-Trichter raus
    "committee_threshold":   50_000.0,

    # ── Stufe 3: Zeitlicher Abstand ──────────────────────────────────────────
    # Bestellungen vom selben Lieferant/Warengruppe mit Abstand > X Tage = kein Maverick
    "time_gap_days":         21,   # 3 Wochen

    # ── Stufe 4: Materialbeschreibung ────────────────────────────────────────
    # Ähnlichkeits-Schwelle: Wert 0-1, je höher desto strenger
    "description_similarity_threshold": 0.6,

    # ── Stufe 5a: Rahmenvertrags-Ausschluss ──────────────────────────────────
    # Wenn Rahmenvertrag-Flag gesetzt UND kein zeitliches Clustering → raus
    "trust_contract_flag":   True,

    # ── Täuschungs-Indikatoren (Stufe 6) ────────────────────────────────────
    # Maximale Einzelbestellungen ohne Rahmenvertrag bei gleichem Lieferant+Warengruppe
    # bevor Täuschungsverdacht ausgelöst wird
    "deception_order_count": 5,
    # Mehrere Einkäufer für denselben Lieferanten ohne Rahmenvertrag = Verdacht
    "deception_multi_buyer":  True,
}


# ─────────────────────────────────────────────────────────────────────────────
# CONNECTOR-SCHICHT
# ─────────────────────────────────────────────────────────────────────────────
class DataConnector:
    @staticmethod
    def from_csv(path: str, **kwargs) -> pd.DataFrame:
        return pd.read_csv(path, **kwargs)

    @staticmethod
    def from_excel(path: str, sheet_name=0, **kwargs) -> pd.DataFrame:
        return pd.read_excel(path, sheet_name=sheet_name, **kwargs)

    @staticmethod
    def from_database(connection_string: str, query: str) -> pd.DataFrame:
        """SQLAlchemy-Anbindung. pip install sqlalchemy + Treiber."""
        try:
            from sqlalchemy import create_engine, text
            engine = create_engine(connection_string)
            with engine.connect() as conn:
                return pd.read_sql(text(query), conn)
        except ImportError:
            raise ImportError("pip install sqlalchemy")

    @staticmethod
    def from_dataframe(df: pd.DataFrame) -> pd.DataFrame:
        return df.copy()


# ─────────────────────────────────────────────────────────────────────────────
# NORMALISIERUNG
# ─────────────────────────────────────────────────────────────────────────────
def normalize(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    c = cfg
    df = df.copy()
    df.columns = df.columns.str.strip()

    for col in [c["col_order_date"], c["col_delivery_date"]]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", dayfirst=True)

    for col in [c["col_amount"], c["col_unit_price"], c["col_quantity"]]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Betrag ableiten falls nicht vorhanden
    if c["col_amount"] not in df.columns:
        if c["col_unit_price"] in df.columns and c["col_quantity"] in df.columns:
            df[c["col_amount"]] = df[c["col_unit_price"]] * df[c["col_quantity"]]

    # Rahmenvertrag-Flag normalisieren
    if c["col_contract_flag"] in df.columns:
        flag = df[c["col_contract_flag"]].astype(str).str.strip().str.lower()
        df["_contract_active"] = flag.isin(["ja", "yes", "1", "true", "x"])
    else:
        df["_contract_active"] = False

    # Automatische Bestellung
    if c["col_auto_order_flag"] in df.columns:
        af = df[c["col_auto_order_flag"]].astype(str).str.strip().str.lower()
        df["_auto_order"] = af.isin(["ja", "yes", "1", "true", "x"])
    else:
        df["_auto_order"] = False

    # Prüfstufe initialisieren
    df["_pruef_stufe"] = ""
    df["_ausgeschlossen"] = False
    df["_ausschluss_grund"] = ""
    df["_maverick_flags"] = [[] for _ in range(len(df))]
    df["_risk_score"] = 0

    return df


# ─────────────────────────────────────────────────────────────────────────────
# HILFSFUNKTIONEN
# ─────────────────────────────────────────────────────────────────────────────
def _add_flag(df, mask, reason, score=0):
    for idx in df[mask & ~df["_ausgeschlossen"]].index:
        df.at[idx, "_maverick_flags"].append(reason)
        df.at[idx, "_risk_score"] += score


def _exclude(df, mask, grund, stufe):
    """Scheidet Transaktionen aus dem Maverick-Trichter aus."""
    active = mask & ~df["_ausgeschlossen"]
    df.loc[active, "_ausgeschlossen"] = True
    df.loc[active, "_ausschluss_grund"] = grund
    df.loc[active, "_pruef_stufe"] = stufe
    return df


def _remaining(df):
    return df[~df["_ausgeschlossen"]]


def _text_similarity(a: str, b: str) -> float:
    """Einfache Jaccard-Ähnlichkeit auf Wortebene."""
    if not a or not b:
        return 0.0
    words_a = set(str(a).lower().split())
    words_b = set(str(b).lower().split())
    if not words_a or not words_b:
        return 0.0
    return len(words_a & words_b) / len(words_a | words_b)


# ─────────────────────────────────────────────────────────────────────────────
# PRÜFSTUFEN
# ─────────────────────────────────────────────────────────────────────────────

def stufe1_lieferant_aggregation(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """
    Stufe 1: Sortierung und Aggregation nach Lieferant.
    Keine Ausschlüsse – erzeugt Übersichtsstruktur.
    """
    c = cfg
    if c["col_supplier"] in df.columns and c["col_amount"] in df.columns:
        agg = (df.groupby(c["col_supplier"])[c["col_amount"]]
               .agg(["sum", "count", "mean"])
               .rename(columns={"sum": "_vol_total", "count": "_vol_count",
                                 "mean": "_vol_mean"})
               .reset_index())
        df = df.merge(agg, on=c["col_supplier"], how="left")
    df.loc[~df["_ausgeschlossen"], "_pruef_stufe"] = "S1"
    return df


def stufe2_gremien_ausschluss(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """
    Stufe 2: Bestellungen >= committee_threshold durch Gremium geprüft → raus.
    """
    c = cfg
    threshold = cfg["committee_threshold"]
    if c["col_amount"] in df.columns:
        mask = df[c["col_amount"]] >= threshold
        df = _exclude(df, mask, f"Gremiumspflichtig (≥ {threshold:,.0f} €)", "S2")
        n = mask.sum()
        print(f"   S2: {n} Transaktionen ausgeschlossen (Gremium, ≥{threshold:,.0f}€)")
    return df


def stufe3_zeitlicher_abstand(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """
    Stufe 3: Bestellungen desselben Lieferanten/Warengruppe mit Abstand
    > time_gap_days → kein Maverick, ausschließen.
    Nur Bestellungen INNERHALB des Zeitfensters bleiben im Trichter.
    """
    c = cfg
    gap = cfg["time_gap_days"]
    date_col = c["col_order_date"]
    supplier_col = c["col_supplier"]

    if date_col not in df.columns or supplier_col not in df.columns:
        return df

    remaining = _remaining(df).copy()
    group_cols = [supplier_col]
    if c["col_category"] in df.columns:
        group_cols.append(c["col_category"])

    # Flag: hat diese Bestellung eine zeitlich nahe Schwesterbestellung?
    df["_has_cluster"] = False

    for key, group in remaining.groupby(group_cols, dropna=False):
        dates = group[date_col].dropna().sort_values()
        if len(dates) < 2:
            continue
        # Prüfe Abstände: wenn irgendein Paar <= gap Tage → cluster
        clustered_idx = set()
        dates_list = list(dates.items())  # (idx, date)
        for i in range(len(dates_list)):
            for j in range(i + 1, len(dates_list)):
                idx_i, d_i = dates_list[i]
                idx_j, d_j = dates_list[j]
                if abs((d_j - d_i).days) <= gap:
                    clustered_idx.add(idx_i)
                    clustered_idx.add(idx_j)

        df.loc[list(clustered_idx), "_has_cluster"] = True

    # Bestellungen OHNE zeitliches Cluster → kein Maverick-Verdacht → raus
    no_cluster = ~df["_has_cluster"] & ~df["_ausgeschlossen"]
    df = _exclude(df, no_cluster, f"Einzelkauf (kein Zeitcluster ≤{gap}d)", "S3")
    n_out = no_cluster.sum()
    n_cluster = df["_has_cluster"].sum()
    print(f"   S3: {n_out} Einzelkäufe ausgeschlossen · {n_cluster} im Zeitcluster")
    return df


def stufe4_materialbeschreibung(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """
    Stufe 4: Materialbeschreibung analysieren.
    - Sehr ähnliche Beschreibungen bei zeitlich nahen Bestellungen = Split-Verdacht
    - Klar unterschiedliche Beschreibungen → Ausschluss
    """
    c = cfg
    desc_col = c["col_item_description"]
    supplier_col = c["col_supplier"]
    date_col = c["col_order_date"]
    threshold = cfg["description_similarity_threshold"]

    if desc_col not in df.columns:
        return df

    remaining = _remaining(df)
    group_cols = [supplier_col]
    if c["col_category"] in df.columns:
        group_cols.append(c["col_category"])

    df["_desc_similar"] = False
    df["_desc_generic"] = False

    GENERIC_TOKENS = {
        "material", "artikel", "produkt", "ware", "teil", "verschiedene",
        "sonstiges", "misc", "various", "general", "other", "item",
        "goods", "supply", "supplies"
    }

    for key, group in remaining.groupby(group_cols, dropna=False):
        if len(group) < 2:
            continue

        descs = group[desc_col].fillna("").astype(str).tolist()
        idxs = group.index.tolist()

        # Genericität prüfen
        for i, desc in enumerate(descs):
            words = set(desc.lower().split())
            generic_ratio = len(words & GENERIC_TOKENS) / max(len(words), 1)
            if generic_ratio > 0.4 or len(words) <= 2:
                df.at[idxs[i], "_desc_generic"] = True

        # Paarweise Ähnlichkeit
        for i in range(len(descs)):
            for j in range(i + 1, len(descs)):
                sim = _text_similarity(descs[i], descs[j])
                if sim >= threshold:
                    df.at[idxs[i], "_desc_similar"] = True
                    df.at[idxs[j], "_desc_similar"] = True

    # Klar unterschiedliche, nicht-generische Beschreibungen → Ausschluss
    clearly_different = (~df["_desc_similar"] & ~df["_desc_generic"]
                         & ~df["_ausgeschlossen"])
    df = _exclude(df, clearly_different,
                  "Klar unterschiedliche Artikelbeschreibungen", "S4")

    # Split-Verdacht flaggen
    split_mask = df["_desc_similar"] & df["_has_cluster"] & ~df["_ausgeschlossen"]
    _add_flag(df, split_mask, "Split-Verdacht: ähnliche Beschreibung + Zeitcluster", score=3)

    # Generisch-Flag
    generic_mask = df["_desc_generic"] & ~df["_ausgeschlossen"]
    _add_flag(df, generic_mask, "Generische Artikelbeschreibung", score=1)

    n_out = clearly_different.sum()
    n_split = split_mask.sum()
    print(f"   S4: {n_out} klar unterschiedlich ausgeschlossen · {n_split} Split-Verdacht")
    return df


def stufe5a_rahmenvertrag(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """
    Stufe 5a: Rahmenvertrag / automatische Bestellung prüfen.
    Wenn aktiver Rahmenvertrag UND kein Split-Cluster-Verdacht → regelkonform, raus.
    Verbleibende mit Rahmenvertrag aber Clusterauffälligkeit → erhöhter Klärungsbedarf.
    """
    c = cfg

    remaining_mask = ~df["_ausgeschlossen"]

    # Regelkonform: Rahmenvertrag aktiv + kein Split-Verdacht
    has_split = df["_maverick_flags"].apply(
        lambda x: any("Split" in f for f in x)
    )
    regelkonform = (df["_contract_active"] | df["_auto_order"]) & ~has_split & remaining_mask
    df = _exclude(df, regelkonform,
                  "Rahmenvertrag/Autom. Bestellung regelkonform (Rücksprache bestätigt)", "S5a")

    # Rahmenvertrag + Split-Verdacht → eskaliert
    rv_mit_verdacht = (df["_contract_active"] | df["_auto_order"]) & has_split & remaining_mask
    _add_flag(df, rv_mit_verdacht,
              "Rahmenvertrag vorhanden aber Split-Muster auffällig – Klärung nötig", score=2)

    # Kein Rahmenvertrag → weiter in Trichter
    kein_rv = ~df["_contract_active"] & ~df["_auto_order"] & remaining_mask
    _add_flag(df, kein_rv, "Kein Rahmenvertrag", score=2)

    n_out = regelkonform.sum()
    print(f"   S5a: {n_out} regelkonform (Rahmenvertrag) ausgeschlossen")
    return df


def stufe5b_einkäufer_klärung(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """
    Stufe 5b: Einkäufer-Klärung.
    Wenn Genehmigungsnachweis vorhanden → ausschließen (geklärt).
    Verbleibende ohne Nachweis bleiben im Trichter.
    """
    c = cfg
    approval_col = c["col_approval_doc"]
    remaining_mask = ~df["_ausgeschlossen"]

    if approval_col in df.columns:
        has_approval = (df[approval_col].notna() &
                        df[approval_col].astype(str).str.strip().str.len() > 0)
        mask = has_approval & remaining_mask
        df = _exclude(df, mask,
                      "Genehmigung durch Einkäufer dokumentiert", "S5b")
        n_out = mask.sum()
        print(f"   S5b: {n_out} mit Einkäufer-Nachweis ausgeschlossen")
    else:
        # Spalte nicht vorhanden → alle verbleibenden brauchen manuelle Klärung
        _add_flag(df, remaining_mask,
                  "Einkäufer-Klärung ausstehend (kein Nachweis-Feld vorhanden)", score=1)
        print(f"   S5b: Spalte '{approval_col}' fehlt – alle verbleibenden zur Klärung markiert")

    return df


def stufe6_täuschung_prozessfehler(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """
    Stufe 6: Bewusste Täuschung vs. Prozessfehler unterscheiden.

    Täuschungs-Indikatoren:
    - Sehr hohe Anzahl Bestellungen bei gleichem Lieferant ohne Rahmenvertrag
    - Mehrere verschiedene Einkäufer für denselben Lieferanten ohne Rahmenvertrag
    - Zeitcluster direkt unterhalb des Gremien-Schwellenwerts (Splitting)

    Prozessfehler-Indikatoren:
    - Einmaliger Vorfall ohne Muster
    - Erster Einkäufer-Kontakt mit diesem Lieferanten
    """
    c = cfg
    remaining_mask = ~df["_ausgeschlossen"]
    remaining = df[remaining_mask]

    if remaining.empty:
        return df

    supplier_col = c["col_supplier"]
    buyer_col = c["col_buyer_id"]
    amount_col = c["col_amount"]

    df["_deception_score"] = 0
    df["_deception_flags"] = [[] for _ in range(len(df))]

    for supplier, group in remaining.groupby(supplier_col, dropna=False):
        idxs = group.index.tolist()
        n = len(group)

        # Indikator 1: Viele Bestellungen ohne Rahmenvertrag
        no_rv = group[~group["_contract_active"]]
        if len(no_rv) >= cfg["deception_order_count"]:
            for idx in idxs:
                df.at[idx, "_deception_score"] += 3
                df.at[idx, "_deception_flags"].append(
                    f"Systematisch ohne Rahmenvertrag ({len(no_rv)}x)"
                )

        # Indikator 2: Mehrere Einkäufer ohne Rahmenvertrag
        if cfg["deception_multi_buyer"] and buyer_col in group.columns:
            buyers_no_rv = no_rv[buyer_col].nunique()
            if buyers_no_rv >= 2:
                for idx in idxs:
                    df.at[idx, "_deception_score"] += 2
                    df.at[idx, "_deception_flags"].append(
                        f"Mehrere Einkäufer ohne Rahmenvertrag ({buyers_no_rv})"
                    )

        # Indikator 3: Beträge knapp unter Gremien-Schwellenwert
        if amount_col in group.columns:
            threshold = cfg["committee_threshold"]
            near_threshold = group[
                (group[amount_col] >= threshold * 0.85) &
                (group[amount_col] < threshold)
            ]
            if len(near_threshold) >= 2:
                for idx in idxs:
                    df.at[idx, "_deception_score"] += 3
                    df.at[idx, "_deception_flags"].append(
                        f"Beträge knapp unter Gremiumschwelle ({len(near_threshold)}x)"
                    )

    # Klassifizierung
    high_deception = (df["_deception_score"] >= 5) & remaining_mask
    low_deception = (df["_deception_score"] > 0) & (df["_deception_score"] < 5) & remaining_mask
    process_error = (df["_deception_score"] == 0) & remaining_mask

    df.loc[high_deception, "_final_classification"] = "🔴 Täuschungsverdacht"
    df.loc[low_deception, "_final_classification"] = "🟠 Möglicher Prozessfehler"
    df.loc[process_error, "_final_classification"] = "🟡 Ungeklärter Einzelfall"
    df.loc[df["_ausgeschlossen"], "_final_classification"] = "✅ Ausgeschlossen"

    # Deception-Flags in Maverick-Flags integrieren
    for idx in df[remaining_mask].index:
        for f in df.at[idx, "_deception_flags"]:
            if f not in df.at[idx, "_maverick_flags"]:
                df.at[idx, "_maverick_flags"].append(f)
        df.at[idx, "_risk_score"] += df.at[idx, "_deception_score"]

    n_td = high_deception.sum()
    n_pf = low_deception.sum()
    n_ef = process_error.sum()
    print(f"   S6: {n_td} Täuschungsverdacht · {n_pf} Prozessfehler · {n_ef} Einzelfälle")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# HAUPT-ANALYSE
# ─────────────────────────────────────────────────────────────────────────────
def analyze(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Führt alle Prüfstufen sequenziell aus."""

    print("\n🔍 Starte mehrstufige Maverick-Prüfung ...")
    print(f"   Eingang: {len(df):,} Transaktionen\n")

    df = stufe1_lieferant_aggregation(df, cfg)
    print(f"   S1: Lieferant-Aggregation abgeschlossen")

    df = stufe2_gremien_ausschluss(df, cfg)
    df = stufe3_zeitlicher_abstand(df, cfg)
    df = stufe4_materialbeschreibung(df, cfg)
    df = stufe5a_rahmenvertrag(df, cfg)
    df = stufe5b_einkäufer_klärung(df, cfg)
    df = stufe6_täuschung_prozessfehler(df, cfg)

    # Finales Maverick-Flag
    df["_is_maverick"] = ~df["_ausgeschlossen"]
    df["_maverick_reason"] = df["_maverick_flags"].apply(
        lambda x: "; ".join(x) if x else "—"
    )
    df["_risk_level"] = df["_risk_score"].apply(_score_to_level)

    # Klassifizierung für ausgeschlossene
    df.loc[df["_ausgeschlossen"] & df["_final_classification"].isna(),
           "_final_classification"] = "✅ Ausgeschlossen"

    remaining = (~df["_ausgeschlossen"]).sum()
    print(f"\n   → Verbleibende Maverick-Kandidaten: {remaining:,}")
    return df


def _score_to_level(score):
    if score == 0:   return "✅ OK"
    if score <= 2:   return "🟡 Niedrig"
    if score <= 5:   return "🟠 Mittel"
    return               "🔴 Hoch"


# ─────────────────────────────────────────────────────────────────────────────
# REPORT-GENERATOR
# ─────────────────────────────────────────────────────────────────────────────
def generate_report(df: pd.DataFrame, cfg: dict,
                    output_path: str = "maverick_report_v2.xlsx"):
    """
    Excel-Report mit 5 Sheets:
    1. Zusammenfassung / Trichter-KPIs
    2. Maverick-Kandidaten (prüffähig, sortiert nach Risiko)
    3. Täuschungsverdacht (Eskalationsliste)
    4. Vollständige Transaktionsliste
    5. Lieferanten-Ranking
    """
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    wb = Workbook()

    # ── Design-Konstanten ──────────────────────────────────────────────────
    HDR    = "1F3864"
    RED    = "FFCCCC"
    ORANGE = "FFE0B2"
    YELLOW = "FFF9C4"
    GREEN  = "C8E6C9"
    BLUE   = "BBDEFB"
    GREY   = "F5F5F5"

    thin = Side(style="thin", color="CCCCCC")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    def hdr(cell, bg=HDR, fg="FFFFFF"):
        cell.font = Font(bold=True, color=fg, name="Arial", size=9)
        cell.fill = PatternFill("solid", start_color=bg)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = border

    def cell_style(cell, bg=None, bold=False, align="left", size=9):
        cell.font = Font(name="Arial", size=size, bold=bold)
        cell.alignment = Alignment(horizontal=align, vertical="center", wrap_text=False)
        cell.border = border
        if bg:
            cell.fill = PatternFill("solid", start_color=bg)

    def autofit(ws, mn=8, mx=50):
        for col in ws.columns:
            w = max(len(str(c.value or "")) for c in col)
            ws.column_dimensions[get_column_letter(col[0].column)].width = \
                min(max(w + 2, mn), mx)

    def row_bg(classification):
        if "Täuschung" in str(classification): return RED
        if "Prozessfehler" in str(classification): return ORANGE
        if "Einzelfall" in str(classification): return YELLOW
        if "Ausgeschlossen" in str(classification): return GREEN
        return None

    # ── SHEET 1: ZUSAMMENFASSUNG ───────────────────────────────────────────
    ws = wb.active
    ws.title = "📊 Zusammenfassung"
    ws.sheet_view.showGridLines = False

    total = len(df)
    amt_col = cfg["col_amount"]
    total_spend = df[amt_col].sum() if amt_col in df.columns else 0

    # Trichter-Daten
    stufen = {
        "S2 – Gremium":          df[df["_ausschluss_grund"].str.contains("Gremium", na=False)],
        "S3 – Zeitabstand":      df[df["_ausschluss_grund"].str.contains("Einzelkauf", na=False)],
        "S4 – Materialbeschr.":  df[df["_ausschluss_grund"].str.contains("Beschreibung", na=False)],
        "S5a – Rahmenvertrag":   df[df["_ausschluss_grund"].str.contains("Rahmenvertrag|Autom", na=False)],
        "S5b – Einkäufer":       df[df["_ausschluss_grund"].str.contains("Genehmigung", na=False)],
    }

    mav_df = df[df["_is_maverick"]]
    mav_vol = mav_df[amt_col].sum() if amt_col in mav_df.columns else 0

    ws["A1"] = "MAVERICK BUYING ANALYSE – PRÜFTRICHTER"
    ws["A1"].font = Font(bold=True, size=14, name="Arial", color="1F3864")
    ws["A2"] = f"Erstellt: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    ws["A2"].font = Font(size=9, name="Arial", color="888888")

    ws["A4"] = "Prüfstufe"
    ws["B4"] = "Ausgeschlossen"
    ws["C4"] = "Volumen (€)"
    ws["D4"] = "Anteil (%)"
    for cell in [ws["A4"], ws["B4"], ws["C4"], ws["D4"]]:
        hdr(cell)

    row = 5
    for label, subset in stufen.items():
        vol = subset[amt_col].sum() if amt_col in subset.columns else 0
        ws.cell(row, 1, label)
        ws.cell(row, 2, len(subset))
        ws.cell(row, 3, round(vol, 2))
        ws.cell(row, 4, f"{len(subset)/total*100:.1f}%")
        for col in range(1, 5):
            cell_style(ws.cell(row, col), bg=BLUE if row % 2 == 0 else None)
        row += 1

    # Maverick-Ergebnis
    ws.cell(row + 1, 1, "→ Verbleibende Maverick-Kandidaten")
    ws.cell(row + 1, 2, len(mav_df))
    ws.cell(row + 1, 3, round(mav_vol, 2))
    ws.cell(row + 1, 4, f"{len(mav_df)/total*100:.1f}%")
    for col in range(1, 5):
        c = ws.cell(row + 1, col)
        cell_style(c, bg=RED, bold=True)

    ws.cell(row + 3, 1, "Gesamttransaktionen")
    ws.cell(row + 3, 2, total)
    ws.cell(row + 3, 3, round(total_spend, 2))
    for col in range(1, 4):
        cell_style(ws.cell(row + 3, col), bg=GREY, bold=True)

    # Klassifizierungsübersicht
    if "_final_classification" in df.columns:
        ws.cell(row + 5, 1, "Klassifizierung")
        ws.cell(row + 5, 2, "Anzahl")
        hdr(ws.cell(row + 5, 1))
        hdr(ws.cell(row + 5, 2))
        for i, (cls, cnt) in enumerate(
                df["_final_classification"].value_counts().items(), start=row + 6):
            ws.cell(i, 1, str(cls))
            ws.cell(i, 2, cnt)
            bg = row_bg(cls)
            for col in [1, 2]:
                cell_style(ws.cell(i, col), bg=bg)

    autofit(ws)

    # ── SHEET 2: MAVERICK-KANDIDATEN ───────────────────────────────────────
    def write_transactions(ws_target, subset, title_suffix=""):
        ws_target.sheet_view.showGridLines = False
        base_cols = _base_cols(df, cfg)
        extra = ["_final_classification", "_risk_level", "_maverick_reason", "_risk_score"]
        headers = base_cols + ["Klassifizierung", "Risiko", "Maverick-Grund", "Score"]

        for ci, h in enumerate(headers, 1):
            hdr(ws_target.cell(1, ci))
            ws_target.cell(1, ci, h)

        for ri, (_, row_data) in enumerate(
                subset.sort_values("_risk_score", ascending=False).iterrows(), 2):
            bg = row_bg(row_data.get("_final_classification", ""))
            all_vals = [row_data.get(col, "") for col in base_cols] + \
                       [row_data.get(col, "") for col in extra]
            for ci, val in enumerate(all_vals, 1):
                if isinstance(val, pd.Timestamp):
                    val = val.strftime("%d.%m.%Y") if not pd.isna(val) else ""
                elif isinstance(val, float) and np.isnan(val):
                    val = ""
                elif isinstance(val, list):
                    val = "; ".join(val)
                c = ws_target.cell(ri, ci, val)
                cell_style(c, bg=bg)

        ws_target.auto_filter.ref = f"A1:{get_column_letter(len(headers))}1"
        ws_target.freeze_panes = "A2"
        autofit(ws_target)

    ws2 = wb.create_sheet("🔍 Maverick-Kandidaten")
    write_transactions(ws2, df[df["_is_maverick"]])

    # ── SHEET 3: TÄUSCHUNGSVERDACHT ────────────────────────────────────────
    ws3 = wb.create_sheet("🔴 Täuschungsverdacht")
    td_df = df[df.get("_final_classification", pd.Series()).str.contains(
        "Täuschung|Prozessfehler", na=False)] if "_final_classification" in df.columns \
        else df[df["_is_maverick"] & (df["_deception_score"] > 0)]
    write_transactions(ws3, td_df)

    # ── SHEET 4: VOLLSTÄNDIGE LISTE ────────────────────────────────────────
    ws4 = wb.create_sheet("📋 Alle Transaktionen")
    write_transactions(ws4, df)

    # ── SHEET 5: LIEFERANTEN-RANKING ───────────────────────────────────────
    ws5 = wb.create_sheet("🏢 Lieferanten-Ranking")
    ws5.sheet_view.showGridLines = False
    sup_col = cfg["col_supplier"]

    if sup_col in df.columns and amt_col in df.columns:
        grp = df.groupby(sup_col).agg(
            Transaktionen=(amt_col, "count"),
            Gesamtvolumen=(amt_col, "sum"),
            Maverick_Anzahl=("_is_maverick", "sum"),
            Avg_Score=("_risk_score", "mean"),
        ).reset_index()
        grp["Maverick_%"] = grp["Maverick_Anzahl"] / grp["Transaktionen"] * 100
        grp = grp.sort_values("Maverick_%", ascending=False)

        headers5 = [sup_col, "Transaktionen", "Gesamtvolumen (€)",
                    "Maverick-Transakt.", "Maverick %", "Ø Score"]
        for ci, h in enumerate(headers5, 1):
            hdr(ws5.cell(1, ci))
            ws5.cell(1, ci, h)

        for ri, (_, row_data) in enumerate(grp.iterrows(), 2):
            vals = [row_data[sup_col], row_data["Transaktionen"],
                    round(row_data["Gesamtvolumen"], 2),
                    row_data["Maverick_Anzahl"],
                    f"{row_data['Maverick_%']:.1f}%",
                    round(row_data["Avg_Score"], 1)]
            pct = row_data["Maverick_%"]
            bg = RED if pct > 60 else ORANGE if pct > 30 else YELLOW if pct > 10 else None
            for ci, val in enumerate(vals, 1):
                c = ws5.cell(ri, ci, val)
                cell_style(c, bg=bg,
                           align="right" if isinstance(val, (int, float)) else "left")

        ws5.auto_filter.ref = f"A1:{get_column_letter(len(headers5))}1"
        ws5.freeze_panes = "A2"
        autofit(ws5)

    wb.save(output_path)
    print(f"\n✅ Report gespeichert: {output_path}")
    _print_summary(df, cfg)


def _base_cols(df, cfg):
    desired = [
        cfg["col_order_id"], cfg["col_supplier"], cfg["col_category"],
        cfg["col_cost_center"], cfg["col_buyer_id"], cfg["col_order_date"],
        cfg["col_delivery_date"], cfg["col_quantity"], cfg["col_unit_price"],
        cfg["col_amount"], cfg["col_item_description"], cfg["col_contract_flag"],
    ]
    return [col for col in desired if col in df.columns]


def _print_summary(df, cfg):
    total = len(df)
    mav = df["_is_maverick"].sum()
    amt = cfg["col_amount"]
    total_vol = df[amt].sum() if amt in df.columns else 0
    mav_vol = df[df["_is_maverick"]][amt].sum() if amt in df.columns else 0

    print("\n" + "=" * 55)
    print("  MAVERICK BUYING – ERGEBNIS")
    print("=" * 55)
    print(f"  Transaktionen gesamt:      {total:>8,}")
    print(f"  Maverick-Kandidaten:       {mav:>8,}  ({mav/total*100:.1f}%)")
    if total_vol:
        print(f"  Gesamtvolumen:             {total_vol:>12,.2f} €")
        print(f"  Maverick-Volumen:          {mav_vol:>12,.2f} €  ({mav_vol/total_vol*100:.1f}%)")

    if "_final_classification" in df.columns:
        print("\n  Klassifizierung:")
        for cls, cnt in df["_final_classification"].value_counts().items():
            print(f"    {str(cls):<45} {cnt:>5}")
    print("=" * 55)


# ─────────────────────────────────────────────────────────────────────────────
# EINSTIEGSPUNKT
# ─────────────────────────────────────────────────────────────────────────────
def run_analysis(source: str,
                 source_type: str = "excel",
                 output: str = "maverick_report_v2.xlsx",
                 sheet_name=0,
                 db_query: Optional[str] = None,
                 config: dict = None) -> pd.DataFrame:
    """
    Hauptfunktion.

    Parameters
    ----------
    source       : Dateipfad (CSV/Excel) oder DB-Connection-String
    source_type  : 'excel' | 'csv' | 'database'
    output       : Ausgabepfad
    sheet_name   : Excel-Sheet (Index oder Name)
    db_query     : SQL-Query (nur bei 'database')
    config       : Überschreibt Standard-CONFIG
    """
    cfg = {**CONFIG, **(config or {})}

    print(f"📂 Lade Daten ({source_type}): {source}")
    if source_type == "excel":
        df = DataConnector.from_excel(source, sheet_name=sheet_name)
    elif source_type == "csv":
        df = DataConnector.from_csv(source)
    elif source_type == "database":
        df = DataConnector.from_database(source, db_query)
    else:
        raise ValueError(f"Unbekannter source_type: {source_type}")

    print(f"   → {len(df):,} Zeilen geladen")
    df = normalize(df, cfg)
    df = analyze(df, cfg)
    generate_report(df, cfg, output_path=output)
    return df


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # ── Beispiel CSV ──
    # run_analysis("bestellungen.csv", source_type="csv")

    # ── Beispiel Excel ──
    # run_analysis("bestellungen.xlsx", source_type="excel", sheet_name="Bestellungen")

    # ── Beispiel Datenbank ──
    # run_analysis(
    #     "postgresql://user:pass@host/db",
    #     source_type="database",
    #     db_query="SELECT * FROM orders WHERE year = 2024"
    # )

    # ── Demo ──────────────────────────────────────────────────────────────
    print("⚙️  Demo-Modus ...")
    from demo_data_v2 import create_demo_data
    create_demo_data("/tmp/demo_v2.xlsx")
    run_analysis("/tmp/demo_v2.xlsx", source_type="excel",
                 output="/tmp/maverick_report_v2.xlsx")
