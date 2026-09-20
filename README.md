# md-dis

A Markdown viewer for Windows with diagram support, available in **two variants**:

| | Desktop app | HTTP server |
|---|---|---|
| File | `md_dis.py` (PyQt6 GUI) | `md_dis_server.py` (headless) |
| Interaction | Local window | Browser (index, raw, live view, upload) |
| Use case | Interactive viewing / editing workflow | Remote reading, sharing, CI, Watch |

Both share a single **Qt-free render core** (`md_render.py`) — same output in GUI and server.

---

## Features

- GitHub-Flavored Markdown (tables, code blocks, strikethrough, lists)
- **Diagram rendering inside Markdown:**
  - **PlantUML** — via `plantuml.jar` (Java). The JAR is downloaded automatically on first use and cached next to the binary.
  - **Mermaid** — via `mmdc` (mermaid-cli), if installed
- Dark / light theme toggle
- Zoom (`Ctrl+` / `Ctrl-` / `Ctrl+0`, mouse wheel)
- File Watch with auto-reload (`F5`)
- German UI; yaml frontmatter rendered as an info box
- Headless HTTP server also supports **browser upload** of `.md` files

## Requirements

- Python 3.11+ (requirements.txt)
- Desktop app: PyQt6 + PyQt6-WebEngine
- HTTPServer: Python standard library only (no Qt)
- PlantUML diagrams: Java runtime + `plantuml.jar`
- Mermaid diagrams: `mmdc` from `@mermaid-js/mermaid-cli`

```bash
pip install -r requirements.txt
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
| `Ctrl+F` | Search |
| `F2` | Edit file |
| `F1` | Help |
| `Esc` / `Ctrl+W` | Close / quit |

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

Endpoints:

| Route | Description |
|---|---|
| `GET /` | Index of Markdown files (or redirect when `--file` is set) |
| `GET /<pfad>.md` | Rendered HTML (with toolbar + optional watch script) |
| `GET /raw/<pfad>` | Raw Markdown source |
| `GET /poll?path=…` | Change stamp for the watch client |
| `GET /upload` / `POST /upload` | Browser upload of `.md` files (stored under `<root>/uploads/`, max 10 MB) |

## Build

```bash
python build.py              # GUI → dist/md-dis/
python build.py --server     # Server → dist/md-dis-server/
python build.py --clean      # remove build/ + dist/ + specs first
```

Note: the frozen executables must be run from a **local** Windows path
(not a UNC/`\\wsl.localhost` path).

## Project structure

```
md-dis/
├── md_render.py          # Qt-free shared render core
├── md_dis.py             # PyQt6 desktop app
├── md_dis_server.py      # headless HTTP server (stdlib only)
├── build.py              # PyInstaller build script
├── DESIGN.md             # design notes & shortcuts (German)
├── HANDOFF.md            # session handoff (German)
└── requirements.txt
```

## License

See `LICENSE` (closed source). German UI; project language is German.
