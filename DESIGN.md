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

#### Wiki-Links `[[…]]`
- `WikiLinkProcessor` in `md_render.py`, Priorität **170** – also **hinter** dem
  Bild-Embed (175), damit `![[bild.png]]` weiterhin als Bild gilt und nicht als
  Link missverstanden wird.
- `[[Datei]]` ergänzt bei fehlender Dateiendung `.md`; `[[Datei#Abschnitt]]`
  hängt den über `_slugify` erzeugten Anker an; `[[Datei|Alias]]` setzt den
  Linktext (Default: Dateiname ohne Endung).
- Wie das Bild-Embed ein `InlineProcessor` – in Code-Fences und Inline-Code
  bleibt die Syntax sichtbarer Text.
- Liefert ein `etree.Element("a")`, dadurch werden `href` und Linktext escaped.

### Diagramm-Unterstützung
- **Mermaid**: Server-seitig via `mmdc` (mermaid-cli, npm install -g @mermaid-js/mermaid-cli)
- **PlantUML**: Lokales Java + `plantuml.jar` (im gleichen Verzeichnis wie die .exe)
  - Automatischer Download beim ersten Start, wenn Java vorhanden ist
  - Der Download ist atomar (`plantuml.jar.part` + `os.replace`); liefert die
    Release-Seite eine `plantuml.jar.sha256`, wird der Download zusätzlich gegen
    deren Prüfsumme verifiziert (sonst läuft er unverändert weiter).

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
- Die Info-Box rendert `render_frontmatter_html`, die Auswertung übernimmt
  `_parse_frontmatter_pairs`. Das ist **kein** YAML-Parser, versteht aber die in
  Frontmatter üblichen Formen: `key: wert`, mehrzeilige Plain-Skalare, Listen
  unter einem Key (`- a`) und Block-Skalare (`key: >` folded bzw. `key: |` literal,
  inklusive Chomping- und Einrückungs-Indikator). Vor 1.4.3 wurde die Frontmatter
  zeilenweise geparst: bei `description: >` landete nur der Indikator `>` in der
  Zelle, die eingerückten Fortsetzungszeilen fielen weg (und damit der ganze Text).

### Darstellung
- Scrollbar
- Zoombar (Ctrl+/- oder Mausrad)
- Farbschema: Hell/Dunkel Toggle
- Farbschema und Zoom werden in `md-dis.ini` neben der .exe gespeichert

#### Inhaltsverzeichnis (Sidebar)
- Automatisch aus den Überschriften **h1–h3** erzeugt; die toc-Extension von
  Python-Markdown war bereits aktiv (sie vergibt die `id` der Überschriften),
  es fehlte nur die Auswertung.
- `markdown_to_html(..., toc=True)` hängt links ein `<nav class="md-toc">` mit
  dem Verzeichnis an. Die Anker sind reine HTML-`#id`-Sprünge und funktionieren
  deshalb ohne JavaScript (GUI hat JS aus).
- Aufbau: Das Template hat einen festen Wrapper `.md-page > (.md-toc? +
  .md-content > .markdown-body)`. Der Wrapper ist **immer** vorhanden – auch
  ohne Sidebar –, damit die Server-Toolbar-Injektion (sucht
  `<div class="markdown-body">`) und das CSS nicht auseinanderlaufen.
- `md.toc` ist auch ohne Überschriften nicht leer (leeres `<ul>`), deshalb
  entscheidet `bool(md.toc_tokens)`, ob überhaupt Einträge da sind. Das
  Attribut `data-toc-has` auf `.md-page` transportiert das an den Server.
- Eigene `<nav class="md-toc">`-Hülle statt `toc_class`: Ein vom Autor
  platzierter `[TOC]`-Marker erzeugt ein `<div class="toc">`; mit gemeinsamer
  Klasse hätte dieser Marker wie die Sidebar ausgesehen. Enthält ein Dokument
  `[TOC]`, wird **keine** zusätzliche Sidebar erzeugt (sonst zwei Verzeichnisse).
- `position: sticky`, feste Breite 240 px, `max-height: 100vh`. Unter 900 px
  Breite (Media-Query) tritt die Sidebar zur Seite, der Text bleibt lesbar.
- **PDF:** `@media print` setzt `.md-page` auf `display: block` und blendet
  `.md-toc` aus – die PDF bleibt wie vor dem Feature. `scroll-margin-top`
  verhindert, dass angesprungene Überschriften unter der Server-Toolbar landen.
- Toggle: GUI-Action „Verzeichnis“ (Strg+T, `appearance/showToc` in der INI);
  Server `--no-toc` plus `?toc=0/1`-Link in der Toolbar. Der Server-Cache
  schlüsselt auf `(Pfad, toc-Zustand)`.

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
| Strg+T | Inhaltsverzeichnis-Sidebar ein-/ausblenden |
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

## Sicherheit (Server)

- **Pfad-Traversal:** `resolve_within_root` löst den Zielpfad auf und prüft
  anschließend mit `Path.relative_to(root)`, ob er innerhalb der Wurzel bleibt –
  statt eines Präfix-Vergleichs auf Strings, der z. B. `Root2` fälschlich als
  innerhalb von `Root` akzeptiert hätte. Pfade mit versteckten Segmenten
  (`.git`, `.venv`, `.env`) werden zusätzlich blockiert.
- **CSP & Header:** jede Antwort trägt `Content-Security-Policy`
  (`script-src 'self'`) und `X-Content-Type-Options: nosniff`; der Watch-Client
  lädt sein Skript über `GET /watch.js` (Pfad per `data-path`).
- **DNS-Rebinding/CSRF:** Fremde `Host`-Header werden (bei Loopback-Bindung)
  abgewiesen, `POST` ohne passenden `Origin` ebenfalls.
