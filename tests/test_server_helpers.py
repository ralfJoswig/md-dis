"""Tests für die reine Logik des HTTP-Servers (``md_dis_server.py``).

Deckt den Pfad-Resolver (Traversal-Schutz) und die Dateinamen-Bereinigung ab,
also die Stellen, an denen ein Fehler sicherheitsrelevant waere.
"""

from pathlib import Path

from md_dis_server import _sanitize_filename, resolve_within_root


class TestResolveWithinRoot:
    def test_empty_rel_returns_root(self, tmp_path):
        root = tmp_path / "root"
        root.mkdir()
        assert resolve_within_root(root, "") == root
        assert resolve_within_root(root, ".") == root

    def test_child_file_is_resolved(self, tmp_path):
        root = tmp_path / "root"
        root.mkdir()
        (root / "a.md").write_text("x", encoding="utf-8")
        assert resolve_within_root(root, "a.md") == (root / "a.md").resolve()

    def test_subdirectory_is_resolved(self, tmp_path):
        root = tmp_path / "root"
        (root / "sub").mkdir(parents=True)
        (root / "sub" / "b.md").write_text("x", encoding="utf-8")
        assert resolve_within_root(root, "sub/b.md") == (root / "sub" / "b.md").resolve()

    def test_parent_traversal_is_rejected(self, tmp_path):
        root = tmp_path / "root"
        root.mkdir()
        (tmp_path / "secret.md").write_text("x", encoding="utf-8")
        assert resolve_within_root(root, "../secret.md") is None

    def test_sibling_with_same_prefix_is_rejected(self, tmp_path):
        # Regression: Ein Praefix-Vergleich (startswith) haette "root2" als
        # innerhalb von "root" akzeptiert. relative_to lehnt es korrekt ab.
        root = tmp_path / "root"
        sibling = tmp_path / "root2"
        root.mkdir()
        sibling.mkdir()
        (sibling / "x.md").write_text("x", encoding="utf-8")
        assert resolve_within_root(root, "../root2/x.md") is None


class TestSanitizeFilename:
    def test_plain_name_is_kept(self):
        assert _sanitize_filename("test.md") == "test.md"

    def test_empty_name_falls_back(self):
        assert _sanitize_filename("") == "upload.md"

    def test_path_separators_are_removed(self):
        name = _sanitize_filename("../../evil.md")
        assert "/" not in name
        assert "\\" not in name

    def test_umlauts_are_kept(self):
        assert _sanitize_filename("größe.md") == "größe.md"

    def test_length_is_capped(self):
        assert len(_sanitize_filename("a" * 200 + ".md")) <= 80
