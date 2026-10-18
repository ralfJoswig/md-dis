#!/usr/bin/env python3
"""md-dis-server – HTTP-Server für die Markdown-Vorschau.

Headless (ohne Qt/GUI) und baut auf dem gemeinsamen Render-Kern
md_render.py auf. Rendert Markdown-Dateien (inkl. PlantUML/Mermaid)
identisch zur Desktop-App und liefert sie per HTTP aus.

Beispiel:
    md-dis-server --port 8080 --root . --dark --watch
    md-dis-server --root . --watch README.md    # zeigt direkt diese Datei an

Client-Dateien: Über "Hochladen" (GET /upload, POST /upload) kann der
Browser eine .md-Datei an den Server schicken; sie wird unter
<Root>/uploads/ abgelegt und direkt angezeigt.
"""

import argparse
import mimetypes
import os
import re
import sys
import threading
import time
import traceback
import urllib.parse
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from md_render import VERSION, markdown_to_html

CONFIG = {}  # wird in main() gefüllt

CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
       "img-src 'self' data:; object-src 'none'; base-uri 'none'; form-action 'self'")

WATCH_JS = """(function() {
  var path = document.currentScript.dataset.path;
  var first = null;
  setInterval(function() {
    fetch("/poll?path=" + encodeURIComponent(path))
      .then(function(r) { if (r.ok) return r.text(); throw 0; })
      .then(function(t) {
        if (first === null) { first = t; return; }
        if (t !== first) { location.reload(); }
      })
      .catch(function() {});
  }, 1000);
})();
"""


class MDDisServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, server_address, handler):
        super().__init__(server_address, handler)
        self._cache = {}
        self._lock = threading.Lock()
        self._max_cache = 20
        # (Zeitstempel, HTML) der Index-Liste; siehe INDEX_CACHE_TTL.
        self._index_cache = (0.0, "")


def resolve_within_root(root: Path, rel: str) -> Path | None:
    """Resolve relativen Pfad; nur zulässig, wenn er nicht aus dem Root hinaus führt."""
    if not rel or rel in (".", "/"):
        return root
    root_real = root.resolve()
    try:
        target = (root / rel).resolve()
    except (OSError, RuntimeError):
        return None
    try:
        target.relative_to(root_real)
    except ValueError:
        return None
    return target


MD_SUFFIXES = (".md", ".markdown")
# Außer Markdown werden nur Bilder ausgeliefert (für eingebettete Grafiken)
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp")

# Größere Markdown-Dateien werden nicht gerendert (deckt sich mit dem
# Upload-Limit von 10 MB).
MAX_MD_BYTES = 10 * 1024 * 1024
# Index-Liste kurz zwischenspeichern, damit wiederholte GET / nicht jedes Mal
# den ganzen Baum durchlaufen (Watch-Clients pollen nur /poll, nicht den Index).
INDEX_CACHE_TTL = 2.0


def _is_hidden(rel: str) -> bool:
    """True, wenn ein Pfadsegment mit '.' beginnt (.git, .venv, .env, ...)."""
    return any(part.startswith(".") for part in rel.replace("\\", "/").split("/") if part)


def _toc_setting(query) -> bool:
    """Effektiver Sidebar-Zustand: ?toc=0/1 übersteuert den Server-Standard.

    Ohne (gültigen) Parameter gilt der Wert aus --no-toc / --toc.
    """
    if query:
        value = query.get("toc", [""])[0].strip().lower()
        if value in ("0", "off", "false", "nein", "aus"):
            return False
        if value in ("1", "on", "true", "ja", "an"):
            return True
    return CONFIG["toc"]


def file_stamp(path: Path) -> str:
    """Kompakter Änderungsstempel für den Watch-Modus."""
    try:
        st = path.stat()
        return f"{st.st_mtime_ns}"
    except OSError:
        return "missing"


def _parse_multipart(content_type: str, body: bytes):
    """Parst einen multipart/form-data-Body (stdlib-only, ohne cgi-Modul).

    Liefert (filename, datei_inhalt) des ersten Datei-Teils oder None.
    """
    m = re.search(r'boundary=("?)([^";]+)\1', content_type)
    if not m:
        return None
    boundary = m.group(2).encode("utf-8")
    delim = b"--" + boundary

    for chunk in body.split(delim):
        if chunk in (b"", b"\r\n", b"--", b"--\r\n"):
            continue
        if chunk.startswith(b"\r\n"):
            chunk = chunk[2:]
        head, sep, data = chunk.partition(b"\r\n\r\n")
        if not sep:
            continue
        if data.endswith(b"\r\n"):
            data = data[:-2]
        header_text = head.decode("utf-8", errors="replace")
        ff = re.search(r'filename="([^"]*)"', header_text, flags=re.IGNORECASE)
        if ff:
            return ff.group(1), data
    return None


_WINDOWS_RESERVED_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)


def _sanitize_filename(name: str) -> str:
    """Macht einen Dateinamen unbedenklich (nur Basisname, sichere Zeichen)."""
    name = name.replace("\\", "/").replace("/", " ").strip()
    name = re.sub(r'[^\w\-. ]', "_", name, flags=re.UNICODE).strip().lstrip(".")
    if not name:
        name = "upload.md"
    # Windows wertet CON/PRN/NUL/COM1 ... als Gerät, auch mit Endung ("CON.md"):
    # ein solcher Name liesse sich nicht als Datei anlegen/oeffnen.
    if name.split(".")[0].upper() in _WINDOWS_RESERVED_NAMES:
        name = "_" + name
    return name[:80]


class MDDisHandler(BaseHTTPRequestHandler):
    server_version = f"md-dis-server/{VERSION}"

    # ---------------------------------------------------------------- helpers
    def _send(self, status: int, body: bytes, content_type: str):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        # Nur Skripte vom eigenen Server (/watch.js) – blockiert Skripte aus Markdown-Inhalten
        self.send_header("Content-Security-Policy", CSP)
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, status: int, text: str, content_type="text/plain; charset=utf-8"):
        self._send(status, text.encode("utf-8"), content_type)

    def _log_req(self, status: int, start: float):
        elapsed = time.perf_counter() - start
        print(f"[md-dis-server] {self.command} {self.path} {status} ({elapsed:.2f}s)")

    def _request_allowed(self) -> bool:
        """Schutz vor DNS-Rebinding (Host) und CSRF (Origin bei POST)."""
        allowed = CONFIG.get("allowed_hosts")
        host = self.headers.get("Host", "")
        if allowed is not None and host not in allowed:
            return False
        origin = self.headers.get("Origin")
        if self.command == "POST" and origin is not None:
            return urllib.parse.urlsplit(origin).netloc == host
        return True

    def _send_forbidden(self):
        self._last_status = 403
        self._send_text(403, "Zugriff verweigert")

    # ------------------------------------------------------------------- GET
    def do_GET(self):
        start = time.perf_counter()
        parsed = urllib.parse.urlsplit(self.path)
        url_path = urllib.parse.unquote(parsed.path)
        query = urllib.parse.parse_qs(parsed.query)
        try:
            if not self._request_allowed():
                self._send_forbidden()
            elif url_path == "/":
                redirect = CONFIG.get("redirect")
                if redirect:
                    self._last_status = 302
                    self.send_response(302)
                    self.send_header("Location", "/" + urllib.parse.quote(redirect))
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                else:
                    self._handle_index()
            elif url_path == "/poll":
                self._handle_poll(query.get("path", [""])[0])
            elif url_path == "/upload":
                self._handle_upload_page()
            elif url_path == "/watch.js":
                self._last_status = 200
                self._send_text(200, WATCH_JS, "text/javascript; charset=utf-8")
            elif url_path.startswith("/raw/"):
                self._handle_raw(url_path[len("/raw/"):])
            else:
                self._handle_doc_or_static(url_path, start, query)
        except Exception:  # pragma: no cover – letzter Notnagel
            traceback.print_exc()
            self._last_status = 500
            self._send_text(500, "Interner Fehler")
        self._log_req(self._last_status, start)

    _last_status = 200

    # ------------------------------------------------------------------ POST
    def do_POST(self):
        start = time.perf_counter()
        parsed = urllib.parse.urlsplit(self.path)
        try:
            if not self._request_allowed():
                self._send_forbidden()
            elif parsed.path == "/upload":
                self._handle_upload_post()
            else:
                self._last_status = 404
                self._send_text(404, "Unbekannte POST-Route")
        except Exception:
            traceback.print_exc()
            self._last_status = 500
            self._send_text(500, "Interner Fehler")
        self._log_req(self._last_status, start)

    # --------------------------------------------------------- upload page
    def _handle_upload_page(self):
        dark = CONFIG["dark"]
        bg = "#0d1117" if dark else "#ffffff"
        fg = "#c9d1d9" if dark else "#24292e"
        link = "#58a6ff" if dark else "#0366d6"
        border = "#30363d" if dark else "#e1e4e8"
        html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>md-dis-server – Datei hochladen</title>
<style>
body {{ font-family: sans-serif; background:{bg}; color:{fg}; max-width: 60em; margin:0 auto; padding: 2em; }}
a {{ color:{link}; }}
h1 {{ border-bottom:1px solid {border}; padding-bottom:0.3em; }}
input[type=file] {{ display:block; margin: 12px 0; }}
button {{ font-size: 1em; padding: 6px 16px; }}
</style>
</head>
<body>
<h1>md-dis-server – Datei hochladen</h1>
<p><a href="/">&#9664; Index</a></p>
<form action="/upload" method="post" enctype="multipart/form-data">
<label for="up">Markdown-Datei auswählen:</label>
<input type="file" id="up" name="file" accept=".md,.markdown,text/markdown" required>
<button type="submit">Hochladen und anzeigen</button>
</form>
</body>
</html>
"""
        self._last_status = 200
        self._send_text(200, html, "text/html; charset=utf-8")

    def _handle_upload_post(self):
        length = int(self.headers.get("Content-Length") or 0)
        max_size = 10 * 1024 * 1024
        if length <= 0:
            self._last_status = 400
            self._send_text(400, "Keine Daten empfangen")
            return
        if length > max_size:
            self._last_status = 413
            self._send_text(413, "Datei zu groß (max. 10 MB)")
            return
        body = self.rfile.read(length)

        content_type = self.headers.get("Content-Type", "")
        if content_type.startswith("multipart/form-data"):
            uploaded = _parse_multipart(content_type, body)
        else:
            name = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get("name", ["upload.md"])[0]
            uploaded = (name, body) if body else None
        if not uploaded:
            self._last_status = 400
            self._send_text(400, "Keine Datei im Request gefunden")
            return

        filename, data = uploaded
        filename = _sanitize_filename(filename)
        if not filename.lower().endswith((".md", ".markdown")):
            self._last_status = 400
            self._send_text(400, "Nur .md- oder .markdown-Dateien erlaubt")
            return

        upload_dir = CONFIG["root"] / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        p = Path(filename)
        stem, suf = p.stem, p.suffix
        target = upload_dir / filename
        i = 1
        while target.exists():
            candidate = f"{stem}_{i}{suf}"
            target = upload_dir / candidate
            i += 1
            if i > 100:
                break
        try:
            target.write_bytes(data)
        except OSError:
            self._last_status = 500
            self._send_text(500, "Datei konnte nicht gespeichert werden")
            return

        self._last_status = 303
        rel = target.relative_to(CONFIG["root"]).as_posix()
        self.send_response(303)
        self.send_header("Location", "/" + urllib.parse.quote(rel))
        self.send_header("Content-Length", "0")
        self.end_headers()

    # ------------------------------------------------------------------ index
    def _handle_index(self):
        server: MDDisServer = self.server
        now = time.monotonic()
        with server._lock:
            stamp, cached = server._index_cache
        if cached and now - stamp < INDEX_CACHE_TTL:
            html = cached
        else:
            html = self._build_index_html()
            with server._lock:
                server._index_cache = (time.monotonic(), html)
        self._last_status = 200
        self._send_text(200, html, "text/html; charset=utf-8")

    def _build_index_html(self) -> str:
        root = CONFIG["root"]
        files = []
        for dirpath, dirs, names in os.walk(root):
            dirs[:] = [d for d in dirs if not d.startswith(".")]  # .git, .venv, ... nicht durchsuchen
            for name in names:
                if not name.startswith(".") and name.lower().endswith(MD_SUFFIXES):
                    files.append((Path(dirpath) / name).relative_to(root).as_posix())
        files.sort()
        dark = CONFIG["dark"]
        bg = "#0d1117" if dark else "#ffffff"
        fg = "#c9d1d9" if dark else "#24292e"
        link = "#58a6ff" if dark else "#0366d6"
        border = "#30363d" if dark else "#e1e4e8"

        rows = []
        for rel in files:
            safe = urllib.parse.quote(rel)
            rows.append(f'<li><a href="/{safe}">{escape(rel)}</a></li>')
        listing = "\n".join(rows) if rows else "<li><i>Keine Markdown-Dateien gefunden.</i></li>"

        return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>md-dis-server – Index</title>
<style>
body {{ font-family: sans-serif; background:{bg}; color:{fg}; max-width: 60em; margin:0 auto; padding: 2em; }}
a {{ color:{link}; }}
h1 {{ border-bottom:1px solid {border}; padding-bottom:0.3em; }}
</style>
</head>
<body>
<h1>md-dis-server – Index</h1>
<p>Wurzel: <code>{escape(str(CONFIG['root']))}</code> &mdash; Adresse: <code>{CONFIG['host']}:{CONFIG['port']}</code></p>
<p><a href="/upload">&#128229; Datei hochladen</a></p>
<ul>
{listing}
</ul>
</body>
</html>
"""

    # ------------------------------------------------------------------- poll
    def _handle_poll(self, rel: str):
        root = CONFIG["root"]
        target = None if _is_hidden(rel) else resolve_within_root(root, rel)
        if not target or not target.is_file():
            self._last_status = 404
            self._send_text(404, "missing")
            return
        self._last_status = 200
        self._send_text(200, file_stamp(target))

    # ------------------------------------------------------------------- raw
    def _handle_raw(self, rel: str):
        root = CONFIG["root"]
        target = None if _is_hidden(rel) else resolve_within_root(root, rel)
        if not target or not target.is_file() or target.suffix.lower() not in MD_SUFFIXES:
            self._last_status = 404
            self._send_text(404, f"Datei nicht gefunden: {rel}")
            return
        try:
            body = target.read_bytes()
        except OSError:
            self._last_status = 500
            self._send_text(500, "Lesefehler")
            return
        self._last_status = 200
        self._send(200, body, "text/plain; charset=utf-8")

    # ------------------------------------------------------- doc or static
    def _send_markdown(self, rel: str, target: Path, start_ns: int, toc: bool):
        dark = CONFIG["dark"]
        zoom = CONFIG["zoom"]
        # Ein Eintrag pro Datei und TOC-Zustand
        key = (str(target.resolve()), toc)
        server: MDDisServer = self.server
        with server._lock:
            entry = server._cache.get(key)
        cached = entry[1] if entry and entry[0] == start_ns else None
        if cached is None:
            try:
                if target.stat().st_size > MAX_MD_BYTES:
                    self._last_status = 413
                    self._send_text(413, "Markdown-Datei zu groß (max. 10 MB)")
                    return
                # utf-8-sig wie in der GUI: eine BOM darf die Frontmatter-
                # Erkennung nicht stoeren. errors="replace": fehlerhaft
                # kodierte Bytes loesen keinen irrefuehrenden 500er aus.
                text = target.read_text(encoding="utf-8-sig", errors="replace")
            except OSError:
                self._last_status = 500
                self._send_text(500, "Datei konnte nicht gelesen werden")
                return
            html = markdown_to_html(text, dark_mode=dark, zoom_level=zoom, sandbox=True, toc=toc)
            if CONFIG["watch"]:
                html = _inject_watch(html, rel)
            html = _inject_toolbar(html, rel, dark, toc)
            with server._lock:
                # LRU-ähnlich: entfernen falls vorhanden, dann hinten anhängen
                server._cache.pop(key, None)
                server._cache[key] = (start_ns, html)
                # Begrenzung auf max. 20 Dateien
                if len(server._cache) > getattr(server, "_max_cache", 20):
                    oldest = next(iter(server._cache))
                    server._cache.pop(oldest, None)
        else:
            with server._lock:
                # Zugriff bringt Eintrag ans "Ende" der Reihenfolge
                server._cache.pop(key, None)
                server._cache[key] = entry
            html = cached
        self._last_status = 200
        self._send_text(200, html, "text/html; charset=utf-8")

    def _handle_doc_or_static(self, url_path: str, start: float, query=None):
        root = CONFIG["root"]
        rel = url_path.lstrip("/")
        target = None if _is_hidden(rel) else resolve_within_root(root, rel)
        if not target:
            self._last_status = 404
            self._send_text(404, "Ungültiger Pfad")
            return
        if target.is_file():
            if target.suffix.lower() in MD_SUFFIXES:
                stamp = int(target.stat().st_mtime_ns)
                self._send_markdown(rel, target, stamp, _toc_setting(query))
            elif target.suffix.lower() not in IMAGE_SUFFIXES:
                self._last_status = 404
                self._send_text(404, f"Nicht gefunden: {url_path}")
            else:
                try:
                    body = target.read_bytes()
                except OSError:
                    self._last_status = 500
                    self._send_text(500, "Lesefehler")
                    return
                ctype, _enc = mimetypes.guess_type(target.name)
                self._last_status = 200
                self._send(200, body, ctype or "application/octet-stream")
        else:
            # Unterverzeichnisse (auch mit Slash) gibt es nicht als Index,
            # deshalb hier direkt 404 statt eines 301 auf "/dir/", der
            # anschliessend wieder auf sich selbst umleitete (Review M7).
            self._last_status = 404
            self._send_text(404, f"Nicht gefunden: {url_path}")

    def log_message(self, fmt, *args):  # Standard-Logging unterdrücken
        pass


def _inject_toolbar(html: str, rel: str, dark: bool, toc: bool) -> str:
    bg = "#161b22" if dark else "#f6f8fa"
    fg = "#c9d1d9" if dark else "#24292e"
    link = "#58a6ff" if dark else "#0366d6"
    border = "#30363d" if dark else "#e1e4e8"
    raw_url = f"/raw/{urllib.parse.quote(rel)}"
    index_link = ""
    if CONFIG.get("redirect") != rel:
        index_link = f'<a href="/" style="color:{link};">&#9664; Index</a>&nbsp;&nbsp;'
    # Umschalt-Link nur, wenn das Dokument überhaupt Überschriften hat. Der
    # relative Query-Link behält Pfad und Watch-Zustand bei (location.reload()).
    toc_link = ""
    if 'data-toc-has="1"' in html:
        if toc:
            toc_link = f'<a href="?toc=0" style="color:{link};">Verzeichnis ausblenden</a>&nbsp;&nbsp;'
        else:
            toc_link = f'<a href="?toc=1" style="color:{link};">Verzeichnis einblenden</a>&nbsp;&nbsp;'
    bar = (f'<div style="position:sticky;top:0;background:{bg};color:{fg};'
           f'border-bottom:1px solid {border};padding:8px 12px;margin:0 0 12px;'
           f'font-size:13px;">'
           f'{index_link}'
           f'<a href="/upload" style="color:{link};">Hochladen</a>&nbsp;&nbsp;'
           f'<a href="{raw_url}" style="color:{link};">Rohdaten</a>&nbsp;&nbsp;'
           f'{toc_link}</div>')
    if "<div class=\"markdown-body\">" in html:
        return html.replace('<div class="markdown-body">', bar + '<div class="markdown-body">', 1)
    return bar + html


def _inject_watch(html: str, rel: str) -> str:
    script = f'\n<script src="/watch.js" data-path="{escape(rel)}"></script>\n'
    return html.replace("</body>", script + "</body>", 1)


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)
        sys.stderr.reconfigure(line_buffering=True)
    ap = argparse.ArgumentParser(
        prog="md-dis-server",
        description="HTTP-Server für die Markdown-Vorschau von md-dis (headless, ohne Qt).",
    )
    ap.add_argument("--host", default="127.0.0.1",
                    help="Bind-Adresse (Standard: 127.0.0.1)")
    ap.add_argument("--port", type=int, default=8080,
                    help="Port (Standard: 8080)")
    ap.add_argument("--root", default=".",
                    help="Wurzelverzeichnis mit den Markdown-Dateien (Standard: .)")
    ap.add_argument("file", nargs="?", default=None,
                    help="Markdown-Datei, die direkt angezeigt werden soll (optional)")
    ap.add_argument("--dark", action="store_true",
                    help="Dunkles Theme wie im Client")
    ap.add_argument("--zoom", type=float, default=1.0,
                    help="Schriftgrößen-Faktor (Standard: 1.0)")
    ap.add_argument("--watch", action="store_true",
                    help="Bei Dateiänderung automatisch neu laden (Browser-polling)")
    ap.add_argument("--no-toc", dest="toc", action="store_false", default=True,
                    help="Inhaltsverzeichnis-Sidebar standardmäßig ausblenden")
    args = ap.parse_args(argv)

    root = Path(args.root).expanduser().resolve()
    if not root.is_dir():
        print(f"Fehler: --root existiert nicht oder ist kein Verzeichnis: {root}", file=sys.stderr)
        return 2

    redirect = None
    if args.file:
        file_path = Path(args.file).expanduser().resolve()
        if not file_path.is_file():
            print(f"Fehler: Datei nicht gefunden: {file_path}", file=sys.stderr)
            return 2
        try:
            rel = file_path.relative_to(root)
        except ValueError:
            print(f"Fehler: Datei liegt außerhalb von --root ({root}): {file_path}", file=sys.stderr)
            return 2
        redirect = rel.as_posix()

    server = MDDisServer((args.host, args.port), MDDisHandler)
    # Erst nach dem Binden steht der tatsaechliche Port fest: mit --port 0
    # waehlt das Betriebssystem einen freien Port. allowed_hosts muss diesen
    # Port kennen, sonst antwortet der Host-Check auf jeden Request mit 403.
    actual_port = server.server_address[1]

    CONFIG.update(
        host=args.host,
        port=actual_port,
        root=root,
        dark=args.dark,
        zoom=args.zoom,
        watch=args.watch,
        toc=args.toc,
        redirect=redirect,
        # Bei Loopback-Bindung nur localhost-Host-Header zulassen (DNS-Rebinding)
        allowed_hosts=({f"localhost:{actual_port}", f"127.0.0.1:{actual_port}", f"[::1]:{actual_port}"}
                       if args.host in ("127.0.0.1", "localhost", "::1") else None),
    )

    print(f"md-dis-server v{VERSION} – http://{args.host}:{actual_port}")
    print(f"  Wurzel: {root}")
    if redirect:
        print(f"  Datei:  {redirect} (direkte Anzeige)")
    print(f"  Theme:  {'dunkel' if args.dark else 'hell'} | Zoom: x{args.zoom} | Watch: {'an' if args.watch else 'aus'} | Verzeichnis: {'an' if args.toc else 'aus'}")
    print("  Beenden mit Strg+C.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nmd-dis-server beendet.")
    return 0


if __name__ == "__main__":
    sys.exit(main())