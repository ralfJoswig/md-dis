# Handoff: md-dis (Markdown-Viewer)

Stand: 27.08.2026. Alle von der vorherigen Session beauftragten Aufgaben sind **fertig und verifiziert**. Kein offener Blocker.

## Ziel / Kontext
- Nutzer arbeitet am Windows-Markdown-Viewer **md-dis** (PyQt6 + QWebEngineView), gebaut mit PyInstaller (one-dir).
- Projektpfad (WSL): `/home/ralf/Coding/md-dis` = Windows-UNC: `\\wsl.localhost\Ubuntu\home\ralf\Coding\md-dis`
- Hierarchie: Hauptdatei `md_dis.py`, Build-Skript `build.py`, fertiger Build in `dist/md-dis/`.
- Kommende Session könnte: `plantuml.jar`-Download abschließen, UI/UX verfeinern, Feature-Arbeit. Keine Aufgabe ist fest zugesagt.

## Umgebung (wichtig, Build-Fallstricke!)
- **Build MUSS mit Windows-Python laufen**, nicht WSL-Python (WSL `python3` hat kein pip/PyInstaller).
  - Windows-Python: `C:\Users\ralfj\AppData\Local\Microsoft\WindowsApps\python.exe` (Python 3.13.14, PyInstaller 6.22.2, PyQt6 6.11.0, PyQt6-WebEngine 6.11.0, Markdown 3.10.3, pip 25.3)
  - Build-Befehl (PowerShell, `workdir` = UNC-Pfad): `python.exe build.py`
- **Vor jedem Build muss `dist` geleert werden**, sonst PyInstaller-COLLECT-Fehler:
  `wsl -d Ubuntu -- bash -lc 'cd /home/ralf/Coding/md-dis; python3 -m py_compile md_dis.py; rm -rf dist'`
  (Syntax-Check direkt mit `wsl -d Ubuntu -- bash -lc '...'`; `;`/`&&` nur INNERHALB der `bash -lc`-Kette verwenden, nicht im PowerShell-Teil!)
- **EXE von UNC-Pfad startet nicht** (`\\wsl.localhost\...`) → für Tests nach lokal kopieren, z. B. nach `C:\Users\ralfj\AppData\Local\Temp\opencode\smoke\md-dis\md-dis.exe`.
- Beim Headless-Testen erscheint der modale **PlantUML-Dialog** (fehlende `plantuml.jar`) und blockiert den Test → zum Testen leere Stub-Datei `plantuml.jar` neben der EXE anlegen (verhindert den Dialog).
- PowerShell/WSL-Quoting ist fehleranfällig; komplexe Diagnose-Sequenzen als Skripte nach `C:\Users\ralfj\AppData\Local\Temp\opencode\` schreiben und ausführen.

## Erledigtes (Verzeichnis der Änderungen)
### 1. Drag&Drop-Fix
- `eventFilter` prüft nicht mehr `obj is self`; stattdessen `QApplication.instance().installEventFilter(self)` in `__init__` (md_dis.py, `eventFilter`-Methode). Drops erreichen die App auch bei sichtbarer WebView.

### 2. Edit-Modus
- Toolbar: **Speichern** (Ctrl+S → `_save_file`), **Bearbeiten/Anzeigen** (F2 → `_toggle_edit_mode`).
- Editor: `QPlainTextEdit` in `_ensure_editor`; Dirty-Tracking via `_on_editor_changed` + `_editor_suppress_change`; Verwerfen-Bestätigung `_confirm_discard`; `closeEvent` mit Dirty-Guard.
- `_load_file` refaktoriert: extrahierte `_render_md_content(md_text)`; Dirty-Guard in `_load_file` und `_reload_current`.

### 3. Absturz-Fix (Wechsel zurück in Vorschau)
- Ursache: `setCentralWidget`-Reparenting. Behoben: permanentes zentrales `QStackedWidget` (`self.stack`) hält `welcome_label`, `web_view`, `editor`; es wird nur `setCurrentWidget(...)` aufgerufen, kein Child-Re-Parenting.

### 4. Qt-Modul-Pruning (build.py `prune_dist()`)
- Gehalten (KEEP_QT_BIN): `Core, Gui, Widgets, Network, WebChannel, WebEngineCore, WebEngineWidgets, Quick, Qml, Positioning, PrintSupport, QuickWidgets, OpenGL, QmlModels, QmlMeta, QmlWorkerScript`, `QtWebEngineProcess.exe`, `opengl32sw.dll`, `qt.conf`, `MSVCP140*`/`VCRUNTIME140*`.
- KEEP_QML = `{QtQuick, QtQml}`; KEEP_IMAGEFORMATS = `{qico, qjpeg, qgif}`; DROP_QPLUGIN_DIRS = `{generic, position, iconengines}`; DROP_QPLATFORMS = `{qminimal, qoffscreen}`; entfernt `*.debug.pak`.
- Einsparung: **~549 MB → 414 MB** gesamt, `_internal` 541→409 MB; `Qt6\bin` nur noch 24 Dateien.
- Begründung (objdump-verifiziert): `Qt6WebEngineCore.dll` verlinkt fest `Qt6Quick`, `Qt6Qml`, `Qt6Positioning`, `Qt6WebChannel` → diese bleiben. Quick3D, ShaderTools, Multimedia, Pdf, Svg, QuickControls u. ä. sind Hook-Beimischung und werden entfernt.

### 5. Diagnose + Verifikation
- Symptom „Frozen-Build lädt keine Datei“ wurde **als Fehlalarm geklärt**: während `_load_file` ruft `QApplication.processEvents()` auf; dadurch feuert der geplante 0-ms-Timer von `_check_plantuml`, der bei fehlender `plantuml.jar` (und vorhandenem Java) den modalen `QMessageBox.question`-Dialog zeigt → blockierte nur den Headless-Test, kein App-Bug.
- Bekanntes UX-Problem (vorbestehend, nicht im Auftrag): `_check_plantuml` kann den Datei-Load via Dialog unterbrechen. Lösungsidee für später: Download/Output in Thread verlagern oder Dialog async/unterdrücken.
- Kurzzeitige Debug-Instrumentierung (`_dbg`, gesteuert via Env `MD_DIS_DEBUG`, schrieb `debug.log`) wurde **vollständig wieder entfernt** (Grep auf `_dbg` = 0 Treffer). Finaler sauberer Build wurde danach neu gebaut.
- **Final-Smoke-Test (geprüfter Zustand):** lokale Kopie der EXE + `einfach.md` → `PREVIEW-OK ~6s`, Prozess lebt, Fenstertitel `md-dis - einfach.md`, WebEngine-Prozess startet. Grün.

## Test-Setup & Helfer (C:\Users\ralfj\AppData\Local\Temp\opencode\)
- `smoke\` – Smoke-Umgebung: `smoke\md-dis\md-dis.exe` (Kopie von `dist\md-dis`), `smoke\einfach.md` (einfaches Markdown), Vorschau wird als `.md-dis-preview.html` erzeugt.
- `probe.py`, `runner.py`, `detached_runner.py`, `detached2.py` – Quellcode-Läufer (offscreen/interaktiv/detached mit `QTWEBENGINE_CHROMIUM_FLAGS=--no-sandbox` + gepatchtem `QMessageBox.question`→No).
- `check_deps.sh`, `check_deps2.sh`, `check_py.sh` – Toolchain-/Abhängigkeitschecks.

## Nächste Schritte (Empfehlung)
1. `plantuml.jar`-Autodownload abschließen/testen (Code-Sequenz existiert in `md_dis.py` `_check_plantuml`; Download von `https://plantuml.com/plantuml.jar`). Test mit echtem Netz + Java.
2. Optional: PlantUML-Dialog aus dem Load-Pfad lösen (async), damit Datei-Loads nie am Dialog hängen.
3. Neuer Build-Weg bei weiteren Änderungen ist Pflicht: feines `rm -rf dist`, dann `python.exe build.py` (workdir UNC), danach Smoke-Test wie oben.

## Suggested Skills
- **grill-with-docs** – Plan gegen bestehenden Code prüfen lassen, bevor du `_check_plantuml` o. ä. umbaust (Terminologie/Entscheidungen in ADRs eintragen).
- **tdd** – Wenn neue Features/Regressionstests (z. B. PlantUML-Download, Edit-Speichern) test-first sollen.
- **caveman** – Falls der Nutzer für Follow-up-Chats Token sparen will („caveman mode“, „be brief“).