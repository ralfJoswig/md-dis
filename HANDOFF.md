# Handoff – md-dis

Stand: 2026-09-20 (letzte Sitzung abgeschlossen: Browser-Upload + `--file`-Redirect)

## Projekt
`md-dis` = Windows-Markdown-Viewer (PyQt6/QWebEngine, Dark-Mode, Zoom, Watch, PlantUML/Mermaid)
mit **zwei Build-Varianten**:
- **GUI-Client** (`md-dis`): Desktop-App zum lokalen Anzeigen/Editieren von `.md`.
- **Server** (`md-dis-server`): headless HTTP-Server, rendert identisch per HTTP (stdlib-only, ohne Qt).

Konvention: App-Sprache und sämtliche Meldungen sind **Deutsch**.

## Architektur / Dateien (Projektwurzel `C:\SAP\ClaudeCode\Coding\md-dis`, Git-Repo `github.com/ralfJoswig/md-dis`)
| Datei | Rolle |
|---|---|
| `md_render.py` | **Qt-freier gemeinsamer Render-Kern** (VERSION="1.1.0", HTML_TEMPLATE, CSS_LIGHT/DARK, `markdown_to_html`, PlantUML/Mermaid-Finder+Renderer, Frontmatter). Importiert KEIN Qt. |
| `md_dis.py` | GUI-Client (ca. 47 KB / 1114 Zeilen); importiert nur noch `VERSION, get_plantuml_jar_path, get_base_dir, check_java_available, download_plantuml_jar, find_mmdc, markdown_to_html` aus `md_render`. |
| `md_dis_server.py` | HTTP-Server (ca. 18 KB / ~490 Zeilen, `http.server.ThreadingHTTPServer`). |
| `build.py` | PyInstaller: `python build.py` → GUI, `python build.py --server` → Server, `--clean` löscht build/dist/Specs. Entfernt vor jedem Build das jeweilige Ziel-Dist (verhindert „not empty“-Fehler). |
| `plantuml.jar` | echtes JAR (29,7 MB) im Projektwurzel – wird von Source-Aufrufen + Frozen-Exe (Ordner der Exe) genutzt. |

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

## Desktop-App
- JavaScript in der Vorschau aus (fremde `.md` können keine lokalen Dateien lesen/ausleiten).
- Zoom über `setZoomFactor` ohne Neurendern.
- Logging: `sys.stdout/.stderr.reconfigure(line_buffering=True)` in `main()` – sonst leere Redirect-Logs.
- Banner zeigt: Wurzel, bei `--file` `Datei: X (direkte Anzeige)`, Theme, Zoom, Watch.

## Work State (verifiziert)
- `md_render.py` existiert und ist durch `py_compile` + Rendering-Scratch-Tests (Markdown/Dark/Zoom/Frontmatter) bestätigt; `md_dis.py` baut auf dem Kern auf.
- **GUI-Frozen** `dist/md-dis/` (417 MB): Regression geprüft (Fenstertitel `md-dis - einfach.md`, Status `Geladen: einfach.md`, WebEngine aktiv, Preview-Datei `preview\.md-dis-preview.html` im Programmordner, Dark-Theme). **Nicht neu gebaut** – `md_dis.py` unverändert seit damaligem Build.
- **Server-Frozen** `dist/md-dis-server/` (84 MB): **aktuellster Build** – enthält `--file`-Redirect UND Browser-Upload; per HTTP verifiziert (Upload 303+Render 200, PlantUML→SVG mit echtem JAR, Dark, Traversal-404, Watch/Poll, raw).
  - Hinweis: Wechsel 55→84 MB durch erneuten COLLECT/Analysis-Lauf; unkritisch.
- Source-Mode Tests laufen über `Start-Process python … --port <n>` + `curl.exe` (Achtung: bei `RedirectStandardOutput` werden Konsol-Ausgaben nur bei line-buffering sichtbar).
- Kein automatisches Test-Framework – Verifikation manuell über Skripte im Smoke-Ordner.

## Wichtige Regeln & Fallstricke
1. **Build nur mit Windows-Python** (py launcher aus `C:\Users\…\PythonSoftwareFoundation…`), workdir = UNC-Projektordner. WSL-Python (`wsl -d Ubuntu -- python3 -m py_compile`) nur für Syntaxcheck.
2. Vor erneutem Build: Ziel-Dist nicht manuell löschen nötig (build.py macht das); bei `--clean` wird `dist/` komplett weg.
3. Frozen-EXEs starten **nie von UNC-Pfad** → immer nach lokal kopieren (z. B. `C:\Users\ralfj\AppData\Local\Temp\opencode\smoke\`).
4. **Headless-GUI-Test-Falle:** fehlt neben der Exe eine `plantuml.jar`, erscheint ein modaler Download-Dialog → Stub-JAR anlegen, wenn GUI ohne echte Diagramme getestet wird.
5. `--file` wird gegen **CWD** aufgelöst (nicht `--root`), `file` außerhalb von `--root` → Exit 2 (bewusst so).
6. Legt man `uploads/` auf das Root: Index listet sie; Refresh bei Upload via Watch (frische mtime).
7. Uploads überschreiben gleichnamige Dateien in `uploads/` (kein Timestamp) – gewollt für Vorschau.

## Umgebung / Pfade
- Projekt: `C:\SAP\ClaudeCode\Coding\md-dis` (Git-Clone); früherer Ort war `\\wsl.localhost\Ubuntu\home\ralf\Coding\md-dis`.
- Python-Umgebung: `.venv\` im Projekt (`.\.venv\Scripts\python.exe`), Abhängigkeiten aus `requirements.txt`.
- Smoke-Ordner und Test-Skripte (`server_test.ps1`, `frozen_test.ps1`, `ui_dump.ps1`) lagen unter `…\Temp\opencode\` der alten Umgebung und sind **nicht im Repo** – hier nicht vorhanden.
- Alter/veralteter Handoff: `HANDOFF-md-dis.md` → **dieses Dokument ersetzt ihn.**

## Nächste Schritte (Vorschläge)
1. Optional: automatisierten Regressionstest als Skript (Start-Server → curl-Checks → Upload → Watch) ins Repo legen.
2. Optional: `--auth`-/Token-Schutz für Upload/Serverzugriff, wenn der Server über LAN exponiert wird – bisher nur localhost-Bindung getestet (im Banner steht die URL).
3. Optional: GUI-Client „Datei an Server senden“ (wurde von Nutzer nicht gewählt; Browser-Upload stattdessen).
4. Optional: Icon/Logo prüfen, deutsche README.

## Suggested Skills
- `tdd` (wenn Schritt 1 umgesetzt wird – Red-Green-Refactor passend für die HTTP-Routen).
- `grill-with-docs` für die nächste Design-Entscheidung (z. B. Auth, Projektstruktur), um die ADR/Doku-Disziplin zu etablieren.
- `handoff` erneut aufrufen, wenn eine lange Sitzung erneut abgeschlossen wird.