"""Suchleiste in der Statusleiste: darf nicht von Statusmeldungen überdeckt werden."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

QtWidgets = pytest.importorskip("PyQt6.QtWidgets")

import md_dis  # noqa: E402


@pytest.fixture
def viewer(tmp_path, monkeypatch):
    monkeypatch.setattr(md_dis, "app_dir", lambda: str(tmp_path))
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = md_dis.MarkdownViewer()
    window.show()
    yield window
    window.deleteLater()
    app.processEvents()


def test_suchleiste_bleibt_bei_statusmeldung_sichtbar(viewer):
    viewer.statusBar().showMessage("Geladen: C:/ein/sehr/langer/pfad/zur/datei.md")
    viewer._toggle_search()
    viewer.statusBar().showMessage("Geladen: C:/noch/ein/pfad.md")

    for w in (
        viewer.search_input,
        viewer.search_prev_btn,
        viewer.search_next_btn,
        viewer.search_close_btn,
    ):
        assert w.isVisible()
