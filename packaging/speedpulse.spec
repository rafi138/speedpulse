# PyInstaller spec for SpeedPulse: windowed, one directory per OS.
# Run from the repository root:  pyinstaller packaging/speedpulse.spec --noconfirm
import os
import sys

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))

blocklist = [
    # Qt modules the tray app never touches; excluding keeps bundles small.
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebChannel",
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuickWidgets",
    "PySide6.Qt3DCore",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtPdf",
    "PySide6.QtPdfWidgets",
    "PySide6.QtSql",
    "PySide6.QtTest",
    "PySide6.QtDesigner",
    "PySide6.QtHelp",
    "PySide6.QtUiTools",
    "PySide6.QtNetworkAuth",
    "PySide6.QtSensors",
    "PySide6.QtSerialPort",
    "PySide6.QtPositioning",
    "PySide6.QtBluetooth",
    "PySide6.QtNfc",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "tkinter",
    "unittest",
    "pydoc_data",
]

icon_path = os.path.join(ROOT, "packaging", "icons", "speedpulse.ico")
icon = icon_path if os.path.exists(icon_path) else None

a = Analysis(
    [os.path.join(ROOT, "src", "speedpulse", "__main__.py")],
    pathex=[os.path.join(ROOT, "src")],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=blocklist,
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="speedpulse",
    debug=False,
    console=False,  # windowed: no console window on Windows, none needed elsewhere
    icon=icon,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="speedpulse",
)

if sys.platform == "darwin":
    # Wrap the one-directory payload in a proper .app bundle.
    bundle = BUNDLE(
        coll,
        name="SpeedPulse.app",
        info_plist={
            "CFBundleName": "SpeedPulse",
            "CFBundleDisplayName": "SpeedPulse",
            "CFBundleIdentifier": "org.speedpulse.app",
            "CFBundleShortVersionString": "0.1.0",
            "LSUIElement": True,  # menu-bar/tray app: no Dock icon window churn
        },
    )
