"""HTTP-Integrationstests für ``md_dis_server.py``.

Startet einen echten ``MDDisServer`` auf Port 0 im Hintergrund-Thread und prüft
die in den Reviews genannten Punkte: CSP ohne Fremdbilder (N6), Größenlimit und
robustes Dekodieren (M5), BOM-Toleranz (N9) sowie den Host-Schutz.
"""

import threading
import urllib.error
import urllib.request

import pytest

import md_dis_server
from md_dis_server import CONFIG, MDDisHandler, MDDisServer

# Proxy aus, sonst kann ein HTTP_PROXY in der Umgebung die Loopback-Requests
# umleiten und die Tests schlagen grundlos fehl.
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _start_server(root):
    server = MDDisServer(("127.0.0.1", 0), MDDisHandler)
    port = server.server_address[1]
    CONFIG.update(
        host="127.0.0.1",
        port=port,
        root=root,
        dark=False,
        zoom=1.0,
        watch=False,
        toc=True,
        redirect=None,
        allowed_hosts={f"localhost:{port}", f"127.0.0.1:{port}", f"[::1]:{port}"},
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, f"http://127.0.0.1:{port}"


@pytest.fixture
def server(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (root / "doc.md").write_text("# Titel\n\nText\n", encoding="utf-8")
    srv, thread, base = _start_server(root)
    try:
        yield base
    finally:
        srv.shutdown()
        srv.server_close()
        thread.join(timeout=5)


def _get(url: str, headers: dict | None = None):
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with _OPENER.open(req, timeout=5) as resp:
            return resp.status, resp.read(), dict(resp.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers)


def test_index_lists_markdown(server):
    status, body, _ = _get(server + "/")
    assert status == 200
    assert b"doc.md" in body


def test_doc_route_renders_markdown(server):
    status, body, _ = _get(server + "/doc.md")
    assert status == 200
    assert "Titel".encode() in body
    assert b"<h1" in body


def test_csp_disallows_remote_images(server):
    _, _, headers = _get(server + "/")
    csp = headers.get("Content-Security-Policy", "")
    assert "img-src 'self' data:" in csp


def test_foreign_host_is_rejected(server):
    status, _, _ = _get(server + "/", headers={"Host": "evil.example"})
    assert status == 403


def test_directory_returns_404(server):
    # Review M7: Verzeichnisse lieferten eine 301 auf sich selbst (Endlosschleife).
    root = CONFIG["root"]
    (root / "unterordner").mkdir()
    assert _get(server + "/unterordner")[0] == 404
    assert _get(server + "/unterordner/")[0] == 404



def test_oversized_markdown_returns_413(server, tmp_path, monkeypatch):
    monkeypatch.setattr(md_dis_server, "MAX_MD_BYTES", 8)
    root = CONFIG["root"]
    (root / "big.md").write_text("# " + "x" * 100, encoding="utf-8")
    status, _, _ = _get(server + "/big.md")
    assert status == 413


def test_bom_file_renders_without_bom(server):
    root = CONFIG["root"]
    (root / "bom.md").write_text(
        "---\ntitle: X\n---\n# T\n", encoding="utf-8-sig"
    )
    status, body, _ = _get(server + "/bom.md")
    assert status == 200
    assert b"\xef\xbb\xbf" not in body
    assert b'class="frontmatter"' in body


def test_invalid_utf8_does_not_500(server):
    root = CONFIG["root"]
    (root / "broken.md").write_bytes(b"# T\n\xff\xfe kaputt\n")
    status, _, _ = _get(server + "/broken.md")
    assert status == 200
