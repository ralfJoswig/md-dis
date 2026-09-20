# md-dis – Markdown-Viewer

## Übersicht
Desktop-Anwendung zur Anzeige von Markdown-Dateien mit Diagramm-Unterstützung.

## Technische Entscheidungen

| Aspekt | Entscheidung |
|---|---|
| Sprache | Python |
| GUI | PyQt6 + QWebEngineView |
| Plattform | Windows Desktop |
| Paketierung | PyInstaller → .exe |

## Features

### Datei-Öffnung
- Datei-Dialog (Öffnen)
- Kommandozeilenargument: `md-dis.exe datei.md`
- Drag & Drop ins Fenster

### Markdown-Unterstützung
- GitHub-Flavored Markdown (Tabellen, Code-Blöcke, Strikethrough, etc.)
- Umlaute / Sonderzeichen (DE-korrektes Rendering)

### Diagramm-Unterstützung
- **Mermaid**: Server-seitig via `mmdc` (mermaid-cli, npm install -g @mermaid-js/mermaid-cli)
- **PlantUML**: Lokales Java + `plantuml.jar` (im gleichen Verzeichnis wie die .exe)
  - Automatischer Download beim ersten Start, wenn Java vorhanden ist

### Darstellung
- Scrollbar
- Zoombar (Ctrl+/- oder Mausrad)
- Farbschema: Hell/Dunkel Toggle

### Vorschau
- Kein Auto-Reload bei Dateiänderungen

## Projektstruktur

```
md-dis/
├── DESIGN.md              # Diese Dokumentation
├── md_dis.py              # Hauptanwendung
├── requirements.txt       # Python-Abhängigkeiten
└── build.py               # PyInstaller-Build-Skript
```

## Abhängigkeiten

- Python 3.10+
- PyQt6
- PyQt6-WebEngine
- markdown (Python-Paket für GFM)
- PyInstaller (für .exe-Erzeugung)
- Java Runtime (für PlantUML, optional)
- plantuml.jar (wird bei Bedarf automatisch heruntergeladen)

## Tastenkürzel

| Kürzel | Aktion |
|---|---|
| Strg+O | Datei öffnen |
| F5 | Aktuelle Datei neu laden |
| Strg++ | Vergrößern |
| Strg+- | Verkleinern |
| Strg+0 | Zoom zurücksetzen |
| Strg+D | Hell/Dunkel umschalten |

## Build

```bash
pip install -r requirements.txt
python build.py
```

Die .exe befindet sich danach in `dist/md-dis/`.
`plantuml.jar` wird bei Bedarf automatisch heruntergeladen (benötigt Java + Internet).
