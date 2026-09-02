# CAD Intelligence & Automation Engine

An engineering-grade CAD intelligence system powered by FreeCAD / OpenCASCADE (OCCT) and deterministic B-Rep geometry analysis.

---

## Environment & Execution

FreeCAD 1.1 is built against **Python 3.11** (`python311.dll`).

### Option A: Using FreeCAD's Built-in Python (Recommended & Zero Config)
```powershell
& "C:\Program Files\FreeCAD 1.1\bin\python.exe" tests\test_phase1_box.py
```

### Option B: Using a Python 3.11 Conda Environment
```powershell
conda activate agrihub
python tests\test_phase1_box.py
```

---

## Project Structure
```
satven_freecad/
├── input/                  # Raw STEP / CAD files for processing
├── output/                 # Generated JSON analyses and text reports
├── src/
│   ├── cad/
│   │   ├── freecad_env.py  # Automated DLL & path configuration for FreeCAD
│   │   ├── step_loader.py  # STEP file loading & validation (Phase 2)
│   │   ├── geometry.py     # B-Rep surface & curve geometry extraction
│   │   ├── topology.py     # Topological graph (solids, shells, faces, edges, vertices)
│   │   ├── features.py     # Rule-based engineering feature recognition
│   │   └── measurements.py # High-precision CAD measurement engine
│   ├── analysis/
│   │   ├── analyzer.py     # Model intelligence pipeline
│   │   └── report.py       # JSON & human-readable report generators
│   └── main.py             # CLI Entrypoint
├── tests/
│   └── test_phase1_box.py  # Phase 1 box geometry validation test
├── docs/
│   ├── architecture.md     # System architecture & CAD abstraction layer
│   ├── development_log.md  # Phase-by-phase execution & diagnostic log
│   └── findings.md         # Technical notes on FreeCAD/OCCT APIs
├── requirements.txt
└── README.md
```

---

## Verification

### Running Phase 1 Test
```powershell
& "C:\Program Files\FreeCAD 1.1\bin\python.exe" tests\test_phase1_box.py
```
Expected output:
```
============================================================
PHASE 1 — FREECAD SOLID GEOMETRY TEST
============================================================
FreeCAD Version : 1.1.3
Python Version  : 3.11.14
------------------------------------------------------------
FreeCAD test successful

Box:
Length = 100.0 mm
Width = 60.0 mm
Height = 20.0 mm
------------------------------------------------------------
Solid count     : 1
Face count      : 6
Edge count      : 12
Vertex count    : 8
Bounding Box Min: (0.0, 0.0, 0.0) mm
Bounding Box Max: (100.0, 60.0, 20.0) mm
============================================================
```
