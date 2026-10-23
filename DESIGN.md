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
  Markdown-Text griff früher auch in Code-Fences und Inline-Code. Der
  PlantUML-/Mermaid-Vorabpass ist inzwischen auf zustandsbasiertes
  Fence-Parsing umgestellt (`_extract_diagram_blocks`, siehe unten); für
  text-level-Syntax wie `![[…]]` bleibt ein Inline-Prozessor trotzdem das
  einfachere Mittel, weil in `<pre>`/`<code>` die Syntax sichtbarer Text bleibt.
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
- `_slugify` verwendet **denselben** Slugify wie die toc-Extension
  (`markdown.extensions.toc.slugify`, Trenner `-`). Eine frühere eigene
  Implementierung erzeugte bei Unterstrichen `a-b-c` statt `a_b-c` und
  verfehlte damit die Heading-`id` (Review M3). Doppelt vorkommende
  Überschriftentexte bleiben eine Einschränkung: die Extension nummeriert sie
  (`_1`), `_slugify` kennt nur die Basis.
- Wie das Bild-Embed ein `InlineProcessor` – in Code-Fences und Inline-Code
  bleibt die Syntax sichtbarer Text.
- Liefert ein `etree.Element("a")`, dadurch werden `href` und Linktext escaped.

### Diagramm-Unterstützung
- **Mermaid**: Server-seitig via `mmdc` (mermaid-cli, npm install -g @mermaid-js/mermaid-cli)
- **PlantUML**: Lokales Java + `plantuml.jar` (im gleichen Verzeichnis wie die .exe)
  - Download erst **bei Bedarf**: beim Laden einer Datei mit ` ```plantuml `-Fence,
    wenn die JAR fehlt (nicht mehr beim Start – dort steht nur ein Hinweis in der
    Statuszeile). Eine Ablehnung oder ein Fehlschlag wird für die Sitzung gemerkt.
  - Der Download ist atomar (`plantuml.jar.part` + `os.replace`); liefert die
    Release-Seite eine `plantuml.jar.sha256`, wird der Download zusätzlich gegen
    deren Prüfsumme verifiziert (sonst läuft er unverändert weiter).
- **Extraktion fence-aware:** `_extract_diagram_blocks` geht die Zeilen
  zustandsbasiert durch und erkennt ` ```plantuml `/` ```mermaid ` nur auf
  oberster Ebene (gleiches Fence-Zeichen, Schließ-Fence mindestens so lang,
  ohne Info-String). Ein ` ```plantuml `-Beispiel *innerhalb* eines anderen
  Code-Blocks wird dadurch nicht als Diagramm ausgeführt – der frühere
  `re.sub`-Vorabpass über den ganzen Text tat das (Review M1).

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
- Farbschema, Zoom, Inhaltsverzeichnis-Zustand sowie Fensterposition und -größe
  (inkl. maximiertem Fenster) werden in `md-dis.ini` neben der .exe gespeichert.
  Passt die gespeicherte Position nicht mehr zum Bildschirmaufbau, startet das
  Fenster stattdessen zentriert in Standardgröße.
- Mehrbildschirm: Der Monitor wird als `window/screen` (Name, z. B.
  `\\.\DISPLAY2`) plus `window/screenRect` (Fläche als Ersatz) gemerkt und beim
  Start wiedergefunden. Steht das Fenster danach nicht auf diesem Monitor,
  schiebt `_move_into_screen` es in dessen nutzbare Fläche (und verkleinert es,
  falls nötig). Fehlt der Monitor, bleibt die wiederhergestellte Position.

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

## Startzeit

Messwerte (Frozen-Build, lokal, 3–4 Läufe; vor der Überarbeitung 777/904/1085 ms bis
zum Fenster):

| Pfad | Vorher | Nachher |
|---|---|---|
| GUI: erstes sichtbares Fenster (Splash) | – | **58–149 ms** |
| GUI: Hauptfenster | 777–1085 ms | **649–688 ms** |
| Server: Banner | 492–763 ms | **155–159 ms** (warm) |
| Server: erster Request (400 ms nach Banner) | 287–320 ms | **207–233 ms** |
| Bundle-Größe | 442,4 MB / 1035 Dateien | **381,4 MB / 1009 Dateien** |

Maßnahmen und ihre Begründung:

- **Importe verzögern** (`md_render.py`): `hashlib`/`urllib.request` liegen hinter dem
  Frühabbruch „JAR vorhanden", die Mermaid-Hilfen im Mermaid-Zweig. Der Normalfall
  (JAR vorhanden) zahlt nichts. `import md_dis` spart dadurch ~40–58 ms.
- **QtWebEngine erst beim ersten Dokument** (`md_dis.py`): Der Import kostet ~26 ms und
  zieht `Qt6WebEngineCore.dll` nach. Bedingungen, beide dokumentiert im Modulkopf:
  `Qt.ApplicationAttribute.AA_ShareOpenGLContexts` muss **vor** der `QApplication`
  gesetzt sein, und die `QApplication` braucht ein nicht-leeres `argv` (Chromium baut
  daraus seine Kommandozeile; `QApplication([])` stürzt beim späten Start mit
  `0xC0000409` ab). Die Seitenklasse `ExternalLinkPage` entsteht deshalb über die
  gecachte Fabrik `external_link_page_class()`.
- **Splash** (`build.py` + `_close_splash()`): PyInstaller-Tk-Splash nach ~60 ms;
  geschlossen wird erst nach `show()` + `processEvents()`, damit das Hauptfenster
  bereits gezeichnet ist. Nur die GUI, nicht der Server. Tcl/Tk kostet ~3,4 MB.
- **Fokus** (`_bring_to_front`): Der Splash hält den Vordergrund und Windows gibt
  ihn beim Schließen nicht an md-dis weiter – der Doppelklick-Start blieb hinter
  dem Explorer. Deshalb `raise_()` + `activateWindow()` plus (Windows)
  `AttachThreadInput` auf den Vordergrund-Thread + `SetForegroundWindow`, dreimal
  per `QTimer.singleShot(0/150/500)` nach dem Event-Loop-Start.
- **Chromium vorwärmen**: 250 ms nach `show()` wird die Ansicht angelegt und eine
  leere Seite geladen. Der Stack bleibt auf dem Willkommens-Label, die PDF-Action
  bleibt ohne Datei deaktiviert. Das erste Dokument ist dadurch ~0,3 s schneller.
- **PlantUML-Prüfung ohne Startkosten**: kein `java -version` (~148 ms) und kein
  modaler Dialog beim Start, nur ein Statuszeilen-Hinweis. Der Dialog kommt beim
  ersten Dokument mit ` ```plantuml `-Fence (Vorfilter `_contains_plantuml_block`).
- **Bundle**: `numpy`, `PIL`, `psutil`, `setuptools`, `charset_normalizer`, `olefile`
  und `defusedxml` sind ausgeschlossen (nur über die Analyse-Kette
  `codehilite → pygments.formatters.img → PIL` hereingekommen, zur Laufzeit nie
  importiert). `--noupx` ist explizit: UPX würde die 195-MB-WebEngine-DLL packen und
  den Start durch Entpacken verlangsamen.
- **Server**: Daemon-Thread `render-warmup` rendert nach dem Binden ein
  Mini-Dokument mit Codeblock, damit Markdown-/Pygments-Importe und Caches beim
  ersten Request bereit sind.

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
  (`script-src 'self'`, `img-src 'self' data:`) und `X-Content-Type-Options:
  nosniff`; der Watch-Client lädt sein Skript über `GET /watch.js` (Pfad per
  `data-path`). Fremdbilder in einem Dokument werden damit **nicht** geladen.
- **Größen-/Kodier-Grenzen:** Markdown über 10 MB → 413; gelesen wird mit
  `utf-8-sig` und `errors="replace"` (BOM-tolerant, kein 500er bei kaputten
  Bytes). Der Index wird kurz zwischengespeichert, damit wiederholte Aufrufe
  nicht jedes Mal den Baum durchlaufen.
- **DNS-Rebinding/CSRF:** Fremde `Host`-Header werden (bei Loopback-Bindung)
  abgewiesen, `POST` ohne passenden `Origin` ebenfalls. Der erlaubte Port kommt
  aus der tatsächlichen Bindung (`server.server_address[1]`), damit `--port 0`
  funktioniert.
