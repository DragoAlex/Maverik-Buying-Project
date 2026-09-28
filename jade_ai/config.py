"""
Jade.AI — Konfiguration
=======================
Alle Feldnamen, Verknüpfungsregeln, Archetypen und Gewichte liegen hier.
Die Logik in den anderen Modulen bleibt unverändert, wenn sich die Datenlage ändert.
"""

CONFIG = {
    # --- Belegtabellen: Schlüsselspalte, Verweise auf andere Belegtypen, Kontextspalten ---
    # refs: {Spalte in dieser Tabelle: Belegtyp, auf den sie verweist}
    # Fehlende Spalten/Tabellen werden übersprungen und im Qualitätsbericht gemeldet.
    "tables": {
        "ANGEBOT": {
            "key": "angebot_nr",
            "refs": {"kunden_po": "KUNDEN_PO"},
        },
        "SALES_ORDER": {
            "key": "so_nr",
            "refs": {"kunden_po": "KUNDEN_PO"},
            "context": {"werk": "werk", "customer": "kunde",
                        "quantity": "menge", "price": "preis"},
        },
        "LIEFERUNG": {
            "key": "liefer_nr",
            "refs": {"so_nr": "SALES_ORDER"},
        },
        "MATERIALBELEG": {
            "key": "mat_beleg",
            "refs": {"ref_key": "REFKEY", "liefer_nr": "LIEFERUNG"},
        },
        "FAKTURA": {
            "key": "faktura_nr",
            "refs": {"liefer_nr": "LIEFERUNG", "so_nr": "SALES_ORDER"},
        },
        "FI_BELEG": {
            "key": "fi_beleg",
            "refs": {"ref_key": "REFKEY", "sd_rechnung": "FAKTURA"},
        },
        "ZAHLUNG": {
            "key": "zahlungs_nr",
            "refs": {"fi_beleg": "FI_BELEG", "sd_rechnung": "FAKTURA"},
        },
    },

    # --- Prozessarchetypen: erwartete Belegabfolge je Archetyp ---
    "archetypes": {
        "Verkauf": ["ANGEBOT", "SALES_ORDER", "LIEFERUNG", "MATERIALBELEG",
                    "FAKTURA", "FI_BELEG", "ZAHLUNG"],
    },

    # --- Datenqualität ---
    "min_months_coverage": 12,
    "excel_row_limit": 1_048_576,
    "date_columns": {"SALES_ORDER": "erstellt_am"},

    # --- Abhängigkeitsmatrix: Analyseschritt -> benötigte Tabellen ---
    "step_requirements": {
        "Beleggraph / Prozessketten": ["SALES_ORDER", "LIEFERUNG", "FAKTURA"],
        "Bruchanalyse": ["SALES_ORDER"],
        "Volumen / Menge": ["SALES_ORDER"],
        "Zahlungsabschluss": ["ZAHLUNG"],
    },

    # --- Priorisierung ---
    # Gewichte je Maß (werden auf Summe 1 normiert), variabel anpassbar
    "weights": {
        "frequency": 1.0,
        "volume": 1.0,
        "quantity": 1.0,
        "customer_frequency": 1.0,
        "break_probability": 1.0,
        "strategic": 1.0,
    },
    # "max": Anteil relativ zum größten Wert (bestes Maß = 1)
    # "sum": Anteil an der Gesamtsumme aller Ausprägungen (wörtliche Lesart)
    "share_mode": "max",
    # Untergrenzen der Priorität auf der Skala 0-10
    "priority_bounds": [
        (8.0, "sehr hoch"), (6.0, "hoch"), (3.0, "mittel"),
        (2.0, "gering"), (0.0, "sehr gering"),
    ],

    # --- Bewertung für Test: Quantilgrenzen der normierten Werte (0-1) ---
    "rating_bounds": [
        (0.85, "sehr hoch"), (0.65, "hoch"), (0.45, "mittel"),
        (0.25, "gering"), (0.0, "sehr gering"),
    ],
}
