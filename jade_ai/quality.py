"""Schritt 1: Daten laden, Qualität prüfen, verfügbare Analyseschritte ableiten."""

from pathlib import Path

import pandas as pd

from .config import CONFIG


def load_tables(path, config=CONFIG):
    """Lädt Excel-/CSV-Dateien; Dateiname (ohne Endung) oder Blattname = Belegtyp."""
    path = Path(path)
    tables = {}
    files = [path] if path.is_file() else sorted(path.iterdir())
    for f in files:
        if f.suffix.lower() in (".xlsx", ".xls"):
            for sheet, df in pd.read_excel(f, sheet_name=None, dtype=str).items():
                tables[sheet.upper()] = df
        elif f.suffix.lower() == ".csv":
            tables[f.stem.upper()] = pd.read_csv(f, dtype=str, sep=None, engine="python")
    return {name: normalize(df) for name, df in tables.items() if name in config["tables"]}


def normalize(df):
    """Spaltennamen vereinheitlichen, Leerzeichen entfernen, Leerwerte als NaN."""
    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]
    for col in df.columns:
        if df[col].dtype == object or str(df[col].dtype).startswith("str"):
            df[col] = df[col].str.strip().replace("", pd.NA)
    return df


def quality_report(tables, config=CONFIG):
    """Prüft je Tabelle Schlüssel, Duplikate, Nullen, Zeilenlimit und Zeitraum."""
    rows = []
    for name, spec in config["tables"].items():
        if name not in tables:
            rows.append({"table": name, "issue": "Tabelle fehlt", "severity": "hoch"})
            continue
        df = tables[name]
        key = spec["key"]
        if key not in df.columns:
            rows.append({"table": name, "issue": f"Schlüsselspalte '{key}' fehlt", "severity": "hoch"})
            continue
        if len(df) >= config["excel_row_limit"] - 1:
            rows.append({"table": name, "issue": "Zeilenlimit erreicht, Extrakt evtl. abgeschnitten", "severity": "hoch"})
        null_share = df[key].isna().mean()
        if null_share > 0:
            rows.append({"table": name, "issue": f"{null_share:.1%} Schlüssel leer", "severity": "mittel"})
        dups = int(df[key].dropna().duplicated().sum())
        if dups:
            rows.append({"table": name, "issue": f"{dups} doppelte Schlüssel", "severity": "mittel"})
        lengths = df[key].dropna().str.len()
        if lengths.nunique() > 1 and df[key].dropna().str.isdigit().all():
            rows.append({"table": name, "issue": "Schlüssel unterschiedlich lang, führende Nullen evtl. verloren", "severity": "mittel"})
        for ref_col in spec["refs"]:
            if ref_col not in df.columns:
                rows.append({"table": name, "issue": f"Verweisspalte '{ref_col}' fehlt, Verknüpfung entfällt", "severity": "mittel"})
        date_col = config["date_columns"].get(name)
        if date_col and date_col in df.columns:
            dates = pd.to_datetime(df[date_col], errors="coerce").dropna()
            if not dates.empty:
                months = (dates.max() - dates.min()).days / 30.4
                if months < config["min_months_coverage"]:
                    rows.append({"table": name, "issue": f"Zeitraum nur {months:.0f} Monate (Soll {config['min_months_coverage']})", "severity": "hoch"})
    return pd.DataFrame(rows, columns=["table", "issue", "severity"])


def available_steps(tables, config=CONFIG):
    """Abhängigkeitsmatrix: welche Analyseschritte sind mit den vorhandenen Tabellen möglich."""
    rows = []
    for step, needed in config["step_requirements"].items():
        missing = [t for t in needed if t not in tables]
        rows.append({"step": step, "possible": not missing, "missing_tables": ", ".join(missing)})
    return pd.DataFrame(rows)
