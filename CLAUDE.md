# CLAUDE.md — Arbeitsverzeichnis Schaumberg Consulting

Dieses Dokument beschreibt das Arbeitsverzeichnis, die Projektstruktur und die Entwicklungsrichtlinien für Claude Code.

---

## Workspace-Überblick

Das Heimverzeichnis dient als zentraler Workspace. Projekte sind thematisch in Unterverzeichnisse aufgeteilt.

| Verzeichnis | Inhalt |
|---|---|
| `Projects/jupyter-lab/` | Python / KI-Entwicklung (Jupyter Notebooks, Chatbots, RAG, Datenanalyse) |
| `Maverik-Buying-Project/` | Python-Tool zur Maverick-Buying-Erkennung in Einkaufsdaten |
| `gstack/` | Internes Tooling (TypeScript) |
| `openclaw/` | Claude Code Extension (TypeScript) |
| `Projects/Projekte Firma/` | Geschäftsprojekte und Kundendaten |

---

## Sprache & Kommunikation

- **Projektsprache: Deutsch**
- Commit-Messages, Kommentare, Dokumentation: Deutsch
- Code-Bezeichner (Variablen, Funktionen, Klassen): Englisch (Konvention)
- Antworten von Claude: Deutsch

---

## Allgemeine Entwicklungsrichtlinien

- Keine unnötigen Abstraktionen — drei ähnliche Zeilen sind besser als eine voreilige Abstraktion
- Keine Fehlerbehandlung für Szenarien, die nicht eintreten können
- Keine neuen Dateien erstellen, wenn bestehende Dateien editiert werden können
- Sicherheitslücken (SQL-Injection, Command-Injection, XSS) von Anfang an vermeiden
- Keine sensiblen Daten (API-Keys, Passwörter) in Code oder Commits

### Kommentarregeln

Kurze Code-Abschnitte und selbsterklärende Logik: **kein Kommentar**.

Bei längeren, verschachtelten oder mehrstufigen Code-Bereichen werden **kurze Abschnittskommentare** eingefügt, die beschreiben was der Block erreicht — nicht wie er es tut:

```python
# --- Schritt 1: Rohdaten laden und normalisieren ---
...

# --- Schritt 2: Schwellenwert-Filterung ---
...

# --- Schritt 3: Ergebnis exportieren ---
...
```

Regeln für diese Kommentare:
- Maximal eine Zeile pro Abschnitt
- Beschreibt das **Ziel** des Blocks, nicht die Mechanik
- Trennlinie-Stil (`# ---`) für Hauptabschnitte, einfaches `#` für Unterabschnitte
- Sprache: Deutsch

---

## Modul: Python

**Aktuelle Hauptsprache** — genutzt für KI-Entwicklung, Datenanalyse und Automatisierung.

### Umgebung

```bash
# Jupyter Lab starten
jl   # Alias in ~/.zshrc (aktiviert venv + startet Lab)

# Virtuelle Umgebungen
~/Projects/jupyter-lab/venv/     # Standard Python-Umgebung (Jupyter)
~/Projects/jupyter-lab/venv311/  # Python 3.11 Umgebung
~/venv/                          # Allgemeine Umgebung
```

### Pakete & Abhängigkeiten

Wichtige installierte Pakete:
- `pandas`, `numpy`, `matplotlib`, `seaborn` — Datenanalyse
- `langchain`, `faiss-cpu` — RAG / LLM-Pipelines
- `chainlit` — Chat-UI für LLM-Anwendungen
- `sqlalchemy`, `psycopg2-binary` — Datenbankanbindung
- `azure-storage-blob` — Azure Storage

### Konventionen

- Virtuelle Umgebung immer aktivieren vor `pip install`
- `requirements.txt` bei neuen Projekten anlegen
- Konfigurationsparameter in einem `CONFIG`-Dictionary bündeln (siehe `maverick_analyzer_v2.py`)
- Jupyter Notebooks: aussagekräftige Zellkommentare verwenden, da Notebooks interaktiv sind

### Wichtige Projekte

**Maverick-Buying-Analyzer** (`~/Maverik-Buying-Project/`)
- 6-stufiger Prüftrichter zur Erkennung von Maverick Buying in Einkaufsdaten
- Einstiegspunkt: `maverick_export.py --demo` für Testlauf
- Dashboard: `maverick_dashboard.html` direkt im Browser öffnen

**KI-Entwicklung** (`~/Projects/jupyter-lab/KI Development/`)
- RAG-Entwicklung, Web-Scraping, Azure-Integration
- Chatbot-Prototypen (Chainlit-basiert)

---

## Modul: JavaScript / TypeScript

> **Status: Geplant** — Erweiterung für Frontend- und Node.js-Projekte

### Vorbereitete Infrastruktur

```bash
# Verfügbare Laufzeiten
bun    # Primäre JS-Runtime (installiert via ~/.bun)
node   # Node.js (via Homebrew /opt/homebrew/bin)
```

### Geplante Konventionen

- Runtime: **Bun** bevorzugen (schneller als npm/node für lokale Skripte)
- Paketmanager: `bun` statt `npm` für neue Projekte
- TypeScript für alle Nicht-Wegwerf-Skripte
- Linting: oxlint (bereits in `openclaw/` konfiguriert, `.oxlintrc.json`)

### Referenzprojekte

- `gstack/` und `openclaw/` als TypeScript-Referenz für Code-Stil und Projektstruktur

---

## Modul: Java

> **Status: Geplant** — Erweiterung für Enterprise- und Backend-Projekte

### Vorbereitung (noch ausstehend)

```bash
# Wenn Java eingerichtet ist, hier eintragen:
# java --version
# mvn --version  oder  gradle --version
```

### Geplante Konventionen

- Build-Tool: Maven oder Gradle (je nach Projektanforderung)
- Java-Version: LTS (21 oder neuer bevorzugen)
- Paket-Struktur: `com.schaumbergconsulting.<projekt>`
- Tests: JUnit 5

---

## Modul: C++

> **Status: Geplant** — Erweiterung für Performance-kritische oder Robotik-Projekte

### Vorbereitung (noch ausstehend)

```bash
# Wenn C++-Toolchain eingerichtet ist, hier eintragen:
# clang++ --version  oder  g++ --version
# cmake --version
```

### Geplante Konventionen

- Standard: C++17 oder neuer
- Build-System: CMake
- Compiler: Clang (macOS Standard via Xcode Command Line Tools)
- Für Robotik-Code: Referenz-Notebook `Robotik Code.ipynb` in `Projects/jupyter-lab/`

---

## Umgebungsvariablen

Sensible Schlüssel werden **nicht** in Code oder `.env`-Dateien im Projektverzeichnis gespeichert.

| Variable | Quelle |
|---|---|
| `TELEGRAM_BOT_TOKEN` | `~/KEYs/telegram_token.txt` (via `.zshrc` geladen) |
| Azure-Credentials | `~/.azure/` |
| Weitere API-Keys | `~/KEYs/` und `~/Projects/` (`.rtf`-Dateien) |

> API-Keys niemals in Git committen. `.gitignore` vor dem ersten Commit prüfen.

---

## Git-Workflow

- Commits auf Deutsch verfassen
- Feature-Branches vor Merge in `main`/`master`
- Keine Force-Pushes ohne explizite Bestätigung
- Keine Commits mit `--no-verify`

---

## Erweiterung dieses Dokuments

Wenn ein neues Sprachmodul aktiv wird:
1. Den `> Status: Geplant`-Hinweis im entsprechenden Abschnitt entfernen
2. Installierte Toolchain eintragen
3. Konventionen anpassen und spezifische Projekte verlinken
