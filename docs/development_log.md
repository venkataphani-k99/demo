# CAD Intelligence Project — Development Log

## Phase 0: Environment Discovery

**Date**: 2026-08-26  
**Operating System**: Windows 11 (AMD64)  
**FreeCAD Version**: FreeCAD 1.1.3 (Build 20260725)  
**FreeCAD Installation Path**: `C:\Program Files\FreeCAD 1.1`  
**FreeCAD Python Version**: Python 3.11.14 (packaged by conda-forge, 64-bit)  
**FreeCAD Binaries**:
- `C:\Program Files\FreeCAD 1.1\bin\freecad.exe` (GUI)
- `C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe` (CLI)
- `C:\Program Files\FreeCAD 1.1\bin\python.exe` (Bundled Python 3.11.14)
- `C:\Program Files\FreeCAD 1.1\bin\FreeCAD.pyd` (Core C++ Python binding)
- `C:\Program Files\FreeCAD 1.1\lib\Part.pyd` (OpenCASCADE / OCCT CAD module)
- `C:\Program Files\FreeCAD 1.1\lib\Import.pyd` (STEP / IGES import module)

### Python Environment & Compatibility Findings
1. **FreeCAD 1.1 is built against Python 3.11 (ABI: `python311.dll`)**:
   - Running with a Python 3.13 interpreter (e.g. `conda activate sales` which has Python 3.13.12) produces `ImportError: Module use of python311.dll conflicts with this version of Python.`
   - Any Python 3.11 interpreter (such as `D:\anaconda\envs\agrihub\python.exe` with Python 3.11.14 or FreeCAD's native `C:\Program Files\FreeCAD 1.1\bin\python.exe`) successfully loads `FreeCAD`, `Part`, and `Import` without issue.
2. **DLL & Module Resolution on Windows**:
   - For Python 3.8+ on Windows, `os.add_dll_directory(r"C:\Program Files\FreeCAD 1.1\bin")` must be invoked before importing `FreeCAD` so that dependent DLLs (`FreeCADBase.dll`, `FreeCADApp.dll`, OCCT libraries) are located.
   - `sys.path.append(r"C:\Program Files\FreeCAD 1.1\bin")` and `sys.path.append(r"C:\Program Files\FreeCAD 1.1\lib")` allow standard `import FreeCAD` and `import Part`.

### Status
- [x] Operating system determined (Windows 64-bit)
- [x] FreeCAD 1.1 located and verified
- [x] FreeCAD Python modules (`FreeCAD`, `Part`, `Import`) tested and verified working
- [x] Environment discovery documented

---

## Phase 1: Simple FreeCAD Solid Test

**Date**: 2026-08-26  
**Test Script**: `tests/test_phase1_box.py`  
**Target Geometry**: Solid box $100 \times 60 \times 20\text{ mm}$  
**Topology Results**:
- Solids: 1
- Faces: 6
- Edges: 12
- Vertices: 8
- Bounding Box: $100.0 \times 60.0 \times 20.0\text{ mm}$
**Status**: [x] Passed cleanly

---

## Phase 2: STEP Import and B-Rep Geometry Inspection

**Date**: 2026-08-26  
**Target Model**: `input/Pieza18_1.STEP`  
**File Size**: 175,631 bytes  
**STEP Preprocessor**: SwSTEP 2.0 (SolidWorks 2020)  
**STEP Schema**: `AUTOMOTIVE_DESIGN` (AP214)  
**Detected Units**: `mm`  

### Measured B-Rep Geometry & Topology:
- **Solids**: 1
- **Shells**: 1
- **Faces**: 43
- **Edges**: 103
- **Vertices**: 62
- **Bounding Box (min)**: `(-35.019, -12.007, -0.212) mm`
- **Bounding Box (max)**: `(35.019, 12.007, 30.659) mm`
- **Overall Dimensions**: `70.037 × 24.014 × 30.871 mm`
- **Total Surface Area**: `6,766.739 mm²`
- **Total Volume**: `16,856.332 mm³`

### Surface Classification Breakdown:
- **Cylinder**: 22 faces ($2,313.901\text{ mm}^2$)
- **Plane**: 8 faces ($4,036.205\text{ mm}^2$)
- **BSplineSurface**: 7 faces ($186.382\text{ mm}^2$)
- **Toroid**: 6 faces ($230.251\text{ mm}^2$)

### Curve / Edge Classification Breakdown:
- **Circle**: 41 edges
- **Line**: 38 edges
- **BSplineCurve**: 24 edges

### Generated Artifacts:
- JSON Dataset: `output/Pieza18_1_analysis.json`
- Text Report: `output/Pieza18_1_report.txt`
- Unit Test Suite: `tests/test_phase2_step_import.py` (Passed)
- CLI Entrypoint: `python -m src.main input/Pieza18_1.STEP`

### Status:
- [x] Real STEP file imported and verified
- [x] B-Rep topology (faces, edges, vertices) fully mapped
- [x] Zero LLM guessing; 100% deterministic OCCT geometry calculation
- [x] Phase 2 complete

---

## Phase 3: Deep Geometry Inspection & Topology Graph (3A–3F)

**Date**: 2026-08-26  
**Target Model**: `input/Pieza18_1.STEP`  
**Test Suites**: 
- `tests/test_phase3_deep_geometry.py` (Passed)
- `tests/test_phase2_step_import.py` (Regression Passed)
- `tests/test_phase1_box.py` (Regression Passed)

### Key Mathematical & Topological Findings:

1. **Cylindrical Surfaces Deep Analysis (22 Faces Total)**:
   - **Central Vertical Counterbore**:
     - Inner hole cylinders: `Face4` & `Face22` ($R = 2.75\text{ mm}$, $\text{Dia} = 5.50\text{ mm}$, Axial length $= 3.30\text{ mm}$, Axis $=(0, 0, 1)$ at $(0, 0, 7)$)
     - Outer bore cylinders: `Face5` & `Face21` ($R = 5.50\text{ mm}$, $\text{Dia} = 11.00\text{ mm}$, Axial length $= 4.745\text{ mm}$, Axis $=(0, 0, 1)$ at $(0, 0, 7)$)
     - Counterbore transition step: `Face23` (planar ring floor at $Z = 3.30\text{ mm}$, connecting `Face4/22` to `Face5/21`)
   - **Horizontal Bore Cylinders**:
     - `Face6`, `Face7`, `Face14`, `Face15` ($R = 5.00\text{ mm}$, $\text{Dia} = 10.00\text{ mm}$, Axis $=(1, 0, 0)$ at $(-40, 0, 22)$)
   - **Outer Cylindrical Bosses**:
     - `Face8`, `Face9` ($R = 15.00\text{ mm}$, $\text{Dia} = 30.00\text{ mm}$, Length $= 46.0\text{ mm}$, Axis $=(1, 0, 0)$)
     - `Face17`, `Face18` ($R = 8.00\text{ mm}$, $\text{Dia} = 16.00\text{ mm}$, Length $= 3.977\text{ mm}$, Axis $=(1, 0, 0)$)
   - **Fillet & Blend Cylinders (10 Faces)**:
     - `Face24`, `Face26`, `Face27`, `Face29`, `Face30`, `Face34`, `Face35`, `Face39`, `Face40`, `Face43` (All have uniform fillet radius $R = 2.00\text{ mm}$, $\text{Dia} = 4.00\text{ mm}$, angular sweep $89.1^\circ$ to $110.7^\circ$)

2. **Planar Surfaces Deep Analysis (8 Faces Total)**:
   - Base mounting plane: `Face16` ($\text{Area} = 1,652.864\text{ mm}^2$, Normal $=(0, 0, -1)$)
   - Symmetrical inclined side faces: `Face19` and `Face20` ($\text{Area} = 668.381\text{ mm}^2$, Normal $=(0, 0.98, \pm 0.17)$)
   - Vertical end faces: `Face10` and `Face11` ($\text{Area} = 151.477\text{ mm}^2$, Normal $=(1, 0, 0)$ at $X = \pm 25.0$)
   - Angled flange end faces: `Face12` and `Face13` ($\text{Area} = 336.175\text{ mm}^2$)
   - Counterbore internal floor: `Face23` ($\text{Area} = 71.275\text{ mm}^2$, Normal $=(0, 0, -1)$ at $Z = 3.30$)

3. **Topology Graph**:
   - Mapped full bidirectional dual graph: 43 faces $\leftrightarrow$ 103 shared edges $\leftrightarrow$ 62 vertices.
   - Adjacency symmetry is 100% verified.

4. **Visual Debug Tool**:
   - `src/cad/visual_debugger.py` implemented for interactive color-coding and face highlighting inside FreeCAD GUI.

### Status:
- [x] Phase 3A: Deep geometry parameter extraction complete
- [x] Phase 3B: Topology relationships (Face-Edge-Face) complete
- [x] Phase 3C: All 22 cylinders analyzed and strictly labeled as `cylindrical_face`
- [x] Phase 3D: FreeCAD visual debugging script complete
- [x] Phase 3E: Detailed JSON and ASCII tables generated in reports
- [x] Phase 3F: Automated test suite passed
- [x] Phase 3 Complete

---

## Phase 4: Exact CAD Measurement Engine

**Date**: 2026-08-26  
**Module**: `src/cad/measurements.py`  
**Test Suite**: `tests/test_phase4_measurements.py` (All Passed)  

### Measurement API & Capabilities:
- `measure_cylinder_diameter(face_ids)`: Computes exact diameter across single or multi-face compound B-Rep features with coaxiality validation.
- `measure_cylinder_radius(face_ids)`: Computes exact radius.
- `measure_cylinder_relationship(cyl_a, cyl_b)`: Computes shortest 3D axis distance, angle between axes, and checks coaxiality / parallelism / perpendicularity.
- `measure_thickness(face_a, face_b)`: Computes perpendicular distance between parallel planar faces.
- `measure_angle(entity_a, entity_b)`: Computes 3D angle in degrees between planar normals, cylinder axes, linear edges, or custom direction vectors.
- `measure_edge_length(edge_id)`: Exact B-Rep curve length.
- `measure_point_to_point(pt_a, pt_b)`: Exact Euclidean distance.
- `measure_solid_volume()` & `measure_total_surface_area()`: Exact 3D volume and surface area.
- `measure_bounding_box()`: Overall $L_x, L_y, L_z$ and coordinate extrema.

### Verified Measurements on `input/Pieza18_1.STEP`:
- **Central Inner Cylinder**: $\varnothing 5.500\text{ mm}$ ($R = 2.750\text{ mm}$) — Source: `["Face4", "Face22"]`
- **Central Counterbore**: $\varnothing 11.000\text{ mm}$ ($R = 5.500\text{ mm}$) — Source: `["Face5", "Face21"]`
- **Horizontal Bore**: $\varnothing 10.000\text{ mm}$ ($R = 5.000\text{ mm}$) — Source: `["Face6", "Face7", "Face14", "Face15"]`
- **Main Outer Boss**: $\varnothing 30.000\text{ mm}$ ($R = 15.000\text{ mm}$) — Source: `["Face8", "Face9"]`
- **Side Boss**: $\varnothing 16.000\text{ mm}$ ($R = 8.000\text{ mm}$) — Source: `["Face17", "Face18"]`
- **Corner Fillets**: $R = 2.000\text{ mm}$ ($\varnothing 4.000\text{ mm}$) — Source: `Face24`
- **End-to-End Thickness**: $50.000\text{ mm}$ — Source: `["Face10", "Face11"]`
- **Total Volume**: $16,856.332\text{ mm}^3$
- **Total Surface Area**: $6,766.739\text{ mm}^2$
- **Overall Bounding Box**: $70.037 \times 24.014 \times 30.871\text{ mm}$
- **Central Hole & Counterbore Relationship**: Coaxial ($\text{dist} = 0.000\text{ mm}$, $\text{angle} = 0.0^\circ$)
- **Central Hole & Horizontal Bore Relationship**: Perpendicular intersection ($\text{dist} = 0.000\text{ mm}$, $\text{angle} = 90.0^\circ$)

### Status:
- [x] Measurement contract implemented (`type`, `value`, `raw_value`, `unit`, `source_entities`, `method`, `status`, `details`)
- [x] Multi-face B-Rep compound feature measurements supported
- [x] Full traceability to source B-Rep entities
- [x] 100% test coverage passed on all measurement types and error conditions
- [x] Phase 4 Complete

---

## Phase 5: Deterministic Feature Recognition (5A–5J)

**Date**: 2026-08-26  
**Module**: `src/cad/features.py`  
**Test Suite**: `tests/test_phase5_feature_recognition.py` (All Passed)  

### Key Implementations:

1. **Logical Cylindrical Feature Grouping (5A)**:
   - Evaluates radius equality within $10^{-4}\text{ mm}$, collinear axis direction within $10^{-3\circ}$, axis distance within $10^{-3}\text{ mm}$, and internal/external orientation.
   - Synthesizes 22 raw B-Rep split faces into **15 unified logical cylinder features** (e.g. `Face4+Face22` into single $D=5.5\text{ mm}$ cylinder; `Face5+Face21` into single $D=11.0\text{ mm}$ cylinder; `Face6+Face7+Face14+Face15` into single $D=10.0\text{ mm}$ cylinder).

2. **Internal vs External Surface Orientation (5B)**:
   - Evaluates outward B-Rep face normal $\mathbf{n}$ with respect to the cylinder radial vector $\mathbf{r}$:
     - $\mathbf{n} \cdot \mathbf{r} < 0 \implies$ Normal points towards axis $\rightarrow$ **Internal Cavity / Hole / Bore**.
     - $\mathbf{n} \cdot \mathbf{r} > 0 \implies$ Normal points away from axis $\rightarrow$ **External Boss / Shaft / Protrusion**.

3. **Counterbored Hole Recognition (5C)**:
   - Detects coaxial inner cylinder (`Face4+Face22`, $\varnothing 5.5\text{ mm}$) and outer cylinder (`Face5+Face21`, $\varnothing 11.0\text{ mm}$) connected by intermediate annular planar step face (`Face23`).
   - Produces confirmed `CBORE_001` feature with bore depth $3.30\text{ mm}$, counterbore depth $4.75\text{ mm}$, and total depth $8.05\text{ mm}$.

4. **Through Bore & Hole Recognition (5B)**:
   - Detects full $360^\circ$ circular cavity (`Face6+Face7+Face14+Face15`, $\varnothing 10.0\text{ mm}$) aligned along the X-axis $(1, 0, 0)$.

5. **External Boss Recognition (5D)**:
   - Detects external cylindrical protrusion (`Face17+Face18`, $\varnothing 16.0\text{ mm}$) with $320^\circ$ sweep on side walls.

6. **Fillet & Blend Recognition (5E)**:
   - Detects 10 constant-radius cylindrical edge fillets ($R = 2.00\text{ mm}$, sweep $\approx 90^\circ$) and 6 toroidal corner blends ($R = 2.00\text{ mm}$).

7. **Feature Validation & Rejection (5G)**:
   - Verifies geometric invariants (e.g. bore diameter < counterbore diameter, positive dimensions, valid entity IDs); flags invalid geometry with `status: "rejected"`.

8. **Visual Debugger Extended (5I)**:
   - `src/cad/visual_debugger.py` supports `highlight_feature("CBORE_001")`, `highlight_feature("HOLE_002")`, `highlight_feature("BOSS_004")`, highlighting all constituent B-Rep faces simultaneously in distinct feature colors.

### Status:
- [x] 20 Confirmed Engineering Features recognized on `Pieza18_1.STEP`
- [x] Zero LLM / visual guessing; 100% deterministic geometry & topology inference
- [x] Dedicated artifacts generated: `output/Pieza18_1_features.json` & `output/Pieza18_1_features.txt`
- [x] All test suites (Phase 1 to Phase 5) passing with 100% success
- [x] Phase 5 Complete

---

## Phase 6: Automated TechDraw Drawing Generation (6A–6M)

**Date**: 2026-08-26  
**Module**: `src/cad/techdraw_generator.py`, `src/cad/drawing_validator.py`  
**Test Suite**: `tests/test_phase6_techdraw.py` (All 15 Tests Passed)  

### FreeCAD 1.1.3 TechDraw APIs Discovered and Used:
| API | Type | Description |
|-----|------|-------------|
| `TechDraw::DrawPage` | DocObj | Page container, `Template`, `ProjectionType`, `Views` |
| `TechDraw::DrawSVGTemplate` | DocObj | SVG template, `Template`, `Width`, `Height` |
| `TechDraw::DrawProjGroup` | DocObj | Orthographic group, `addProjection()`, `Anchor`, `spacingX/Y` |
| `TechDraw::DrawProjGroupItem` | DocObj | Individual view, `Direction`, `X`, `Y`, `Scale`, `Type` |
| `TechDraw.viewPartAsSvg()` | Function | Per-view SVG string export |
| `TechDraw.writeDXFPage()` | Function | Full page DXF export |
| `doc.saveAs()` | Method | FreeCAD FCStd document persistence |

### Drawing Configuration:
- **Template**: `A3_Landscape_blank.svg` — 420 × 297 mm — auto-detected from FreeCAD resource dir
- **Projection Convention**: Third-Angle (ASME/ISO, configurable to First-Angle via `--projection first`)
- **Scale**: Automatic (FreeCAD computes optimal scale; effective scale = 1.0 for Pieza18_1)
- **Views**: Front, Top, Left, Right, Bottom (AutoDistribute enabled)

### Third-Angle Projection Layout:
```
             TOP  (looking from +Z, y=+52mm)

        LEFT    FRONT    RIGHT
   (x=-72mm) (origin) (x=+72mm)

            BOTTOM  (looking from -Z, y=-52mm)
```
Direction vectors (FreeCAD TechDraw):
- Front: `(0, -1, 0)` — looking from +Y
- Top: `(0, 0, +1)` — looking from -Z downward
- Left: `(-1, 0, 0)` — looking from +X
- Right: `(+1, 0, 0)` — looking from -X
- Bottom: `(0, 0, -1)` — looking from +Z upward

### Outputs Generated:
- `output/Pieza18_1_drawing.FCStd` — 62 KB, reopenable FreeCAD drawing document
- `output/Pieza18_1_drawing.svg` — 36 KB, composite multi-view SVG
- `output/Pieza18_1_drawing.dxf` — 172 KB, full DXF drawing

### CLI Command:
```powershell
& "C:\Program Files\FreeCAD 1.1\bin\python.exe" -m src.main draw input/Pieza18_1.STEP
```

### Status:
- [x] TechDraw Page, Template, Projection Group created programmatically
- [x] 5 orthographic views: Front, Top, Left, Right, Bottom
- [x] FCStd saved and successfully reopened in FreeCAD
- [x] SVG composite export
- [x] DXF export via `TechDraw.writeDXFPage()`
- [x] DrawingValidator validates all structural invariants
- [x] 15 automated tests in `test_phase6_techdraw.py` all passed
- [x] All Phase 1–6 regressions passing (exit code 0)
- [x] Phase 6 Complete

---

## Phase 7: Deterministic Dimension Candidate Engine (7A–7N)

**Date**: 2026-08-26  
**Module**: `src/cad/dimensions.py`, `src/cad/view_analysis.py`  
**Test Suite**: `tests/test_phase7_dimensions.py` (All 10 Tests Passed)  

### Highlights & Architecture:
1. **Dimension Data Model (7A)**:
   - Structured `DimensionCandidate` model preserving full B-Rep entity traceability, source feature linkage, exact mathematical measurement method, units, semantics, and status.
2. **Deterministic Diameters (7B)**:
   - Extracted from recognized cylindrical features: $\varnothing 5.50\text{ mm}$, $\varnothing 11.00\text{ mm}$ (from `CBORE_001`), $\varnothing 10.00\text{ mm}$ (`HOLE_002`), $\varnothing 30.00\text{ mm}$ (`BORE_003`), $\varnothing 16.00\text{ mm}$ (`BOSS_004`).
3. **Grouped Radius Deduplication (7C & 7H)**:
   - 16 individual fillet/blend faces mapped to a single consolidated $R = 2.00\text{ mm}$ candidate (`FILLET_R2.000`), preserving all constituent source face IDs.
4. **Linear & Thickness Candidates (7D)**:
   - Planar thickness between parallel faces (`Face10` & `Face11`: $50.00\text{ mm}$, `Face16` & `Face23`: $3.30\text{ mm}$), overall B-Rep bounding box extents ($70.037 \times 24.014 \times 30.871\text{ mm}$), and feature axial lengths ($8.513\text{ mm}$, $3.977\text{ mm}$).
5. **Depth Candidates (7F)**:
   - Separate depth representations for `CBORE_001`: bore depth ($3.30\text{ mm}$), counterbore depth ($4.75\text{ mm}$), total depth ($8.05\text{ mm}$).
6. **Angular Relationships (7E)**:
   - Cylinder-to-cylinder orthogonal axes ($90.00^\circ$ perpendicularity) and coaxial relationships ($0.00^\circ$).
7. **View Visibility Analysis (7K)**:
   - Evaluates orthographic projection angles of feature axes against standard TechDraw views (Front, Top, Left, Right, Bottom) to classify circular profile vs edge-on vs planar profile vs foreshortened/unsuitable.
8. **Candidate Statuses & Ambiguity (7I)**:
   - Evaluated under explicit status vocabulary (`valid`, `candidate`, `ambiguous`, `rejected`, `unsupported`). Flagged ambiguous cases with explicit reasoning (e.g. partial cylindrical sweep on `BORE_003`).

### CLI Command:
```powershell
& "C:\Program Files\FreeCAD 1.1\bin\python.exe" -m src.main dimensions input/Pieza18_1.STEP
```

### Outputs Generated:
- `output/Pieza18_1_dimensions.json` (44 KB)
- `output/Pieza18_1_dimensions.txt` (13 KB)

### Status:
- [x] Dimension data model created with strict entity traceability
- [x] 20 candidate dimensions extracted (19 valid, 1 ambiguous, 0 rejected)
- [x] View visibility projection analyser implemented
- [x] Dedicated JSON and TXT report generators integrated
- [x] 10 test cases in `test_phase7_dimensions.py` passed
- [x] Full regression suite (Phases 1–7) passed with 100% success
- [x] Phase 7 Complete

---

## Phase 8: Dimension View Assignment & TechDraw Placement (8A–8M)

**Date**: 2026-08-26  
**Module**: `src/cad/dimension_placement.py`  
**Test Suite**: `tests/test_phase8_dimension_placement.py` (All 14 Tests Passed)  

### FreeCAD 1.1.3 Dimension APIs Discovered:
| API | Type | Description |
|-----|------|-------------|
| `TechDraw::DrawViewDimension` | DocObj | Dimension object placed on `DrawPage` or associated view |
| `References3D` | Property | `[(src_obj, 'FaceX')]` — links directly to 3D B-Rep entities |
| `MeasureType` | Property | `'True'` (exact 3D Euclidean/analytic CAD measure) or `'Projected'` |
| `Type` | Property | `'Diameter'`, `'Radius'`, `'Distance'`, `'DistanceX'`, `'DistanceY'`, etc. |
| `X`, `Y` | Property | Annotation placement coordinates on printable page in mm |

### First Safe Subset Placed on Drawing:
| Dimension ID | Formatted Value | Selected View | Projection Status | 3D Source Entity | Placement (X, Y) | Validation Status |
|:---|:---|:---|:---|:---|:---|:---|
| **D001** | $\varnothing 5.500\text{ mm}$ | `Top` | `circular_profile` | `Face4` | $(150.0, 207.0)\text{ mm}$ | `PASSED` |
| **D002** | $\varnothing 11.000\text{ mm}$ | `Top` | `circular_profile` | `Face5` | $(150.0, 224.0)\text{ mm}$ | `PASSED` |
| **D003** | $\varnothing 10.000\text{ mm}$ | `Left` | `circular_profile` | `Face6` | $(53.0, 130.0)\text{ mm}$ | `PASSED` |
| **D005** | $\varnothing 16.000\text{ mm}$ | `Right` | `circular_profile` | `Face17` | $(250.0, 130.0)\text{ mm}$ | `PASSED` |
| **D006** | $R 2.000\text{ mm}$ | `Top` | `circular_profile` | `Face24` | $(182.0, 182.0)\text{ mm}$ | `PASSED` |

### Excluded / Deferred Candidates:
- **D013** ($46.000\text{ mm}$ partial bore length): Excluded as `ambiguous` (incomplete $61.3^\circ$ sweep).
- **Other valid candidates** (depths, thicknesses, overall extents): Deferred outside the Phase 8H initial safe feature subset.

### Outputs Generated:
- `output/Pieza18_1_dimensioned.FCStd` (81 KB) — Reopenable FreeCAD drawing document with attached dimensions
- `output/Pieza18_1_placement.json` (10 KB) — Structured placement plan & validation results
- `output/Pieza18_1_placement.txt` (3 KB) — Human-readable placement summary

### CLI Command:
```powershell
& "C:\Program Files\FreeCAD 1.1\bin\python.exe" -m src.main dimension-drawing input/Pieza18_1.STEP
```

### Status:
- [x] Deterministic view assignment based on Phase 7 visibility analysis
- [x] Initial safe subset (D001, D002, D003, D005, D006) placed onto TechDraw drawing
- [x] Ambiguous (D013) and non-subset candidates safely excluded with reasons recorded
- [x] Non-overlapping, page-bounded coordinates verified
- [x] Reopened FCStd document confirms intact `TechDraw::DrawViewDimension` objects
- [x] 14 automated tests in `test_phase8_dimension_placement.py` passed
- [x] Full regression suite (Phases 1–8) passed with 100% success
- [x] Phase 8 Complete

---

## Phase 9A: Complete Deterministic Engineering Dimensioning (9A.1–9A.20)

**Date**: 2026-08-26  
**Module**: `src/cad/complete_dimensioning.py`, `src/cad/dimension_dependencies.py`, `src/cad/dimension_redundancy.py`  
**Test Suite**: `tests/test_phase9a_complete_dimensioning.py` (All 18 Tests Passed)  

### Highlights & Architecture:
1. **Semantic Role Classification (9A.8 & 9A.11)**:
   - Evaluated each of the 20 candidates under formal semantic roles (`feature_size`, `overall_size`, `thickness`, `feature_depth`, `feature_length`, `geometric_relationship`, `ambiguous`).
   - Assigned deterministic engineering priorities (`PRIMARY`, `SECONDARY`, `OPTIONAL`, `AMBIGUOUS`).
2. **Dimension Dependency Graph (9A.9)**:
   - Built mathematical dependency tracking: detects additive chains, e.g. $\text{Total Depth } D017 (8.045\text{ mm}) = \text{Bore Depth } D015 (3.300\text{ mm}) + \text{Cbore Depth } D016 (4.745\text{ mm})$.
   - Classified candidates into `independent` (16), `derived` (1), `geometric_constraint` (3), and `redundant_candidate` (0).
3. **Redundancy & Over-Dimensioning Prevention (9A.12)**:
   - Excluded derived candidate $D017$ to prevent double-dimensioning.
   - Excluded duplicate thickness $D008$ ($3.300\text{ mm}$) which is already communicated by bore depth $D015$.
   - Filtered angular constraints ($D018$, $D019$, $D020$) from active drawing placement.
4. **Datum-Like Reference Analysis (9A.10)**:
   - Identified primary seating base (`Face16` at $Z=0$, area $1,652.86\text{ mm}^2$) and parallel end stops (`Face10`, `Face11` at $X=\pm 25\text{ mm}$).
5. **Complete Drawing View Assignment & Placement (9A.13 & 9A.14)**:
   - Placed **14 primary non-redundant dimensions** across Front, Top, Left, and Right orthographic views with zero collisions:
     - **Top View**: $\varnothing 5.50\text{ mm}$ ($D001$), $\varnothing 11.00\text{ mm}$ ($D002$), $R 2.00\text{ mm}$ ($D006$), Overall Y $24.01\text{ mm}$ ($D010$).
     - **Front View**: Thickness $50.00\text{ mm}$ ($D007$), Overall X $70.04\text{ mm}$ ($D009$), Overall Z $30.87\text{ mm}$ ($D011$), Hole length $8.51\text{ mm}$ ($D012$), Boss length $3.98\text{ mm}$ ($D014$), Bore depth $3.30\text{ mm}$ ($D015$), Cbore depth $4.75\text{ mm}$ ($D016$).
     - **Left View**: Through bore $\varnothing 10.00\text{ mm}$ ($D003$).
     - **Right View**: Boss $\varnothing 16.00\text{ mm}$ ($D005$), Partial bore $\varnothing 30.00\text{ mm}$ ($D004$).
6. **Feature Engineering Coverage (9A.18)**:
   - `CBORE_001`: Fully dimensioned (bore dia, cbore dia, bore depth, cbore depth).
   - `HOLE_002`: Fully dimensioned (diameter, axial length).
   - `BOSS_004`: Fully dimensioned (diameter, axial length).
   - `FILLET_R2.000`: Fully dimensioned (radius).
   - `OVERALL_SIZE`: Fully dimensioned ($X \times Y \times Z$).
   - `BORE_003`: Ambiguous / partially dimensioned (partial $61.3^\circ$ vaulted arch).

### Outputs Generated:
- `output/Pieza18_1_complete_dimensioned.FCStd` (118 KB) — Complete dimensioned FreeCAD drawing document
- `output/Pieza18_1_complete_dimensions.json` (26 KB) — Complete structured dimensions dataset with dependencies, coverage, and datums
- `output/Pieza18_1_complete_dimensions.txt` (11 KB) — Complete human-readable engineering drawing report

### CLI Command:
```powershell
& "C:\Program Files\FreeCAD 1.1\bin\python.exe" -m src.main complete-dimensions input/Pieza18_1.STEP
```

### Status:
- [x] Complete deterministic dimensioning engine implemented
- [x] 14 dimensions successfully placed and validated against 3D CAD geometry
- [x] Dependency graph & redundancy engine prevents over-dimensioning
- [x] Feature coverage analysis and datum reference discovery completed
- [x] 18 automated tests in `test_phase9a_complete_dimensioning.py` passed
- [x] Full regression suite (Phases 1–9A) passed with 100% success
- [x] Phase 9A Complete

---

## Phase 9.5: FastAPI Service Layer (9.5A–9.5X)

**Date**: 2026-08-26  
**Module**: `src/api/app.py`, `src/api/routes/`, `src/api/services/`, `src/api/schemas/`  
**Test Suite**: `tests/test_api.py` (All 14 Tests Passed)  

### Highlights & Architecture:
1. **FastAPI Application Boundary (9.5A & 9.5B)**:
   - Modern RESTful service exposing `/api/v1/` prefix with auto-generated Swagger UI (`/docs`) and OpenAPI spec (`/openapi.json`).
   - CORS middleware enabled for local Next.js development (`http://localhost:3000`).
2. **Project Workspace & Storage Isolation (9.5C, 9.5D & 9.5S)**:
   - `ProjectService` generates unique UUID project IDs, isolates uploads in `workspaces/{project_id}/`, validates `.step` and `.stp` extensions, and eliminates path traversal vulnerabilities.
3. **Thin Route & Service Architecture (9.5E, 9.5F, 9.5G, 9.5L)**:
   - Routes remain lightweight dispatchers delegating to `CadService` and `DrawingService`, ensuring zero CAD logic duplication.
   - Pydantic models for all requests, responses, and errors.
4. **Drawing & Dimension Generation Endpoints (9.5H & 9.5I)**:
   - `POST /api/v1/projects/{id}/drawings`: Generates standard 5-view TechDraw drawing (`.FCStd`, `.svg`, `.dxf`).
   - `POST /api/v1/projects/{id}/dimensioned-drawing`: Executes complete Phase 9A deterministic dimensioning pipeline.
5. **Secure Artifact Downloads (9.5J)**:
   - `GET /api/v1/projects/{id}/artifacts/{artifact_id}`: Validates artifact ownership against project metadata and safely streams `.FCStd`, `.svg`, `.dxf`, `.json`, and `.txt` files.
6. **CLI & Engine Compatibility (9.5Q)**:
   - Both CLI (`python -m src.main ...`) and FastAPI server (`uvicorn src.api.app:app`) remain 100% functional side-by-side.

### Endpoints Created:
| Method | Route | Description |
|:---|:---|:---|
| `GET` | `/api/v1/health` | Service health status |
| `POST` | `/api/v1/projects` | Upload STEP file & create project |
| `GET` | `/api/v1/projects/{id}` | Project status & artifact list |
| `POST` | `/api/v1/projects/{id}/analyze` | Execute full CAD analysis |
| `GET` | `/api/v1/projects/{id}/features` | Retrieve recognized features |
| `GET` | `/api/v1/projects/{id}/dimensions` | Retrieve dimension candidates & coverage |
| `POST` | `/api/v1/projects/{id}/drawings` | Generate standard 5-view drawing |
| `POST` | `/api/v1/projects/{id}/dimensioned-drawing` | Generate complete dimensioned drawing |
| `GET` | `/api/v1/projects/{id}/artifacts/{artifact_id}` | Download generated CAD artifact |

### Server Startup Command:
```powershell
& "D:\anaconda\envs\sales\python.exe" -m uvicorn src.api.app:app --host 127.0.0.1 --port 8000 --reload
```

### Status:
- [x] FastAPI service layer implemented with clean Pydantic schemas
- [x] Thin routing and service separation established
- [x] All 14 API tests in `test_api.py` passed
- [x] All 9 regression suites (Phases 1–9A) passed with 100% success
- [x] Documentation created (`docs/api.md`) and updated (`docs/architecture.md`)
- [x] Phase 9.5 Complete

---

## Phase 10: Engineering Drawing Intelligence Layer (10A–10O)

**Date**: 2026-08-26  
**Module**: `src/intelligence/` (`decision_model.py`, `tools.py`, `providers.py`, `vision_reviewer.py`, `pipeline.py`)  
**Test Suite**: `tests/test_phase10_engineering_intelligence.py` (All 7 Tests Passed)  

### Highlights & Architecture:
1. **Core Philosophy Enforced**:
   - The AI acts strictly as an advisory reasoning agent for engineering intent, view selection, redundancy pruning, and visual critique.
   - FreeCAD / OCCT remains the immutable, mathematical source of truth for numeric values and B-Rep topology.
   - The AI never calculates, guesses, or invents dimensions.
2. **CAD Tool Registry (`src/intelligence/tools.py`)**:
   - Provides 12 structured, programmatic tools (`get_model_summary`, `get_features`, `get_feature`, `get_dimension_candidates`, `get_dimension`, `measure_distance`, `measure_angle`, `get_available_views`, `get_view_visibility`, `get_datums`, `get_dimension_dependencies`, `get_dimension_coverage`).
3. **Pluggable Multi-Model Reasoning Providers (`src/intelligence/providers.py`)**:
   - `EngineeringReasoningProvider` base class.
   - `MockReasoningProvider`: High-quality deterministic expert baseline for offline testing.
   - `ClaudeReasoningProvider`: Multi-model connector for Anthropic Claude (e.g. `claude-3-7-sonnet-20250219`).
   - `GeminiReasoningProvider`: Multi-model connector for Google Gemini (e.g. `gemini-2.5-pro` / `gemini-2.5-flash`).
4. **Deterministic Validation Gatekeeper (`src/intelligence/pipeline.py`)**:
   - Verifies candidate ID existence, validates exact OCCT numerical values within $10^{-3}\text{ mm}$, checks B-Rep face existence, and flags `validation_failed` on any hallucination attempt.
5. **Multimodal Drawing Vision Reviewer (`src/intelligence/vision_reviewer.py`)**:
   - Critiques rendered SVG sheet layout, visual readability, text overlaps, and missing visible annotations.
6. **Outputs Generated for Reference Model `Pieza18_1.STEP`**:
   - `output/Pieza18_1_engineering_context.json` (54 KB) — Structured CAD context fed to AI
   - `output/Pieza18_1_engineering_decisions.json` (24 KB) — Auditable engineering decisions with rationales
   - `output/Pieza18_1_intelligent_drawing.FCStd` (118 KB) — Reopenable drawing with 14 approved dimensions

---

## Phase 11: Live Multimodal Engineering Intelligence (11A–11H)

**Date**: 2026-08-26  
**Module**: `src/intelligence/` (`providers.py`, `review_engine.py`, `decision_model.py`, `tools.py`), `src/api/routes/ai_review.py`  
**Test Suite**: `tests/test_phase11_live_ai.py` (All 6 Tests Passed)  

### Highlights & Architecture:
1. **Live Provider Implementations (11A)**:
   - **Claude Provider (`ClaudeReasoningProvider`)**: Connected via Anthropic Messages API (`https://api.opusmax.pro/v1/messages`) utilizing `claude-3-5-sonnet-20241022` with robust thinking-block text extraction and 8192 token limit.
   - **Gemini Provider (`GeminiReasoningProvider`)**: Connected via Google Gemini API (`gemini-2.5-flash`) with structured JSON schema responses.
   - **Mock Provider (`MockReasoningProvider`)**: Deterministic expert baseline for offline testing.
   - **Strict API Key Validation**: Selecting `--provider claude` or `--provider gemini` when environment variables are missing raises an immediate, explicit error (zero silent fallbacks).
2. **Deterministic Validation Gatekeeper for AI Recommendations (11C)**:
   - Every AI recommendation is checked before acceptance:
     - Referenced `dimension_id` must match real `DimensionCandidate` IDs.
     - Referenced `feature_id` must match real recognized features.
     - Referenced B-Rep entities in `evidence[]` must exist in the 3D CAD model.
     - Zero AI-invented measurements are permitted; unmodeled geometry must be flagged as `requires_new_cad_analysis = True`.
3. **Structured Multimodal Engineering Review (11D)**:
   - Evaluates:
     - Overall assessment (`good`, `acceptable`, `needs_improvement`).
     - Strengths (`good_aspects[]`).
     - Improvement areas (`improvement_areas[]`).
     - Recommendations (`recommendations[]` with actions: `include`, `exclude`, `investigate`, `section_view`).
     - Warnings & Human review triggers (`warnings[]`, `requires_human_review`).
4. **Independent Model Consensus on `Pieza18_1.STEP`**:
   - Both Claude and Gemini independently reached unanimous consensus:
     - **Ambiguous Geometry**: Partial $61.3^\circ$ vaulted arch on `BORE_003` is ambiguous and requires a dedicated section view or arc callout (`D013`).
     - **Redundancy Pruning**: Total depth $D017$ ($8.05\text{ mm}$) is derived from $D015 + D016$ and must be excluded to prevent tolerance stack buildup.
     - **Fillet Consolidation**: 16 uniform $R2.00\text{ mm}$ fillets should be summarized in general drawing notes (`ALL FILLETS R2 UNLESS NOTED`).
     - **Seating Datum**: Base `Face16` ($Z=0$) should be formally designated as Datum [A].
     - **100% Gatekeeper Pass Rate**: 0 recommendations rejected across all live models.
5. **FastAPI Endpoints (11E)**:
   - `POST /api/v1/projects/{project_id}/ai-review`: Executes live review using specified provider (`mock`, `claude`, `gemini`).
   - `GET /api/v1/projects/{project_id}/ai-review`: Retrieves existing review artifacts and recommendations.
6. **Outputs Generated for Reference Model `Pieza18_1.STEP`**:
   - `output/Pieza18_1_ai_review.json` (12 KB)
   - `output/Pieza18_1_ai_review.txt` (4 KB)
   - `output/Pieza18_1_ai_review_claude.json` (12 KB)
   - `output/Pieza18_1_ai_review_gemini.json` (8 KB)
   - `output/Pieza18_1_ai_review_comparison.json` (3 KB)

### CLI Command:
```powershell
& "C:\Program Files\FreeCAD 1.1\bin\python.exe" -m src.main ai-review input/Pieza18_1.STEP --provider mock
& "C:\Program Files\FreeCAD 1.1\bin\python.exe" -m src.main ai-review input/Pieza18_1.STEP --provider claude
& "C:\Program Files\FreeCAD 1.1\bin\python.exe" -m src.main ai-review input/Pieza18_1.STEP --provider gemini
```

### Status:
- [x] Live Claude provider implemented and verified
- [x] Live Gemini provider implemented and verified
- [x] Mock expert provider verified
- [x] Strict API key error handling with zero silent fallbacks
- [x] Multimodal review engine answering all 7 criteria
- [x] Deterministic validation gatekeeper verifies 100% of AI recommendations
- [x] FastAPI review endpoints (`POST` & `GET` `/ai-review`) implemented
- [x] Phase 11 Complete

---

## Phase 11.5: Multimodal Input Pipeline Audit

**Date**: 2026-08-26  
**Target Reference Drawing**: `output/Pieza18_1_complete_dimensioned.FCStd`  
**Test Suite**: `tests/test_phase11_multimodal_audit.py`

### Key Results & Findings:
1. **Deterministic Drawing State**: Direct inspection of `Pieza18_1_complete_dimensioned.FCStd` confirmed 14 placed dimensions (`DrawViewDimension`) across 5 orthographic views.
2. **Root Cause Analysis (Code D)**:
   - Traced runtime request payloads for Claude and Gemini.
   - Proved that previous reviews received only serialized JSON text metadata (`placed_dimension_ids: []` from bare STEP context) with zero visual payload attached.
   - Identified and documented root cause Code D (*The models received only metadata*).
3. **Artifacts Generated**:
   - `output/Pieza18_1_multimodal_input_audit.json`
   - `output/audit/Pieza18_1_complete_dimensioned_audit_sheet.svg`
4. **Status**: [x] Passed cleanly

---

## Phase 11.6: Real Visual Engineering Drawing Review

**Date**: 2026-08-26  
**Target Reference Drawing**: `output/Pieza18_1_complete_dimensioned.FCStd`  
**Rendered Artifact**: `output/audit/Pieza18_1_complete_dimensioned.png` (2481x1754 px, 150 DPI, 95 KB)  
**Test Suite**: `tests/test_phase11_6_visual_review.py`

### Key Capabilities & Findings:
1. **Real Visual Multimodal Input**:
   - High-resolution PNG rasterization of `Pieza18_1_complete_dimensioned.FCStd` at 150 DPI.
   - Base64 encoded image transmitted to Claude (`claude-3-5-sonnet-20241022`) via Anthropic Messages API (`image` content block) and Gemini (`gemini-2.5-flash`) via `inline_data` image part.
2. **Exact Request Payload Instrumentation**:
   - `output/Pieza18_1_multimodal_request_claude.json` and `output/Pieza18_1_multimodal_request_gemini.json` record exact SHA-256 hashes, base64 char length, byte size, and prompts.
3. **Visual Dimension Recognition**:
   - **Deterministic Ground Truth**: 14 placed dimensions, 5 views.
   - **Claude Visually Observed**: 14 dimensions (`MATCH`), 5 views (`TOP`, `FRONT`, `LEFT`, `RIGHT`, `BOTTOM`).
   - **Gemini Visually Observed**: 14 dimensions (`MATCH`), 5 views (`TOP`, `FRONT`, `LEFT`, `RIGHT`, `BOTTOM`).
4. **Zero FCStd Mutation**:
   - SHA-256 hash before review: `4cf07a7579286451...`
   - SHA-256 hash after review: `4cf07a7579286451...` (100% immutable).
5. **Artifacts Generated**:
   - `output/Pieza18_1_visual_ground_truth.json`
   - `output/Pieza18_1_multimodal_request_claude.json`
   - `output/Pieza18_1_multimodal_request_gemini.json`
   - `output/Pieza18_1_visual_review_claude.json`
   - `output/Pieza18_1_visual_review_gemini.json`
   - `output/Pieza18_1_visual_comparison.json`
   - `output/Pieza18_1_visual_review.txt`
   - `output/audit/Pieza18_1_complete_dimensioned.png`
6. **Regression Status**: All 13 regression suites passing cleanly.

---

## Phase 12: Engineering Issue & Recommendation Engine

**Date**: 2026-08-26  
**Module**: `src/intelligence/issues.py`, `src/intelligence/recommendations.py`, `src/intelligence/issue_engine.py`, `src/api/routes/issues.py`  
**Test Suite**: `tests/test_phase12_engineering_issues.py` (All 16 Tests Passed)  
**API Suite**: `tests/test_api.py` (All 22 Tests Passed)  
**Full Regression Suite**: `tests/run_regression.py` (All 14 Suites Passed)

### Key Architectural Capabilities:
1. **Engineering Issue Model (`src/intelligence/issues.py`)**:
   - Standardized `EngineeringIssue` data structure with categories (`missing_dimension`, `ambiguous_geometry`, `drawing_clarity`, `dimension_layout`, `section_view`, `datum`, `feature_communication`, `manufacturing_communication`, `other`), severities (`info`, `low`, `medium`, `high`, `critical`), provenance tracking (`source_providers`, `source_models`), and approval statuses (`REVIEWED`, `VALIDATED`, `AWAITING_HUMAN_APPROVAL`, `APPROVED`, `REJECTED`, `EXECUTED`).
2. **Recommendation Model (`src/intelligence/recommendations.py`)**:
   - Structured `EngineeringRecommendation` with actions (`ADD_SECTION_VIEW`, `ADD_DETAIL_VIEW`, `ADD_DIMENSION`, `MOVE_DIMENSION`, `ADD_LEADER_LINE`, `ADD_DRAWING_NOTE`, `ADD_DATUM_FEATURE_SYMBOL`, `INVESTIGATE`), affected CAD entities, dimensions, and views.
3. **Consensus & Evidence Engine (`src/intelligence/issue_engine.py`)**:
   - Ingests multimodal visual reviews from Claude and Gemini.
   - Consolidates duplicated findings across providers into unified consensus issues.
   - Enriches each issue with exact mathematical B-Rep CAD proof from FreeCAD/OCCT (e.g. `BORE_003` diameter $30.00\text{ mm}$, sweep angle $61.32^\circ$ across `Face8`, `Face9`).
   - Rejects hallucinated features (`FEATURE_999`), candidate IDs (`D999`), and B-Rep faces (`Face999`) via `DeterministicValidationGatekeeper`.
4. **Human Approval Boundary Enforced**:
   - All generated recommendations are set strictly to `AWAITING_HUMAN_APPROVAL`.
   - `approve_recommendation` and `reject_recommendation` update issue/recommendation states with **zero CAD mutation**.
5. **Zero FCStd Mutation Guarantee**:
   - Original `output/Pieza18_1_complete_dimensioned.FCStd` SHA-256 hash verified identical before and after review (`8a56d0d511c0a39d...`).
6. **FastAPI Endpoints**:
   - `GET /api/v1/projects/{id}/issues`: Returns validated issues with CAD proof.
   - `GET /api/v1/projects/{id}/recommendations`: Returns actionable recommendations.
   - `GET /api/v1/projects/{id}/review-summary`: Returns provider consensus summary.
   - `POST /api/v1/projects/{id}/recommendations/{id}/approve`: Approves recommendation.
   - `POST /api/v1/projects/{id}/recommendations/{id}/reject`: Rejects recommendation.
7. **CLI Integration**:
   - `python -m src.main engineering-review input/Pieza18_1.STEP`
8. **Generated Artifacts**:
   - `output/Pieza18_1_engineering_issues.json`
   - `output/Pieza18_1_engineering_recommendations.json`
   - `output/Pieza18_1_engineering_review_summary.json`
   - `output/Pieza18_1_engineering_review.txt`

---

## Phase 13: First Engineering Product Frontend

**Date**: 2026-08-26  
**Application Directory**: `frontend/`  
**Frontend Framework**: React 19 + TypeScript + Vite + Tailwind CSS + Three.js + Lucide Icons  
**Test Suite**: `frontend/tests/frontend.test.tsx` (All 6 Tests Passed)  
**Production Build**: `npm run build` (Clean compile, 0 errors)

### Key Capabilities Implemented:
1. **Typed API Client (`frontend/lib/api.ts`)**:
   - Strictly typed client mirroring FastAPI schemas with 0% `any` usage.
   - Handles network errors, loading states, and configurable backend URL (`VITE_API_BASE_URL` / `NEXT_PUBLIC_API_BASE_URL`).
2. **Project Upload Flow (`/projects`)**:
   - Drag-and-drop STEP upload accepting `.step` and `.stp` models.
   - Connects to `POST /api/v1/projects` and triggers automated CAD analysis.
3. **Interactive 3D B-Rep Viewport (`src/components/Viewer3D.tsx`)**:
   - Three.js WebGL viewport with Orbit controls (rotate, zoom, pan, fit-to-view).
   - Preset camera view angles: `ISO`, `FRONT`, `TOP`, `RIGHT`, `BOTTOM`.
   - Interactive feature selection and highlighting linked with B-Rep faces.
4. **2D TechDraw Engineering Sheet Viewer (`src/components/DrawingViewer.tsx`)**:
   - Renders 5-view orthographic sheets with 14 placed dimensions.
   - One-click downloads: `[ Download SVG ]`, `[ Download DXF ]`, `[ Open in FreeCAD ]`.
5. **Interactive Tables**:
   - `FeaturesTable.tsx`: Displays feature IDs, types, exact parameters, B-Rep faces, and 100% deterministic status.
   - `DimensionsTable.tsx`: Displays nominal values, best orthographic views, linked features, and placement status.
6. **Multimodal AI Review Panel (`src/components/AIReviewPanel.tsx`)**:
   - Side-by-side tabs for Claude 3.5 Sonnet, Google Gemini 2.5 Flash, and Provider Consensus.
   - Displays 14/14 visual dimension count matches and observations.
7. **Engineering Issues & Human Approval Gate (`src/components/EngineeringIssuesPanel.tsx`)**:
   - Displays Phase 12 issues with deterministic B-Rep CAD proof.
   - Interactive `[ APPROVE ]` and `[ REJECT ]` buttons calling FastAPI approval routes.
   - Enforces human approval boundary with **zero automatic CAD modification**.









