"""
maverick_export.py
==================
Führt die Maverick-Analyse aus und exportiert das Ergebnis als JSON
für das lokale Browser-Frontend.

Verwendung:
    python maverick_export.py --input bestellungen.xlsx --output ergebnis.json
    python maverick_export.py --demo
"""

import json
import argparse
import sys
import os
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from maverick_analyzer_v2 import (
    DataConnector, normalize, analyze, CONFIG
)


def df_to_json_export(df, cfg):
    """Konvertiert analysiertes DataFrame in JSON-Struktur für das Frontend."""
    import numpy as np

    amt = cfg["col_amount"]
    sup = cfg["col_supplier"]
    buyer = cfg["col_buyer_id"]
    cost = cfg["col_cost_center"]
    cat = cfg["col_category"]
    desc = cfg["col_item_description"]
    order_id = cfg["col_order_id"]
    date_col = cfg["col_order_date"]
    req_col = "Anforderung"  # Angestellten-Anforderungsfeld

    def safe(v):
        if v is None: return None
        try:
            import pandas as pd
            if pd.isna(v): return None
        except: pass
        if isinstance(v, float) and (v != v): return None
        if hasattr(v, 'isoformat'): return v.strftime("%d.%m.%Y")
        if isinstance(v, (np.integer,)): return int(v)
        if isinstance(v, (np.floating,)): return round(float(v), 2)
        if isinstance(v, list): return v
        return v

    total = len(df)
    total_vol = float(df[amt].sum()) if amt in df.columns else 0
    mav_df = df[df["_is_maverick"]]
    mav_vol = float(mav_df[amt].sum()) if amt in mav_df.columns else 0

    # ── KPIs ──────────────────────────────────────────────────────────────
    kpis = {
        "total_orders": total,
        "total_volume": round(total_vol, 2),
        "maverick_orders": int(df["_is_maverick"].sum()),
        "maverick_volume": round(mav_vol, 2),
        "maverick_rate_orders": round(df["_is_maverick"].sum() / total * 100, 1) if total else 0,
        "maverick_rate_volume": round(mav_vol / total_vol * 100, 1) if total_vol else 0,
        "deception_count": int((df.get("_final_classification", "") == "🔴 Täuschungsverdacht").sum()),
        "process_error_count": int((df.get("_final_classification", "") == "🟠 Möglicher Prozessfehler").sum()),
        "unclarified_count": int((df.get("_final_classification", "") == "🟡 Ungeklärter Einzelfall").sum()),
    }

    # ── Trichter ──────────────────────────────────────────────────────────
    funnel = []
    stage_labels = {
        "Gremium": "S2 – Gremiumspflichtig",
        "Einzelkauf": "S3 – Zeitabstand > 3 Wo.",
        "Beschreibung": "S4 – Unterschiedl. Material",
        "Rahmenvertrag|Autom": "S5a – Rahmenvertrag OK",
        "Genehmigung": "S5b – Einkäufer bestätigt",
    }
    remaining = total
    for key, label in stage_labels.items():
        import re
        mask = df["_ausschluss_grund"].str.contains(key, na=False, regex=True)
        n = int(mask.sum())
        vol = float(df.loc[mask, amt].sum()) if amt in df.columns else 0
        funnel.append({"stage": label, "excluded": n, "volume": round(vol, 2), "remaining": remaining})
        remaining -= n
    funnel.append({
        "stage": "Maverick-Kandidaten",
        "excluded": 0,
        "volume": round(mav_vol, 2),
        "remaining": remaining
    })

    # ── Lieferanten-Ranking ───────────────────────────────────────────────
    supplier_data = []
    if sup in df.columns and amt in df.columns:
        grp = df.groupby(sup).agg(
            orders=(amt, "count"),
            volume=(amt, "sum"),
            maverick=("_is_maverick", "sum"),
            avg_score=("_risk_score", "mean"),
        ).reset_index()
        grp["mav_pct"] = grp["maverick"] / grp["orders"] * 100
        grp = grp.sort_values("maverick", ascending=False)
        for _, r in grp.iterrows():
            supplier_data.append({
                "name": safe(r[sup]),
                "orders": int(r["orders"]),
                "volume": round(float(r["volume"]), 2),
                "maverick": int(r["maverick"]),
                "mav_pct": round(float(r["mav_pct"]), 1),
                "avg_score": round(float(r["avg_score"]), 1),
            })

    # ── Einkäufer-Ranking ─────────────────────────────────────────────────
    buyer_data = []
    if buyer in df.columns and amt in df.columns:
        grp = df.groupby(buyer).agg(
            orders=(amt, "count"),
            volume=(amt, "sum"),
            maverick=("_is_maverick", "sum"),
            deception=("_deception_score", "sum"),
        ).reset_index()
        grp["mav_pct"] = grp["maverick"] / grp["orders"] * 100
        grp = grp.sort_values("maverick", ascending=False)
        for _, r in grp.iterrows():
            buyer_data.append({
                "id": safe(r[buyer]),
                "orders": int(r["orders"]),
                "volume": round(float(r["volume"]), 2),
                "maverick": int(r["maverick"]),
                "mav_pct": round(float(r["mav_pct"]), 1),
                "deception_score": int(r["deception"]),
            })

    # ── Kostenstellen / Abteilungen ───────────────────────────────────────
    dept_data = []
    if cost in df.columns and amt in df.columns:
        grp = df.groupby(cost).agg(
            orders=(amt, "count"),
            volume=(amt, "sum"),
            maverick=("_is_maverick", "sum"),
        ).reset_index()
        grp["mav_pct"] = grp["maverick"] / grp["orders"] * 100
        grp = grp.sort_values("maverick", ascending=False)
        for _, r in grp.iterrows():
            dept_data.append({
                "name": safe(r[cost]),
                "orders": int(r["orders"]),
                "volume": round(float(r["volume"]), 2),
                "maverick": int(r["maverick"]),
                "mav_pct": round(float(r["mav_pct"]), 1),
            })

    # ── Anforderungen (Abteilung/Angestellter → Einkäufer) ───────────────
    # Anforderungsnachweis: wer hat angefordert, wer hat genehmigt
    request_data = []
    if buyer in df.columns:
        mav_only = df[df["_is_maverick"]]
        if cost in df.columns:
            for (b, c_val), grp in mav_only.groupby([buyer, cost]):
                approved = grp["_ausschluss_grund"].str.contains("Genehmigung", na=False).sum()
                missing = len(grp) - approved
                if missing > 0:
                    request_data.append({
                        "buyer": safe(b),
                        "dept": safe(c_val),
                        "total_mav": len(grp),
                        "missing_approval": int(missing),
                        "volume": round(float(grp[amt].sum()), 2) if amt in grp.columns else 0,
                    })
        request_data.sort(key=lambda x: x["missing_approval"], reverse=True)

    # ── Zeitverlauf ───────────────────────────────────────────────────────
    timeline = []
    if date_col in df.columns and amt in df.columns:
        df["_month"] = df[date_col].dt.to_period("M").astype(str)
        tl = df.groupby("_month").agg(
            all_orders=(amt, "count"),
            mav_orders=("_is_maverick", "sum"),
            volume=(amt, "sum"),
        ).reset_index()
        for _, r in tl.iterrows():
            timeline.append({
                "month": safe(r["_month"]),
                "all_orders": int(r["all_orders"]),
                "mav_orders": int(r["mav_orders"]),
                "volume": round(float(r["volume"]), 2),
            })

    # ── Transaktionsliste (Maverick-Kandidaten) ───────────────────────────
    transactions = []
    mav_sorted = df[df["_is_maverick"]].sort_values("_risk_score", ascending=False)
    for _, r in mav_sorted.iterrows():
        transactions.append({
            "order_id":       safe(r.get(order_id, "")),
            "supplier":       safe(r.get(sup, "")),
            "category":       safe(r.get(cat, "")),
            "dept":           safe(r.get(cost, "")),
            "buyer":          safe(r.get(buyer, "")),
            "date":           safe(r.get(date_col, "")),
            "amount":         safe(r.get(amt, 0)),
            "description":    safe(r.get(desc, "")),
            "contract":       "Ja" if r.get("_contract_active", False) else "Nein",
            "classification": safe(r.get("_final_classification", "")),
            "risk_level":     safe(r.get("_risk_level", "")),
            "risk_score":     int(r.get("_risk_score", 0)),
            "reasons":        r.get("_maverick_flags", []),
            "approval_doc":   safe(r.get(cfg["col_approval_doc"], "")),
        })

    return {
        "meta": {
            "generated": datetime.now().strftime("%d.%m.%Y %H:%M"),
            "source": "Maverick Buying Analyzer v2",
        },
        "kpis": kpis,
        "funnel": funnel,
        "suppliers": supplier_data,
        "buyers": buyer_data,
        "departments": dept_data,
        "requests": request_data,
        "timeline": timeline,
        "transactions": transactions,
    }


def run_export(source, source_type="excel", output_json="ergebnis.json",
               sheet_name=0, config=None):
    cfg = {**CONFIG, **(config or {})}

    print(f"📂 Lade: {source}")
    if source_type == "excel":
        df = DataConnector.from_excel(source, sheet_name=sheet_name)
    elif source_type == "csv":
        df = DataConnector.from_csv(source)
    else:
        raise ValueError(f"Unbekannter Typ: {source_type}")

    print(f"   → {len(df):,} Zeilen")
    df = normalize(df, cfg)
    df = analyze(df, cfg)

    data = df_to_json_export(df, cfg)
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"✅ JSON exportiert: {output_json}")
    return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Maverick Buying Export")
    parser.add_argument("--input", help="Eingabedatei (Excel/CSV)")
    parser.add_argument("--type", default="excel", choices=["excel", "csv"])
    parser.add_argument("--output", default="ergebnis.json")
    parser.add_argument("--sheet", default=0)
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args()

    if args.demo:
        from demo_data_v2 import create_demo_data
        create_demo_data("/tmp/demo_v2.xlsx")
        run_export("/tmp/demo_v2.xlsx", output_json=args.output)
    elif args.input:
        run_export(args.input, source_type=args.type,
                   output_json=args.output, sheet_name=args.sheet)
    else:
        print("Verwendung: python maverick_export.py --input datei.xlsx")
        print("            python maverick_export.py --demo")
