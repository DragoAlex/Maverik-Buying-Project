# Jade.AI — Basis (MVP-Kern)

Lokales Analysewerkzeug (Python, pandas, numpy): Belegketten aus SAP-Extrakten (Excel/CSV)
rekonstruieren, Brüche erkennen, Prozesse priorisieren und eine Testreihenfolge bewerten.

## Module

| Modul | Aufgabe |
|---|---|
| `config.py` | Tabellen, Verweisspalten, Archetypen, Gewichte, Schwellen |
| `quality.py` | Laden, Qualitätsprüfung, Abhängigkeitsmatrix (welche Schritte sind möglich) |
| `doc_graph.py` | Beleggraph, Prozessketten, Archetyp-Zuordnung, Brüche/Sprünge, Kontext (Werk, Kunde, Wert) |
| `priority.py` | Maße, Priorisierungskennzahl, Bewertung für Test (Quantilgrenzen) |
| `demo_data.py`, `run_demo.py` | synthetische Daten und Demolauf |

## Start

```bash
pip install -r requirements.txt
python -m jade_ai.run_demo
python -m pytest jade_ai/tests
```

## Stand und getroffene Annahmen

- Umgesetzt ist nur der Archetyp **Verkauf** (Angebot → Auftrag → Lieferung → Materialbeleg → Faktura → FI-Beleg → Zahlung).
- Feld- und Tabellennamen sind Platzhalter und werden in `config.py` an die echten Extrakte angepasst.
- Prioritätsanteil je Maß relativ zum Maximum (`share_mode = "max"`). Die wörtliche Lesart (Anteil an der Gesamtsumme) ist mit `"sum"` einstellbar, führt bei vielen Prozessen aber zu durchgehend niedrigen Kennzahlen. **Zu bestätigen.**
- Prioritätsgrenzen 8 / 6 / 3 / 2 als Untergrenzen; die Lücken in der Vorgabe (5–6, 2–3, 1–2) sind damit geschlossen. **Zu bestätigen.**
- Manuelle Eingriffe sind nicht erkennbar, solange Benutzer/Erfassungsart nicht in den Daten liegen.
- Noch nicht enthalten: Beschaffung/Produktion, Sequenzen über Prozessgrenzen, PCF-Mapping, Department, Z-Transaktionen, Testfall-Ausgabe.
