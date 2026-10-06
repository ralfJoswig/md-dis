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
| PDF | `QWebEnginePage.printToPdf` (Chromium), keine Zusatzabhängigkeit |
| Einstellungen | `QSettings` im INI-Format, Datei neben der .exe |

## Features

### Datei-Öffnung
- Datei-Dialog (Öffnen)
- Kommandozeilenargument: `md-dis.exe datei.md`
- Drag & Drop ins Fenster

### Markdown-Unterstützung
- GitHub-Flavored Markdown (Tabellen, Code-Blöcke, Strikethrough, etc.)
- Umlaute / Sonderzeichen (DE-korrektes Rendering)
- Bildeinbettung `![[grafik.png]]` und `![[grafik.png|Alt-Text]]` (siehe unten)

#### Bildeinbettung `![[…]]`
- Als `InlineProcessor` in `md_render.py` (`EmbedImageProcessor`), registriert mit
  Priorität **175** auf der `markdown.Markdown`-Instanz in `markdown_to_html`.
- **Warum Inline-Prozessor und kein Regex-Vorabpass:** Ein Vorabpass auf dem
  Markdown-Text greift auch in Code-Fences und Inline-Code — genau das Problem,
  das der PlantUML-/Mermaid-Vorabpass bei `md_render.py:802` hat. Inline-Prozessoren
  laufen nur in Fließtext, in `<pre>`/`<code>` bleibt die Syntax sichtbarer Text.
- Priorität 175 liegt **vor** dem eingebauten Bildmuster (160), `![…](…)` bleibt
  unverändert.
- Erzeugt `etree.Element("img")` statt HTML-String, dadurch sind Attributwerte
  automatisch escaped. `alt` wird immer gesetzt, sonst liest ein Screenreader den
  Dateinamen vor.
- Zugelassen sind dieselben Endungen wie in `IMAGE_SUFFIXES` des Servers
  (`.png .jpg .jpeg .gif .svg .webp`), damit GUI und Server dasselbe behandeln.
  Alles andere bleibt sichtbarer Text.
- Bewusst **keine** Breitenangabe (`![[b.png|300]]`): `attr_list` ist nicht aktiv,
  und `max-width: 100%` begrenzt Bilder ohnehin.
- Da `![[…]]` vorher kein gültiges Markdown war, wird kein bestehendes Dokument
  umgedeutet.

### Diagramm-Unterstützung
- **Mermaid**: Server-seitig via `mmdc` (mermaid-cli, npm install -g @mermaid-js/mermaid-cli)
- **PlantUML**: Lokales Java + `plantuml.jar` (im gleichen Verzeichnis wie die .exe)
  - Automatischer Download beim ersten Start, wenn Java vorhanden ist

### Frontmatter
- `strip_frontmatter` in `md_render.py` erkennt YAML-Frontmatter am Dateianfang und
  eine ```markdown-Hülle.
- Fehler ab 1.3.0 behoben: das Hüllen-Muster verlangt **verpflichtend** `markdown`.
  Vorher hat auch jeder **nackte** ```-Fence am Dokumentanfang das Muster getroffen,
  wodurch Code als Markdown gerendert wurde — Links und Bilder wurden also lebendig.
- `[^\S\n]` statt `\s`, damit der horizontale Whitespace nicht über Zeilengrenzen
  greift, und `\n*` statt `\n?`, damit die Folgezeile nicht angeklebt wird.
- `_join_wrapped` setzt Inhalt und Folge mit einem Trenner zusammen; vorher ergab
  `# T` + `# Nachfolger` das Wort `# T# Nachfolger`.

### Darstellung
- Scrollbar
- Zoombar (Ctrl+/- oder Mausrad)
- Farbschema: Hell/Dunkel Toggle
- Farbschema und Zoom werden in `md-dis.ini` neben der .exe gespeichert

### PDF-Export
- `Ctrl+P` → Dialog für Seitenformat, Ausrichtung und Rand-Preset
- Erzeugung über `QWebEnginePage.printToPdf`, asynchron; Ergebnis meldet `pdfPrintingFinished`
- `CSS_PRINT` in `md_render.py` erzwingt im `@media print` die helle Palette,
  damit eine PDF aus dem Dunkelmodus nicht schwarz gedruckt wird
- Layout-Auswahl wird unabhängig vom Zieldateinamen gespeichert
- Kein Skalierungsregler: `printToPdf` bietet in PyQt6 keinen `scaleFactor`.
  Für breite Diagramme gibt es Querformat

### Vorschau
- Kein Auto-Reload bei Dateiänderungen
- Anzeige per `setHtml` mit `baseUrl` auf dem Verzeichnis der Markdown-Datei,
  damit relative Bildpfade auflösen (vorher `setUrl` auf `preview/`, wodurch
  Bilder aus dem Dokumentverzeichnis fehlten)

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
| Strg+P | Vorschau als PDF speichern |
| Strg+F | Suchen |
| F2 | Bearbeiten |

## Build

```bash
pip install -r requirements.txt
python build.py
```

Die .exe befindet sich danach in `dist/md-dis/`.
`plantuml.jar` wird bei Bedarf automatisch heruntergeladen (benötigt Java + Internet).
