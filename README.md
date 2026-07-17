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

## Category-Management-Analysepaket (`analyse_definition/`)

Erweiterung des Stacks um Category-Management-Auswertungen für den Einkauf.
Lokal, dateibasiert, kein Server. Jede Ausgabe trägt n, Zeitraum und
Datengrundlage (Decision-Support-Prinzip: nie stillschweigend rechnen, als
wäre die Historie ausreichend).

> **Hinweis zur Entstehung:** Der ursprünglich referenzierte, extern
> geprüfte Basis-Stack (`analyse_definition/` aus dem vorherigen
> Ausbaupaket) war in diesem Repository nicht vorhanden. `stats_core.py`
> wurde daher nach der Spezifikation des Prüfauftrags neu implementiert
> (Quantile Typ 7, MAD roh, Varianz n−1, Pearson/Spearman/Eta,
> n≥3-Sperre) und über `pruefung/test_oracle.py` gegen NumPy als
> unabhängige Referenz abgesichert. Liegt der extern geprüfte Kern später
> vor, kann er dank identischer Signaturen direkt eingetauscht werden.

### Module

| Modul | Phase | Inhalt |
|---|---|---|
| `stats_core.py` | Fundament | Portabler Statistik-Kern (reine Listen, ohne Pandas/NumPy): Quantile Typ 7, MAD roh, Varianz n−1, Variationskoeffizient, Pearson/Spearman/Eta mit n≥3-Sperre. Einzige Statistik-Implementierung im System. |
| `zeitreihen.py` | 0 | Monats-Bucketing der P2P-Belegzeilen je Schlüsselkombination (Material, Warengruppe, Lieferant, Material×Lieferant, Warengruppe×Lieferant). Je Bucket: Summe Menge, Summe Wert, **mengengewichteter** Durchschnittspreis (Summe Wert / Summe Menge), Anzahl Belege, Preisbasis-Kennzeichen. |
| `spend_analyse.py` | 1 | Spend-Würfel Warengruppe×Lieferant×Monat, Pareto/ABC auf den Jahres-Spend (letzte 12 Kalendermonate; Grenzen 80/95 % konfigurierbar), Konzentrationskennzahlen je Warengruppe (Top-1-/Top-3-Lieferantenanteil). Ausgaben: `spend_wuerfel.csv`, `abc_material.csv`, `abc_lieferant.csv`, `konzentration.csv`, `spend.md` — jede Datei trägt Zeitraum, n und Preisbasis als Metazeile. |

### Grundsätze Zeitreihen (Phase 0)

- **Lücken bleiben Lücken:** Monate ohne Belege werden nicht mit 0
  aufgefüllt — null Bestellungen ist keine Preisinformation. Funktionen,
  die durchgängige Reihen brauchen, dokumentieren ihren Lücken-Umgang
  einzeln. `monatsluecken()` weist Lücken explizit aus.
- **Preisbasis konfigurierbar:** `KONFIG["preisbasis"]` = `"auto"`
  (Default: Rechnungs-Ist-Preis, wenn vorhanden, sonst Bestellpreis),
  `"bestellung"` oder `"rechnung"`. Jeder Bucket trägt ein Kennzeichen
  (`bestellung` / `rechnung` / `gemischt`).
- **Befunde statt stiller Annahmen:** fehlende Warengruppe, unlesbares
  Datum oder unbrauchbare Menge/Preis erzeugen Befunde;
  `historientiefe()` meldet „Aussagekraft eingeschränkt, n=X Monate"
  unterhalb der konfigurierten Schwelle (Default 12 Monate).

### Tests

```bash
python -m pytest analyse_definition pruefung   # oder:
python -m unittest discover -s analyse_definition -t .
```

`pruefung/test_oracle.py` prüft `stats_core` gegen NumPy als Orakel
(einzige Stelle mit NumPy-Bedarf; der Kern selbst bleibt frei davon).

### Bewusst nicht umgesetzt

- **Sentiment-Analyse:** Es existiert keine Textquelle dafür.
  Dokumentierter Andockpunkt für später: Ereignistexte aus der
  Informationsfluss-Zuordnungsstrecke, sobald diese produktiv Volumen
  liefert.
- **ML-Modelle:** Preisprognosen nutzen ausschließlich die
  Baseline-Verfahren des Stacks (Phase 4).
- **DEF-Klassifizierung aus Daten:** Beschaffungsrisiko steht nicht in
  Belegen. DEF bleibt manuelles Eingabefeld in der Konfiguration mit
  Default „unbewertet".

## Lizenz

MIT
