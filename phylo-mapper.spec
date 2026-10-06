# PyInstaller config. Builds dist/PhyloMapper/ with PhyloMapper.exe and its libraries, no console window.
# Build with: .\build.ps1   (or: python -m PyInstaller phylo-mapper.spec --noconfirm)

# Qt modules the app never uses. Leaving them out keeps the exe smaller.
unused_qt = [
    "PySide6.Qt3DAnimation", "PySide6.Qt3DCore", "PySide6.Qt3DExtras",
    "PySide6.Qt3DInput", "PySide6.Qt3DLogic", "PySide6.Qt3DRender",
    "PySide6.QtBluetooth", "PySide6.QtCharts", "PySide6.QtDataVisualization",
    "PySide6.QtGraphs", "PySide6.QtLocation", "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets", "PySide6.QtNetworkAuth", "PySide6.QtNfc",
    "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.QtPositioning",
    "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuick3D",
    "PySide6.QtQuickWidgets", "PySide6.QtRemoteObjects", "PySide6.QtScxml",
    "PySide6.QtSensors", "PySide6.QtSerialPort", "PySide6.QtSpatialAudio",
    "PySide6.QtSql", "PySide6.QtStateMachine", "PySide6.QtTextToSpeech",
    "PySide6.QtWebChannel", "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets", "PySide6.QtWebSockets",
]

a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=unused_qt + ["tkinter", "matplotlib", "IPython", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

# One-folder build: the Qt DLLs stay as separate files next to the exe so users
# can swap in their own Qt build, which the LGPL requires.
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PhyloMapper",
    debug=False,
    strip=False,
    upx=False,
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="PhyloMapper",
)
