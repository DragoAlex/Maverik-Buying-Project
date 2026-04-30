# Maverick Buying Analyzer

Mehrstufiges Python-Tool zur systematischen Identifikation von Maverick Buying in Einkaufsdaten. Inkl. lokalem Browser-Dashboard.

## Was ist Maverick Buying?

Maverick Buying bezeichnet Beschaffungsvorgänge, die außerhalb genehmigter Rahmenverträge, Prozesse oder Genehmigungswege getätigt werden – bewusst oder durch Prozessfehler.

## Funktionsweise: 6-stufiger Prüftrichter

```
Alle Bestellungen
    │
    ▼ S2: Gremiumspflichtige Bestellungen raus (≥ Schwellenwert)
    ▼ S3: Zeitabstand > 3 Wochen → kein Maverick-Verdacht
    ▼ S4: Klar unterschiedliche Materialbeschreibungen → raus
    ▼ S5a: Aktiver Rahmenvertrag / automatische Bestellung → raus
    ▼ S5b: Genehmigungsnachweis durch Einkäufer vorhanden → raus
    ▼ S6: Täuschung vs. Prozessfehler klassifizieren
    │
    └─► Maverick-Kandidaten (🔴 Täuschung / 🟠 Prozessfehler / 🟡 Ungeklärt)
```

## Dateien

| Datei | Beschreibung |
|---|---|
| `maverick_analyzer_v2.py` | Kern-Analyse-Engine (6 Prüfstufen) |
| `maverick_export.py` | Exportiert Ergebnis als JSON für Dashboard |
| `maverick_dashboard.html` | Lokales Browser-Dashboard (kein Server nötig) |
| `demo_data_v2.py` | Synthetische Testdaten mit allen Maverick-Mustern |
| `requirements.txt` | Python-Abhängigkeiten |

## Installation

```bash
git clone https://github.com/DEIN-NAME/maverick-buying-analyzer
cd maverick-buying-analyzer
pip install -r requirements.txt
```

## Verwendung

### 1. Analyse ausführen & JSON exportieren

```bash
# Excel-Datei
python maverick_export.py --input bestellungen.xlsx --output ergebnis.json

# CSV-Datei
python maverick_export.py --input bestellungen.csv --type csv --output ergebnis.json

# Demo-Daten (zum Ausprobieren)
python maverick_export.py --demo --output ergebnis.json
```

### 2. Dashboard im Browser öffnen

`maverick_dashboard.html` direkt im Browser öffnen (Doppelklick oder `File > Open`), dann `ergebnis.json` laden.

Alternativ: Im Dashboard auf **"Demo-Daten laden"** klicken – ohne Python.

### 3. Excel-Report (optional)

```python
from maverick_analyzer_v2 import run_analysis
df = run_analysis("bestellungen.xlsx", output="report.xlsx")
```

## Eingabedaten

Benötigte Spalten (Namen in `CONFIG` in `maverick_analyzer_v2.py` anpassbar):

| Spalte | Pflicht | Beschreibung |
|---|---|---|
| `Bestellnummer` | ✓ | Eindeutige Bestell-ID |
| `Lieferant` | ✓ | Lieferantenname |
| `Betrag` | ✓ | Bestellwert in € |
| `Warengruppe` | ✓ | Materialkategorie |
| `Kostenstelle` | ✓ | Abteilung / KST |
| `Einkäufernummer` | ✓ | Zuständiger Einkäufer |
| `Bestelldatum` | ✓ | Datum der Bestellung |
| `Artikelbeschreibung` | ✓ | Freitext-Beschreibung |
| `Rahmenvertrag` | ✓ | Ja/Nein oder 1/0 |
| `Genehmigungsnachweis` | optional | Belegnummer / Freitext |
| `AutoBestellung` | optional | Automatisierte Bestellung Ja/Nein |

## Dashboard-Ansichten

- **Dashboard** – KPIs, Zeitverlauf, Risikoverteilung
- **Prüftrichter** – Wieviele Transaktionen fallen in welcher Stufe raus?
- **Lieferanten** – Ranking nach Maverick-Quote und Volumen
- **Einkäufer** – Fehlquoten, Täuschungs-Score je Einkäufer
- **Abteilungen** – Welche Kostenstellen bestellen am häufigsten ohne Freigabe?
- **Anforderungen** – Fehlende Genehmigungsnachweise je Einkäufer/Abteilung
- **Transaktionen** – Vollständige Prüfliste, filterbar

## Konfiguration

Alle Parameter in `maverick_analyzer_v2.py` im `CONFIG`-Block:

```python
CONFIG = {
    "committee_threshold": 50_000.0,  # Gremien-Schwellenwert in €
    "time_gap_days": 21,              # Zeitfenster Split-Erkennung (Tage)
    "description_similarity_threshold": 0.6,  # Ähnlichkeits-Schwelle 0-1
    "deception_order_count": 5,       # Ab wann Täuschungsverdacht
    ...
}
```

## Datenbankanbindung

```python
from maverick_analyzer_v2 import run_analysis
df = run_analysis(
    source="postgresql://user:pass@host/db",
    source_type="database",
    db_query="SELECT * FROM orders WHERE year = 2024"
)
```
Benötigt: `pip install sqlalchemy psycopg2-binary`

## Lizenz

MIT
