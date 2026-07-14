# CLAUDE.md — Category-Management-Analyse

## Projekt

Dateibasiertes Category-Management-Analysepaket für P2P-Einkaufsdaten.
Ausbauplan und Modulübersicht: siehe README.md.

## Sprache & Stil

- Projektsprache Deutsch: Commits, Kommentare, Dokumentation, Berichte
- Code-Bezeichner in diesem Stack: Deutsch (Bestandskonvention des
  Analyse-Stacks, z. B. `baue_monatsreihe`, `lineare_regression`)
- Expliziter Code-Stil, Warum-Kommentare statt Was-Kommentare
- Abschnittskommentare im Trennlinien-Stil (`# --- Ziel des Blocks ---`)

## Architekturregeln

- Lokal, dateibasiert, kein Server
- `stats_core.py` ist die einzige Statistik-Implementierung im System
  und bleibt frei von Pandas/NumPy (reine Listen, portierbar)
- Erweiterung über Konfiguration (`KONFIG`-Dictionaries) statt
  Code-Duplikation
- Rohwerte poolen, nie bereits berechnete Kennzahlen aggregieren
- Decision-Support: jede Ausgabe trägt n, Zeitraum, Datengrundlage;
  zu wenig Daten → None bzw. „Aussagekraft eingeschränkt, n=X Monate",
  nie stillschweigend rechnen
- Monate ohne Belege bleiben Lücke (kein Auffüllen mit 0)
- Korrelationen nur auf Preisänderungen, nie auf Preisniveaus

## Tests

- Jedes Modul hat eine Testdatei mit Grenzfällen (`test_<modul>.py`)
- `pruefung/test_oracle.py`: stats_core gegen NumPy als Orakel
- Vor und nach jeder Änderung alle Tests ausführen:
  `python -m pytest analyse_definition pruefung`
- Rote Tests = kein Commit

## Nicht-Umfang (bewusst)

Keine Sentiment-Analyse (keine Textquelle vorhanden), keine ML-Modelle,
keine DEF-Klassifizierung aus Belegdaten (manuelles Konfigfeld,
Default „unbewertet"). Details im README unter „Bewusst nicht umgesetzt".
