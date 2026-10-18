"""Gemeinsamer Render-Kern von md-dis.

Qt-freies Modul: konvertiert Markdown (inkl. PlantUML/Mermaid) zu HTML.
Wird sowohl von der Desktop-App (md_dis.py) als auch vom HTTP-Server
(md_dis_server.py) verwendet.
"""

import html
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.request
import xml.etree.ElementTree as etree
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import quote

import markdown
from markdown.extensions.toc import slugify as _toc_slugify
from markdown.inlinepatterns import InlineProcessor

VERSION = "1.4.4"

HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
{css}
</style>
</head>
<body>
<div class="md-page" data-toc-has="{has_toc}">
{toc}
<div class="md-content">
<div class="markdown-body">
{content}
</div>
</div>
</div>
</body>
</html>
"""

CSS_LIGHT = """
body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    font-size: {font_size}px;
    line-height: 1.6;
    color: #24292e;
    background-color: #ffffff;
}}
/* Zweispaltiges Grundlayout: links die Inhaltsverzeichnis-Sidebar, rechts der
   Text. Der Wrapper ist immer vorhanden, damit Server-Toolbar-Injektion und
   CSS auch ohne Sidebar dieselbe Struktur vorfinden. */
.md-page {{
    max-width: 90%;
    margin: 0 auto;
    padding: 20px 40px;
    display: flex;
    align-items: flex-start;
    gap: 32px;
}}
.md-content {{
    flex: 1 1 auto;
    min-width: 0;
}}
.md-toc {{
    position: sticky;
    top: 0;
    flex: 0 0 240px;
    align-self: flex-start;
    max-height: 100vh;
    overflow-y: auto;
    font-size: 0.9em;
    padding-right: 12px;
    border-right: 1px solid #eaecef;
}}
.md-toc ul {{
    list-style: none;
    margin: 0;
    padding-left: 0.9em;
}}
.md-toc li {{
    margin: 0.15em 0;
}}
.md-toc a {{
    color: #0366d6;
}}
.md-toc a:hover {{
    text-decoration: underline;
}}
@media (max-width: 900px) {{
    .md-page {{ display: block; }}
    .md-toc {{ display: none; }}
}}
.markdown-body h1, .markdown-body h2, .markdown-body h3,
.markdown-body h4, .markdown-body h5, .markdown-body h6 {{
    margin-top: 24px;
    margin-bottom: 16px;
    font-weight: 600;
    line-height: 1.25;
    /* Anker aus der Sidebar duerfen nicht unter der Sticky-Toolbar landen */
    scroll-margin-top: 56px;
}}
.markdown-body h1 {{ font-size: 2em; border-bottom: 1px solid #eaecef; padding-bottom: 0.3em; }}
.markdown-body h2 {{ font-size: 1.5em; border-bottom: 1px solid #eaecef; padding-bottom: 0.3em; }}
.markdown-body h3 {{ font-size: 1.25em; }}
.markdown-body p {{ margin-top: 0; margin-bottom: 16px; }}
.markdown-body code {{
    padding: 0.2em 0.4em;
    background-color: rgba(27,31,35,0.05);
    border-radius: 3px;
    font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
    font-size: 85%;
}}
.markdown-body pre {{
    padding: 16px;
    overflow: auto;
    font-size: 85%;
    line-height: 1.45;
    background-color: #f6f8fa;
    border-radius: 6px;
    border: 1px solid #e1e4e8;
}}
.markdown-body pre code {{
    background: transparent;
    padding: 0;
    border: none;
    font-size: 100%;
}}
.markdown-body blockquote {{
    margin: 0 0 16px 0;
    padding: 0 1em;
    color: #6a737d;
    border-left: 0.25em solid #dfe2e5;
}}
.markdown-body table {{
    border-collapse: collapse;
    border-spacing: 0;
    display: block;
    width: max-content;
    max-width: 100%;
    overflow: auto;
    margin-bottom: 16px;
}}
.markdown-body table th, .markdown-body table td {{
    padding: 6px 13px;
    border: 1px solid #dfe2e5;
}}
.markdown-body table tr {{
    background-color: #ffffff;
    border-top: 1px solid #c6cbd1;
}}
.markdown-body table tr:nth-child(2n) {{
    background-color: #f6f8fa;
}}
.markdown-body img {{
    max-width: 100%;
    box-sizing: border-box;
}}
.markdown-body a {{
    color: #0366d6;
    text-decoration: none;
}}
.markdown-body a:hover {{
    text-decoration: underline;
}}
.markdown-body ul, .markdown-body ol {{
    padding-left: 2em;
    margin-bottom: 16px;
}}
.markdown-body li + li {{
    margin-top: 0.25em;
}}
.markdown-body del {{
    text-decoration: line-through;
}}
.markdown-body hr {{
    height: 0.25em;
    padding: 0;
    margin: 24px 0;
    background-color: #e1e4e8;
    border: 0;
}}
"""

CSS_DARK = """
body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    font-size: {font_size}px;
    line-height: 1.6;
    color: #c9d1d9;
    background-color: #0d1117;
}}
/* Zweispaltiges Grundlayout: links die Inhaltsverzeichnis-Sidebar, rechts der
   Text. Der Wrapper ist immer vorhanden, damit Server-Toolbar-Injektion und
   CSS auch ohne Sidebar dieselbe Struktur vorfinden. */
.md-page {{
    max-width: 90%;
    margin: 0 auto;
    padding: 20px 40px;
    display: flex;
    align-items: flex-start;
    gap: 32px;
}}
.md-content {{
    flex: 1 1 auto;
    min-width: 0;
}}
.md-toc {{
    position: sticky;
    top: 0;
    flex: 0 0 240px;
    align-self: flex-start;
    max-height: 100vh;
    overflow-y: auto;
    font-size: 0.9em;
    padding-right: 12px;
    border-right: 1px solid #21262d;
}}
.md-toc ul {{
    list-style: none;
    margin: 0;
    padding-left: 0.9em;
}}
.md-toc li {{
    margin: 0.15em 0;
}}
.md-toc a {{
    color: #58a6ff;
}}
.md-toc a:hover {{
    text-decoration: underline;
}}
@media (max-width: 900px) {{
    .md-page {{ display: block; }}
    .md-toc {{ display: none; }}
}}
.markdown-body h1, .markdown-body h2, .markdown-body h3,
.markdown-body h4, .markdown-body h5, .markdown-body h6 {{
    margin-top: 24px;
    margin-bottom: 16px;
    font-weight: 600;
    line-height: 1.25;
    color: #c9d1d9;
    /* Anker aus der Sidebar duerfen nicht unter der Sticky-Toolbar landen */
    scroll-margin-top: 56px;
}}
.markdown-body h1 {{ font-size: 2em; border-bottom: 1px solid #21262d; padding-bottom: 0.3em; }}
.markdown-body h2 {{ font-size: 1.5em; border-bottom: 1px solid #21262d; padding-bottom: 0.3em; }}
.markdown-body h3 {{ font-size: 1.25em; }}
.markdown-body p {{ margin-top: 0; margin-bottom: 16px; }}
.markdown-body code {{
    padding: 0.2em 0.4em;
    background-color: rgba(110,118,129,0.2);
    border-radius: 3px;
    font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
    font-size: 85%;
}}
.markdown-body pre {{
    padding: 16px;
    overflow: auto;
    font-size: 85%;
    line-height: 1.45;
    background-color: #161b22;
    border-radius: 6px;
    border: 1px solid #30363d;
}}
.markdown-body pre code {{
    background: transparent;
    padding: 0;
    border: none;
    font-size: 100%;
    color: #c9d1d9;
}}
.markdown-body blockquote {{
    margin: 0 0 16px 0;
    padding: 0 1em;
    color: #8b949e;
    border-left: 0.25em solid #30363d;
}}
.markdown-body table {{
    border-collapse: collapse;
    border-spacing: 0;
    display: block;
    width: max-content;
    max-width: 100%;
    overflow: auto;
    margin-bottom: 16px;
}}
.markdown-body table th, .markdown-body table td {{
    padding: 6px 13px;
    border: 1px solid #30363d;
}}
.markdown-body table tr {{
    background-color: #0d1117;
    border-top: 1px solid #21262d;
}}
.markdown-body table tr:nth-child(2n) {{
    background-color: #161b22;
}}
.markdown-body img {{
    max-width: 100%;
    box-sizing: border-box;
}}
.markdown-body a {{
    color: #58a6ff;
    text-decoration: none;
}}
.markdown-body a:hover {{
    text-decoration: underline;
}}
.markdown-body ul, .markdown-body ol {{
    padding-left: 2em;
    margin-bottom: 16px;
}}
.markdown-body li + li {{
    margin-top: 0.25em;
}}
.markdown-body del {{
    text-decoration: line-through;
}}
.markdown-body hr {{
    height: 0.25em;
    padding: 0;
    margin: 24px 0;
    background-color: #21262d;
    border: 0;
}}
"""

# Wird hinter CSS_LIGHT/CSS_DARK gehaengt und greift nur beim PDF-Export
# (QWebEnginePage.printToPdf in md_dis.py). Ersetzt das Dark-Theme durch die
# helle Palette, damit die PDF auf Papier und am Bildschirm gleich gut
# lesbar ist, und sorgt fuer sinnvolle Seitenumbrueche.
CSS_PRINT = """
@media print {{
    html, body {{
        background: #ffffff !important;
        color: #24292e !important;
        /* Zoom wirkt nur auf die Ansicht (setZoomFactor), printToPdf ignoriert
           ihn. Die feste Groesse haelt das PDF unabhaengig vom Bildschirm-Zoom. */
        font-size: 16px !important;
        /* Seitenrand kommt aus QPageLayout, nicht aus dem body-Padding */
        max-width: 100% !important;
        margin: 0 !important;
        padding: 0 !important;
    }}
    /* Die Inhaltsverzeichnis-Sidebar ist eine Bildschirmhilfe und gehoert nicht
       ins PDF: Layout zurueck auf einspaltig, Sidebar ausblenden. */
    .md-page {{
        display: block !important;
        max-width: 100% !important;
        margin: 0 !important;
        padding: 0 !important;
    }}
    .md-toc {{
        display: none !important;
    }}
    /* Chromium druckt Hintergruende nur auf ausdrueckliche Anforderung */
    html, body, .markdown-body, pre, code, table, tr, th, td, .frontmatter {{
        -webkit-print-color-adjust: exact;
        print-color-adjust: exact;
    }}
    .markdown-body h1, .markdown-body h2, .markdown-body h3,
    .markdown-body h4, .markdown-body h5, .markdown-body h6 {{
        color: #24292e !important;
        break-after: avoid;
        page-break-after: avoid;
    }}
    .markdown-body h1, .markdown-body h2 {{
        border-bottom-color: #eaecef !important;
    }}
    .markdown-body a {{
        color: #0366d6 !important;
    }}
    .markdown-body hr {{
        background-color: #e1e4e8 !important;
    }}
    .markdown-body code {{
        background-color: rgba(27,31,35,0.05) !important;
    }}
    .markdown-body pre {{
        background-color: #f6f8fa !important;
        border-color: #e1e4e8 !important;
        color: #24292e !important;
        /* overflow: auto wuerde den Block am Seitenrand beschneiden */
        overflow: visible !important;
        break-inside: avoid;
        page-break-inside: avoid;
    }}
    /* Das Dark-Theme setzt die Code-Farbe an pre code, nicht an pre –
       ohne diese Zeile bleibt der Codeblock hellgrau auf hellgrau. */
    .markdown-body pre code, .markdown-body pre > code {{
        color: #24292e !important;
    }}
    .markdown-body blockquote {{
        color: #6a737d !important;
        border-left-color: #dfe2e5 !important;
        break-inside: avoid;
        page-break-inside: avoid;
    }}
    /* display:block und overflow:auto verhindern sonst den Seitenumbruch
       innerhalb einer Tabelle und schneiden breite Spalten ab */
    .markdown-body table {{
        display: table !important;
        width: 100% !important;
        max-width: 100% !important;
        overflow: visible !important;
    }}
    .markdown-body table th, .markdown-body table td {{
        border-color: #dfe2e5 !important;
    }}
    .markdown-body table tr {{
        background-color: #ffffff !important;
        border-top-color: #c6cbd1 !important;
        break-inside: avoid;
        page-break-inside: avoid;
    }}
    .markdown-body table tr:nth-child(2n) {{
        background-color: #f6f8fa !important;
    }}
    /* Die Frontmatter-Box setzt Inline-Styles, die nur !important ueberstimmt */
    .frontmatter {{
        background: #f6f8fa !important;
        border-color: #e1e4e8 !important;
        break-inside: avoid;
        page-break-inside: avoid;
    }}
    /* PlantUML und Mermaid werden als Inline-SVG eingefuegt */
    .markdown-body svg {{
        display: block !important;
        max-width: 100% !important;
        height: auto !important;
        margin: 0 auto;
        break-inside: avoid;
        page-break-inside: avoid;
    }}
    .markdown-body img {{
        max-width: 100% !important;
        height: auto !important;
        break-inside: avoid;
        page-break-inside: avoid;
    }}
}}
"""


JAR_NAME = "plantuml.jar"
PLANTUML_JAR_ENV = "MD_DIS_PLANTUML_JAR"


def get_base_dir() -> Path:
    """Get the base directory of the application."""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).parent


def get_cache_dir() -> Path:
    """Benutzerlokales Verzeichnis fuer mitgelieferte Hilfsdateien (z. B. plantuml.jar)."""
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    return Path(base) / "md-dis" if base else get_base_dir()


def get_jar_search_dirs() -> list[Path]:
    """Orte, an denen plantuml.jar gesucht wird – in dieser Prioritaet.

    1. explizit gesetzte Umgebungsvariable MD_DIS_PLANTUML_JAR
    2. Programmverzeichnis (Exe-Ordner bei frozen, sonst Skriptordner)
    3. Benutzer-Cache (%LOCALAPPDATA%\\md-dis)
    """
    candidates = []
    override = os.environ.get(PLANTUML_JAR_ENV)
    if override:
        candidates.append(Path(override).expanduser())
    candidates.append(get_base_dir())
    candidates.append(get_cache_dir())

    dirs = []
    for d in candidates:
        try:
            resolved = d.resolve()
        except OSError:
            continue
        if resolved not in dirs:
            dirs.append(resolved)
    return dirs


def get_plantuml_jar_path() -> str | None:
    """Findet plantuml.jar in einem der Suchverzeichnisse (siehe get_jar_search_dirs)."""
    for d in get_jar_search_dirs():
        jar = d / JAR_NAME
        try:
            if jar.is_file() and jar.stat().st_size > 0:
                return str(jar)
        except OSError:
            continue
    return None


# Gefundene Programmpfade (nur Treffer, damit eine spätere Installation erkannt wird)
_found_tools = {}


def find_java() -> str | None:
    """Locate a usable java executable (cached after the first hit)."""
    if "java" not in _found_tools:
        path = _locate_java()
        if not path:
            return None
        _found_tools["java"] = path
    return _found_tools["java"]


def _locate_java() -> str | None:
    """Locate a usable java executable: PATH, JAVA_HOME, and common install dirs."""
    candidate = shutil.which("java")
    if candidate:
        return candidate

    candidates = []
    home = os.environ.get("JAVA_HOME")
    if home:
        candidates.append(os.path.join(home, "bin", "java.exe"))
        candidates.append(os.path.join(home, "bin", "java"))

    candidates.append(r"C:\Program Files\Common Files\Oracle\Java\javapath\java.exe")

    for base in (r"C:\Program Files\Java",
                 r"C:\Program Files (x86)\Java",
                 r"C:\Program Files\Eclipse Adoptium",
                 r"C:\Program Files\Zulu",
                 r"C:\Program Files\Microsoft"):
        latest = os.path.join(base, "latest", "bin", "java.exe")
        if os.path.isfile(latest):
            candidates.append(latest)
        if os.path.isdir(base):
            for entry in sorted(os.listdir(base), reverse=True):
                p = os.path.join(base, entry, "bin", "java.exe")
                if os.path.isfile(p):
                    candidates.append(p)
                    break

    for p in candidates:
        if os.path.isfile(p):
            return p
    return None


def check_java_available() -> bool:
    """Check if Java is available on the system."""
    java = find_java()
    if not java:
        return False
    try:
        kwargs = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
        result = subprocess.run(
            [java, "-version"],
            capture_output=True,
            stdin=subprocess.DEVNULL,
            timeout=10,
            **kwargs
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _jar_download_target() -> Path:
    """Zielverzeichnis fuer den Download: Programmordner, sonst Benutzer-Cache.

    Der Programmordner ist bei Installationen unter C:\\Program Files nicht
    beschreibbar – dann landet die JAR im Benutzer-Cache.
    """
    for d in (get_base_dir(), get_cache_dir()):
        try:
            d.mkdir(parents=True, exist_ok=True)
        except OSError:
            continue
        if os.access(d, os.W_OK):
            return d
    return get_cache_dir()


def download_plantuml_jar(progress_callback=None) -> bool:
    """Download plantuml.jar from GitHub releases.

    Ziel: das Programmverzeichnis, falls beschreibbar, sonst der Benutzer-Cache.
    Versuch optionaler SHA256-Integritätsprüfung (falls plantuml.jar.sha256 existiert).
    """
    if get_plantuml_jar_path():
        return True

    jar_url = "https://github.com/plantuml/plantuml/releases/latest/download/plantuml.jar"
    sha_url = "https://github.com/plantuml/plantuml/releases/latest/download/plantuml.jar.sha256"
    target_path = _jar_download_target() / JAR_NAME
    tmp_path = target_path.with_name(JAR_NAME + ".part")
    sha_tmp_path = target_path.with_name(JAR_NAME + ".sha256.part")

    def _say(msg):
        if progress_callback:
            progress_callback(msg)

    expected_sha = None
    try:
        _say("Prüfe SHA256-Prüfsumme (optional)...")
        req_sha = urllib.request.Request(
            sha_url,
            headers={"User-Agent": f"md-dis/{VERSION}"}
        )
        with urllib.request.urlopen(req_sha, timeout=60) as resp_sha:
            sha_data = resp_sha.read().strip()
        try:
            sha_text = sha_data.decode("utf-8", errors="replace").strip()
        except Exception:
            sha_text = ""
        m = re.search(r"([0-9a-fA-F]{64})", sha_text)
        if m:
            expected_sha = m.group(1).lower()
            _say(f"Erwartete SHA256: {expected_sha}")
        else:
            _say("Keine gültige SHA256-Datei gefunden – überspringe Integritätsprüfung.")
    except Exception as e:
        _say(f"SHA256-Prüfung nicht möglich: {type(e).__name__}")
        expected_sha = None
        try:
            if sha_tmp_path.exists():
                sha_tmp_path.unlink()
        except OSError:
            pass

    try:
        _say(f"Lade plantuml.jar herunter... (Ziel: {target_path})")

        req = urllib.request.Request(
            jar_url,
            headers={"User-Agent": f"md-dis/{VERSION}"}
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = resp.read()

        if not data:
            _say("Fehler: Heruntergeladene Datei ist leer.")
            return False

        if expected_sha:
            actual_sha = hashlib.sha256(data).hexdigest()
            if actual_sha != expected_sha:
                _say(f"SHA256-Mismatch: erwartet {expected_sha}, erhalten {actual_sha}")
                try:
                    if tmp_path.exists():
                        tmp_path.unlink()
                except OSError:
                    pass
                return False
            _say("SHA256-Prüfung bestanden.")

        with open(tmp_path, 'wb') as f:
            f.write(data)
        os.replace(tmp_path, target_path)

        _say(f"plantuml.jar erfolgreich heruntergeladen ({target_path.stat().st_size} Bytes).")
        return True

    except Exception as e:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except OSError:
            pass
        try:
            if sha_tmp_path.exists():
                sha_tmp_path.unlink()
        except OSError:
            pass
        _say(f"Fehler beim Herunterladen: {type(e).__name__}: {e}")
        return False


def _diagram_error(msg: str, code: str) -> str:
    """Error box plus the diagram source (msg must already be HTML-safe)."""
    return f'<pre style="color:red;">{msg}</pre><pre>{html.escape(code)}</pre>'


# Auto-Download von plantuml.jar höchstens einmal pro Prozess versuchen
_auto_download_tried = False


def _plantuml_batch(codes: list[str], sandbox: bool = False) -> list[tuple[str, bool]]:
    """Render several PlantUML diagrams with a single JVM start.

    Returns one (html, ok) tuple per input; ok is False for error output.
    sandbox=True forbids !include & co. from reading local files or URLs.
    """
    global _auto_download_tried
    jar_path = get_plantuml_jar_path()
    if not jar_path and not _auto_download_tried:
        _auto_download_tried = True
        download_plantuml_jar()
        jar_path = get_plantuml_jar_path()
    if not jar_path:
        searched = ", ".join(html.escape(str(d)) for d in get_jar_search_dirs())
        msg = f"PlantUML: plantuml.jar nicht gefunden. Gesucht in: {searched}"
        return [(_diagram_error(msg, c), False) for c in codes]

    java = find_java()
    if not java:
        return [(_diagram_error("PlantUML: Java nicht gefunden. Bitte Java installieren.", c), False) for c in codes]

    cmd = [java]
    if sandbox:
        cmd.append("-DPLANTUML_SECURITY_PROFILE=SANDBOX")
    try:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = []
            for i, code in enumerate(codes):
                path = os.path.join(tmp, f"{i}.puml")
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(code)
                inputs.append(path)

            kwargs = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
            result = subprocess.run(
                cmd + ["-jar", jar_path, "-tsvg", "-charset", "UTF-8"] + inputs,
                capture_output=True, text=True, timeout=30 + 10 * len(codes),
                stdin=subprocess.DEVNULL,
                **kwargs
            )

            results = []
            for i, code in enumerate(codes):
                output_path = os.path.join(tmp, f"{i}.svg")
                if os.path.exists(output_path):
                    with open(output_path, 'r', encoding='utf-8') as f:
                        results.append((f.read(), True))
                else:
                    error_msg = result.stderr or result.stdout or "Unbekannter Fehler"
                    results.append((_diagram_error(f"PlantUML-Fehler:<br>{html.escape(error_msg)}", code), False))
            return results

    except subprocess.TimeoutExpired:
        return [(_diagram_error("PlantUML: Timeout beim Rendern.", c), False) for c in codes]
    except FileNotFoundError:
        return [(_diagram_error("PlantUML: Java nicht gefunden. Bitte Java installieren.", c), False) for c in codes]
    except Exception as e:
        return [(_diagram_error(f"PlantUML-Fehler: {html.escape(str(e))}", c), False) for c in codes]


def render_plantuml(code: str, sandbox: bool = True) -> str:
    """Render PlantUML code to SVG using local plantuml.jar."""
    return _plantuml_batch([code], sandbox)[0][0]


def find_mmdc():
    """Find mmdc executable (cached after the first hit)."""
    if "mmdc" not in _found_tools:
        path = _locate_mmdc()
        if not path:
            return None
        _found_tools["mmdc"] = path
    return _found_tools["mmdc"]


def _locate_mmdc():
    """Find mmdc executable."""
    for name in ("mmdc", "mmdc.cmd", "mmdc.bat"):
        path = shutil.which(name)
        if path:
            return path
    appdata = os.environ.get("APPDATA", "")
    if appdata:
        candidate = os.path.join(appdata, "npm", "mmdc.cmd")
        if os.path.isfile(candidate):
            return candidate
    return None


def _mermaid(code: str) -> tuple[str, bool]:
    """Render Mermaid code to SVG using local mmdc (mermaid-cli). Returns (html, ok)."""
    mmdc_path = find_mmdc()
    if not mmdc_path:
        return _diagram_error("Mermaid: mmdc nicht gefunden. Bitte installieren: npm install -g @mermaid-js/mermaid-cli", code), False

    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.mmd', delete=False, encoding='utf-8') as f:
            f.write(code)
            input_path = f.name
        output_path = input_path.replace('.mmd', '.svg')

        cmd = [mmdc_path, "-i", input_path, "-o", output_path, "-b", "transparent"]
        kwargs = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
        if os.name == "nt" and mmdc_path.lower().endswith((".cmd", ".bat", ".ps1")):
            cmd = ["cmd", "/c"] + cmd

        result = subprocess.run(
            cmd,
            capture_output=True,
            stdin=subprocess.DEVNULL,
            timeout=60,
            **kwargs
        )

        if os.path.exists(output_path):
            with open(output_path, 'r', encoding='utf-8') as f:
                svg_content = f.read()
            os.unlink(output_path)
            os.unlink(input_path)
            return svg_content, True
        else:
            if os.path.exists(input_path):
                os.unlink(input_path)
            error_msg = (result.stderr or result.stdout or b"Unbekannter Fehler").decode("utf-8", errors="replace")
            return _diagram_error(f"Mermaid-Fehler:<br>{html.escape(error_msg)}", code), False

    except subprocess.TimeoutExpired:
        return _diagram_error("Mermaid: Timeout beim Rendern.", code), False
    except FileNotFoundError:
        return _diagram_error("Mermaid: mmdc nicht gefunden. Bitte installieren: npm install -g @mermaid-js/mermaid-cli", code), False
    except Exception as e:
        return _diagram_error(f"Mermaid-Fehler: {html.escape(str(e))}", code), False


def render_mermaid(code: str) -> str:
    """Render Mermaid code to SVG using local mmdc (mermaid-cli)."""
    return _mermaid(code)[0]


def _join_wrapped(head: str, tail: str) -> str:
    """Fuegt Inhalt und Folge zusammen, ohne sie ohne Trenner ankleben zu lassen."""
    if head and tail:
        return head + "\n" + tail
    return head + tail


def strip_frontmatter(md_text: str) -> tuple[str, str]:
    """Strip YAML frontmatter from markdown text.

    Handles two cases:
    1. Standard YAML frontmatter: --- ... ---
    2. Wrapped in markdown code block: ```markdown ... ```

    Returns (frontmatter, content) tuple.
    Content includes everything after the wrapper (e.g. PlantUML blocks).
    """
    # Case 1: Content wrapped in markdown code block.
    # 'markdown' ist Pflicht, sonst wuerde jeder nackte ```-Fence am Dateianfang
    # mit-entpackt und der Code als Markdown gerendert. [^\S\n] statt \s, damit der
    # horizontale Whitespace nicht ueber Zeilengrenzen greift, und \n* statt \n?,
    # damit die Folgezeile nicht an den Code angeklebt wird ("code# Titel") und die
    # Huelle auch am Dokumentende noch greift.
    wrapped_pattern = r'^```markdown[^\S\n]*\n(.*?)\n```[^\S\n]*\n*(.*)'
    match = re.match(wrapped_pattern, md_text, re.DOTALL)
    if match:
        inner_content = match.group(1)
        remaining = match.group(2)
        # Check if inner content has YAML frontmatter
        fm_pattern = r'^---\s*\n(.*?)\n---\s*\n'
        fm_match = re.match(fm_pattern, inner_content, re.DOTALL)
        if fm_match:
            frontmatter = fm_match.group(1).strip()
            content = _join_wrapped(inner_content[fm_match.end():], remaining)
            return frontmatter, content
        # No frontmatter, just return the inner content + remaining
        return "", _join_wrapped(inner_content, remaining)

    # Case 2: Standard YAML frontmatter at start of file
    pattern = r'^---\s*\n(.*?)\n---\s*\n'
    match = re.match(pattern, md_text, re.DOTALL)
    if match:
        frontmatter = match.group(1).strip()
        content = md_text[match.end():]
        return frontmatter, content

    return "", md_text


# Indikator fuer YAML-Block-Scalare: "key: >", "key: |", "key: >-", "key: |2", ...
# (ggf. mit Chomping- und Einrueckungs-Indikator sowie Kommentar)
_FM_BLOCK_RE = re.compile(r'^([>|])(?:[+-]?\d*|\d*[+-]?)?\s*(?:#.*)?$')


def _parse_frontmatter_pairs(frontmatter: str) -> list[tuple[str, str]]:
    """Einfache YAML-Auswertung der Frontmatter fuer die Info-Box.

    Versteht gewoehnliche Skalare (ggf. mehrzeilig gefaltet), Block-Skalare mit
    folded/literal-Style ("key: >" bzw. "key: |", inkl. Chomping- und
    Einrueckungs-Indikator) sowie Listen unter einem Key. Kein vollstaendiger
    YAML-Parser - nur das, was in Frontmatter-Bloecken real vorkommt.
    """
    pairs: list[tuple[str, str]] = []
    lines = frontmatter.split('\n')
    i, n = 0, len(lines)
    while i < n:
        raw = lines[i]
        i += 1
        if not raw.strip() or raw.lstrip().startswith('#'):
            continue
        if raw[0].isspace():
            # Einrueckzeile ohne vorausgegangenen Key - ignorieren
            continue
        key, sep, rest = raw.partition(':')
        if not sep or not key.strip():
            continue
        key = key.strip()
        rest = rest.strip()

        block = _FM_BLOCK_RE.match(rest)
        if block:
            # Block-Scalar: alle folgenden eingerueckten (bzw. leeren) Zeilen
            # gehoeren zum Wert. folded (">") fuegt die Zeilen mit Leerzeichen
            # zusammen, literal ("|") behaelt die Zeilenumbrueche.
            style = block.group(1)
            collected: list[str] = []
            while i < n and (not lines[i].strip() or lines[i][0].isspace()):
                collected.append(lines[i].strip())
                i += 1
            if style == '>':
                value = ' '.join(c for c in collected if c)
            else:
                value = '\n'.join(collected).strip('\n')
        elif not rest and i < n and lines[i][:1].isspace() \
                and lines[i].lstrip().startswith('-'):
            # Liste unter dem Key: "- a", "- b" -> "a, b"
            items = []
            while i < n and lines[i][:1].isspace() \
                    and lines[i].lstrip().startswith('-'):
                items.append(lines[i].lstrip()[1:].strip())
                i += 1
            value = ', '.join(items)
        else:
            # Gewoehnlicher Skalar, ggf. mit eingerueckten Fortsetzungszeilen
            value = rest
            while i < n and lines[i].strip() and lines[i][:1].isspace():
                value += ' ' + lines[i].strip()
                i += 1
            value = value.strip().strip('"').strip("'")

        if key and value:
            pairs.append((key, value))
    return pairs


def render_frontmatter_html(frontmatter: str, dark_mode: bool = False) -> str:
    """Render YAML frontmatter as a styled info box."""
    if not frontmatter:
        return ""

    rows = []
    for key, value in _parse_frontmatter_pairs(frontmatter):
        value_html = html.escape(value).replace('\n', '<br>')
        rows.append(f'<tr><td class="fm-key">{html.escape(key)}</td><td class="fm-value">{value_html}</td></tr>')

    if not rows:
        return ""

    bg_color = "#161b22" if dark_mode else "#f6f8fa"
    border_color = "#30363d" if dark_mode else "#e1e4e8"
    text_color = "#c9d1d9" if dark_mode else "#24292e"
    key_color = "#8b949e" if dark_mode else "#6a737d"

    return f'''<div class="frontmatter" style="background:{bg_color}; border:1px solid {border_color}; border-radius:6px; padding:12px 16px; margin-bottom:24px;">
<table style="border-collapse:collapse; width:100%; font-size:0.9em;">
{"".join(rows)}
</table>
</div>'''


# Cache fertiger Diagramm-SVGs (unabhängig von Theme/Zoom), Schlüssel (art, sandbox, code)
SVG_CACHE_MAX = 256
_svg_cache = OrderedDict()
_svg_cache_lock = threading.Lock()


def _cache_get(key):
    with _svg_cache_lock:
        svg = _svg_cache.get(key)
        if svg is not None:
            _svg_cache.move_to_end(key)
        return svg


def _cache_put(key, svg):
    with _svg_cache_lock:
        _svg_cache[key] = svg
        _svg_cache.move_to_end(key)
        while len(_svg_cache) > SVG_CACHE_MAX:
            _svg_cache.popitem(last=False)


# Explizite Einbettung: ![[pfad/zur/grafik.png]] und ![[grafik.png|Alternativtext]]
# ergeben ein <img>. Bewusst als InlineProcessor und nicht als Regex-Vorabpass auf
# dem Markdown-Text: Inline-Prozessoren laufen nicht in Code-Fences oder in
# Inline-Code, ein Vorabpass dagegen schon (vgl. PlantUML/Mermaid weiter unten).
EMBED_IMAGE_PATTERN = r"\!\[\[([^\]\|]+)(?:\|([^\]]*))?\]\]"

# Bewusst identisch zu IMAGE_SUFFIXES in md_dis_server.py, damit GUI und Server
# dieselben Dateien als Bild behandeln. Fuer andere Formate bleibt ![[...]] bei
# sichtbarem Text stehen; die gewoehnliche ![...](...)-Syntax bettet weiterhin
# beliebige Formate ein.
EMBED_IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp")


class EmbedImageProcessor(InlineProcessor):
    """Wandelt ![[datei.png]] in ein <img>-Element."""

    def handleMatch(self, m, data):
        target = m.group(1).strip()
        # Kein Bildformat: nichts einbetten, der Text bleibt sichtbar.
        if not target.lower().endswith(EMBED_IMAGE_SUFFIXES):
            return None, None, None
        el = etree.Element("img")
        el.set("src", target)
        # alt immer setzen - ein fehlendes alt liest ein Screenreader als
        # Dateinamen vor, das eingebaute Bildmuster von Python-Markdown
        # verhaelt sich genauso.
        el.set("alt", (m.group(2) or "").strip())
        return el, m.start(0), m.end(0)


def _slugify(text: str) -> str:
    """Anker wie die toc-Extension bilden.

    Nutzt bewusst denselben Slugify mit demselben Trenner wie die Extension,
    die die Heading-ids vergibt. Eine eigene Implementierung wich bei
    Unterstrichen ab ("a_b c" -> "a-b-c" statt "a_b-c"), wodurch
    [[Datei#Abschnitt]]-Links das Ziel verfehlten.
    """
    return _toc_slugify(text, '-')


WIKILINK_PATTERN = r'(?<!\!)\[\[([^\]\|#]+?)(?:#([^\]\|]+))?(?:\|([^\]]+))?\]\]'


class WikiLinkProcessor(InlineProcessor):
    """Wandelt [[Datei]] bzw. [[Datei#Abschnitt|Alias]] in <a>-Links um."""

    def __init__(self, pattern, md=None, base_path=None):
        super().__init__(pattern, md)
        self.base_path = base_path

    def handleMatch(self, m, data):
        target_raw = (m.group(1) or '').strip()
        anchor_raw = (m.group(2) or '').strip()
        alias = (m.group(3) or '').strip()

        if not target_raw:
            return None, None, None

        # Ziel normalisieren: füge .md hinzu, falls keine Dateiendung
        target = target_raw
        # Prüfe, ob bereits eine Erweiterung vorhanden ist
        p = Path(target)
        if not p.suffix:
            target = target + '.md'

        # Anker anhängen falls vorhanden
        href = target
        if anchor_raw:
            href = target + '#' + _slugify(anchor_raw)

        # Anzeigetext bestimmen
        if alias:
            link_text = alias
        else:
            link_text = Path(target_raw).name
            link_text_p = Path(link_text)
            if link_text_p.suffix == '.md':
                link_text = link_text[:-3]

        el = etree.Element('a')
        el.set('href', href)
        el.text = link_text
        return el, m.start(0), m.end(0)


# Fence-Zeile nach CommonMark: bis zu 3 Leerzeichen Einrueckung, dann ``` bzw.
# ~~~ (mindestens 3), dann der Info-String. Bei Backtick-Fences darf der
# Info-String keine Backticks enthalten.
_FENCE_RE = re.compile(r'^ {0,3}(`{3,}|~{3,})(.*)$')


def _fence_info(line: str) -> tuple[str, int, str] | None:
    """Zerlegt eine Fence-Zeile in (Zeichen, Laenge, Info-String) oder None."""
    m = _FENCE_RE.match(line)
    if not m:
        return None
    fence, info = m.group(1), m.group(2)
    if fence[0] == '`' and '`' in info:
        return None
    return fence[0], len(fence), info.strip()


def _extract_diagram_blocks(md_text: str) -> tuple[str, dict[str, str], dict[str, str]]:
    """Zieht PlantUML-/Mermaid-Fences aus dem Text und ersetzt sie durch Keys.

    Arbeitet zeilen- und zustandsbasiert ueber Fences. Ein ```plantuml-Beispiel
    *innerhalb* eines anderen Code-Blocks wird dadurch nicht als Diagramm
    ausgefuehrt - der fruehere ``re.sub``-Vorabpass tat genau das, weil er den
    ganzen Text ohne Fence-Kontext durchsuchte. Liefert
    ``(neuer_text, plantuml_blocks, mermaid_blocks)``; die Keys sind ueber beide
    Maps eindeutig.
    """
    lines = md_text.split('\n')
    plantuml_blocks: dict[str, str] = {}
    mermaid_blocks: dict[str, str] = {}
    out: list[str] = []
    counter = 0
    i, n = 0, len(lines)
    while i < n:
        opening = _fence_info(lines[i])
        if opening is None:
            out.append(lines[i])
            i += 1
            continue
        char, length, info = opening
        # Ende des Blocks suchen: gleiches Zeichen, mindestens so lang, ohne Info.
        j = i + 1
        closed = False
        while j < n:
            closing = _fence_info(lines[j])
            if closing and closing[0] == char and closing[1] >= length and closing[2] == "":
                closed = True
                break
            j += 1
        lang = info.split()[0].lower() if info else ""
        if closed and lang in ("plantuml", "mermaid"):
            code = "\n".join(lines[i + 1:j])
            if lang == "plantuml":
                key = f"__PLANTUML_{counter}__"
                plantuml_blocks[key] = code
            else:
                key = f"__MERMAID_{counter}__"
                mermaid_blocks[key] = code
            counter += 1
            out.append(f"```text\n{key}\n```")
            i = j + 1
        elif closed:
            out.extend(lines[i:j + 1])
            i = j + 1
        else:
            # Unabgeschlossener Fence: bis zum Dokumentende unveraendert lassen.
            out.extend(lines[i:])
            i = n
    return "\n".join(out), plantuml_blocks, mermaid_blocks


def markdown_to_html(md_text: str, dark_mode: bool = False, zoom_level: float = 1.0, progress_callback=None,
                     sandbox: bool = False, toc: bool = False, base_path: Path | str | None = None) -> str:
    """Convert markdown text to full HTML page.

    sandbox=True renders PlantUML without access to local files/URLs (for untrusted input).
    toc=True haengt links ein sticky Inhaltsverzeichnis aus den Ueberschriften
    h1-h3 an (sofern das Dokument welche hat).
    """

    # Strip YAML frontmatter if present
    frontmatter, md_text = strip_frontmatter(md_text)

    # Extract PlantUML/Mermaid blocks BEFORE markdown conversion
    # (otherwise pygments/codehilite overwrites the language class). Der Parser
    # respektiert Code-Fences, damit Beispiel-Snippets in anderen Code-Bloecken
    # unberuehrt bleiben.
    md_text, plantuml_blocks, mermaid_blocks = _extract_diagram_blocks(md_text)

    extensions = [
        'markdown.extensions.fenced_code',
        'markdown.extensions.codehilite',
        'markdown.extensions.tables',
        'markdown.extensions.toc',
        'markdown.extensions.nl2br',
        'markdown.extensions.sane_lists',
    ]
    extension_configs = {
        'markdown.extensions.codehilite': {
            'css_class': 'highlight',
            'guess_lang': True,
        },
        # Verzeichnis nur bis Ebene 3; die Extension vergibt zugleich die ids
        # der Ueberschriften, damit die Anker der Sidebar ziehen.
        'markdown.extensions.toc': {
            'toc_depth': '1-3',
            'anchorlink': False,
            'permalink': False,
        },
    }

    md = markdown.Markdown(extensions=extensions, extension_configs=extension_configs)
    # Vor das eingebaute Bildmuster (Prioritaet 160), damit ![...] unberuehrt bleibt.
    md.inlinePatterns.register(EmbedImageProcessor(EMBED_IMAGE_PATTERN), "md_dis_embed", 175)
    # Wiki-Links [[...]] – niedriger als Bilder, damit ![[bild.png]] von EmbedImageProcessor gefangen wird
    md.inlinePatterns.register(WikiLinkProcessor(WIKILINK_PATTERN, md, base_path), "md_dis_wikilink", 170)
    content = md.convert(md_text)

    # Ein inline platzierter [TOC]-Marker wurde von der toc-Extension ersetzt
    # (Ergebnis traegt die Klasse "toc"); dann keine zusaetzliche Sidebar
    # erzeugen (sonst zwei Verzeichnisse im Dokument). Bewusst erst am
    # konvertierten Inhalt pruefen: Ein [TOC] in einem Code-Block ist kein
    # Marker und darf die Sidebar nicht unterdruecken (Review M9).
    has_toc_marker = '<div class="toc">' in content

    # Inhaltsverzeichnis aus den Ueberschriften (h1-h3). md.toc liefert das
    # fertige <div class="toc">...</div>; die toc-Extension vergibt dabei auch
    # die id der Ueberschriften, auf die die Anker zeigen.
    # Wichtig: md.toc ist auch ohne Ueberschriften nicht leer (leeres <ul>),
    # deshalb entscheidet md.toc_tokens. Die Sidebar ist ein eigenes <nav>,
    # damit ein inline platzierter [TOC]-Marker (Klasse "toc") nicht wie die
    # Sidebar aussieht.
    sidebar_available = bool(md.toc_tokens) and not has_toc_marker
    toc_html = f'<nav class="md-toc">{md.toc}</nav>' if (toc and sidebar_available) else ""

    # Diagramme rendern – bereits bekannte SVGs kommen aus dem Cache
    rendered = {}
    todo_plantuml = []
    todo_mermaid = []
    for key, code in plantuml_blocks.items():
        svg = _cache_get(("plantuml", sandbox, code))
        if svg is None:
            todo_plantuml.append((key, code))
        else:
            rendered[key] = svg
    for key, code in mermaid_blocks.items():
        svg = _cache_get(("mermaid", False, code))
        if svg is None:
            todo_mermaid.append((key, code))
        else:
            rendered[key] = svg

    total = len(todo_plantuml) + len(todo_mermaid)
    current = 0

    # PlantUML: alle Blöcke mit einem einzigen JVM-Start
    if todo_plantuml:
        if progress_callback:
            progress_callback(f"Rendere PlantUML ({len(todo_plantuml)} Diagramme)...", current, total)
        results = _plantuml_batch([code for _key, code in todo_plantuml], sandbox)
        for (key, code), (svg, ok) in zip(todo_plantuml, results):
            rendered[key] = svg
            if ok:
                _cache_put(("plantuml", sandbox, code), svg)
        current += len(todo_plantuml)

    # Mermaid: jeder mmdc-Aufruf startet einen Browser – parallel ausführen
    if todo_mermaid:
        max_workers = min(4, os.cpu_count() or 4)
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(_mermaid, code): (key, code) for key, code in todo_mermaid}
            for future in as_completed(futures):
                key, code = futures[future]
                svg, ok = future.result()
                rendered[key] = svg
                if ok:
                    _cache_put(("mermaid", False, code), svg)
                current += 1
                if progress_callback:
                    progress_callback(f"Rendere Mermaid ({current}/{total})...", current, total)

    for key, svg in rendered.items():
        content = content.replace(key, svg)

    # Prepend frontmatter info box if present
    fm_html = render_frontmatter_html(frontmatter, dark_mode)
    if fm_html:
        content = fm_html + content

    css = CSS_DARK if dark_mode else CSS_LIGHT
    # Print-Regeln hinten anhaengen: gleiche Spezifitaet, spaeter im Stylesheet
    # gewinnt, und der Block ist damit theme-unabhaengig hell.
    css += CSS_PRINT
    font_size = int(16 * zoom_level)
    css = css.format(font_size=font_size)

    return HTML_TEMPLATE.format(
        css=css,
        content=content,
        toc=toc_html,
        has_toc="1" if sidebar_available else "0",
    )