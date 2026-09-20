#!/usr/bin/env python3
"""Build-Skript für md-dis mit PyInstaller."""

import subprocess
import sys
import os
import shutil


# Qt-DLLs, die beim Lauf wirklich benötigt werden (direkte Abhängigkeiten
# der geladenen Qt-Module). Alles andere im Qt6/bin-Verzeichnis ist nur durch
# den PyQt6-Hook beigemischt und würde ungenutzt mitgeliefert.
KEEP_QT_BIN = {
    "Qt6Core.dll",
    "Qt6Gui.dll",
    "Qt6Widgets.dll",
    "Qt6Network.dll",
    "Qt6WebChannel.dll",
    "Qt6WebEngineCore.dll",
    "Qt6WebEngineWidgets.dll",
    "Qt6Quick.dll",
    "Qt6Qml.dll",
    "Qt6Positioning.dll",
    "Qt6PrintSupport.dll",
    "Qt6QuickWidgets.dll",
    "Qt6OpenGL.dll",
    "Qt6QmlModels.dll",
    "Qt6QmlMeta.dll",
    "Qt6QmlWorkerScript.dll",
    "QtWebEngineProcess.exe",
    "opengl32sw.dll",
    "qt.conf",
}

# QML-Importverzeichnisse, die gebraucht werden (QtQuick ist feste Abhängigkeit
# von Qt6WebEngineCore). Alles andere (QtQuick3D, QtTest, ...) ist überflüssig.
KEEP_QML = {"QtQuick", "QtQml"}

# Bildformat-Plugins: Icon (ico), jpeg & gif reichen – PNG ist in QtGui
# eingebaut, WebEngine (Chromium) dekodiert selbst.
KEEP_IMAGEFORMATS = {"qico.dll", "qjpeg.dll", "qgif.dll"}

# Nicht benötigte Plugin-Verzeichnisse vollständig entfernen.
DROP_QPLUGIN_DIRS = {"generic", "position", "iconengines"}

# Plattform-Plugins, die entfernt werden können (nur qwindows wird genutzt).
DROP_QPLATFORMS = {"qminimal.dll", "qoffscreen.dll"}


def prune_dist(base_dir):
    """Entfernt unbenutzte Qt-Module aus dem PyInstaller-Output."""
    qt6_dir = os.path.join(base_dir, "dist", "md-dis", "_internal", "PyQt6", "Qt6")
    if not os.path.isdir(qt6_dir):
        print("  (Hinweis: Qt6-Verzeichnis nicht gefunden – kein Pruning)")
        return

    freed = 0

    def _rm(path):
        nonlocal freed
        if os.path.isfile(path):
            freed += os.path.getsize(path)
            os.remove(path)
        elif os.path.isdir(path):
            for root, _dirs, files in os.walk(path, topdown=False):
                for f in files:
                    fp = os.path.join(root, f)
                    freed += os.path.getsize(fp)
            shutil.rmtree(path, ignore_errors=True)

    # 1) bin/ – alle Qt-DLLs entfernen, die nicht im Keep-Satz stehen
    qbin = os.path.join(qt6_dir, "bin")
    for f in os.listdir(qbin):
        if f in KEEP_QT_BIN:
            continue
        if f.startswith(("MSVCP140", "VCRUNTIME140")):
            continue
        _rm(os.path.join(qbin, f))

    # 2) qml/ – nur QtQuick und QtQml behalten
    qqml = os.path.join(qt6_dir, "qml")
    if os.path.isdir(qqml):
        for d in os.listdir(qqml):
            if d not in KEEP_QML:
                _rm(os.path.join(qqml, d))

    # 3) resources/ – Debug-Pakete entfernen
    qres = os.path.join(qt6_dir, "resources")
    if os.path.isdir(qres):
        for f in os.listdir(qres):
            if ".debug." in f or f == "v8_context_snapshot.debug.bin":
                _rm(os.path.join(qres, f))

    # 4) plugins/ – unbenutzte Plugin-Kategorien entfernen
    qplugins = os.path.join(qt6_dir, "plugins")
    if os.path.isdir(qplugins):
        for d in DROP_QPLUGIN_DIRS:
            _rm(os.path.join(qplugins, d))
        if os.path.isdir(os.path.join(qplugins, "imageformats")):
            for f in os.listdir(os.path.join(qplugins, "imageformats")):
                if f not in KEEP_IMAGEFORMATS:
                    _rm(os.path.join(qplugins, "imageformats", f))
        if os.path.isdir(os.path.join(qplugins, "platforms")):
            for f in os.listdir(os.path.join(qplugins, "platforms")):
                if f in DROP_QPLATFORMS:
                    _rm(os.path.join(qplugins, "platforms", f))

    print(f"  Unbenutzte Qt-Module entfernt ({freed / 1024 / 1024:.1f} MB)")


def build():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    clean = "--clean" in sys.argv
    server = "--server" in sys.argv

    if clean:
        for d in ["build", "dist"]:
            p = os.path.join(base_dir, d)
            if os.path.isdir(p):
                shutil.rmtree(p)
        if not server:
            spec = os.path.join(base_dir, "md-dis.spec")
            if os.path.isfile(spec):
                os.remove(spec)
        if server:
            spec = os.path.join(base_dir, "md-dis-server.spec")
            if os.path.isfile(spec):
                os.remove(spec)
        print("Cache geleert.\n")

    if server:
        dist_dir = os.path.join(base_dir, "dist", "md-dis-server")
        if os.path.isdir(dist_dir):
            shutil.rmtree(dist_dir)
        cmd = [
            sys.executable, "-m", "PyInstaller",
            "--onedir",
            "--console",
            "--name", "md-dis-server",
            "md_dis_server.py",
        ]
        print("Baue md-dis-server.exe (headless, ohne Qt) ...")
        result = subprocess.run(cmd, cwd=base_dir)
        if result.returncode == 0:
            print("\nBuild erfolgreich!")
            print("Der Server befindet sich in: dist/md-dis-server/")
            print("Start: dist/md-dis-server/md-dis-server.exe --port 8080 --root .")
        else:
            print("\nBuild fehlgeschlagen!")
            sys.exit(1)
        return

    icon_path = os.path.join(base_dir, "icon.ico")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onedir",
        "--windowed",
        "--name", "md-dis",
    ]

    if os.path.isfile(icon_path):
        cmd.extend(["--icon", icon_path])
        cmd.extend(["--add-data", f"{icon_path};."])

    cmd.append("md_dis.py")

    dist_dir = os.path.join(base_dir, "dist", "md-dis")
    if os.path.isdir(dist_dir):
        shutil.rmtree(dist_dir)

    print("Baue md-dis.exe ...")
    result = subprocess.run(cmd, cwd=base_dir)

    if result.returncode == 0:
        print("\nBuild erfolgreich!")
        print("Die Anwendung befindet sich in: dist/md-dis/")
        print("Entferne unbenutzte Qt-Module ...")
        prune_dist(base_dir)
        print("plantuml.jar wird bei Bedarf automatisch heruntergeladen.")
    else:
        print("\nBuild fehlgeschlagen!")
        sys.exit(1)


if __name__ == "__main__":
    build()