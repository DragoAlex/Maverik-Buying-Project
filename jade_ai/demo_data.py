"""Synthetische Verkaufsketten (Angebot bis Zahlung) mit gezielten Brüchen für Tests und Demo."""

import numpy as np
import pandas as pd


def make_demo_tables(n=200, seed=42):
    rng = np.random.default_rng(seed)
    rows = {k: [] for k in ("ANGEBOT", "SALES_ORDER", "LIEFERUNG", "MATERIALBELEG",
                            "FAKTURA", "FI_BELEG", "ZAHLUNG")}
    start = pd.Timestamp("2025-01-01")

    for i in range(n):
        po = f"PO{i:06d}"
        so, lf, mb, fk, fi, zl, ang = (f"{p}{i:06d}" for p in ("SO", "LF", "MB", "FK", "FI", "ZL", "AN"))
        werk = rng.choice(["W10", "W20"], p=[0.7, 0.3])
        kunde = f"K{rng.integers(1, 15):03d}"
        # Bruchszenario: 0 = vollständig, 1 = endet nach Lieferung, 2 = ohne Angebot, 3 = ohne Materialbeleg
        scenario = rng.choice([0, 1, 2, 3], p=[0.7, 0.1, 0.1, 0.1])

        if scenario != 2:
            rows["ANGEBOT"].append({"angebot_nr": ang, "kunden_po": po})
        rows["SALES_ORDER"].append({
            "so_nr": so, "kunden_po": po, "werk": werk, "kunde": kunde,
            "menge": int(rng.integers(1, 100)), "preis": round(float(rng.uniform(5, 500)), 2),
            "erstellt_am": (start + pd.Timedelta(days=int(rng.integers(0, 540)))).strftime("%Y-%m-%d"),
        })
        rows["LIEFERUNG"].append({"liefer_nr": lf, "so_nr": so})
        if scenario != 3:
            rows["MATERIALBELEG"].append({"mat_beleg": mb, "ref_key": lf, "liefer_nr": lf})
        if scenario == 1:
            continue
        rows["FAKTURA"].append({"faktura_nr": fk, "liefer_nr": lf, "so_nr": so})
        rows["FI_BELEG"].append({"fi_beleg": fi, "ref_key": lf, "sd_rechnung": fk})
        rows["ZAHLUNG"].append({"zahlungs_nr": zl, "fi_beleg": fi, "sd_rechnung": fk})

    return {k: pd.DataFrame(v) for k, v in rows.items()}
