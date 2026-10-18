# md-dis

A Markdown viewer for Windows with diagram support, available in **two variants**:

| | Desktop app | HTTP server |
|---|---|---|
| File | `md_dis.py` (PyQt6 GUI) | `md_dis_server.py` (headless) |
| Interaction | Local window | Browser (index, raw, live view, upload) |
| Use case | Interactive viewing / editing workflow | Remote reading, sharing, CI, Watch |
| Current build | `dist/md-dis/` — 1.4.3 | `dist/md-dis-server/` — 1.4.4 |

Both share a single **Qt-free render core** (`md_render.py`) — same output in GUI and server.

**Status 2026-10-15:** the source is at **1.4.4** (1.4 series with the table-of-contents
sidebar and the frontmatter block-scalar fix). Both frozen builds are current again:
`dist/md-dis/` (1.4.3) and `dist/md-dis-server/` (1.4.4) include the `![[…]]` embed,
the `strip_frontmatter` fix, the TOC feature and the frontmatter fix. Newer commits on
top of 1.4.4 add **wiki links** (`[[…]]`), the optional **SHA256** check for the JAR
download and an **LRU server cache**; these are not part of a release build yet, so
`VERSION` still reads 1.4.4.

---

## Features

- GitHub-Flavored Markdown (tables, code blocks, strikethrough, lists)
- **Diagram rendering inside Markdown:**
  - **PlantUML** — via `plantuml.jar` (Java). The JAR is downloaded automatically on first use. Search order: `$MD_DIS_PLANTUML_JAR` → directory of the executable/script → `%LOCALAPPDATA%\md-dis`. The download goes to the executable directory if writable, otherwise to the user cache; if the release provides a `.sha256` checksum, the download is verified against it.
  - **Mermaid** — via `mmdc` (mermaid-cli), if installed
- Dark / light theme toggle
- Zoom (`Ctrl+` / `Ctrl-` / `Ctrl+0`, mouse wheel)
- **Image embed** — `![[pfad/grafik.png]]`, optionally `![[grafik.png|Alt-Text]]`
- **Wiki links** — `[[datei.md]]`, `[[datei.md#Abschnitt]]`, optionally `[[datei.md|Alias]]`
- **Table of contents** — a sticky sidebar generated from the headings (h1–h3), toggleable
- **PDF export** (`Ctrl+P`) with page format, orientation and margin
- File Watch with auto-reload (`F5`)
- German UI; yaml frontmatter rendered as an info box
- Headless HTTP server also supports **browser upload** of `.md` files

## Requirements

- Python 3.11+ (requirements.txt)
- Desktop app: PyQt6 + PyQt6-WebEngine
- HTTPServer: Python standard library only (no Qt)
- PlantUML diagrams: Java runtime + `plantuml.jar`
- Mermaid diagrams: `mmdc` from `@mermaid-js/mermaid-cli`

`pymupdf` is **not** a runtime dependency. It was only used in ad-hoc scripts to
measure generated PDFs and is not needed for the regression tests in `tests/`.

```bash
pip install -r requirements.txt
```

## Tests

The committed regression tests cover the pure parts of the render core
(frontmatter, block scalars, wiki links, image embeds, diagram extraction,
anchors) and the server helpers (path traversal guard, filename sanitising).
They need `pytest`:

```bash
pip install pytest
python -m pytest
```

## Usage

### Desktop app (`md-dis`)

```bash
python md_dis.py [datei.md]
```

Keyboard shortcuts:

| Keys | Action |
|---|---|
| `Ctrl+O` | Open file |
| `F5` | Reload current file |
| `Ctrl+=` / `Ctrl+-` / `Ctrl+0` | Zoom in / out / reset |
| `Ctrl+D` | Toggle dark/light |
| `Ctrl+T` | Toggle the table-of-contents sidebar |
| `Ctrl+P` | Save the preview as PDF |
| `Ctrl+F` | Search |
| `F2` | Edit file |
| `F1` | Help |
| `Esc` / `Ctrl+W` | Close / quit |

**Image embed.** `[[ … ]]` is not valid Markdown and rendered as literal text
before, so `![[grafik.png]]` is free to mean "put the image here" without
changing any existing document. Inside code blocks and inline code the syntax
stays visible as text, so it can be documented without being executed. Only
`.png`, `.jpg`, `.jpeg`, `.gif`, `.svg` and `.webp` are embedded; for anything
else the text stays visible. The result is identical to `![alt](grafik.png)`, so
the usual image syntax remains the better choice whenever a caption is wanted.
Works in the desktop app and in the server.

**Wiki links.** `[[ … ]]` links to another file or to a section inside it. A
link without a file extension gets `.md` appended, an `#Abschnitt` suffix is
resolved to the heading anchor, and the optional `|Alias` sets the visible
text. Like the image embed, the syntax is handled by an inline processor, so
inside code blocks and inline code it stays visible as text; `![[…]]` is the
image form and keeps priority over the link form. The result is an ordinary
`<a>` element, so relative paths behave the same as in any other Markdown link.
Works in the desktop app and in the server.

**Table of contents.** Every document that has headings gets a sticky sidebar
on the left with the headings h1–h3, clickable to jump to the section. It is
switched on by default; `Ctrl+T` (toolbar button "Verzeichnis") toggles it and
the choice is stored in `md-dis.ini` (`appearance/showToc`). On narrow windows
the sidebar steps aside automatically. A document that already uses the
`[TOC]` marker keeps its own inline table instead. The sidebar is a
screen-only aid and is omitted from the PDF export.

**PDF export.** `Ctrl+P` opens a dialog for page format (A4, A3, A5, Letter,
Legal, Executive, Tabloid), orientation and margin preset, then asks for the
target file. The PDF always uses a light colour scheme, independent of the
dark theme, and reproduces relative image paths, PlantUML/Mermaid diagrams and
tables. The on-screen zoom is not applied — the PDF is always laid out at
100 %.

**Settings.** Theme, zoom and the PDF options are stored in `md-dis.ini` next
to the executable, so they travel with a portable copy. If that directory is
not writable, the settings are kept in memory for the session only.

### HTTP server (`md-dis-server`)

```bash
python md_dis_server.py --root . --watch [datei.md]
```

Options:

| Option | Default | Description |
|---|---|---|
| `--host` | `127.0.0.1` | Bind address |
| `--port` | `8080` | Listen port |
| `--root` | `.` | Directory to serve |
| `--file` / positional | – | Directly display one Markdown file (redirects `/` to it) |
| `--dark` | off | Dark theme |
| `--zoom` | `1.0` | Starting zoom factor |
| `--watch` | off | Auto-reload on file change |
| `--no-toc` | – | Hide the table-of-contents sidebar (shown by default) |

Endpoints:

| Route | Description |
|---|---|
| `GET /` | Index of Markdown files (or redirect when `--file` is set) |
| `GET /<pfad>.md` | Rendered HTML (with toolbar + optional watch script). `?toc=0` / `?toc=1` toggles the table-of-contents sidebar for this request |
| `GET /raw/<pfad>` | Raw Markdown source |
| `GET /poll?path=…` | Change stamp for the watch client |
| `GET /upload` / `POST /upload` | Browser upload of `.md` files (stored under `<root>/uploads/`, max 10 MB) |

Responses carry a strict `Content-Security-Policy`: scripts only from the
server (`/watch.js`), images only same-origin or `data:` — remote images inside
a document are not loaded. Markdown files larger than 10 MB are refused with
`413`; a file with broken UTF-8 is still rendered (invalid bytes are replaced
instead of failing).

## Build

```bash
python build.py              # GUI → dist/md-dis/
python build.py --server     # Server → dist/md-dis-server/
python build.py --clean      # remove build/ + dist/ + specs first
```

Note: the frozen executables must be run from a **local** Windows path
(not a UNC/`\\wsl.localhost` path).

## Version

`MAJOR.MINOR.BUILD`, and there is exactly one place where it is written:

```python
# md_render.py
VERSION = "1.4.4"
```

Both variants import `VERSION` from the render core, so a frozen executable
always carries the version it was built with. Nothing else in the tree holds a
version number.

### Rules

| Part | Changed by | Notes |
|---|---|---|
| `MAJOR` / `MINOR` | `python build.py --set-version 2.0` | Only on request. Resets the build counter. |
| `BUILD` | every `python build.py` / `--server` | Incremented automatically by 1. |

- `--set-version` takes `MAJOR.MINOR` and starts a new series at build 1, so
  `1.1.0 → 2.0` is what you get, never `1.1.0 → 2.0.3`.
- The build number is consumed **even if the build then fails**. That is
  deliberate: two different artifacts must never end up with the same number.
- The counter is **shared** between both variants. Building the GUI at 1.2.1 and
  then the server produces 1.2.2 — the numbers keep counting up across variants
  instead of resetting per variant.
- A build **rewrites `md_render.py`**, so the version bump shows up as an
  uncommitted change. Commit it together with the feature it belongs to, or the
  source and the frozen build drift apart.
- Line endings in `md_render.py` are preserved (CRLF stays CRLF).

### Where the version shows up

| Where | What you see |
|---|---|
| Desktop: `Help` → `Über / Version` (or `F1` → About) | `md-dis <version>` plus PyQt/Qt versions and the license |
| Desktop: window properties / task manager | The version from `QApplication.setApplicationVersion` |
| Server: startup banner | `md-dis-server v<version> - http://127.0.0.1:8080` |
| Server: HTTP response header | `Server: md-dis-server/<version> Python/<x.y.z>` |

Quick check of a frozen build:

```bash
dist/md-dis-server/md-dis-server.exe --port 8080
```

The source version moves ahead of the frozen builds, so a binary reports the
version it was frozen with, not the current one. `dist/md-dis/` prints 1.4.3 and
`dist/md-dis-server/` 1.4.4 while the source is at 1.4.4.

### Changelog

| Version | Date | Changes |
|---|---|---|
| **1.4.3** | 2026-10-15 | Fixed the frontmatter info box: YAML block scalars (`key: >` folded, `key: \|` literal, incl. chomping/indentation indicators) are now resolved to their full text instead of showing only the `>`/`\|` indicator. Multi-line plain scalars and lists under a key are rendered as well. |
| **1.4.0** | 2026-10-12 | Auto table of contents: a sticky sidebar built from the headings h1–h3, clickable without JavaScript. Toggle in the desktop app (`Ctrl+T`, persisted in `md-dis.ini`) and in the server (`--no-toc`, plus a `?toc=0/1` link in the toolbar). Off screen it is hidden in the PDF export. |
| **1.3.0** | 2026-09-29 | Image embed `![[grafik.png]]` with optional `\|Alt-Text`, for `.png/.jpg/.jpeg/.gif/.svg/.webp`, in desktop app and server. Fixed `strip_frontmatter`, which unwrapped *any* document starting with a bare ` ``` ` fence and glued the following line onto the code (`code# Titel`). |
| **1.2.1** | 2026-09-29 | PDF export (`Ctrl+P`) with page format, orientation and margin presets, always light regardless of theme. Theme, zoom and PDF options persist in `md-dis.ini` next to the executable. Fixed relative image paths and `src="…"`. Dead `_render_markdown` removed. |
| **1.2.0** | 2026-09-29 | Corrected MIT license declaration in the About dialog and README. `plantuml.jar` is now searched in `$MD_DIS_PLANTUML_JAR` → program directory → `%LOCALAPPDATA%\md-dis`, downloaded atomically. Added version management to `build.py` (`--set-version`, automatic build number). |
| **1.1.0** | 2026-09-24 | Security and performance overhaul (`a279401`): browser upload, path-traversal 404, foreign `Host` header 403, version in the response header, caching of rendered output. |
| **1.0.0** | 2026-09-20 | Initial release (`dd1a2c5`): render core, PyQt6 desktop app, stdlib-only HTTP server. |

## Project structure

```
md-dis/
├── md_render.py          # Qt-free shared render core, holds VERSION
├── md_dis.py             # PyQt6 desktop app
├── md_dis_server.py      # headless HTTP server (stdlib only)
├── build.py              # PyInstaller build script, owns the version scheme
├── DESIGN.md             # design notes & shortcuts (German)
├── HANDOFF.md            # session handoff (German)
└── requirements.txt
```

`plantuml.jar` (28.5 MB) is **not** in the repository — it is gitignored and
re-downloaded on first use, or you can drop it into the project root.

`md-dis.ini` is gitignored for the same reason: it is per-user state that is
created next to the executable on first run.

## License

MIT — see `LICENSE`. Corrected in 1.2.0, so builds older than that show the
wrong license text in the About dialog. German UI; project language is German.
