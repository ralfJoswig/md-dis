# Handoff – md-dis

Stand: 2026-09-29 (letzte Sitzung: Lizenz auf MIT vereinheitlicht, plantuml.jar-Suche über mehrere Orte, Doku bereinigt)

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
- Optionen: `--host` (127.0.0.1), `--port` (8080), `--root`, `--dark`, `--zoom`, `--watch`; optionales **Positionsargument `file`**.
- Routen:
  - `GET /` → Index-Liste aller `.md/.markdown` unter `--root`; bei `--file` → **302** auf `/<datei>`.
  - `GET /<pfad>.md` → gerendertes HTML (Toolbar: Index/Link je nach Redirect + „Hochladen“ + „Rohdaten“; Watch-Skript bei `--watch`).
  - `GET /raw/<pfad>` (`text/plain`), `GET /poll?path=` (mtime_ns-Stempel), statische Dateien (mimetypes).
  - **Upload (neu):** `GET /upload` → Formular; `POST /upload` (multipart/form-data, stdlib-only-Parser, kein `cgi` – in Py3.13 entfernt) → speichert unter `<Root>/uploads/<bereinigter Name>`, 303-Redirect auf Anzeige. Schutz: nur `.md/.markdown` (sonst 400), Dateiname gesäubert (Postfix `_sanitize_filename`), 10-MB-Limit (413), `resolve_within_root` blockiert Traversal.
- Cache in-memory, ein Eintrag pro Datei (abspath → (mtime_ns, html)), wird bei Änderung überschrieben. 500-Handler loggt Traceback.
- Sicherheit: alle Antworten mit `Content-Security-Policy` (`script-src 'self'`) + `nosniff`; Watch-Skript kommt extern über `GET /watch.js` (Pfad per `data-path`). Frontmatter, Diagramm-Fehlerausgaben und Index-Dateinamen werden HTML-maskiert. Rohes HTML im Markdown bleibt erlaubt, Skripte darin blockiert die CSP.
- Ausgeliefert werden nur Markdown und Bilder (png/jpg/jpeg/gif/svg/webp); `/raw/` nur für Markdown. Pfade mit Dot-Segment (`.git`, `.venv`, `.env`) → 404, Index überspringt sie.
- Bei Loopback-Bindung nur `Host: localhost|127.0.0.1|[::1]:<port>` (DNS-Rebinding) → sonst 403; `POST` mit fremdem `Origin` → 403 (CSRF). 500 ohne Details an den Client.
- PlantUML rendert im Server mit `-DPLANTUML_SECURITY_PROFILE=SANDBOX` (`markdown_to_html(..., sandbox=True)`), kein `!include` lokaler Dateien.

## Render-Kern (`md_render.py`)
- SVG-Cache (max. 256, Schlüssel art/sandbox/code, thread-safe) – Theme-Wechsel, F5, Bearbeiten→Anzeigen rendern Diagramme nicht neu.
- PlantUML: alle Blöcke eines Dokuments in **einem** JVM-Aufruf (`-charset UTF-8`); Mermaid: bis zu 4 `mmdc` parallel.
- Auto-Download von `plantuml.jar` höchstens einmal pro Prozess; `find_java`/`find_mmdc` merken Treffer.
- **`plantuml.jar`-Suche** (`get_jar_search_dirs`, Reihenfolge = Priorität): `MD_DIS_PLANTUML_JAR` (falls gesetzt) → Programmverzeichnis → `%LOCALAPPDATA%\md-dis`. Gilt für Source *und* Frozen-Build, damit die JAR z. B. auch aus dem Quellcode heraus gefunden wird.
- **Download-Ziel** (`_jar_download_target`): Programmverzeichnis, sofern beschreibbar, sonst Benutzer-Cache (schützt Installationen unter `C:\Program Files`). Download läuft über `plantuml.jar.part` + `os.replace`, ein abgebrochener Download hinterlässt also keine kaputte JAR.

## Desktop-App
- JavaScript in der Vorschau aus (fremde `.md` können keine lokalen Dateien lesen/ausleiten).
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
- `md-dis.ini` (IniFormat) im Verzeichnis aus `app_dir()` – bewusst neben der .exe, damit `preview/`, `plantuml.jar` und die Einstellungen zusammen wandern.
- Gespeichert: `appearance/darkMode`, `appearance/zoomLevel`, `pdf/pageSize`, `pdf/landscape`, `pdf/marginPreset`.
- Lesen **immer** mit `type=bool` / `type=float`. Bei einer von Hand editierten INI kommt der Wert als String zurück, und `bool("false")` ist `True`. Beim app-eigenen Roundtrip liefert QSettings dagegen einen echten `bool`.
- `sync()` mit `AccessError` → `_settings_persist = False`, die App läuft dann nur noch im Speicher weiter (schreibgeschützter Installationsordner).
- `_clamp_zoom` begrenzt geladene Werte auf 0,5–3,0, damit eine handgeschriebene INI die Ansicht nicht unbedienbar macht.
- `theme_action`-Beschriftung wird in `_create_toolbar` an den geladenen Dark-Mode gekoppelt, sonst bietet der Knopf nach einem Hellmodus-Start den Wechsel an, den er nicht ausführt.

## Work State (verifiziert)
- `md_render.py` existiert und ist durch `py_compile` + Rendering-Scratch-Tests (Markdown/Dark/Zoom/Frontmatter) bestätigt; `md_dis.py` baut auf dem Kern auf.
- **Source-Mode verifiziert am 2026-09-29** nach der Lizenz- und JAR-Änderung: `py_compile` aller Module, Render-Probe (Frontmatter/Tabellen/Mermaid-SVG) und kompletter Server-Routen-Durchlauf (Index, Doc, raw, poll, watch.js, Upload-Pfad, Traversal-404, Fremd-Host-403).
- **GUI-Frozen** `dist/md-dis/` (414 MB): **aktuell, Version 1.2.1**, gebaut am 2026-09-29. Enthält MIT-Lizenz, JAR-Fix, PDF-Export, Einstellungen und den `baseUrl`-Fix. `warn-md-dis.txt` meldet 0 fehlende PyQt6-Module.
- **Server-Frozen** `dist/md-dis-server/` (55 MB): **weiter veraltet** – kein MIT-/JAR-Fix, kein PDF (bewusst GUI-only). `--file`-Redirect und Browser-Upload waren im letzten Build enthalten. Nächster Server-Build würde 1.2.2 ergeben.
- **PDF-Export im eingefrorenen Build end-to-end geprüft** (2026-09-29, Kopie unter `%TEMP%\opencode\smoke\md-dis`, `plantuml.jar` danebenlegen): `Strg+P` öffnet „PDF-Optionen", Enter öffnet „Als PDF speichern", Pfad + Enter erzeugt eine gültige PDF. A4 hoch → 595×841 pt, 3 Seiten, 74.325 Bytes, 1 Bild, nur Print-Farben. Danach `md-dis.ini` mit `pageSize=A4/landscape=false/marginPreset=Normal`.
- **Persistenz-Kette im eingefrorenen Build geprüft:** INI auf `pageSize=Letter`, `landscape=true`, `marginPreset=Weit`, `darkMode=false` gesetzt, App neu gestartet → Dialog übernimmt die Vorgaben, Ergebnis **792×612 pt** (Letter quer) und Textbeginn bei x=71,2 pt bei 25 mm Rand (Soll 70,9 pt). Die Vorschau enthielt kein `#0d1117`, Hellmodus also ebenfalls übernommen.
- **Smoke-Test-Skript:** `Start-Process` + `WScript.Shell.SendKeys` funktioniert, aber der Prozess muss **im selben** PowerShell-Aufruf gestartet und bedient werden – sonst beendet das Tool ihn nach dem Aufruf.
- **PDF-Export verifiziert am 2026-09-29** (Source-Mode, echte Chromium-Exporte): Seitenmaße A4 hoch 595×841 pt, A4 quer 841×595 pt, Letter 612×792 pt; Text, Frontmatter, Tabelleninhalt extrahierbar; relatives Bild als 30×22 pt eingebettet; Codeblock-Hintergrund `#f6f8fa` wirklich gedruckt; keine Dark-Theme-Farbe im Text; Text beginnt bei x=42,8 pt innerhalb des 15-mm-Randes (42,5 pt). 297 mm ergeben 841,89 pt, Chromium rundet auf 841 ab – 1 pt Toleranz einplanen.
- **Relativer-Bild-Bug gegengeprüft:** mit `setUrl` auf `preview/` liefert `naturalWidth` `0x0`, mit `setHtml` + `baseUrl` `40x30`. Fix damit belegt.
- **QWebEngine im Test:** braucht eine vollwertige `QApplication` (kein `QCoreApplication`) und **kein** `QT_QPA_PLATFORM=offscreen` – Chromium stürzt dort mit Exit `0xC0000409` ab. Fenster via `view.show()` real anlegen.
- **Nicht möglich:** Skalierung im PDF-Export. `printToPdf` hat in PyQt6 nur `(filePath, pageLayout, ranges)`, keinen `scaleFactor`. Ausweg für breite Diagramme: Querformat.
- `_render_markdown` in `md_dis.py` war toter Code (seit dem Erstcommit `dd1a2c5` nie aufgerufen) und wurde entfernt – er hätte bei Reaktivierung doppelt skaliert. Belegt mit `git log -S`.
- Source-Mode Tests laufen über `Start-Process python … --port <n>` + `curl.exe` (Achtung: bei `RedirectStandardOutput` werden Konsol-Ausgaben nur bei line-buffering sichtbar).
- Kein automatisches Test-Framework – Verifikation manuell über Skripte im Smoke-Ordner.

## Wichtige Regeln & Fallstricke
1. **Build nur mit Windows-Python** (py launcher aus `C:\Users\…\PythonSoftwareFoundation…`), workdir = UNC-Projektordner. WSL-Python (`wsl -d Ubuntu -- python3 -m py_compile`) nur für Syntaxcheck.
2. Vor erneutem Build: Ziel-Dist nicht manuell löschen nötig (build.py macht das); bei `--clean` wird `dist/` komplett weg.
3. Frozen-EXEs starten **nie von UNC-Pfad** → immer nach lokal kopieren (z. B. `C:\Users\ralfj\AppData\Local\Temp\opencode\smoke\`).
4. **Headless-GUI-Test-Falle:** fehlt neben der Exe eine `plantuml.jar`, erscheint ein modaler Download-Dialog → nichtleere Stub-JAR anlegen (die Suche akzeptiert nur Dateien mit Inhalt, `size > 0`).
5. `--file` wird gegen **CWD** aufgelöst (nicht `--root`), `file` außerhalb von `--root` → Exit 2 (bewusst so).
6. Legt man `uploads/` auf das Root: Index listet sie; Refresh bei Upload via Watch (frische mtime).
7. Uploads überschreiben gleichnamige Dateien in `uploads/` (kein Timestamp) – gewollt für Vorschau.
8. **Keine Kommentare zu `md_dis.py` anlegen, die den Zoom- oder `baseUrl`-Pfad „korrigieren"**: beides ist Absicht, ein Durchreichen von `zoom_level` skaliert doppelt, ein Wechsel zurück auf `setUrl` zerstört relative Bilder.

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
1. Optional: automatisierten Regressionstest als Skript (Start-Server → curl-Checks → Upload → Watch) ins Repo legen.
2. Optional: `--auth`-/Token-Schutz für Upload/Serverzugriff, wenn der Server über LAN exponiert wird – bisher nur localhost-Bindung getestet (im Banner steht die URL).
3. Optional: GUI-Client „Datei an Server senden“ (wurde von Nutzer nicht gewählt; Browser-Upload stattdessen).
4. Optional: Icon/Logo prüfen, deutsche README.

## Suggested Skills
- `tdd` (wenn Schritt 1 umgesetzt wird – Red-Green-Refactor passend für die HTTP-Routen).
- `grill-with-docs` für die nächste Design-Entscheidung (z. B. Auth, Projektstruktur), um die ADR/Doku-Disziplin zu etablieren.
- `handoff` erneut aufrufen, wenn eine lange Sitzung erneut abgeschlossen wird.