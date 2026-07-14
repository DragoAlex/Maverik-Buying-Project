# Category-Management-Analyse

Dateibasiertes Category-Management-Analysepaket für den Einkauf auf Basis
von P2P-Belegdaten (Bestellung, Rechnung, Wareneingang, Zahlung).
Lokal, kein Server, keine Datenbank-Pflicht.

**Decision-Support-Prinzip:** Jede Ausgabe trägt n, Zeitraum und
Datengrundlage. Bei dünner Historie wird „Aussagekraft eingeschränkt,
n=X Monate" ausgewiesen — es wird nie stillschweigend gerechnet, als
wäre die Historie ausreichend.

## Datenannahme

Eingabe sind P2P-Tabellen mit mindestens: `materialnummer`,
`warengruppe` (kann fehlen → Befund), `lieferant`, `menge`, `preis`,
`belegdatum`. Historie idealerweise 12–24 Monate; das Paket läuft auch
mit weniger und weist die Einschränkung je Modul aus.

## Module und Ausbauplan

| Modul | Phase | Status | Inhalt |
|---|---|---|---|
| `stats_core.py` | Fundament | ✅ | Portabler Statistik-Kern (reine Listen, ohne Pandas/NumPy): Quantile Typ 7, MAD roh, Varianz n−1, Variationskoeffizient, Pearson/Spearman/Eta mit n≥3-Sperre. Einzige Statistik-Implementierung im System. |
| `zeitreihen.py` | 0 | ✅ | Monats-Bucketing je Schlüsselkombination (Material, Warengruppe, Lieferant, Material×Lieferant) mit mengengewichtetem Durchschnittspreis, konfigurierbarer Preisbasis und expliziter Lückenbehandlung. |
| `spend_analyse.py` | 1 | geplant | Spend-Würfel Warengruppe×Lieferant×Monat, Pareto/ABC (80/95 %), Konzentrationskennzahlen (Top-1/Top-3-Lieferantenanteil). |
| `kategorie_analyse.py` | 2 | geplant | ABC×XYZ-Klassifizierung (XYZ aus Variationskoeffizient der Monatsmengen; unter 6 Monaten Klasse „?"), DEF als manuelles Konfigfeld. |
| `preis_korrelation.py` | 3 | geplant | Spearman auf monatlichen Preisänderungen (nie Niveaus), n≥12-Überlappung, Verhandlungsbündel-Kandidaten ab \|rho\| ≥ 0.7. |
| `preisindex.py` | 4 | geplant | Laspeyres-Preisindex je Warengruppe/Lieferant (Basis = 100), Trend 3/6/12 Monate, Baseline-Prognose mit Rückwärts-Validierung. |
| `erfahrungskurve.py` | 5 | geplant | Lerneffekt: log-log-Regression Preis über kumulierter Menge, Lernrate 1−2^b, Verhandlungsanker in EUR. |
| `cm_lauf.py` | 6 | geplant | Gesamtlauf: ein Aufruf, ein Laufordner, alle Ausgaben, `cm_bericht.md`, Determinismus-Test. |

## Grundsätze Zeitreihen (Phase 0)

- **Mengengewichtung:** Durchschnittspreis je Bucket = Summe Wert /
  Summe Menge — nie das ungewichtete Mittel der Einzelpreise.
- **Lücken bleiben Lücken:** Monate ohne Belege werden nicht mit 0
  aufgefüllt — null Bestellungen ist keine Preisinformation.
  `monatsluecken()` weist Lücken explizit aus; Funktionen, die
  durchgängige Reihen brauchen, dokumentieren ihren Umgang einzeln.
- **Preisbasis konfigurierbar:** `KONFIG["preisbasis"]` = `"auto"`
  (Default: Rechnungs-Ist-Preis, wenn vorhanden, sonst Bestellpreis),
  `"bestellung"` oder `"rechnung"`. Jeder Bucket trägt ein Kennzeichen
  (`bestellung` / `rechnung` / `gemischt`).
- **Befunde statt stiller Annahmen:** fehlende Warengruppe, unlesbares
  Datum oder unbrauchbare Menge/Preis erzeugen Befunde;
  `historientiefe()` meldet kurze Historien (Schwelle: 12 Monate).

## Tests

```bash
pip install -r requirements.txt   # nur für die Orakel-Tests nötig
python -m pytest analyse_definition pruefung
```

`pruefung/test_oracle.py` prüft `stats_core` gegen NumPy als
unabhängige Referenz (Quantile Typ 7, Varianz ddof=1, MAD, Pearson,
Spearman). Der Kern selbst bleibt frei von externen Abhängigkeiten.
Regel: Vor und nach jeder Änderung alle Tests ausführen — rote Tests
bedeuten kein Commit.

## Bewusst nicht umgesetzt

- **Sentiment-Analyse:** Es existiert keine Textquelle dafür.
  Dokumentierter Andockpunkt für später: Ereignistexte aus der
  Informationsfluss-Zuordnungsstrecke, sobald diese produktiv Volumen
  liefert.
- **ML-Modelle:** Preisprognosen nutzen ausschließlich
  Baseline-Verfahren (naiv, gleitender Mittelwert, Drift) mit
  Rückwärts-Validierung.
- **DEF-Klassifizierung aus Daten:** Beschaffungsrisiko steht nicht in
  Belegen. DEF bleibt manuelles Eingabefeld in der Konfiguration mit
  Default „unbewertet".

## Verwandtes Projekt

Der [Maverick Buying Analyzer](https://github.com/DragoAlex/Maverik-Buying-Project)
(Erkennung von Einkäufen außerhalb genehmigter Prozesse) ist ein
eigenständiges Werkzeug und bleibt in seinem eigenen Repository.

## Lizenz

MIT
