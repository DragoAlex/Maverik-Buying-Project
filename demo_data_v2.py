"""
Demo-Datengenerator v2
Erstellt Testdaten mit realistischen Maverick-Mustern für alle 6 Prüfstufen.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random


def create_demo_data(output_path: str = "demo_v2.xlsx", seed: int = 42):
    random.seed(seed)
    np.random.seed(seed)

    base = datetime(2024, 1, 1)
    records = []

    def order(bn, lief, wg, kst, ek, datum, menge, preis, beschr, rv, auto=None, gn=None):
        return {
            "Bestellnummer":        bn,
            "Lieferant":            lief,
            "Warengruppe":          wg,
            "Kostenstelle":         kst,
            "Einkäufernummer":      ek,
            "Bestelldatum":         datum,
            "Lieferdatum":          datum + timedelta(days=random.randint(3, 14)),
            "Menge":                menge,
            "Preis":                preis,
            "Betrag":               round(menge * preis, 2),
            "Artikelbeschreibung":  beschr,
            "Rahmenvertrag":        rv,
            "AutoBestellung":       auto or "Nein",
            "Genehmigungsnachweis": gn or "",
        }

    # ─── Kategorie A: Gremiumspflichtig → S2 raus ────────────────────────
    for i in range(8):
        d = base + timedelta(days=random.randint(0, 300))
        records.append(order(
            f"PO-G{i:03}", "Großlieferant AG", "Maschinen", "KST-1010", "EK-001",
            d, 1, random.uniform(55_000, 200_000),
            "Industrieanlage Typ X", "Nein"
        ))

    # ─── Kategorie B: Zeitabstand > 3 Wochen → S3 raus ───────────────────
    for i in range(10):
        d = base + timedelta(days=i * 35)  # alle 35 Tage = > 3 Wochen Abstand
        records.append(order(
            f"PO-Z{i:03}", "Versorgung GmbH", "Büromaterial", "KST-2020", "EK-002",
            d, random.randint(1, 20), random.uniform(10, 200),
            f"Druckerpapier A4 80g", "Nein"
        ))

    # ─── Kategorie C: Klar unterschiedliche Materialien → S4 raus ─────────
    items = ["Laptop Dell XPS 15", "Netzwerkswitch Cisco",
             "Klimaanlage Mitsubishi", "Drucker HP", "Bildschirm Samsung"]
    for i, item in enumerate(items):
        d = base + timedelta(days=i * 10)
        records.append(order(
            f"PO-M{i:03}", "Technik AG", "IT-Hardware", "KST-3030", "EK-003",
            d, 1, random.uniform(500, 3000), item, "Nein"
        ))

    # ─── Kategorie D: Rahmenvertrag regelkonform → S5a raus ──────────────
    for i in range(15):
        d = base + timedelta(days=random.randint(0, 300))
        records.append(order(
            f"PO-R{i:03}", "Rahmen Partner KG", "Verpackung", "KST-1010", "EK-001",
            d, random.randint(10, 500), random.uniform(2, 30),
            "Kartonage standard", "Ja"
        ))

    # ─── Kategorie E: Genehmigt durch Einkäufer → S5b raus ──────────────
    for i in range(8):
        d = base + timedelta(days=i * 4)
        records.append(order(
            f"PO-E{i:03}", "Kleinlieferant", "MRO", "KST-4040", "EK-004",
            d, 2, random.uniform(50, 400),
            "Wartungsmaterial", "Nein",
            gn=f"Freigabe-{2024}-{i:04}"
        ))

    # ─── Kategorie F: Split-Order-Verdacht (ähnliche Artikel, enge Zeitfolge) ──
    for i in range(6):
        d = base + timedelta(days=10 + i * 4)  # alle 4 Tage
        records.append(order(
            f"PO-SP{i:03}", "SplitLieferant GmbH", "Büromaterial", "KST-2020", "EK-002",
            d, 10, 480,
            "Kopierpapier A4" if i % 2 == 0 else "Kopierpapier weiß A4",
            "Nein"
        ))

    # ─── Kategorie G: Täuschungsverdacht (knapp unter Schwellenwert, systematisch) ──
    for i in range(7):
        d = base + timedelta(days=5 + i * 6)
        ek = f"EK-00{(i % 3) + 1}"  # 3 verschiedene Einkäufer
        records.append(order(
            f"PO-TD{i:03}", "Verdächtiger Lieferant", "Dienstleistungen",
            "KST-5050", ek, d, 1,
            random.uniform(42_000, 49_500),  # knapp unter 50k Gremiumsschwelle
            "Beratungsleistung allgemein", "Nein"
        ))

    # ─── Kategorie H: Normale Bestellungen, regelkonform ─────────────────
    for i in range(30):
        d = base + timedelta(days=random.randint(0, 300))
        records.append(order(
            f"PO-N{i:03}", f"Normlieferant {i % 5 + 1}", "Verschiedenes",
            random.choice(["KST-1010", "KST-2020", "KST-3030"]),
            random.choice(["EK-001", "EK-002"]),
            d, random.randint(1, 50), random.uniform(10, 500),
            f"Artikel {i:04}", "Ja"
        ))

    df = pd.DataFrame(records)
    df.to_excel(output_path, index=False)
    print(f"✅ Demo-Daten v2 erstellt: {output_path} ({len(df)} Zeilen)")
    print(f"   Kategorien: Gremium×8, Zeitabstand×10, Klar unterschiedlich×5,")
    print(f"               Rahmenvertrag×15, Genehmigt×8, Split-Verdacht×6,")
    print(f"               Täuschung×7, Normal×30")
    return df


if __name__ == "__main__":
    create_demo_data()
