# TODO – md-dis: Start beschleunigen

Erstellt: 2026-10-18 (Analyse-Sitzung, Plan-Modus)
Quellstand im Baum: `VERSION = "1.4.6"` (frozen: GUI 1.4.5, Server 1.4.6)
Projektsprache: **Deutsch** – Code, Kommentare, Commit-Nachrichten, Doku auf Deutsch.

Dieses Dokument ist die Arbeitsliste für die nächste Agenten-Sitzung. Reihenfolge der
Aufgaben = Abhängigkeiten (A und B zuerst, weil sie den Start beider Varianten betreffen;
C/D bauen auf dem Build-Skript auf; E/F betreffen die GUI; G den Server).

---

## 0. Ausgangslage (Messwerte dieser Sitzung)

Gemessen auf dieser Maschine, Windows, warm geladener Dateicache, jeweils 3 Läufe.

| Messung | Ergebnis |
|---|---|
| `dist/md-dis/md-dis.exe` → Fenster sichtbar (`MainWindowHandle != 0`) | **777 / 904 / 1085 ms** |
| `dist/md-dis-server.exe` → Banner/Port bereit | **492 / 515 / 763 ms** |
| Quellcode-GUI bis Fenster (Phasenmessung, ohne Interpreterstart) | 659 ms |
| PyInstaller-Aufschlag (frozen `--help` 336 ms vs. Source `--help` 303 ms) | ~30 ms |
| `python -c pass` inkl. Prozessstart (nur Referenz) | ~197 ms |

Phasen der Quellcode-GUI (Wiederholungsmessung möglich, siehe Abschnitt „Nachweis"):

| Phase | Zeit |
|---|---|
| `import PyQt6.QtWidgets` | 43 ms |
| `import PyQt6.QtWebEngineWidgets` (+ QtWebEngineCore) | 25 ms |
| `import md_render` | 99–130 ms |
| `QApplication()` | 22 ms |
| `MarkdownViewer()` | **389 ms** (davon Qt-Erstinit: `statusBar()` 175–238 ms, `addToolBar` 17 ms) |
| `show()` | 55–80 ms |
| `_ensure_web_view()` + erster `setHtml` → `loadFinished` | 114 + 175 ms (danach 30 ms) |

Importkosten in `md_render.py` (Einzelmessung, gleicher Prozess):
`urllib.request` **42 ms** (zieht `http.client` 31 ms, `email.*` 13 ms, `ssl`, `socket`),
`markdown` 21 ms, `html` 16 ms, `re` 13 ms, `subprocess` 5–7 ms, `shutil` 6–7 ms,
`concurrent.futures` 2–8 ms, `hashlib` 5 ms.

Weitere Einzelmessungen:
- `check_java_available()` (startet `java -version` als Subprozess): **148 ms**
- erstes Rendern mit Codeblock (lädt `pygments.lexers`): 91 ms, danach 1 ms
- `README.md` erstes Rendern im Prozess: **339 ms**, Lauf 2/3: ~50 ms
- Editor befüllen (`_set_editor_text`): 13 ms bei 152 KB, 77 ms bei 771 KB
- Bundle: 442,4 MB / 1035 Dateien; davon PyQt6 358,4 MB / 967 Dateien;
  **ungenutzt**: `numpy` 6,6 MB + `numpy.libs` **19,9 MB**, `PIL` 4,9 MB,
  `psutil`, `setuptools`, `charset_normalizer` (~31 MB, ~30 Dateien)
- UPX ist auf dieser Maschine **nicht installiert** → `upx=True` in `md-dis.spec` ist wirkungslos

**Kernbefund:** Der Start ist von der Qt-Widget-Erstinitialisierung dominiert, nicht von
unserem Code. Die realen Hebel sind klein (~70 ms Importzeit), der größte spürbare Gewinn
ist der Splash-Screen (wahrgenommene ~0,5–0,8 s).

---

## Aufgaben

### A – `md_render.py`: schwere Importe verzögern (~45 ms, GUI + Server) — risikolos
**ERLEDIGT am 2026-10-19.** `md_render.py`: `import hashlib` und `import urllib.request` aus dem
Modulkopf entfernt und in `download_plantuml_jar()` **hinter** den Frühabbruch gesetzt (liegt die
JAR vor, wird nichts davon geladen); `from concurrent.futures import ThreadPoolExecutor,
as_completed` in den Mermaid-Zweig von `markdown_to_html` verschoben. `shutil` bleibt oben.
Begründende Kommentare an allen drei Stellen ergänzt.
- [x] Grep abgesichert: alle drei Module werden nur an den erwarteten Stellen genutzt.
- [x] Importe verschoben (JAR-Download bzw. Mermaid-Zweig).
- [x] `python -m pytest` → **47 passed**; `py_compile` aller drei Module ok.
- [x] Nachweis Importzeit: `md_render` cumulative **120,7 / 127,9 ms → 95,5 / 85,9 ms**;
      Kosten der entfernten Importe in-process gemessen **40–58 ms** (3 Läufe).
- [x] Funktionsnachweis Download ohne JAR (gemocktes `urllib.request`): Erfolgsfall schreibt die
      JAR korrekt, SHA-Mismatch liefert `False` und hinterlässt weder JAR noch `.part`-Reste.
- [x] Nachweis „Normalfall ohne Kosten": bei vorhandener JAR ist `urllib.request`/`hashlib`
      nach dem Aufruf **nicht** in `sys.modules`.
- [x] Mermaid-Zweig mit gefaktem Renderer geprüft (SVG landet im HTML, lokaler Import greift).

### B – `md_dis.py`: `QtWebEngineWidgets` erst bei Bedarf (~25 ms) — erledigt
Wichtig: `class ExternalLinkPage(QWebEnginePage)` (Z. 267) braucht `QWebEnginePage` **beim
Modulimport**. Die Verzögerung ist deshalb nur mit einer Strukturänderung möglich.
- [x] In `main()` **vor** `QApplication(sys.argv)`:
      `QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)`.
      (Nötig, weil PyQt6 das WebEngine-Modul sonst vor der QApplication erwartet –
      Fehlermeldung: „QtWebEngineWidgets must be imported or Qt.AA_ShareOpenGLContexts must be
      set before a QCoreApplication instance is created".)
- [x] Top-Level-Importe `PyQt6.QtWebEngineWidgets` / `PyQt6.QtWebEngineCore` entfernt; das
      Modulkopf-Kommentar dokumentiert beide Fallen (AA_ShareOpenGLContexts, argv).
- [x] `ExternalLinkPage` verlagert – statt lokaler Definition im Methodenkörper eine gecachte
      Fabrik `external_link_page_class()`: Die Klassendefinition steht jetzt innerhalb der
      Funktion und wird beim ersten Aufruf ausgeführt. Grund für die Fabrik statt Definition
      in `_ensure_web_view`: sauberere Trennung, nur einmalige Definition, und `_ensure_web_view`
      bleibt auf „Ansicht anlegen" beschränkt.
- [x] In `_ensure_web_view()` die benötigten Klassen importiert (`QWebEngineView`,
      `QWebEngineSettings`). **Zusatzfund:** `_search_prev` (Z. 647) nutzt
      `QWebEnginePage.FindFlag` – dort ebenfalls lokaler Import.
- [x] **Nachweis (Pflicht):** Quellmodus-Test bestanden (15 Prüfungen, 0 Fehler) – WebEngine
      beim Start nicht in `sys.modules`, Import erst beim ersten Dokument, Bild-Embed im DOM,
      Codeblock mit Highlighting, Anker `id="abschnitt"`, Zoom, Suche vor/zurück,
      PDF-Export (38 kB), Theme-Wechsel rendert neu.
- [x] Risiko gegengeprüft: echter App-Start `python md_dis.py probe.md` → Titel
      „md-dis – probe.md" nach 1247 ms, kein Absturz.
- [x] **Zweite Falle dokumentiert:** Chromium baut seine Kommandozeile aus
      `QCoreApplication::arguments()`; eine `QApplication([])` ohne argv lässt den späten
      WebEngine-Start mit `0xC0000409` abstürzen. `main()` übergibt `sys.argv` → im Betrieb
      unkritisch, in Tests aber argv mitgeben.
- [x] Kosten-Nachweis: WebEngine-Import kalt **26–27 ms** (3 Läufe, stabil); `import md_dis`
      enthält danach kein `QtWebEngineWidgets` mehr (per `sys.modules`/`importtime` geprüft).
- [x] `pytest`: 47 passed; `py_compile md_dis.py` ok.

### C – Splash-Screen (wahrgenommen ~0,5–0,8 s)
- [x] `build.py`, GUI-Zweig: `--splash icon.png` ergänzt (nur wenn die Datei existiert;
      `icon.png` ist 256×256, 8 Bit RGBA – PyInstaller akzeptiert das, Transparenz wird
      unterstützt).
- [x] `md_dis.py`: `_close_splash()` ruft `pyi_splash.close()` auf, Import in
      `try/except ImportError` (im Quellmodus existiert das Modul nicht). Aufruf in `main()`
      nach `window.show()` + `app.processEvents()` – erst wenn das Hauptfenster gezeichnet ist,
      sonst blitzt der Desktop kurz auf.
- [x] Nur GUI, nicht Server (Konsole).
- [ ] Nach dem Build prüfen: Bundle-Größe (Tcl/Tk ~3 MB zusätzlich) und ob der Splash beim
      Start wirklich früh erscheint (Messung wie in Abschnitt „Nachweis").

### D – Bundle bereinigen (~31 MB, ~30 Dateien) — Kaltstart/Download, kein Warmstart-Gewinn
Ursache der Blähung: `markdown.extensions.codehilite` → `pygments.formatters.img` → `PIL` →
`numpy` (typing) → `psutil`. Zur Laufzeit wird nichts davon importiert (per `sys.modules`
verifiziert).
- [x] `build.py`: gemeinsame `pyinstaller_flags()` für **beide** Varianten –
      `--exclude-module numpy --exclude-module numpy.libs --exclude-module PIL
      --exclude-module psutil --exclude-module setuptools --exclude-module charset_normalizer
      --exclude-module olefile --exclude-module defusedxml`, dazu `--noupx`.
- [ ] Smoke-Test des Frozen-Builds aus **lokalem** Pfad (nie UNC): Datei mit Codeblock,
      Bild-Embed, PDF-Export, `plantuml.jar` daneben legen (sonst Download-Dialog).
- [ ] Kontrolle: `dist/md-dis/_internal` enthält kein `numpy`/`numpy.libs`/`PIL` mehr.
- [x] Hinweis für die Doku: UPX nicht nachinstallieren – es würde die 195-MB-
      `Qt6WebEngineCore.dll` packen und den Start verlangsamen (Kommentar in `build.py`).

### E – PlantUML-Prüfung vom Start entkoppeln (Verhaltensänderung!)
Heute: `QTimer.singleShot(0, self._init_deferred)` → `_check_plantuml`: fehlt die JAR und ist
Java da, bremst `check_java_available()` **148 ms** auf dem GUI-Thread und es erscheint ein
**modales** 28-MB-Download-Fenster.
- [x] `_check_plantuml` beim Start: kein `check_java_available()`, kein Dialog – nur noch ein
      Hinweis in der Statuszeile, wenn die JAR fehlt (gemessen: 0,1 ms).
- [x] Neue `_ensure_plantuml_jar()`: läuft beim Laden, wenn der Text einen
      ` ```plantuml `-Fence enthält (`_contains_plantuml_block`, erkennt ```/~~~ und längere
      Zäune); zeigt den bestehenden Dialog mit Fortschritt, merkt Ablehnung/Fehler in
      `_plantuml_download_declined` und fragt dann nicht erneut.
- [x] Verifiziert (Quellmodus, 13 Prüfungen): Start ohne Java-Subprozess/Dialog, Statuszeile,
      Datei ohne Diagramm fragt nicht, Datei mit Diagramm fragt genau einmal, zweite Datei
      nicht erneut, vorhandene JAR → weder Java-Test noch Dialog.
- [ ] Doku nachziehen: `README.md` (Zeile ~27 / „Automatically on first use"),
      `DESIGN.md` (Z. 71 „Automatischer Download beim ersten Start"), `HANDOFF.md`.

### F – QWebEngineView nach `show()` vorwärmen (erstes Dokument ~0,3 s schneller)
- [x] `_init_deferred`: `QTimer.singleShot(250, self._warm_up_web_view)`; `_warm_up_web_view`
      legt die Ansicht an und lädt eine leere Seite.
- [x] Verifiziert: Stack bleibt auf dem Willkommens-Label, PDF-Action bleibt ohne Datei
      deaktiviert, `_page_loaded` wird beim echten Laden korrekt zurückgesetzt/gesetzt.
- [x] Hinweis: Der Warm-up lässt Chromium starten, bevor der Nutzer eine Datei öffnet –
      gemessene Ersparnis beim ersten Dokument ~0,3 s (frühere Messung: erstes `setHtml` →
      `loadFinished` 175 ms, danach 30 ms, plus Prozessstart).

### G – Server-Feinschliff
- [x] `md_dis_server.main()`: Daemon-Thread `render-warmup` startet nach dem Binden
      (`server.server_address`, vor dem Banner) und rendert ein Mini-Dokument mit Codeblock.
- [x] Gemessen (3 Läufe, erster Request auf `/README.md`): bei 400 ms nach Banner
      **207–233 ms statt 287–320 ms** (~70–90 ms schneller); bei 0 ms Wartezeit kein
      Unterschied (Thread hat dann keinen Vorsprung).
- [x] Optional bewusst **nicht** umgesetzt: `markdown`-Lazy-Import (bräuchte Fabrik für
      `EmbedImageProcessor`/`WikiLinkProcessor`, ~20 ms bis zum Banner – zu invasiv).
- [x] Konventionen unangetastet: `_slugify` bleibt an `markdown.extensions.toc.slugify`
      gekoppelt, Diagramm-Extraktion bleibt in `_extract_diagram_blocks`.

---

## Nachbrenner

### H – Fokus nach dem Splash (Nutzerbefund nach dem Einbau von C)
Beim Doppelklick auf eine `.md` erschien das Hauptfenster hinter dem Explorer und musste
angeklickt werden.
- [x] Ursache reproduziert: `GetForegroundWindow` lieferte eine fremde PID; der Splash
      (Tk, „always on top") gibt den Vordergrund beim Schließen nicht an Qt weiter.
- [x] `raise_()` + `activateWindow()` allein reichten nicht (1 von 2 Läufen).
- [x] `_bring_to_front()` in `md_dis.py`: zusätzlich `AttachThreadInput` auf den Thread des
      Vordergrundfensters + `SetForegroundWindow`, dreimal per
      `QTimer.singleShot(0/150/500)` nach `app.exec()` (vorher ist das Fenster nicht fertig
      gezeichnet). Ausnahmen werden geschluckt – der Fokus darf den Start nie verhindern.
- [x] Verifiziert: **4/4** Läufe mit Datei, **3/3** mit `smoke.md` (PlantUML/Mermaid),
      **3/3** ohne Datei im Vordergrund; Splash 56–63 ms, Hauptfenster 628–680 ms (keine
      Regression).

---

## Nachweis / Abnahme

- [x] Quellmodus: `python -m pytest` (47 Tests) grün, `py_compile` aller Module.
- [x] Messung vorher/nachher mit denselben Methoden wie in der Analyse:
      - GUI: Splash nach **58–149 ms**, Hauptfenster nach **649–688 ms** (vorher 777–1085 ms)
      - Server: Banner nach **155/159 ms** warm (vorher 492–763 ms), Erststart nach dem Build 1284 ms (Defender)
      - Importe: `import md_dis` ohne `QtWebEngineWidgets`; WebEngine-Import kalt 26–27 ms
- [x] Neu gebaut: `python build.py` → GUI **1.4.7**, `python build.py --server` → Server **1.4.8**;
      Quelle steht jetzt auf `VERSION = "1.4.8"`.
- [x] Frozen-Smoke-Test **aus lokalem Pfad** (nie UNC), `plantuml.jar` daneben:
      Datei mit Codeblock und Bild-Embed geöffnet → Titel „md-dis – einfach.md" nach 1412 ms,
      `QtWebEngineProcess` läuft, nur ein sichtbares Fenster; Splash nach 58 ms sichtbar und
      danach geschlossen (Fensterzählung per WinAPI). Dokument mit PlantUML + Mermaid →
      Titel nach 4166 ms, Chromium läuft. PDF-Export und `Strg+T` wurden im Quellmodus geprüft
      (38 kB PDF, Theme-Reload); ein automatisierter Frozen-PDF-Test scheiterte am Fokus
      (`SetForegroundWindow`/`AppActivate` verweigert), nicht an der App.
      Server: `/` → 200, `/README.md` → 200, `/tests/` → 404, `/gibt-es-nicht.md` → 404.
- [x] Doku aktualisiert: `README.md` (Status/Version/Changelog/Features), `DESIGN.md`
      (neuer Abschnitt „Startzeit", PlantUML-Download bei Bedarf), `HANDOFF.md`
      (Work State, Messwerte, Fallstricke 19–23).
- [ ] Zum Schluss diese Datei aufräumen oder die erledigten Häkchen in `HANDOFF.md` überführen.

---

## Offene Entscheidungen (entschieden und umgesetzt)

1. **E:** Statuszeilen-Hinweis beim Start **behalten**, Dialog erst beim PlantUML-Dokument.
2. **G:** nur Vorwärmen, **kein** invasiver `markdown`-Lazy-Import.
3. **C:** Splash mit `icon.png` (256×256 RGBA).
4. **D:** alle genannten Pakete ausschließen (`numpy`, `PIL`, `psutil`, `setuptools`,
   `charset_normalizer`, `olefile`, `defusedxml`).

## Bewusst nicht umsetzen

- `--onefile`: entpackt bei jedem Start → langsamer.
- UPX aktivieren: packt die großen Qt-DLLs → langsamer (UPX ist derzeit ohnehin nicht installiert).
- Toolbar/Statusbar „weglassen": die Qt-Erstinitialisierung verschiebt sich nur zu `show()`
  (gemessen: `QStatusBar()` 175 ms, `statusBar()` 238 ms, `addToolBar` 17 ms).
- Windows Defender / SmartScreen / signierte Exe: außerhalb des Codes; bei Kaltstart nach
  Download/Update aber der größte Einzelfaktor.
