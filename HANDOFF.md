# Handoff – md-dis

Stand: 2026-10-18 (letzte Sitzung: Wiki-Links `[[…]]`, optionale SHA256-Prüfung beim JAR-Download und LRU-Server-Cache ergänzt, committet und dokumentiert – `VERSION` bleibt bewusst 1.4.4, kein neuer Build)

## Projekt
`md-dis` = Windows-Markdown-Viewer (PyQt6/QWebEngine, Dark-Mode, Zoom, Watch, PlantUML/Mermaid)
mit **zwei Build-Varianten**:
- **GUI-Client** (`md-dis`): Desktop-App zum lokalen Anzeigen/Editieren von `.md`.
- **Server** (`md-dis-server`): headless HTTP-Server, rendert identisch per HTTP (stdlib-only, ohne Qt).

Konvention: App-Sprache und sämtliche Meldungen sind **Deutsch**.

## Architektur / Dateien (Projektwurzel `C:\Users\ralfj\Coding\md-dis`, Git-Repo `github.com/ralfJoswig/md-dis`)
| Datei | Rolle |
|---|---|
| `md_render.py` | **Qt-freier gemeinsamer Render-Kern** (`VERSION="MAJOR.MINOR.BUILD"`, HTML_TEMPLATE, CSS_LIGHT/DARK, `markdown_to_html`, PlantUML/Mermaid-Finder+Renderer, Frontmatter, `get_jar_search_dirs`). Importiert KEIN Qt. |
| `md_dis.py` | GUI-Client (ca. 30 KB / ~800 Zeilen); importiert nur noch `VERSION, get_plantuml_jar_path, get_base_dir, get_jar_search_dirs, check_java_available, download_plantuml_jar, find_mmdc, markdown_to_html` aus `md_render`. |
| `md_dis_server.py` | HTTP-Server (ca. 21 KB / ~534 Zeilen, `http.server.ThreadingHTTPServer`). |
| `build.py` | PyInstaller: `python build.py` → GUI, `python build.py --server` → Server, `--clean` löscht build/dist/Specs. Entfernt vor jedem Build das jeweilige Ziel-Dist (verhindert „not empty"-Fehler). Verwaltet außerdem die Versionsnummer (siehe unten). |
| `plantuml.jar` | echtes JAR (28,5 MB) – liegt im Projektwurzelverzeichnis, wird von Source-Aufrufen und Frozen-EXEs (Ordner der Exe) genutzt. Gitignored, daher nach jedem Clone erneut bereitzustellen. |

## Server-Features (`md_dis_server.py`)
- Optionen: `--host` (127.0.0.1), `--port` (8080), `--root`, `--dark`, `--zoom`, `--watch`, `--no-toc` (Verzeichnis-Sidebar aus); optionales **Positionsargument `file`**.
- Routen:
  - `GET /` → Index-Liste aller `.md/.markdown` unter `--root`; bei `--file` → **302** auf `/<datei>`.
  - `GET /<pfad>.md` → gerendertes HTML (Toolbar: Index/Link je nach Redirect + „Hochladen“ + „Rohdaten“ + „Verzeichnis ein-/ausblenden“; Watch-Skript bei `--watch`). `?toc=0/1` übersteuert den Server-Standard pro Anfrage.
  - `GET /raw/<pfad>` (`text/plain`), `GET /poll?path=` (mtime_ns-Stempel), statische Dateien (mimetypes).
  - **Upload:** `GET /upload` → Formular; `POST /upload` (multipart/form-data, stdlib-only-Parser, kein `cgi` – in Py3.13 entfernt) → speichert unter `<Root>/uploads/<bereinigter Name>`, 303-Redirect auf Anzeige. Schutz: nur `.md/.markdown` (sonst 400), Dateiname gesäubert (Postfix `_sanitize_filename`), 10-MB-Limit (413), `resolve_within_root` blockiert Traversal. Namenkollisionen weichen per Suffix `_1`, `_2`, … aus (max. 100 Versuche).
- Cache in-memory, ein Eintrag pro Datei **und TOC-Zustand** (`(abspath, toc)` → (mtime_ns, html)). **LRU:** max. 20 Einträge, jeder Zugriff hängt den Eintrag hinten an, bei Überlauf fliegt der älteste. Die Index-Liste hat einen eigenen **TTL-Cache** (`INDEX_CACHE_TTL`, 2 s), damit wiederholte `GET /` nicht jedes Mal den ganzen Baum durchlaufen. 500-Handler loggt Traceback.
- **Größenlimit:** Markdown über `MAX_MD_BYTES` (10 MB) wird mit 413 abgelehnt, bevor es gelesen wird. Dateien werden als `utf-8-sig` mit `errors="replace"` gelesen – kaputte Bytes ergeben keinen irreführenden 500er.
- Sicherheit: alle Antworten mit `Content-Security-Policy` (`script-src 'self'`, `img-src 'self' data:`) + `nosniff`; Watch-Skript kommt extern über `GET /watch.js` (Pfad per `data-path`). Frontmatter, Diagramm-Fehlerausgaben und Index-Dateinamen werden HTML-maskiert. Rohes HTML im Markdown bleibt erlaubt, Skripte darin blockiert die CSP; Fremdbilder werden nicht geladen.
- Ausgeliefert werden nur Markdown und Bilder (png/jpg/jpeg/gif/svg/webp); `/raw/` nur für Markdown. Pfade mit Dot-Segment (`.git`, `.venv`, `.env`) → 404, Index überspringt sie.
- Bei Loopback-Bindung nur `Host: localhost|127.0.0.1|[::1]:<port>` (DNS-Rebinding) → sonst 403; `POST` mit fremdem `Origin` → 403 (CSRF). 500 ohne Details an den Client.
- `--port 0` lässt das Betriebssystem einen freien Port wählen; `allowed_hosts` und der Banner nutzen den **tatsächlich gebundenen** Port aus `server.server_address[1]`, sonst würde der Host-Check jeden Request mit 403 abweisen.
- PlantUML rendert im Server mit `-DPLANTUML_SECURITY_PROFILE=SANDBOX` (`markdown_to_html(..., sandbox=True)`), kein `!include` lokaler Dateien.

## Render-Kern (`md_render.py`)
- **Inhaltsverzeichnis:** `markdown_to_html(..., toc=True)` hängt links ein sticky `<nav class="md-toc">` mit den Überschriften h1–h3 an; Anker sind reine `#id`-Sprünge (kein JS nötig). Das Template hat immer den Wrapper `.md-page > (.md-toc? + .md-content > .markdown-body)`; `data-toc-has` meldet dem Server, ob Einträge existieren. Ein `[TOC]`-Marker im Text unterdrückt die Sidebar (die Extension ersetzt ihn bereits inline). Achtung: `md.toc` ist auch ohne Überschriften nicht leer (leeres `<ul>`), deshalb entscheidet `bool(md.toc_tokens)`. `toc_depth='1-3'` begrenzt Verzeichnis **und** Heading-`id`s auf h1–h3.
- SVG-Cache (max. 256, Schlüssel art/sandbox/code, thread-safe) – Theme-Wechsel, F5, Bearbeiten→Anzeigen rendern Diagramme nicht neu.
- PlantUML: alle Blöcke eines Dokuments in **einem** JVM-Aufruf (`-charset UTF-8`); Mermaid: bis zu 4 `mmdc` parallel.
- **Diagramm-Extraktion fence-aware** (`_extract_diagram_blocks`): ` ```plantuml `/` ```mermaid ` werden zeilen- und zustandsbasiert nur auf oberster Fence-Ebene erkannt (gleiches Zeichen, Schließ-Fence mindestens so lang, ohne Info-String). Ein Beispiel-Snippet in einem anderen Code-Block bleibt unberührt (Review M1).
- Auto-Download von `plantuml.jar` höchstens einmal pro Prozess; `find_java`/`find_mmdc` merken Treffer.
- **`plantuml.jar`-Suche** (`get_jar_search_dirs`, Reihenfolge = Priorität): `MD_DIS_PLANTUML_JAR` (falls gesetzt) → Programmverzeichnis → `%LOCALAPPDATA%\md-dis`. Gilt für Source *und* Frozen-Build, damit die JAR z. B. auch aus dem Quellcode heraus gefunden wird.
- **Download-Ziel** (`_jar_download_target`): Programmverzeichnis, sofern beschreibbar, sonst Benutzer-Cache (schützt Installationen unter `C:\Program Files`). Download läuft über `plantuml.jar.part` + `os.replace`, ein abgebrochener Download hinterlässt also keine kaputte JAR. Optional wird zusätzlich `plantuml.jar.sha256` geladen und der Download gegen die Prüfsumme verifiziert (fehlt die Datei oder schlägt der Abruf fehl, läuft der Download ohne Prüfung weiter).
- **Frontmatter-Info-Box:** `strip_frontmatter` trennt die YAML-Frontmatter ab, `render_frontmatter_html` stellt sie als Tabelle dar; die Auswertung macht `_parse_frontmatter_pairs` (bewusst kein vollständiger YAML-Parser). Verstanden werden `key: wert`, mehrzeilige Plain-Skalare (gefaltet mit Leerzeichen), Listen unter einem Key (`- a` → `a, …`) und **Block-Skalare** `key: >` (folded) bzw. `key: |` (literal, Zeilenumbrüche → `<br>`) inkl. Chomping- und Einrückungs-Indikator sowie Kommentar. Werte werden HTML-maskiert.
- **Wiki-Links** `[[Datei]]`, `[[Datei#Abschnitt]]`, `[[Datei|Alias]]` als `InlineProcessor` (`WikiLinkProcessor`, Priorität 170 – **unter** dem Bild-Embed 175, damit `![[bild.png]]` weiterhin als Bild gilt). Fehlt die Dateiendung, wird `.md` ergänzt; Anker laufen über `_slugify`; `handleMatch` liefert ein `etree.Element("a")`, dadurch werden Attribute escaped.

## Desktop-App
- JavaScript in der Vorschau aus (fremde `.md` können keine lokalen Dateien lesen/ausleiten).
- Inhaltsverzeichnis-Sidebar: checkbare Toolbar-Action „Verzeichnis“ (`Strg+T`), Zustand in `appearance/showToc` (`type=bool`). Umschalten speichert und rendert neu (`_reload_current`), der Zustand steckt im HTML. Default an; Help-Seite ohne Sidebar.
- Zoom über `setZoomFactor` ohne Neurendern. `zoom_level` wird deshalb in `_render_md_content` **nicht** an `markdown_to_html` durchgereicht – sonst brennt die CSS-Schriftgröße den Zoom zusätzlich hinein und die Vorschau skaliert doppelt.
- Logging: `sys.stdout/.stderr.reconfigure(line_buffering=True)` in `main()` – sonst leere Redirect-Logs.
- Banner zeigt: Wurzel, bei `--file` `Datei: X (direkte Anzeige)`, Theme, Zoom, Watch.

### PDF-Export (`Ctrl+P`)
- `PdfOptionsDialog` (7 Formate, Ausrichtung, 3 Rand-Presets) → `pdf_page_layout()` → `QWebEnginePage.printToPdf`, asynchron über `pdfPrintingFinished`.
- **Einheit zwingend mitgeben:** `QPageLayout` rechnet ohne 4. Argument in **Punkten**. Geplante „15 mm" wären sonst 15 pt ≈ 5,3 mm.
- **Ausrichtung steckt im Layout, nicht in der QPageSize:** `pageSize().size()` liefert immer 210×297. Maßgeblich ist `fullRectPoints()`.
- `_page_loaded` ist Pflicht: `_toggle_theme` rendert über `_reload_current` neu, ein `printToPdf` mitten im Laden ergäbe ein leeres PDF.
- `CSS_PRINT` (in `md_render.py`, hinter beide Themes gehängt) überschreibt im `@media print` die Palette. Achtung: das Dark-Theme setzt die Code-Farbe an `pre code`, nicht an `pre` – beide Selektoren müssen überschrieben werden, sonst bleibt der Codeblock hellgrau.
- `print-color-adjust: exact` ist nötig, sonst druckt Chromium Hintergründe nicht.

### Einstellungen (`QSettings`)
- `md-dis.ini` (IniFormat) im Verzeichnis aus `app_dir()` – bewusst neben der .exe, damit `plantuml.jar` und die Einstellungen zusammen wandern.
- Gespeichert: `appearance/darkMode`, `appearance/zoomLevel`, `appearance/showToc`, `pdf/pageSize`, `pdf/landscape`, `pdf/marginPreset`.
- Lesen **immer** mit `type=bool` / `type=float`. Bei einer von Hand editierten INI kommt der Wert als String zurück, und `bool("false")` ist `True`. Beim app-eigenen Roundtrip liefert QSettings dagegen einen echten `bool`.
- `sync()` mit `AccessError` → `_settings_persist = False`, die App läuft dann nur noch im Speicher weiter (schreibgeschützter Installationsordner).
- `_clamp_zoom` begrenzt geladene Werte auf 0,5–3,0, damit eine handgeschriebene INI die Ansicht nicht unbedienbar macht.
- `theme_action`-Beschriftung wird in `_create_toolbar` an den geladenen Dark-Mode gekoppelt, sonst bietet der Knopf nach einem Hellmodus-Start den Wechsel an, den er nicht ausführt.

## Work State (verifiziert)
- `md_render.py` existiert und ist durch `py_compile` + Rendering-Scratch-Tests (Markdown/Dark/Zoom/Frontmatter) bestätigt; `md_dis.py` baut auf dem Kern auf.
- **Inhaltsverzeichnis verifiziert am 2026-10-12:** 23 Kern-Checks (`%TEMP%\opencode\verify_toc.py`), 22 Server-Routen-Checks (`verify_toc_server.py`: Sidebar, `--no-toc`, `?toc=0/1`, Cache pro Zustand, `/raw`/Traversal/`/poll` unverändert) und 11 GUI-Checks (`verify_toc_gui.py`: Action, `Strg+T`, INI-Persistenz inkl. handgeschriebenem String-`"false"`). `toc_depth=1-3` → h4 ohne `id`, Duplikate `_1`, Anker-`href` == Heading-`id`; `[TOC]`-Marker unterdrückt die Sidebar; Print-CSS blendet `.md-toc` aus; das Gate läuft über `md.toc_tokens` (weil `md.toc` auch ohne Überschriften nicht leer ist).
- **Frontmatter-Fix verifiziert am 2026-10-15:** 26 Checks (`%TEMP%\opencode\verify_frontmatter.py`) mit der Auslöser-Datei `C:\Users\ralfj\Downloads\SKILL.md` (`description: >` / `when_to_use: >`): beide Zellen enthalten jetzt den vollen gefalteten Text, kein `>`-Rest; dazu Edge-Cases (Plain-/Quoted-/Zahlen-Skalar, leerer Wert, Kommentar, mehrzeiliger Plain-Skalar, `|`, `|-`, `>-`, `>2`, `> # Kommentar`, Liste unter Key, `:` im Wert, Stray-Einrückzeile, HTML-Escape). Regression grün: 23 TOC-, 22 Server- und 11 GUI-Checks, `py_compile` aller Module.
- **Wiki-Links, SHA256 und LRU (2026-10-18):** `[[…]]` (`WikiLinkProcessor`), optionale `.sha256`-Prüfung im JAR-Download, LRU-Server-Cache (max. 20) sowie `relative_to`-Traversal-Härtung sind committet (`dd5d4db`). Verifiziert: `py_compile` aller Module und Render-Probe (`[[andere#Abschnitt|Alias]]` → `href="andere.md#abschnitt"`, `![[bild.png]]` bleibt ein Bild).
- **Source-Mode verifiziert am 2026-09-29** nach der Lizenz- und JAR-Änderung: `py_compile` aller Module, Render-Probe (Frontmatter/Tabellen/Mermaid-SVG) und kompletter Server-Routen-Durchlauf (Index, Doc, raw, poll, watch.js, Upload-Pfad, Traversal-404, Fremd-Host-403).
- **GUI-Frozen** `dist/md-dis/` (414 MB + 28,5 MB `plantuml.jar`): **Version 1.4.3, gebaut 2026-10-15** – enthält MIT-Lizenz, JAR-Fix, PDF-Export, Einstellungen, den `baseUrl`-Fix, `![[…]]`, den `strip_frontmatter`-Fix, die Inhaltsverzeichnis-Sidebar und den Frontmatter-Block-Skalar-Fix. `warn-md-dis.txt` meldet nur optionale/conditional fehlende Module (numpy-Init, olefile, ctags, chardet …).
- **Server-Frozen** `dist/md-dis-server/` (55 MB): **Version 1.4.4, gebaut 2026-10-15**, deckungsgleich mit der Quelle. Smoke-Test am 2026-10-12 direkt aus der Exe (9/9 grün, `%TEMP%\opencode\verify_toc_frozen_server.py`): Start, `/test.md` mit Sidebar + „Verzeichnis ausblenden“, `?toc=0/1`, `/raw`.
- **Bildeinbettung `![[…]]` verifiziert am 2026-09-29:** `EmbedImageProcessor` in `md_render.py`, Priorität 175, nur `.png/.jpg/.jpeg/.gif/.svg/.webp`. 47 Checks in `%TEMP%\opencode\verify_embed_syntax.py`, echter Chromium-Durchlauf in `%TEMP%\opencode\verify_embed_real.py` (`naturalWidth=60`, `complete=true`, 1 Bild im PDF). Server geprüft: `/doc.md` liefert genau ein `<img alt="" src="pictures/diagramm.png">`, `/pictures/diagramm.png` antwortet 200 `image/png`, Traversal weiter 404.
- **Frontmatter-Block-Skalar-Bug gefunden und behoben (1.4.3):** `render_frontmatter_html` parste die Frontmatter zeilenweise (`line.strip()` + `partition(':')`). Bei YAML-Block-Skalaren (`description: >`, `when_to_use: >`) stand dann nur der Indikator `>` als Wert in der Zelle, und die eingerückten Fortsetzungszeilen (ohne eigenen Doppelpunkt) fielen komplett weg. Auslöser war `C:\Users\ralfj\Downloads\SKILL.md`. Fix: neuer Helfer `_parse_frontmatter_pairs` mit Zustandslogik über die Zeilen – erkennt `>`/`|` (mit `-`/`+`/Zahl und Kommentar), sammelt die zugehörigen Einrückzeilen (folded → Leerzeichen, literal → `<br>`) und faltet auch mehrzeilige Plain-Skalare; Listen unter einem Key werden zu `a, b`.
- **`strip_frontmatter`-Bug gefunden und behoben (1.3.0):** das Hüllen-Muster war `^```(?:markdown)?\s*\n(.*?)\n```\s*\n?(.*)`. Dadurch traf es **jeden nackten** ```-Fence am Dokumentanfang: der Code wurde als Markdown gerendert, Links und Bilder wurden lebendig, und die Folgezeile klebte an (`code# Titel`). Fix: `markdown` verpflichtend, `[^\S\n]` statt `\s`, `\n*` statt `\n?`, plus `_join_wrapped` für den Trenner zwischen Hüllen-Inhalt und Rest. Betroffen waren nur Fences **ohne** Sprachkennung an Position 0.
- **PDF-Export im eingefrorenen Build end-to-end geprüft** (2026-09-29, Kopie unter `%TEMP%\opencode\smoke\md-dis`, `plantuml.jar` danebenlegen): `Strg+P` öffnet „PDF-Optionen", Enter öffnet „Als PDF speichern", Pfad + Enter erzeugt eine gültige PDF. A4 hoch → 595×841 pt, 3 Seiten, 74.325 Bytes, 1 Bild, nur Print-Farben. Danach `md-dis.ini` mit `pageSize=A4/landscape=false/marginPreset=Normal`.
- **Persistenz-Kette im eingefrorenen Build geprüft:** INI auf `pageSize=Letter`, `landscape=true`, `marginPreset=Weit`, `darkMode=false` gesetzt, App neu gestartet → Dialog übernimmt die Vorgaben, Ergebnis **792×612 pt** (Letter quer) und Textbeginn bei x=71,2 pt bei 25 mm Rand (Soll 70,9 pt). Die Vorschau enthielt kein `#0d1117`, Hellmodus also ebenfalls übernommen.
- **Smoke-Test-Skript:** `Start-Process` + `WScript.Shell.SendKeys` funktioniert, aber der Prozess muss **im selben** PowerShell-Aufruf gestartet und bedient werden – sonst beendet das Tool ihn nach dem Aufruf.
- **PDF-Export verifiziert am 2026-09-29** (Source-Mode, echte Chromium-Exporte): Seitenmaße A4 hoch 595×841 pt, A4 quer 841×595 pt, Letter 612×792 pt; Text, Frontmatter, Tabelleninhalt extrahierbar; relatives Bild als 30×22 pt eingebettet; Codeblock-Hintergrund `#f6f8fa` wirklich gedruckt; keine Dark-Theme-Farbe im Text; Text beginnt bei x=42,8 pt innerhalb des 15-mm-Randes (42,5 pt). 297 mm ergeben 841,89 pt, Chromium rundet auf 841 ab – 1 pt Toleranz einplanen.
- **Relativer-Bild-Bug gegengeprüft:** mit `setUrl` auf `preview/` liefert `naturalWidth` `0x0`, mit `setHtml` + `baseUrl` `40x30`. Fix damit belegt.
- **QWebEngine im Test:** braucht eine vollwertige `QApplication` (kein `QCoreApplication`) und **kein** `QT_QPA_PLATFORM=offscreen` – Chromium stürzt dort mit Exit `0xC0000409` ab. Fenster via `view.show()` real anlegen.
- **Nicht möglich:** Skalierung im PDF-Export. `printToPdf` hat in PyQt6 nur `(filePath, pageLayout, ranges)`, keinen `scaleFactor`. Ausweg für breite Diagramme: Querformat.
- `_render_markdown` in `md_dis.py` war toter Code (seit dem Erstcommit `dd1a2c5` nie aufgerufen) und wurde entfernt – er hätte bei Reaktivierung doppelt skaliert. Belegt mit `git log -S`.
- Source-Mode Tests laufen über `Start-Process python … --port <n>` + `curl.exe` (Achtung: bei `RedirectStandardOutput` werden Konsol-Ausgaben nur bei line-buffering sichtbar).
- **Automatisierte Regressionstests im Repo:** `tests/` (pytest) deckt den Render-Kern (Frontmatter inkl. 1.3.0-Regression, Block-Skalare inkl. 1.4.3-Regression, Wiki-Links/Embeds, Diagramm-Extraktion, Anker-Kompatibilität) und den Server ab – Helfer (`resolve_within_root`, `_sanitize_filename`) plus HTTP-Integration gegen einen echten `MDDisServer` auf Port 0 (Index, Doc-Route, CSP ohne Fremdbilder, Fremd-Host 403, 413-Übergröße, BOM, kaputtes UTF-8). Lauf: `python -m pytest` (42 passed am 2026-10-18). Die früheren Ad-hoc-Skripte (`%TEMP%\opencode\verify_*.py`) bleiben daneben bestehen.
- **Fence-Vorabpass und Slugify behoben (2026-10-18):** `_extract_diagram_blocks` ersetzt den `re.sub`-Vorabpass (Review M1); `_slugify` nutzt jetzt `markdown.extensions.toc.slugify` (Review M3). Verifiziert per pytest: Beispiel-` ```plantuml ` in einem ` ```text `-Block wird nicht mehr extrahiert, `[[doc.md#a_b c]]` trifft exakt die Heading-`id` `a_b-c` (35 passed, vorher 1 xfailed).
- **Chromium-Test-Falle (zweite):** `loadFinished` muss **vor** `setHtml` verbunden werden, sonst geht das Signal verloren. `printToPdf` erwartet an 2. Argument ein `QPageLayout` – ein `QPageSize` an dieser Stelle stürzt hart mit `0xC0000409` ab, ebenso ein leerer stdout wegen Pufferung. Deshalb `sys.stdout.reconfigure(line_buffering=True)`.
- **Review-Nachlauf (2026-10-18):** `[TOC]` am konvertierten Inhalt (M9), Verzeichnis-URLs → 404 statt 301 auf sich selbst (M7), `processEvents` ohne Nutzereingaben (M8), `_mermaid`-Tempdateien per `try/finally` (N7), unbenutzte Imports (N1) entfernt, die Hell/Dunkel-CSS-Palette zentralisiert (N2: `_CSS_TEMPLATE` + `_CSS_PALETTE_LIGHT/_CSS_PALETTE_DARK`, Ausgabe byte-identisch zum Vorzustand). Tests: 46 passed.

## Wichtige Regeln & Fallstricke
1. **Build nur mit Windows-Python** (py launcher aus `C:\Users\…\PythonSoftwareFoundation…`), workdir = UNC-Projektordner. WSL-Python (`wsl -d Ubuntu -- python3 -m py_compile`) nur für Syntaxcheck.
2. Vor erneutem Build: Ziel-Dist nicht manuell löschen nötig (build.py macht das); bei `--clean` wird `dist/` komplett weg.
3. Frozen-EXEs starten **nie von UNC-Pfad** → immer nach lokal kopieren (z. B. `C:\Users\ralfj\AppData\Local\Temp\opencode\smoke\`).
4. **Headless-GUI-Test-Falle:** fehlt neben der Exe eine `plantuml.jar`, erscheint ein modaler Download-Dialog → nichtleere Stub-JAR anlegen (die Suche akzeptiert nur Dateien mit Inhalt, `size > 0`).
5. `--file` wird gegen **CWD** aufgelöst (nicht `--root`), `file` außerhalb von `--root` → Exit 2 (bewusst so).
6. Legt man `uploads/` auf das Root: Index listet sie; Refresh bei Upload via Watch (frische mtime).
7. Uploads überschreiben gleichnamige Dateien in `uploads/` (kein Timestamp) – gewollt für Vorschau.
8. **Keine Kommentare zu `md_dis.py` anlegen, die den Zoom- oder `baseUrl`-Pfad „korrigieren"**: beides ist Absicht, ein Durchreichen von `zoom_level` skaliert doppelt, ein Wechsel zurück auf `setUrl` zerstört relative Bilder.
9. **`strip_frontmatter` nicht wieder auf `(?:markdown)?` erweitern:** die optionale Klammer ist genau der Bug aus 1.3.0. Ein ```markdown-Block am Dokumentanfang wird immer entpackt — auch wenn er nur ein *Beispiel* für Code zeigen sollte. Das ist gewollt, aber überraschend; bei Bedarf auf "Hülle umfasst das ganze Dokument" einschränken.
10. **Frontmatter nicht wieder zeilenweise parsen:** `_parse_frontmatter_pairs` muss die Einrückung auswerten (Block-Skalar `>`/`|`, mehrzeilige Plain-Skalare, Listen). Ein Ansatz „Zeile strippen, bei `:` aufteilen" lässt genau die Fortsetzungszeilen fallen und zeigt nur den `>`-Indikator – das war der Bug aus 1.4.3.
11. **Diagramm-Fences nicht wieder per `re.sub` über den ganzen Text suchen:** Das lief auch in fremde Code-Blöcke hinein (Bug aus Review M1). Extraktion gehört in `_extract_diagram_blocks` mit Fence-Zustand.
12. **`_slugify` an die toc-Extension gekoppelt lassen:** Anker müssen exakt die Heading-`id` treffen. Eine eigene Slugify wich bei Unterstrichen ab (Review M3).
13. **Speichern mit `newline=""`, Lesen mit `utf-8-sig`:** Ohne `newline=""` stellt eine GUI-Speicherung LF auf CRLF um (Review M4); ohne `utf-8-sig` verhindert eine BOM die Frontmatter-Erkennung `^---` (Review N9). Gilt in GUI und Server.
14. **`[TOC]` erst am konvertierten Inhalt prüfen** (`<div class="toc">` im Ergebnis), nicht per `"[TOC]" in md_text`: Sonst zählt ein Beispiel in einem Code-Block fälschlich als Marker und die Sidebar verschwindet (Review M9). Verzeichnis-URLs liefern `404`, keinen `301` auf sich selbst (Review M7).
15. **`QApplication.processEvents` nur mit `ExcludeUserInputEvents`** (Helfer `_process_events` in `md_dis.py`): sonst läuft während des Renderns/Downloads ein zweiter Datei-Öffnen-Aufruf verschachtelt und die alte Anzeige gewinnt (Review M8). `_mermaid` räumt Ein-/Ausgabedatei immer per `try/finally` auf (Review N7).
16. **`_sanitize_filename` gegen Windows-Gerätenamen absichern:** `CON`, `PRN`, `NUL`, `COM1`…`LPT9` bleiben auch mit Endung (`CON.md`) Geräte und lassen sich nicht anlegen; ein führendes `_` löst das (Review N8).
17. **CSS-Palette nur an einer Stelle (`_CSS_TEMPLATE` + `_CSS_PALETTE_*`) pflegen:** Hell und Dunkel unterschieden sich nur in den Farbwerten (Review N2); `CSS_LIGHT`/`CSS_DARK` entstehen über `_css_with_palette`.
18. **Python-Version einheitlich nennen:** Der Code nutzt `X | Y`-Annotationen (3.10) und keine 3.11-exklusiven Features, also 3.10+ in README/DESIGN (Review N12).

## Bekannte Probleme
- **Doppelte Heading-ids:** Kommt eine Überschrift mehrfach vor, nummeriert die toc-Extension (`titel`, `titel_1`, …). `_slugify` kennt nur die Basis, ein `[[Datei#titel]]`-Anker trifft also den ersten Treffer. Offen; die Anker-Angleichung (Review M3) ist erledigt.

## Versionsregel
`VERSION` in `md_render.py` ist die einzige Versionsangabe und hat die Form `MAJOR.MINOR.BUILD`.
- **Major und Minor** werden **ausschließlich auf Anforderung** geändert: `python build.py --set-version 2.0`. Ein normaler Build fasst sie nie an.
- **Build** ist der dritte Teil und wird von `build.py` bei **jedem** Build automatisch um 1 erhöht – auch wenn der Build anschließend fehlschlägt (die Nummer ist dann verbraucht, damit zwei Artefakte nie dieselbe tragen).
- `--set-version` setzt die Build-Nummer auf 0 zurück, wenn sich Major oder Minor tatsächlich ändern; der folgende Build ergibt dann z. B. `2.0.1`. Wird derselbe Wert erneut angegeben, bleibt die Build-Nummer erhalten.
- Beide Build-Varianten (GUI und Server) teilen sich denselben Zähler.
- `build.py` schreibt die Version mit `newline=""` zurück, damit CRLF-Dateien unverändert bleiben.

## Umgebung / Pfade
- Projekt: `C:\Users\ralfj\Coding\md-dis` (Git-Clone); früherer Ort war `\\wsl.localhost\Ubuntu\home\ralf\Coding\md-dis`.
- Python-Umgebung: Abhängigkeiten aus `requirements.txt`; im Projekt existiert **kein** `.venv\` (globally installiertes Python 3.13 genügt).
- Smoke-Ordner und Test-Skripte (`server_test.ps1`, `frozen_test.ps1`, `ui_dump.ps1`) lagen unter `…\Temp\opencode\` der alten Umgebung und sind **nicht im Repo** – hier nicht vorhanden.
- Der veraltete Handoff `HANDOFF-md-dis.md` wurde am 2026-09-29 aus dem Repo entfernt; dieses Dokument ist der einzige Handoff.

## Lizenz
**MIT** ist verbindlich (so auch in `LICENSE` und auf GitHub erkannt). Kein GPL-2-Code mehr im Baum – der frühere 344-Zeilen-GPL-2-Block in `md_dis.py` wurde durch den MIT-Text ersetzt. Bei einer Lizenzänderung sind `LICENSE`, `md_dis.py` (`MIT_TEXT`, About-Dialog, Hilfemenü) und `README.md` gemeinsam anzupassen.

## Nächste Schritte (Vorschläge)
1. Optional: `tests/` erweitern – Server-Routen per `ThreadingHTTPServer` testen, den Fence-Vorabpass (M1) und die Slugify-Kompatibilität (M3) absichern, sobald behoben.
2. Optional: `--auth`-/Token-Schutz für Upload/Serverzugriff, wenn der Server über LAN exponiert wird – bisher nur localhost-Bindung getestet (im Banner steht die URL).
3. Optional: GUI-Client „Datei an Server senden“ (wurde von Nutzer nicht gewählt; Browser-Upload stattdessen).
6. Optional: Icon/Logo prüfen, deutsche README.

## Suggested Skills
- `tdd` (wenn Schritt 1 umgesetzt wird – Red-Green-Refactor passend für die HTTP-Routen).
- `grill-with-docs` für die nächste Design-Entscheidung (z. B. Auth, Projektstruktur), um die ADR/Doku-Disziplin zu etablieren.
- `handoff` erneut aufrufen, wenn eine lange Sitzung erneut abgeschlossen wird.