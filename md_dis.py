#!/usr/bin/env python3
"""md-dis – Markdown-Viewer mit Diagramm-Unterstützung."""

import sys
import os
from pathlib import Path

from md_render import (
    VERSION, get_plantuml_jar_path, get_base_dir, check_java_available,
    download_plantuml_jar, find_mmdc, markdown_to_html,
)

from PyQt6.QtCore import Qt, QUrl, QTemporaryFile, QIODevice, QEvent, QTimer
from PyQt6.QtGui import QAction, QKeySequence, QIcon, QShortcut, QDragEnterEvent, QDropEvent, QDesktopServices, QFont
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QFileDialog, QToolBar, QDialog,
    QLabel, QStatusBar, QMessageBox, QProgressBar, QDialogButtonBox,
    QLineEdit, QWidget, QHBoxLayout, QVBoxLayout, QPlainTextEdit, QStackedWidget,
    QMenu, QToolButton
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

PlantUML nutzt eine `plantuml.jar` im Programmverzeichnis und benötigt **Java**. Fehlt die Jar-Datei, bietet md-dis an, sie automatisch herunterzuladen. Java ist separat zu installieren (siehe Status oben).

[Zurück zur Vorschau](mddis://back)
"""


GPL2_TEXT = """                    GNU GENERAL PUBLIC LICENSE
                       Version 2, June 1991

 Copyright (C) 1989, 1991 Free Software Foundation, Inc.
     51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
 Everyone is permitted to copy and distribute verbatim copies
 of this license document, but changing it is not allowed.

                            Preamble

  The licenses for most software are designed to take away your
freedom to share and change it.  By contrast, the GNU General Public
License is intended to guarantee your freedom to share and change free
software--to make sure the software is free for all its users.  This
General Public License applies to most of the Free Software
Foundation's software and to any other program whose authors commit to
using it.  (Some other Free Software Foundation software is covered by
the GNU Library General Public License instead.)  You can apply it to
your programs, too.

  When we speak of free software, we are referring to freedom, not
price.  Our General Public Licenses are designed to make sure that you
have the freedom to distribute copies of free software (and charge for
this service if you wish), that you receive source code or can get it
if you want it, that you can change the software or use pieces of it
in new free programs; and that you know you can do these things.

  To protect your rights, we need to make restrictions that forbid
anyone to deny you these rights or to ask you to surrender the rights.
These restrictions translate to certain responsibilities for you if you
distribute copies of the software, or if you modify it.

  For example, if you distribute copies of such a program, whether
gratis or for a fee, you must give the recipients all the rights that
you have.  You must make sure that they, too, receive or can get the
source code.  And you must show them these terms so they know their
rights.

  We protect your rights with two steps: (1) copyright the software,
and (2) offer you this license which gives you legal permission to
copy, distribute and/or modify the software.

  Also, for each author's protection and ours, we want to make certain
that everyone understands that there is no warranty for this free
software.  If the software is modified by someone else and passed on, we
want its recipients to know that what they have is not the original, so
that any problems introduced by others will not reflect on the original
authors' reputations.

  Finally, any free program is threatened constantly by software
patents.  We wish to avoid the danger that redistributors of a free
program will individually obtain patent licenses, in effect making the
program proprietary.  To prevent this, we have made it clear that any
patent must be licensed for everyone's free use or not licensed at all.

  The precise terms and conditions for copying, distribution and
modification follow.

                    GNU GENERAL PUBLIC LICENSE
   TERMS AND CONDITIONS FOR COPYING, DISTRIBUTION AND MODIFICATION

  0. This License applies to any program or other work which contains
a notice placed by the copyright holder saying it may be distributed
under the terms of this General Public License.  The "Program", below,
refers to any such program or work, and a "work based on the Program"
means either the Program or any derivative work under copyright law:
that is to say, a work containing the Program or a portion of it,
either verbatim or with modifications and/or translated into another
language.  (Hereinafter, translation is included without limitation in
the term "modification".)  Each licensee is addressed as "you".

Activities other than copying, distribution and modification are not
covered by this License; they are outside its scope.  The act of
running the Program is not restricted, and the output from the Program
is covered only if its contents constitute a work based on the Program
(independent of having been made by running the Program).  Whether that
is true depends on what the Program does.

  1. You may copy and distribute verbatim copies of the Program's
source code as you receive it, in any medium, provided that you
conspicuously and appropriately publish on each copy an appropriate
copyright notice and disclaimer of warranty; keep intact all the
notices that refer to this License and to the absence of any warranty;
and give any other recipients of the Program a copy of this License
along with the Program.

You may charge a fee for the physical act of transferring a copy, and
you may at your option offer warranty protection in exchange for a fee.

  2. You may modify your copy or copies of the Program or any portion
of it, thus forming a work based on the Program, and copy and
distribute such modifications or work under the terms of Section 1
above, provided that you also meet all of these conditions:

    a) You must cause the modified files to carry prominent notices
    stating that you changed the files and the date of any change.

    b) You must cause any work that you distribute or publish, that in
    whole or in part contains or is derived from the Program or any
    part thereof, to be licensed as a whole at no charge to all third
    parties under the terms of this License.

    c) If the modified program normally reads commands interactively
    when run, you must cause it, when started running for such
    interactive use in the most ordinary way, to print or display an
    announcement including an appropriate copyright notice and a
    notice that there is no warranty (or else, saying that you provide
    a warranty) and that users may redistribute the program under
    these conditions, and telling the user how to view a copy of this
    License.  (Exception: if the Program itself is interactive but
    does not normally print such an announcement, your work based on
    the Program is not required to print an announcement.)

These requirements apply to the modified work as a whole.  If
identifiable sections of that work are not derived from the Program,
and can be reasonably considered independent and separate works in
themselves, then this License, and its terms, do not apply to those
sections when you distribute them as separate works.  But when you
distribute the same sections as part of a whole which is a work based
on the Program, the distribution of the whole must be on the terms of
this License, whose permissions for other licensees extend to the
entire whole, and thus to each and every part regardless of who wrote it.

Thus, it is not the intent of this section to claim rights or contest
your rights to work written entirely by you; rather, the intent is to
exercise the right to control the distribution of derivative or
collective works based on the Program.

In addition, mere aggregation of another work not based on the Program
with the Program (or with a work based on the Program) on a volume of
a storage or distribution medium does not bring the other work under
the scope of this License.

  3. You may copy and distribute the Program (or a work based on it,
under Section 2) in object code or executable form under the terms of
Sections 1 and 2 above provided that you also do one of the following:

    a) Accompany it with the complete corresponding machine-readable
    source code, which must be distributed under the terms of Sections
    1 and 2 above on a medium customarily used for software interchange;
    or,

    b) Accompany it with a written offer, valid for at least three
    years, to give any third party, for a charge no more than your
    cost of physically performing source distribution, a complete
    machine-readable copy of the corresponding source code, to be
    distributed under the terms of Sections 1 and 2 above on a medium
    customarily used for software interchange; or,

    c) Accompany it with the information you received as to the offer
    to distribute corresponding source code.  (This alternative is
    allowed only for noncommercial distribution and only if you
    received the program in object code or executable form with such
    an offer, in accord with Subsection b above.)

The source code for a work means the preferred form of the work for
making modifications to it.  For an executable work, complete source
code means all the source code for all modules it contains, plus any
associated interface definition files, plus the scripts used to
control compilation and installation of the executable.  However, as a
special exception, the source code distributed need not include
anything that is normally distributed (in either source or binary
form) with the major components (compiler, kernel, and so on) of the
operating system on which the executable runs, unless that component
itself accompanies the executable.

If distribution of executable or object code is made by offering
access to copy from a designated place, then offering equivalent
access to copy the source code from the same place counts as
distribution of the source code, even though third parties are not
compelled to copy the source along with the object code.

  4. You may not copy, modify, sublicense, or distribute the Program
except as expressly provided under this License.  Any attempt
otherwise to copy, modify, sublicense or distribute the Program is
void, and will automatically terminate your rights under this License.
However, parties who have received copies, or rights, from you under
this License will not have their licenses terminated so long as such
parties remain in full compliance.

  5. You are not required to accept this License, since you have not
signed it.  However, nothing else grants you permission to modify or
distribute the Program or its derivative works.  These actions are
prohibited by law if you do not accept this License.  Therefore, by
modifying or distributing the Program (or any work based on the
Program), you indicate your acceptance of this License to do so, and
all its terms and conditions for copying, distributing or modifying
the Program or works based on it.

  6. Each time you redistribute the Program (or any work based on the
Program), the recipient automatically receives a license from the
original licensor to copy, distribute or modify the Program subject to
these terms and conditions.  You may not impose any further
restrictions on the recipients' exercise of the rights granted herein.
You are not responsible for enforcing compliance by third parties to
this License.

  7. If, as a consequence of a court judgment or allegation of patent
infringement or for any other reason (not limited to patent issues),
conditions are imposed on you (whether by court order, agreement or
otherwise) that contradict the conditions of this License, they do not
excuse you from the conditions of this License.  If you cannot
distribute so as to satisfy simultaneously your obligations under this
License and any other pertinent obligations, then as a consequence you
may not distribute the Program at all.  For example, if a patent
license would not permit royalty-free redistribution of the Program by
all those who receive copies directly or indirectly through you, then
the only way you could satisfy both it and this License would be to
refrain entirely from distribution of the Program.

If any portion of this section is held invalid or unenforceable under
any particular circumstance, the balance of the section is intended to
apply and the section as a whole is intended to apply in other
circumstances.

It is not the purpose of this section to induce you to infringe any
patents or other property right claims or to contest validity of any
such claims; this section has the sole purpose of protecting the
integrity of the free software distribution system, which is
implemented by public license practices.  Many people have made
generous contributions to the wide range of software distributed
through that system in reliance on consistent application of that
system; it is up to the author/donor to decide if he or she is willing
to distribute software through any other system and a licensee cannot
impose that choice.

This section is intended to make thoroughly clear what is believed to
be a consequence of the rest of this License.

  8. If the distribution and/or use of the Program is restricted in
certain countries either by patents or by copyrighted interfaces, the
original copyright holder who places the Program under this License
may add an explicit geographical distribution limitation excluding
those countries, so that distribution is permitted only in or among
countries not thus excluded.  In such case, this License incorporates
the limitation as if written in the body of this License.

  9. The Free Software Foundation may publish revised and/or new
versions of the General Public License from time to time.  Such new
versions will be similar in spirit to the present version, but may
differ in detail to address new problems or concerns.

Each version is given a distinguishing version number.  If the Program
specifies a version number of this License which applies to it and
"any later version", you have the option of following the terms and
conditions either of that version or of any later version published by
the Free Software Foundation.  If the Program does not specify a
version number of this License, you may choose any version ever
published by the Free Software Foundation.

  10. If you wish to incorporate parts of the Program into other free
programs whose distribution conditions are different, write to the
author to ask for permission.  For software which is copyrighted by the
Free Software Foundation, write to the Free Software Foundation; we
sometimes make exceptions for this.  Our decision will be guided by the
two goals of preserving the free status of all derivatives of our free
software and of promoting the sharing and reuse of software generally.

                            NO WARRANTY

  11. BECAUSE THE PROGRAM IS LICENSED FREE OF CHARGE, THERE IS NO
WARRANTY FOR THE PROGRAM, TO THE EXTENT PERMITTED BY APPLICABLE LAW.
EXCEPT WHEN OTHERWISE STATED IN WRITING THE COPYRIGHT HOLDERS AND/OR
OTHER PARTIES PROVIDE THE PROGRAM "AS IS" WITHOUT WARRANTY OF ANY KIND,
EITHER EXPRESSED OR IMPLIED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE.
THE ENTIRE RISK AS TO THE QUALITY AND PERFORMANCE OF THE PROGRAM IS
WITH YOU.  SHOULD THE PROGRAM PROVE DEFECTIVE, YOU ASSUME THE COST OF
ALL NECESSARY SERVICING, REPAIR OR CORRECTION.

  12. IN NO EVENT UNLESS REQUIRED BY APPLICABLE LAW OR AGREED TO IN
WRITING WILL ANY COPYRIGHT HOLDER, OR ANY OTHER PARTY WHO MAY MODIFY
AND/OR REDISTRIBUTE THE PROGRAM AS PERMITTED ABOVE, BE LIABLE TO YOU
FOR DAMAGES, INCLUDING ANY GENERAL, SPECIAL, INCIDENTAL OR
CONSEQUENTIAL DAMAGES ARISING OUT OF THE USE OR INABILITY TO USE THE
PROGRAM (INCLUDING BUT NOT LIMITED TO LOSS OF DATA OR DATA BEING
RENDERED INACCURATE OR LOSSES SUSTAINED BY YOU OR THIRD PARTIES OR A
FAILURE OF THE PROGRAM TO OPERATE WITH ANY OTHER PROGRAMS), EVEN IF
SUCH HOLDER OR OTHER PARTY HAS BEEN ADVISED OF THE POSSIBILITY OF SUCH
DAMAGES.

                     END OF TERMS AND CONDITIONS

        How to Apply These Terms to Your New Programs

  If you develop a new program, and you want it to be of the greatest
possible use to the public, the best way to achieve this is to make it
free software which everyone can redistribute and change under these
terms.

  To do so, attach the following notices to the program.  It is safest
to attach them to the start of each source file to most effectively
convey the exclusion of warranty; and each file should have at least
the "copyright" line and a pointer to where the full notice is found.

    <one line to give the program's name and a brief idea of what it does.>
    Copyright (C) <year>  <name of author>

    This program is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 2 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program; if not, write to the Free Software
    Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA


Also add information on how to contact you by electronic and paper mail.

If the program is interactive, make it output a short notice like this
when it starts in an interactive mode:

    Gnomovision version 69, Copyright (C) year  name of author
    Gnomovision comes with ABSOLUTELY NO WARRANTY; for details type `show w'.
    This is free software, and you are welcome to redistribute it
    under certain conditions; type `show c' for details.

The hypothetical commands `show w' and `show c' should show the
appropriate parts of the General Public License.  Of course, the
commands you use may be called something other than `show w' and
`show c'; they could even be mouse-clicks or menu items--whatever suits
your program.

You should also get your employer (if you work as a programmer) or your
school, if any, to sign a "copyright disclaimer" for the program, if
necessary.  Here is a sample; alter the names:

  Yoyodyne, Inc., hereby disclaims all copyright interest in the program
  `Gnomovision' (which makes passes at compilers) written by James Hacker.

  <signature of Ty Coon>, 1 April 1989
  Ty Coon, President of Vice

This General Public License does not permit incorporating your program
into proprietary programs.  If your program is a subroutine library,
you may consider it more useful to permit linking proprietary
applications with the library.  If this is what you want to do, use the
GNU Library General Public License instead of this License."""


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
        self.dark_mode = True
        self.zoom_level = 1.0
        self.current_file = None
        self.web_view = None
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

    def _init_deferred(self):
        """Run heavy init after window is visible."""
        self._check_plantuml()

    def _ensure_web_view(self):
        """Lazily create QWebEngineView on first use."""
        if self.web_view is not None:
            return

        self.web_view = QWebEngineView()
        self.web_view.setPage(ExternalLinkPage(self, self.web_view))
        settings = self.web_view.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)

        self.stack.addWidget(self.web_view)

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
        self.theme_action.setShortcut(QKeySequence("Ctrl+D"))
        self.theme_action.triggered.connect(self._toggle_theme)
        toolbar.addAction(self.theme_action)

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
        help_menu.addAction("Lizenz (GPL-2)", self._show_license)
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
        html = markdown_to_html(md_text, self.dark_mode, self.zoom_level)
        self._ensure_web_view()
        self.web_view.setHtml(html)
        self.stack.setCurrentWidget(self.web_view)

    def _show_license(self):
        """Show the GNU GPL v2 license in a dialog."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Lizenz – GNU GPL v2")
        dialog.resize(720, 560)

        layout = QVBoxLayout(dialog)

        headline = QLabel("md-dis ist freie Software.")
        headline.setWordWrap(True)
        layout.addWidget(headline)

        text = QPlainTextEdit()
        text.setReadOnly(True)
        text.setPlainText(GPL2_TEXT)
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
            "Lizenziert unter der GNU General Public License v2.".format(
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
                    "Bitte manuell von https://plantuml.com/de/download herunterladen.\n"
                    f"Zielverzeichnis: {get_base_dir()}"
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

        html = markdown_to_html(md_text, self.dark_mode, self.zoom_level,
                                 progress_callback=on_plantuml_progress)
        self._ensure_web_view()
        if self.web_view is not None:
            if not self.edit_mode:
                self.stack.setCurrentWidget(self.web_view)
            tmp_html = os.path.join(self._preview_dir(), ".md-dis-preview.html")
            with open(tmp_html, 'w', encoding='utf-8') as hf:
                hf.write(html)
            self.web_view.setUrl(QUrl.fromLocalFile(tmp_html))

        self.progress_bar.setVisible(False)
        self.statusBar().showMessage(f"Geladen: {self.current_file}")

    def _preview_dir(self) -> str:
        if getattr(sys, 'frozen', False):
            base = os.path.dirname(os.path.abspath(sys.executable))
        else:
            base = os.path.dirname(os.path.abspath(__file__))
        preview_dir = os.path.join(base, "preview")
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
        event.accept()

    def _render_markdown(self, md_text: str):
        html = markdown_to_html(md_text, self.dark_mode, self.zoom_level)
        self._ensure_web_view()
        self.web_view.setHtml(html)

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
        self._reload_current()

    def _zoom_out(self):
        self.zoom_level = max(self.zoom_level - 0.1, 0.5)
        self._reload_current()

    def _zoom_reset(self):
        self.zoom_level = 1.0
        self._reload_current()

    def _toggle_theme(self):
        self.dark_mode = not self.dark_mode
        if self.dark_mode:
            self.theme_action.setText("Hellmodus")
        else:
            self.theme_action.setText("Dunkelmodus")
        self._reload_current()

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
