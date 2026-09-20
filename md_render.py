"""Gemeinsamer Render-Kern von md-dis.

Qt-freies Modul: konvertiert Markdown (inkl. PlantUML/Mermaid) zu HTML.
Wird sowohl von der Desktop-App (md_dis.py) als auch vom HTTP-Server
(md_dis_server.py) verwendet.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

import markdown

VERSION = "1.0.0"

HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
{css}
</style>
</head>
<body>
<div class="markdown-body">
{content}
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
    max-width: 90%;
    margin: 0 auto;
    padding: 20px 40px;
}}
.markdown-body h1, .markdown-body h2, .markdown-body h3,
.markdown-body h4, .markdown-body h5, .markdown-body h6 {{
    margin-top: 24px;
    margin-bottom: 16px;
    font-weight: 600;
    line-height: 1.25;
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
    max-width: 90%;
    margin: 0 auto;
    padding: 20px 40px;
}}
.markdown-body h1, .markdown-body h2, .markdown-body h3,
.markdown-body h4, .markdown-body h5, .markdown-body h6 {{
    margin-top: 24px;
    margin-bottom: 16px;
    font-weight: 600;
    line-height: 1.25;
    color: #c9d1d9;
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


def get_plantuml_jar_path() -> str | None:
    """Find plantuml.jar next to the executable or script."""
    if getattr(sys, 'frozen', False):
        base_dir = Path(sys.executable).parent
    else:
        base_dir = Path(__file__).parent
    jar_path = base_dir / "plantuml.jar"
    if jar_path.exists():
        return str(jar_path)
    return None


def get_base_dir() -> Path:
    """Get the base directory of the application."""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).parent


def find_java() -> str | None:
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


def download_plantuml_jar(progress_callback=None) -> bool:
    """Download plantuml.jar from GitHub releases."""
    jar_url = "https://github.com/plantuml/plantuml/releases/latest/download/plantuml.jar"
    target_path = get_base_dir() / "plantuml.jar"

    if target_path.exists() and target_path.stat().st_size > 0:
        return True

    try:
        if progress_callback:
            progress_callback(f"Lade plantuml.jar herunter... (Ziel: {target_path})")

        import ssl
        req = urllib.request.Request(
            jar_url,
            headers={"User-Agent": "md-dis/1.0"}
        )
        # Try with default SSL first, fall back to unverified context
        try:
            resp = urllib.request.urlopen(req, timeout=120)
        except (urllib.error.URLError, ssl.SSLError):
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            resp = urllib.request.urlopen(req, timeout=120, context=ctx)

        data = resp.read()
        resp.close()

        with open(target_path, 'wb') as f:
            f.write(data)

        if target_path.exists() and target_path.stat().st_size > 0:
            if progress_callback:
                progress_callback(f"plantuml.jar erfolgreich heruntergeladen ({target_path.stat().st_size} Bytes).")
            return True
        else:
            if progress_callback:
                progress_callback("Fehler: Heruntergeladene Datei ist leer.")
            return False

    except Exception as e:
        if progress_callback:
            progress_callback(f"Fehler beim Herunterladen: {type(e).__name__}: {e}")
        return False


def render_plantuml(code: str) -> str:
    """Render PlantUML code to SVG using local plantuml.jar."""
    jar_path = get_plantuml_jar_path()
    if not jar_path:
        # Try auto-download (silently)
        download_plantuml_jar()
        jar_path = get_plantuml_jar_path()
    if not jar_path:
        return f'<pre style="color:red;">PlantUML: plantuml.jar nicht gefunden im App-Verzeichnis ({get_base_dir()}).</pre><pre>{code}</pre>'

    java = find_java()
    if not java:
        return f'<pre style="color:red;">PlantUML: Java nicht gefunden. Bitte Java installieren.</pre><pre>{code}</pre>'

    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.puml', delete=False, encoding='utf-8') as f:
            f.write(code)
            input_path = f.name
        output_path = input_path.replace('.puml', '.svg')

        kwargs = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
        result = subprocess.run(
            [java, "-jar", jar_path, "-tsvg", input_path],
            capture_output=True, text=True, timeout=30,
            stdin=subprocess.DEVNULL,
            **kwargs
        )

        if os.path.exists(output_path):
            with open(output_path, 'r', encoding='utf-8') as f:
                svg_content = f.read()
            os.unlink(output_path)
            os.unlink(input_path)
            return svg_content
        else:
            os.unlink(input_path)
            error_msg = result.stderr or result.stdout or "Unbekannter Fehler"
            return f'<pre style="color:red;">PlantUML-Fehler:<br>{error_msg}</pre><pre>{code}</pre>'

    except subprocess.TimeoutExpired:
        return f'<pre style="color:red;">PlantUML: Timeout beim Rendern.</pre><pre>{code}</pre>'
    except FileNotFoundError:
        return f'<pre style="color:red;">PlantUML: Java nicht gefunden. Bitte Java installieren.</pre><pre>{code}</pre>'
    except Exception as e:
        return f'<pre style="color:red;">PlantUML-Fehler: {e}</pre><pre>{code}</pre>'


def extract_and_replace_plantuml(html: str) -> str:
    """Find PlantUML code blocks and replace them with rendered SVG.

    Handles both raw markdown and HTML-converted code blocks.
    """
    raw_pattern = r'```plantuml\s*\n(.*?)\n```'

    html_pattern = r'<pre><code class="language-plantuml">(.*?)</code></pre>'

    def replace_match(match):
        code = match.group(1)
        code = code.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
        code = code.replace('&#39;', "'").replace('&quot;', '"')
        return render_plantuml(code)

    html = re.sub(raw_pattern, replace_match, html, flags=re.DOTALL)
    html = re.sub(html_pattern, replace_match, html, flags=re.DOTALL)

    return html


def find_mmdc():
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


def render_mermaid(code: str) -> str:
    """Render Mermaid code to SVG using local mmdc (mermaid-cli)."""
    mmdc_path = find_mmdc()
    if not mmdc_path:
        return f'<pre style="color:red;">Mermaid: mmdc nicht gefunden. Bitte installieren: npm install -g @mermaid-js/mermaid-cli</pre><pre>{code}</pre>'

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
            return svg_content
        else:
            if os.path.exists(input_path):
                os.unlink(input_path)
            error_msg = (result.stderr or result.stdout or b"Unbekannter Fehler").decode("utf-8", errors="replace")
            return f'<pre style="color:red;">Mermaid-Fehler:<br>{error_msg}</pre><pre>{code}</pre>'

    except subprocess.TimeoutExpired:
        return f'<pre style="color:red;">Mermaid: Timeout beim Rendern.</pre><pre>{code}</pre>'
    except FileNotFoundError:
        return f'<pre style="color:red;">Mermaid: mmdc nicht gefunden. Bitte installieren: npm install -g @mermaid-js/mermaid-cli</pre><pre>{code}</pre>'
    except Exception as e:
        return f'<pre style="color:red;">Mermaid-Fehler: {e}</pre><pre>{code}</pre>'


def strip_frontmatter(md_text: str) -> tuple[str, str]:
    """Strip YAML frontmatter from markdown text.

    Handles two cases:
    1. Standard YAML frontmatter: --- ... ---
    2. Wrapped in markdown code block: ```markdown ... ```

    Returns (frontmatter, content) tuple.
    Content includes everything after the wrapper (e.g. PlantUML blocks).
    """
    # Case 1: Content wrapped in markdown code block
    wrapped_pattern = r'^```(?:markdown)?\s*\n(.*?)\n```\s*\n?(.*)'
    match = re.match(wrapped_pattern, md_text, re.DOTALL)
    if match:
        inner_content = match.group(1)
        remaining = match.group(2)
        # Check if inner content has YAML frontmatter
        fm_pattern = r'^---\s*\n(.*?)\n---\s*\n'
        fm_match = re.match(fm_pattern, inner_content, re.DOTALL)
        if fm_match:
            frontmatter = fm_match.group(1).strip()
            content = inner_content[fm_match.end():] + remaining
            return frontmatter, content
        # No frontmatter, just return the inner content + remaining
        return "", inner_content + remaining

    # Case 2: Standard YAML frontmatter at start of file
    pattern = r'^---\s*\n(.*?)\n---\s*\n'
    match = re.match(pattern, md_text, re.DOTALL)
    if match:
        frontmatter = match.group(1).strip()
        content = md_text[match.end():]
        return frontmatter, content

    return "", md_text


def render_frontmatter_html(frontmatter: str, dark_mode: bool = False) -> str:
    """Render YAML frontmatter as a styled info box."""
    if not frontmatter:
        return ""

    lines = frontmatter.split('\n')
    rows = []
    for line in lines:
        line = line.strip()
        if ':' in line:
            key, _, value = line.partition(':')
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and value:
                rows.append(f'<tr><td class="fm-key">{key}</td><td class="fm-value">{value}</td></tr>')

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


def markdown_to_html(md_text: str, dark_mode: bool = False, zoom_level: float = 1.0, progress_callback=None) -> str:
    """Convert markdown text to full HTML page."""

    # Strip YAML frontmatter if present
    frontmatter, md_text = strip_frontmatter(md_text)

    # Extract PlantUML blocks BEFORE markdown conversion
    # (otherwise pygments/codehilite overwrites the language class)
    plantuml_blocks = {}
    mermaid_blocks = {}
    counter = [0]

    def save_plantuml(match):
        key = f"__PLANTUML_{counter[0]}__"
        counter[0] += 1
        plantuml_blocks[key] = match.group(1)
        return f"```text\n{key}\n```"

    def save_mermaid(match):
        key = f"__MERMAID_{counter[0]}__"
        counter[0] += 1
        mermaid_blocks[key] = match.group(1)
        return f"```text\n{key}\n```"

    md_text = re.sub(r'```plantuml\s*\n(.*?)\n```', save_plantuml, md_text, flags=re.DOTALL)
    md_text = re.sub(r'```mermaid\s*\n(.*?)\n```', save_mermaid, md_text, flags=re.DOTALL)

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
        }
    }

    md = markdown.Markdown(extensions=extensions, extension_configs=extension_configs)
    content = md.convert(md_text)

    # Replace placeholders with rendered PlantUML SVG
    total = len(plantuml_blocks) + len(mermaid_blocks)
    current = 0
    for key, code in plantuml_blocks.items():
        current += 1
        if progress_callback and total > 0:
            progress_callback(f"Rendere PlantUML ({current}/{total})...", current, total)
        svg = render_plantuml(code)
        content = content.replace(key, svg)

    # Replace placeholders with rendered Mermaid SVG
    for key, code in mermaid_blocks.items():
        current += 1
        if progress_callback and total > 0:
            progress_callback(f"Rendere Mermaid ({current}/{total})...", current, total)
        svg = render_mermaid(code)
        content = content.replace(key, svg)

    # Prepend frontmatter info box if present
    fm_html = render_frontmatter_html(frontmatter, dark_mode)
    if fm_html:
        content = fm_html + content

    css = CSS_DARK if dark_mode else CSS_LIGHT
    font_size = int(16 * zoom_level)
    css = css.format(font_size=font_size)

    return HTML_TEMPLATE.format(
        css=css,
        content=content,
    )