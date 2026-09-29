#!/usr/bin/env python3
"""md-dis – Markdown-Viewer mit Diagramm-Unterstützung."""

import sys
import os
from pathlib import Path

from md_render import (
    VERSION, get_plantuml_jar_path, get_base_dir, get_jar_search_dirs,
    check_java_available, download_plantuml_jar, find_mmdc, markdown_to_html,
)

from PyQt6.QtCore import (
    Qt, QUrl, QTemporaryFile, QIODevice, QEvent, QTimer, QSettings,
    QMarginsF,
)
from PyQt6.QtGui import (
    QAction, QKeySequence, QIcon, QShortcut, QDragEnterEvent, QDropEvent,
    QDesktopServices, QFont, QPageLayout, QPageSize,
)
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QFileDialog, QToolBar, QDialog,
    QLabel, QStatusBar, QMessageBox, QProgressBar, QDialogButtonBox,
    QLineEdit, QWidget, QHBoxLayout, QVBoxLayout, QPlainTextEdit, QStackedWidget,
    QMenu, QToolButton, QComboBox, QRadioButton, QButtonGroup, QFormLayout
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineSettings, QWebEnginePage


MERMAID_JS_URL = "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"

HELP_MARKDOWN = """
# md-dis – Hilfe

[Zurück zur Vorschau](mddis://back)

## Status dieser Installation

| Komponente | Status |
|---|---|
| Mermaid (mmdc / mermaid-cli) | @@MMDC@@ |
| PlantUML (Java) | @@JAVA@@ |
| PlantUML (plantuml.jar) | @@JAR@@ |

---

## Mermaid-Diagramme

Mermaid-Diagramme werden beim Erzeugen der Vorschau mit **mermaid-cli** (Kurzname `mmdc`) lokal gerendert und als SVG in die Vorschau eingebettet. Es ist kein Browser oder Java nötig – nur Node.js und mermaid-cli.

### Voraussetzungen

1. **Node.js** mit npm: <https://nodejs.org>
2. **mermaid-cli** global installiert (siehe unten)

### Installation von mermaid-cli

Paketseite: <https://www.npmjs.com/package/@mermaid-js/mermaid-cli>

1. Node.js von <https://nodejs.org> herunterladen und installieren (im Installer der Standard-Pfad inkl. npm).
2. mermaid-cli global installieren: Konsole öffnen und

   ```bash
    npm install -g @mermaid-js/mermaid-cli
    ```

3. Konsole neu öffnen und prüfen:

    ```bash
    mmdc --version
    ```

**Windows-Hinweis:** Globale npm-Pakete landen unter `%APPDATA%\\npm\\`. dort sucht md-dis die Datei `mmdc.cmd` (bzw. auf dem `PATH`). Nach der Installation muss die Konsole **neu gestartet** werden, damit der Pfad aktualisiert wird.

### So sieht ein Mermaid-Block im Markdown aus

(Geschrieben im Dokument als ` ```mermaid ` – ohne Leerzeichen nach den Backticks.)

~~~text
``` mermaid
graph TD
    A[Start] --> B{OK?}
    B -->|ja| C[Fertig]
    B -->|nein| D[Fehler]
```
~~~

### Erste Verwendung dauert länger

Beim ersten Rendern lädt mermaid-cli eine eingebettete Chromium-Engine (Puppeteer) herunter und startet sie. Das kann über eine Minute dauern – anschließend laufen Folgeansichten deutlich schneller. Ein kurzer Hinweis in der Statusleiste erscheint deshalb während des Renderns.

### Fehlerbehebung

| Anzeige / Meldung | Ursache | Lösung |
|---|---|---|
| *Mermaid: mmdc nicht gefunden* | mermaid-cli ist nicht (global) installiert, oder der Terminal-Pfad wurde nicht aktualisiert | Schritte 2 und 3 oben; Konsole neu öffnen; `npm install -g @mermaid-js/mermaid-cli` |
| *Mermaid-Fehler: …download…/Chromium…* | mermaid-cli kann seine Chromium-Engine nicht laden (z. B. kein Internet beim ersten Start, Netzwerk-Firewall) | Installation mit Internet wiederholen: `npm install -g @mermaid-js/mermaid-cli`; bei erneutem Fehler `npm config get puppeteer_skip_download` prüfen und ggf. `npm rebuild @mermaid-js/mermaid-cli` |
| Diagramm wird nicht angezeigt, nur Code | Der Block beginnt nicht mit ` ```mermaid ` (z. B. Leerzeichen oder anderes Format) | Syntax oben beachten |
| *Timeout beim Rendern* | mermaid-cli braucht länger als 60 s (erster Start, schwacher Rechner) | Erneut rendern (F5); zuerst ein leeres Diagramm laden |

### Alternative ohne globale Installation

Wer nicht global installieren möchte, kann mermaid-cli einmalig ohne Installation ausführen:

```bash
npx -y @mermaid-js/mermaid-cli --version
```

md-dis selbst erwartet allerdings `mmdc` auf dem PATH (bzw. in `%APPDATA%\\npm\\`). Die globale Installation ist also der empfohlene Weg.

---

## PlantUML-Diagramme

PlantUML nutzt eine `plantuml.jar` und benötigt **Java**. Gesucht wird in dieser Reihenfolge: dem Verzeichnis der Programmdatei, dem Skriptverzeichnis (beim Start aus dem Quellcode) und `%LOCALAPPDATA%\\md-dis`; ein expliziter Pfad kann über die Umgebungsvariable `MD_DIS_PLANTUML_JAR` vorgegeben werden. Fehlt die JAR-Datei, bietet md-dis an, sie automatisch herunterzuladen – in das Programmverzeichnis, sofern beschreibbar, sonst in den Benutzer-Cache. Java ist separat zu installieren (siehe Status oben).

[Zurück zur Vorschau](mddis://back)
"""


MIT_TEXT = """MIT License

Copyright (c) 2026 Ralf Joswig

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE."""


# Einstellungen liegen in einer INI neben der EXE – passend dazu, dass auch
# preview/ und plantuml.jar dort landen (siehe _app_dir). Nicht in der
# Registry: der Ordner lässt sich damit samt Einstellungen kopieren.
SETTINGS_FILE = "md-dis.ini"

# Seitenformate im Dialog. Gespeichert wird der Enum-Name, nicht der
# Anzeigename, weil Executive in Qt "Executive.7.5x10in" heisst.
PDF_PAGE_SIZES = ["A4", "A3", "A5", "Letter", "Legal", "Executive", "Tabloid"]

# Rand-Presets in Millimetern. "Normal" ist Default, weil viele Drucker die
# letzten Millimeter nicht bedrucken.
PDF_MARGIN_PRESETS = [("Schmal", 10), ("Normal", 15), ("Weit", 25)]


def app_dir() -> str:
    """Verzeichnis, in dem die App ihre Laufzeitdateien ablegt."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def pdf_page_layout(page_size: str, landscape: bool, margin_mm: int) -> QPageLayout:
    """Baut das Seitenlayout fuer den PDF-Export.

    Die Einheit muss ausdruecklich gesetzt werden: QPageLayout rechnet sonst in
    Punkten, 12 waeren dann 12 pt (~4,2 mm) statt 12 mm.
    """
    size_id = getattr(QPageSize.PageSizeId, page_size, QPageSize.PageSizeId.A4)
    orientation = (QPageLayout.Orientation.Landscape if landscape
                   else QPageLayout.Orientation.Portrait)
    margins = QMarginsF(margin_mm, margin_mm, margin_mm, margin_mm)
    return QPageLayout(QPageSize(size_id), orientation, margins,
                       QPageLayout.Unit.Millimeter)


class PdfOptionsDialog(QDialog):
    """Seitenformat, Ausrichtung und Rand fuer den PDF-Export waehlen."""

    def __init__(self, page_size: str, landscape: bool, margin_label: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PDF-Optionen")

        self.size_combo = QComboBox()
        for name in PDF_PAGE_SIZES:
            self.size_combo.addItem(name, name)
        index = self.size_combo.findData(page_size)
        self.size_combo.setCurrentIndex(index if index >= 0 else 0)

        # Radiobuttons statt Combo, weil die Auswahl eine Entscheidung ist und
        # nicht nur ein Wert – die beiden Richtungen sind sofort ueberschaubar.
        self.portrait_radio = QRadioButton("Hochformat")
        self.landscape_radio = QRadioButton("Querformat")
        (self.landscape_radio if landscape else self.portrait_radio).setChecked(True)
        orientation_group = QButtonGroup(self)
        orientation_group.addButton(self.portrait_radio)
        orientation_group.addButton(self.landscape_radio)

        self.margin_radios = []
        margin_group = QButtonGroup(self)
        for label, mm in PDF_MARGIN_PRESETS:
            radio = QRadioButton(f"{label} ({mm} mm)")
            radio.setProperty("mm", mm)
            radio.setProperty("label", label)
            if label == margin_label:
                radio.setChecked(True)
            margin_group.addButton(radio)
            self.margin_radios.append(radio)
        if not any(r.isChecked() for r in self.margin_radios):
            self.margin_radios[1].setChecked(True)

        orientation_box = QWidget()
        orientation_layout = QHBoxLayout(orientation_box)
        orientation_layout.setContentsMargins(0, 0, 0, 0)
        orientation_layout.addWidget(self.portrait_radio)
        orientation_layout.addWidget(self.landscape_radio)

        margin_box = QWidget()
        margin_layout = QHBoxLayout(margin_box)
        margin_layout.setContentsMargins(0, 0, 0, 0)
        for radio in self.margin_radios:
            margin_layout.addWidget(radio)

        form = QFormLayout()
        form.addRow("Seitenformat:", self.size_combo)
        form.addRow("Ausrichtung:", orientation_box)
        form.addRow("Rand:", margin_box)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def selected(self) -> tuple:
        """(Enum-Name, quer, Rand-Label) fuer _export_pdf und QSettings."""
        checked = next((r for r in self.margin_radios if r.isChecked()), None)
        return (self.size_combo.currentData(),
                self.landscape_radio.isChecked(),
                checked.property("label") if checked else "Normal")

    def page_layout(self) -> QPageLayout:
        page_size, landscape, label = self.selected()
        margin_mm = next(mm for lbl, mm in PDF_MARGIN_PRESETS if lbl == label)
        return pdf_page_layout(page_size, landscape, margin_mm)


class ExternalLinkPage(QWebEnginePage):
    def __init__(self, viewer, parent=None):
        super().__init__(parent)
        self._viewer = viewer

    def acceptNavigationRequest(self, url, nav_type, is_main_frame):
        if url.scheme() == "mddis" and url.host() == "back":
            QTimer.singleShot(0, self._viewer._close_help)
            return False
        if not is_main_frame:
            return True
        if url.scheme() == "file":
            path = url.toLocalFile()
            if path.lower().endswith(('.md', '.markdown', '.mdown', '.mkd')):
                QTimer.singleShot(0, lambda p=path: self._viewer._load_file(p))
                return False
            return True
        if url.scheme() in ("http", "https", "mailto"):
            QDesktopServices.openUrl(url)
            return False
        return True


class MarkdownViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("md-dis – Markdown Viewer")
        self.setMinimumSize(800, 600)

        # Set window icon
        icon_path = get_base_dir() / "icon.ico"
        if not icon_path.exists() and getattr(sys, 'frozen', False):
            icon_path = Path(sys._MEIPASS) / "icon.ico"
        if not icon_path.exists():
            icon_path = get_base_dir() / "icon.png"
        if not icon_path.exists() and getattr(sys, 'frozen', False):
            icon_path = Path(sys._MEIPASS) / "icon.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self.settings = QSettings(
            os.path.join(app_dir(), SETTINGS_FILE), QSettings.Format.IniFormat
        )
        # True, sobald sync() scheitert (z. B. schreibgeschuetzter
        # Installationsordner) – dann laeuft die App nur noch im Speicher.
        self._settings_persist = True

        # Nicht bool(settings.value(...)): aus der INI kommt "false" als
        # String zurueck, und bool("false") ist True. Der type-Kwarg
        # erzwingt die echte Umwandlung.
        self.dark_mode = self.settings.value("appearance/darkMode", True, type=bool)
        self.zoom_level = self._clamp_zoom(
            self.settings.value("appearance/zoomLevel", 1.0, type=float)
        )
        self.pdf_page_size = self.settings.value("pdf/pageSize", "A4", type=str)
        self.pdf_landscape = self.settings.value("pdf/landscape", False, type=bool)
        self.pdf_margin = self.settings.value("pdf/marginPreset", "Normal", type=str)

        self.current_file = None
        self.web_view = None
        # True, sobald mindestens eine Seite vollstaendig geladen ist. Ohne
        # dieses Gate wuerde printToPdf waehrend eines Reloads (z. B. nach
        # einem Theme-Wechsel) ein leeres PDF schreiben.
        self._page_loaded = False
        self._pdf_exporting = False
        self.edit_mode = False
        self._dirty = False
        self.editor = None
        self._editor_suppress_change = False

        # Lightweight welcome label (fast startup)
        self.welcome_label = QLabel(
            '<div style="text-align:center; color:#6a737d; padding-top:20vh;">'
            '<h1 style="font-size:2em;">md-dis</h1>'
            '<p>Markdown-Viewer mit Mermaid &amp; PlantUML-Unterstützung</p>'
            '<p>Drag &amp; Drop eine .md-Datei hierher<br>'
            'oder <kbd>Strg+O</kbd> zum Öffnen</p>'
            '</div>'
        )
        self.welcome_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.welcome_label.setStyleSheet("background: white;")

        # QStackedWidget hält Vorschau und Editor permanent – kein Reparenting.
        self.stack = QStackedWidget()
        self.stack.addWidget(self.welcome_label)
        self.setCentralWidget(self.stack)

        self.setAcceptDrops(True)
        self.installEventFilter(self)
        # App-weiter Filter, damit Drops auch bei sichtbarer
        # QWebEngineView (die Drag&Drop intern behandelt) ankommen.
        QApplication.instance().installEventFilter(self)

        # Toolbar
        self._create_toolbar()

        # Status bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.setVisible(False)
        self.statusBar().addPermanentWidget(self.progress_bar)
        self.statusBar().showMessage("Bereit – Datei öffnen mit Strg+O oder Drag & Drop")

        # Search bar (hidden by default)
        self._create_search_bar()

        # Defer plantuml check & web view init to after window is shown
        QTimer.singleShot(0, self._init_deferred)

    @staticmethod
    def _clamp_zoom(value) -> float:
        """Zoom auf den Bereich begrenzen, den _zoom_in/_zoom_out zulassen.

        Eine von Hand editierte INI darf die Ansicht nicht unbedienbar machen.
        """
        try:
            value = float(value)
        except (TypeError, ValueError):
            return 1.0
        return max(0.5, min(value, 3.0))

    def _save_settings(self):
        """Einstellungen in die INI schreiben; bei fehlender Rechte still."""
        if not self._settings_persist:
            return
        self.settings.setValue("appearance/darkMode", self.dark_mode)
        self.settings.setValue("appearance/zoomLevel", self.zoom_level)
        self.settings.setValue("pdf/pageSize", self.pdf_page_size)
        self.settings.setValue("pdf/landscape", self.pdf_landscape)
        self.settings.setValue("pdf/marginPreset", self.pdf_margin)
        self.settings.sync()
        if self.settings.status() == QSettings.Status.AccessError:
            # z. B. read-only installiert – ab jetzt nur noch im Speicher
            self._settings_persist = False
            self.statusBar().showMessage(
                f"{SETTINGS_FILE} nicht schreibbar – Einstellungen gelten nur für diese Sitzung"
            )

    def _init_deferred(self):
        """Run heavy init after window is visible."""
        self._check_plantuml()

    def _ensure_web_view(self):
        """Lazily create QWebEngineView on first use."""
        if self.web_view is not None:
            return

        self.web_view = QWebEngineView()
        self.web_view.setPage(ExternalLinkPage(self, self.web_view))
        # Zoom wirkt direkt auf die Ansicht – kein Neurendern nötig
        self.web_view.loadFinished.connect(self._on_page_loaded)
        page = self.web_view.page()
        page.pdfPrintingFinished.connect(self._on_pdf_finished)
        settings = self.web_view.settings()
        # Kein JS nötig (Diagramme kommen als fertiges SVG) – verhindert, dass
        # Skripte aus fremden .md-Dateien lokale Dateien lesen und ausleiten
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, False)

        self.stack.addWidget(self.web_view)

    def _on_page_loaded(self, ok):
        """Nach jedem Laden Zoom setzen und den PDF-Export freigeben."""
        self._page_loaded = bool(ok)
        self.web_view.setZoomFactor(self.zoom_level)
        self._update_pdf_action()

    def _update_pdf_action(self):
        if getattr(self, "pdf_action", None) is None:
            return
        enabled = bool(self.current_file) and self._page_loaded and not self._pdf_exporting
        self.pdf_action.setEnabled(enabled)

    def _create_toolbar(self):
        toolbar = QToolBar("Hauptwerkzeugleiste")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # Open action
        open_action = QAction("Öffnen", self)
        open_action.setShortcut(QKeySequence("Ctrl+O"))
        open_action.triggered.connect(self._open_file)
        toolbar.addAction(open_action)

        # Reload action
        reload_action = QAction("Neu laden", self)
        reload_action.setShortcut(QKeySequence("F5"))
        reload_action.triggered.connect(self._reload_current)
        toolbar.addAction(reload_action)

        # Save action
        self.save_action = QAction("Speichern", self)
        self.save_action.setShortcut(QKeySequence("Ctrl+S"))
        self.save_action.triggered.connect(self._save_file)
        self.save_action.setEnabled(False)
        toolbar.addAction(self.save_action)

        # Edit/View mode toggle
        self.edit_action = QAction("Bearbeiten", self)
        self.edit_action.setShortcut(QKeySequence("F2"))
        self.edit_action.triggered.connect(self._toggle_edit_mode)
        self.edit_action.setEnabled(False)
        toolbar.addAction(self.edit_action)

        toolbar.addSeparator()

        # Zoom in
        zoom_in_action = QAction("Vergrößern", self)
        zoom_in_action.setShortcut(QKeySequence("Ctrl+="))
        zoom_in_action.triggered.connect(self._zoom_in)
        toolbar.addAction(zoom_in_action)

        # Zoom out
        zoom_out_action = QAction("Verkleinern", self)
        zoom_out_action.setShortcut(QKeySequence("Ctrl+-"))
        zoom_out_action.triggered.connect(self._zoom_out)
        toolbar.addAction(zoom_out_action)

        # Reset zoom
        zoom_reset_action = QAction("Zoom zurücksetzen", self)
        zoom_reset_action.setShortcut(QKeySequence("Ctrl+0"))
        zoom_reset_action.triggered.connect(self._zoom_reset)
        toolbar.addAction(zoom_reset_action)

        toolbar.addSeparator()

        # Dark/Light toggle – label shows what clicking will do
        self.theme_action = QAction("Hellmodus", self)
        # Beschriftung an den geladenen Zustand anpassen, sonst bietet der Knopf
        # nach einem Start im Hellmodus den Wechsel an, den er nicht ausfuehrt
        self.theme_action.setText("Hellmodus" if self.dark_mode else "Dunkelmodus")
        self.theme_action.setShortcut(QKeySequence("Ctrl+D"))
        self.theme_action.triggered.connect(self._toggle_theme)
        toolbar.addAction(self.theme_action)

        # PDF export – nach dem Theme, weil es die aktuelle Darstellung nutzt
        self.pdf_action = QAction("Als PDF speichern…", self)
        self.pdf_action.setShortcut(QKeySequence("Ctrl+P"))
        self.pdf_action.triggered.connect(self._export_pdf)
        self.pdf_action.setEnabled(False)
        toolbar.addAction(self.pdf_action)
        toolbar.addSeparator()

        # Search
        search_action = QAction("Suchen", self)
        search_action.setShortcut(QKeySequence("Ctrl+F"))
        search_action.triggered.connect(self._toggle_search)
        toolbar.addAction(search_action)

        toolbar.addSeparator()

        # Help menu (Hilfe / Lizenz / Über & Version)
        help_menu = QMenu(self)
        help_open_action = QAction("Hilfe", self)
        help_open_action.setShortcut(QKeySequence("F1"))
        help_open_action.triggered.connect(self._show_help)
        help_menu.addAction(help_open_action)
        help_menu.addAction("Lizenz (MIT)", self._show_license)
        help_menu.addAction("Über / Version", self._show_about)

        help_action = QAction("Hilfe", self)
        help_action.setToolTip("Hilfe, Lizenz und Versionsinfo")
        help_action.setMenu(help_menu)
        toolbar.addAction(help_action)

        help_button = toolbar.widgetForAction(help_action)
        if help_button is not None:
            help_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)

    def _create_search_bar(self):
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Suchen... (Strg+F)")
        self.search_input.setMaximumWidth(300)
        self.search_input.returnPressed.connect(self._search_next)
        self.search_input.textChanged.connect(self._search_live)
        self.search_input.setVisible(False)

        self.search_prev_btn = QLabel("◀")
        self.search_prev_btn.setStyleSheet("color: #58a6ff; padding: 0 6px; font-size: 14px;")
        self.search_prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.search_prev_btn.mousePressEvent = lambda _: self._search_prev()
        self.search_prev_btn.setVisible(False)

        self.search_next_btn = QLabel("▶")
        self.search_next_btn.setStyleSheet("color: #58a6ff; padding: 0 6px; font-size: 14px;")
        self.search_next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.search_next_btn.mousePressEvent = lambda _: self._search_next()
        self.search_next_btn.setVisible(False)

        self.search_close_btn = QLabel("✕")
        self.search_close_btn.setStyleSheet("color: #8b949e; padding: 0 6px; font-size: 14px;")
        self.search_close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.search_close_btn.mousePressEvent = lambda _: self._toggle_search()
        self.search_close_btn.setVisible(False)

        self.statusBar().addWidget(self.search_input)
        self.statusBar().addWidget(self.search_prev_btn)
        self.statusBar().addWidget(self.search_next_btn)
        self.statusBar().addWidget(self.search_close_btn)

        # Escape to close search
        esc = QShortcut(QKeySequence("Escape"), self)
        esc.activated.connect(self._close_search)

    def _toggle_search(self):
        visible = not self.search_input.isVisible()
        self.search_input.setVisible(visible)
        self.search_prev_btn.setVisible(visible)
        self.search_next_btn.setVisible(visible)
        self.search_close_btn.setVisible(visible)
        if visible:
            self.search_input.setFocus()
            self.search_input.selectAll()
        else:
            if self.web_view:
                self.web_view.findText("")

    def _close_search(self):
        self.search_input.setVisible(False)
        self.search_prev_btn.setVisible(False)
        self.search_next_btn.setVisible(False)
        self.search_close_btn.setVisible(False)
        if self.web_view:
            self.web_view.findText("")

    def _search_live(self, text):
        if self.web_view and text:
            self.web_view.findText(text)
        elif self.web_view:
            self.web_view.findText("")

    def _search_next(self):
        if self.web_view and self.search_input.text():
            self.web_view.findText(self.search_input.text())

    def _search_prev(self):
        if self.web_view and self.search_input.text():
            self.web_view.findText(self.search_input.text(),
                                   QWebEnginePage.FindFlag.FindBackward)

    def _show_welcome(self):
        welcome_html = """
        <!DOCTYPE html>
        <html>
        <head><meta charset="utf-8"><style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
               display: flex; justify-content: center; align-items: center; height: 90vh;
               color: #6a737d; text-align: center; margin: 0; }
        h1 { font-size: 2em; margin-bottom: 0.5em; }
        p { font-size: 1.1em; }
        kbd { background: #f6f8fa; border: 1px solid #d1d5da; border-radius: 3px;
              padding: 2px 6px; font-size: 0.9em; }
        </style></head>
        <body>
        <div>
            <h1>md-dis</h1>
            <p>Markdown-Viewer mit Mermaid &amp; PlantUML-Unterstützung</p>
            <p>Drag &amp; Drop eine .md-Datei hierher<br>
            oder <kbd>Strg+O</kbd> zum Öffnen</p>
        </div>
        </body>
        </html>
        """
        self._ensure_web_view()
        self.web_view.setHtml(welcome_html)

    def _show_help(self):
        """Show the built-in help page in the web view."""
        mmdc = find_mmdc()
        status = {
            "@@MMDC@@": "vorhanden" if mmdc else "nicht gefunden",
            "@@JAVA@@": "gefunden" if check_java_available() else "nicht gefunden",
            "@@JAR@@": "vorhanden" if get_plantuml_jar_path() else "fehlt",
        }
        md_text = HELP_MARKDOWN
        for token, value in status.items():
            md_text = md_text.replace(token, value)
        html = markdown_to_html(md_text, self.dark_mode)
        self._ensure_web_view()
        self.web_view.setHtml(html)
        self.stack.setCurrentWidget(self.web_view)

    def _show_license(self):
        """Show the MIT license in a dialog."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Lizenz – MIT")
        dialog.resize(720, 480)

        layout = QVBoxLayout(dialog)

        headline = QLabel("md-dis ist freie Software (MIT-Lizenz).")
        headline.setWordWrap(True)
        layout.addWidget(headline)

        text = QPlainTextEdit()
        text.setReadOnly(True)
        text.setPlainText(MIT_TEXT)
        font = text.font()
        font.setFamily("Consolas")
        font.setPointSize(9)
        text.setFont(font)
        layout.addWidget(text)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        dialog.exec()

    def _show_about(self):
        """Show version and build information in a dialog."""
        try:
            from PyQt6.QtCore import PYQT_VERSION_STR, QT_VERSION_STR
        except ImportError:
            PYQT_VERSION_STR, QT_VERSION_STR = "?", "?"

        dialog = QDialog(self)
        dialog.setWindowTitle("Über md-dis")
        dialog.resize(400, 260)

        layout = QVBoxLayout(dialog)

        title = QLabel("<h2>md-dis</h2>")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        info = QLabel(
            "<b>Version:</b> {version}<br>"
            "<b>Python:</b> {py}<br>"
            "<b>PyQt6:</b> {pyqt}<br>"
            "<b>Qt:</b> {qt}<br>"
            "<br>"
            "Markdown-Viewer mit Mermaid- und PlantUML-Diagrammen.<br>"
            "Lizenziert unter der MIT-Lizenz.".format(
                version=VERSION,
                py=sys.version.split()[0],
                pyqt=PYQT_VERSION_STR,
                qt=QT_VERSION_STR,
            )
        )
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info.setWordWrap(True)
        layout.addWidget(info)

        layout.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        dialog.exec()

    def _close_help(self):
        """Return from the help page to the previous view."""
        if self.edit_mode:
            if self.editor is not None:
                self.stack.setCurrentWidget(self.editor)
            return
        if self.current_file:
            self._reload_current()
        else:
            self._show_welcome()

    def _check_plantuml(self):
        """Check if plantuml.jar is available and offer to download if not."""
        jar_path = get_plantuml_jar_path()
        if jar_path:
            return

        if not check_java_available():
            self.statusBar().showMessage(
                "Hinweis: Java nicht gefunden – PlantUML-Diagramme werden nicht funktionieren."
            )
            return

        reply = QMessageBox.question(
            self,
            "plantuml.jar fehlt",
            "plantuml.jar wurde nicht gefunden.\n\n"
            f"Gesucht in:\n  {chr(10).join(str(d) for d in get_jar_search_dirs())}\n\n"
            "Möchten Sie es jetzt herunterladen?\n"
            "(Benötigt Internetverbindung)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.statusBar().showMessage("Lade plantuml.jar herunter...")
            QApplication.processEvents()

            def _progress(msg):
                self.statusBar().showMessage(msg)
                QApplication.processEvents()

            success = download_plantuml_jar(progress_callback=_progress)

            if success:
                QMessageBox.information(
                    self,
                    "Erfolg",
                    "plantuml.jar wurde erfolgreich heruntergeladen."
                )
            else:
                QMessageBox.warning(
                    self,
                    "Fehler",
                    "plantuml.jar konnte nicht heruntergeladen werden.\n\n"
                    "Bitte manuell von https://plantuml.com/de/download herunterladen und "
                    "in eines dieser Verzeichnisse legen:\n"
                    + "\n".join(f"  {d}" for d in get_jar_search_dirs())
                )

    def _open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Markdown-Datei öffnen",
            "",
            "Markdown-Dateien (*.md *.markdown *.mdown *.mkd);;Alle Dateien (*)"
        )
        if file_path:
            self._load_file(file_path)

    def _load_file(self, file_path: str):
        if self._dirty and not self._confirm_discard():
            return
        try:
            self.statusBar().showMessage(f"Lade: {file_path}")
            QApplication.processEvents()

            with open(file_path, 'r', encoding='utf-8') as f:
                md_text = f.read()
            self.current_file = file_path

            self._ensure_editor()
            self._set_editor_text(md_text)

            self._render_md_content(md_text)

            title = Path(file_path).name
            self.setWindowTitle(f"md-dis – {title}")
            self.save_action.setEnabled(True)
            self.edit_action.setEnabled(True)
            # Erst nach dem Rendern freigeben: _render_md_content setzt
            # _page_loaded zurueck, bis loadFinished kommt.
            self._update_pdf_action()
        except Exception as e:
            self.progress_bar.setVisible(False)
            QMessageBox.critical(self, "Fehler", f"Datei konnte nicht gelesen werden:\n{e}")

    def _render_md_content(self, md_text: str):
        """Render markdown text and display it in the web view."""
        def on_plantuml_progress(msg, current, total):
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(current)
            self.progress_bar.setVisible(True)
            self.statusBar().showMessage(msg)
            QApplication.processEvents()

        self.statusBar().showMessage("Rendere Markdown...")
        QApplication.processEvents()

        # zoom_level wird hier bewusst nicht uebergeben: die Vergroesserung
        # laeuft ausschliesslich ueber setZoomFactor (View-Ebene). Ein
        # Durchreichen wuerde die Schriftgroesse zusaetzlich in das CSS
        # einbrennen und damit doppelt skalieren.
        html = markdown_to_html(md_text, self.dark_mode,
                                 progress_callback=on_plantuml_progress)
        self._ensure_web_view()
        if self.web_view is not None:
            if not self.edit_mode:
                self.stack.setCurrentWidget(self.web_view)
            tmp_html = os.path.join(self._preview_dir(), ".md-dis-preview.html")
            with open(tmp_html, 'w', encoding='utf-8') as hf:
                hf.write(html)
            self._page_loaded = False
            self._update_pdf_action()
            # Anzeige per setHtml mit Basis-URL auf dem Verzeichnis der
            # Markdown-Datei. Ueber setUrl(QUrl.fromLocalFile(...)) loesten
            # sich relative Bildpfade dagegen gegen preview/ auf und brachen.
            base_url = QUrl.fromLocalFile(
                os.path.dirname(os.path.abspath(self.current_file)) + os.sep
            ) if self.current_file else QUrl.fromLocalFile(
                self._preview_dir() + os.sep
            )
            self.web_view.setHtml(html, base_url)

        self.progress_bar.setVisible(False)
        self.statusBar().showMessage(f"Geladen: {self.current_file}")

    def _preview_dir(self) -> str:
        preview_dir = os.path.join(app_dir(), "preview")
        os.makedirs(preview_dir, exist_ok=True)
        return preview_dir

    def _ensure_editor(self):
        """Lazily create the markdown source editor on first use."""
        if self.editor is not None:
            return
        self.editor = QPlainTextEdit()
        font = QFont("Consolas", 12)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.editor.setFont(font)
        self.editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.editor.setTabChangesFocus(False)
        self.editor.textChanged.connect(self._on_editor_changed)
        self.stack.addWidget(self.editor)

    def _set_editor_text(self, text: str):
        """Fill the editor without marking the document as dirty."""
        self._editor_suppress_change = True
        self.editor.setPlainText(text)
        self.editor.document().setModified(False)
        self._editor_suppress_change = False
        self._dirty = False

    def _on_editor_changed(self):
        if not self._editor_suppress_change:
            self._dirty = True

    def _confirm_discard(self) -> bool:
        """Ask the user what to do with unsaved changes. Returns True to proceed."""
        if not self._dirty:
            return True
        reply = QMessageBox.question(
            self,
            "Ungespeicherte Änderungen",
            "Es gibt ungespeicherte Änderungen.\n\n"
            "Möchten Sie sie speichern?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save
        )
        if reply == QMessageBox.StandardButton.Save:
            return self._save_file()
        return reply == QMessageBox.StandardButton.Discard

    def _save_file(self) -> bool:
        """Write the editor content back to the current file."""
        if not self.current_file or self.editor is None:
            return False
        try:
            with open(self.current_file, 'w', encoding='utf-8') as f:
                f.write(self.editor.toPlainText())
            self.editor.document().setModified(False)
            self._dirty = False
            self.statusBar().showMessage(f"Gespeichert: {self.current_file}")
            return True
        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"Speichern fehlgeschlagen:\n{e}")
            return False

    def _toggle_edit_mode(self):
        """Toggle between preview (web view) and editor (source)."""
        if self.current_file is None:
            return
        if not self.edit_mode:
            self._ensure_editor()
            self.stack.setCurrentWidget(self.editor)
            self.edit_mode = True
            self.edit_action.setText("Anzeigen")
            self.statusBar().showMessage("Bearbeiten – Strg+S speichert, F2 zeigt die Vorschau")
            self.editor.setFocus()
        else:
            self.edit_mode = False
            self.edit_action.setText("Bearbeiten")
            self._render_md_content(self.editor.toPlainText())
            self.stack.setCurrentWidget(self.web_view)

    def closeEvent(self, event):
        if self._dirty and not self._confirm_discard():
            event.ignore()
            return
        # Zoom und Theme koennen auch ohne exportiertes PDF veraendert worden sein
        self._save_settings()
        event.accept()

    def _reload_current(self):
        if not self.current_file:
            return
        if self.edit_mode and self.editor is not None:
            self._render_md_content(self.editor.toPlainText())
            return
        if self._dirty and not self._confirm_discard():
            return
        self._load_file(self.current_file)

    def _zoom_in(self):
        self.zoom_level = min(self.zoom_level + 0.1, 3.0)
        self._apply_zoom()

    def _zoom_out(self):
        self.zoom_level = max(self.zoom_level - 0.1, 0.5)
        self._apply_zoom()

    def _zoom_reset(self):
        self.zoom_level = 1.0
        self._apply_zoom()

    def _apply_zoom(self):
        if self.web_view is not None:
            self.web_view.setZoomFactor(self.zoom_level)
        self._save_settings()

    def _toggle_theme(self):
        self.dark_mode = not self.dark_mode
        if self.dark_mode:
            self.theme_action.setText("Hellmodus")
        else:
            self.theme_action.setText("Dunkelmodus")
        self._save_settings()
        self._reload_current()

    def _export_pdf(self):
        """Aktuelle Vorschau als PDF speichern (Chromium printToPdf)."""
        if not self.current_file:
            return
        if self.web_view is None or not self._page_loaded:
            QMessageBox.information(
                self, "PDF-Export",
                "Die Vorschau ist noch nicht geladen. Bitte kurz warten und es erneut versuchen."
            )
            return
        if self._dirty:
            answer = QMessageBox.question(
                self, "PDF-Export",
                "Es gibt ungespeicherte Änderungen. Die PDF enthält den Stand der\n"
                "letzten Vorschau, nicht den Editor-Inhalt. Trotzdem fortfahren?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        dialog = PdfOptionsDialog(
            self.pdf_page_size, self.pdf_landscape, self.pdf_margin, self
        )
        if not dialog.exec():
            return
        page_size, landscape, margin_label = dialog.selected()

        # Layouteinstellung unabhängig vom Ziel speichern: bricht der
        # Dateidialog ab, gilt sie trotzdem beim nächsten Mal.
        self.pdf_page_size = page_size
        self.pdf_landscape = landscape
        self.pdf_margin = margin_label
        self._save_settings()

        default_path = os.path.splitext(self.current_file)[0] + ".pdf"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Als PDF speichern", default_path, "PDF-Dokumente (*.pdf)"
        )
        if not file_path:
            return

        self._pdf_exporting = True
        self._update_pdf_action()
        self.statusBar().showMessage("Erstelle PDF...")
        QApplication.processEvents()
        # Asynchron: das Ergebnis meldet _on_pdf_finished. printToPdf
        # ignoriert setZoomFactor, das PDF ist also unabhaengig vom Zoom.
        self.web_view.page().printToPdf(file_path, dialog.page_layout())

    def _on_pdf_finished(self, file_path, success):
        self._pdf_exporting = False
        self._update_pdf_action()
        if success:
            self.statusBar().showMessage(f"PDF gespeichert: {file_path}", 8000)
        else:
            self.statusBar().showMessage("PDF-Export fehlgeschlagen", 5000)
            QMessageBox.warning(
                self, "PDF-Export",
                f"Die PDF konnte nicht erstellt werden:\n{file_path}"
            )

    # Drag & Drop – Event-Filter auf QMainWindow + QApplication,
    # damit auch die QWebEngineView (internes Render-Widget) Drops abgibt.
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.DragEnter and event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.toLocalFile().lower().endswith(('.md', '.markdown', '.mdown', '.mkd')):
                    event.acceptProposedAction()
                    return True
        elif event.type() == QEvent.Type.Drop and event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                if file_path.lower().endswith(('.md', '.markdown', '.mdown', '.mkd')):
                    self._load_file(file_path)
                    event.acceptProposedAction()
                    return True
        return super().eventFilter(obj, event)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("md-dis")
    app.setApplicationVersion(VERSION)
    # QSettings braucht den Organisationsnamen fuer einen sauberen Pfad, auch
    # wenn die Datei selbst per app_dir() fest verdrahtet ist.
    app.setOrganizationName("md-dis")

    window = MarkdownViewer()
    window.show()

    # Open file from command line
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        if os.path.isfile(file_path):
            window._load_file(file_path)
        else:
            QMessageBox.warning(window, "Fehler", f"Datei nicht gefunden:\n{file_path}")

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
