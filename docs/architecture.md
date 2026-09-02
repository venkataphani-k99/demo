# CAD Intelligence & Automation Architecture

## System Architecture

```
                      ┌──────────────────────────────┐
                      │    Next.js Web Frontend      │
                      │  (UI / Viewer / Dashboard)   │
                      └──────────────┬───────────────┘
                                     │
                                     │ HTTP REST / JSON (CORS localhost:3000)
                                     ▼
                      ┌──────────────────────────────┐
                      │    FastAPI Service Layer     │
                      │          (/api/v1)           │
                      └──────────────┬───────────────┘
                                     │
                                     │ Thin Dispatch / Pydantic Contracts
                                     ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                    Application Orchestration Layer                         │
│   ┌────────────────────┬────────────────────┬──────────────────────────┐   │
│   │   ProjectService   │     CadService     │      DrawingService      │   │
│   │(workspaces/storage)│ (inspection/dims)  │(TechDraw/standard/dimmed)│   │
│   └────────────────────┴────────────────────┴──────────────────────────┘   │
└────────────────────────────────────┬───────────────────────────────────────┘
                                     │
                                     │ Deterministic Engine Calls
                                     ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                      CAD Intelligence Modules                              │
│  - step_loader.py         : Deterministic STEP import & validation         │
│  - topology.py            : Dual adjacency graph & B-Rep connectivity      │
│  - geometry.py            : Analytic surface/curve parameter extraction    │
│  - measurements.py        : Exact OCCT mathematical measurement engine     │
│  - features.py            : Rule-based engineering feature recognition     │
│  - dimensions.py          : Candidate dimension extraction & dedup         │
│  - view_analysis.py       : 3D-to-2D orthographic projection visibility    │
│  - dimension_placement.py : Collision-free drawing view placement         │
│  - dimension_dependencies : Mathematical chain & dependency tracking       │
│  - dimension_redundancy   : Redundancy filtering & feature coverage        │
│  - techdraw_generator.py  : Automated FreeCAD TechDraw page generation     │
└────────────────────────────────────┬───────────────────────────────────────┘
                                     │
                                     │ FreeCAD / OCCT Python 3.11 API
                                     ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                       FreeCAD 1.1.3 + OpenCASCADE                          │
│  - TopoDS_Shape / B-Rep Data Structures                                    │
│  - Analytic Surface Evaluators (Geom_Cylinder, Geom_Plane, Geom_Toroid)    │
│  - TechDraw Engine (DrawPage, DrawSVGTemplate, DrawProjGroup, DrawViewDim) │
└────────────────────────────────────┬───────────────────────────────────────┘
                                     │
                                     │ Output Artifacts
                                     ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                       Generated CAD Artifacts                              │
│  - Reopenable CAD Drawings : .FCStd                                        │
│  - Vector Graphics         : .svg                                          │
│  - CAD Exchange            : .dxf                                          │
│  - Structured Data         : .json                                         │
│  - Engineering Reports     : .txt                                          │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## Separation of Concerns

1. **Frontend Layer (Future Next.js)**:
   - File upload interface with drag-and-drop.
   - Interactive 3D geometry viewer & 2D drawing preview.
   - Real-time processing indicator & project dashboard.
   - Feature & dimension inspection tables.
   - Direct download links for FCStd, SVG, and DXF artifacts.

2. **API & Service Layer (FastAPI)**:
   - Secure request boundary and input validation.
   - Workspace isolation to prevent path traversal.
   - Clean Pydantic schemas for all payloads.
   - Stable HTTP REST API `/api/v1/` contract.

3. **CAD Geometry Engine Responsibility**:
   - Exact geometry & mathematical calculations.
   - Deterministic feature recognition and exact measurements.
   - Automated orthographic projection and dimension placement.

> **Golden Rule**: An LLM must NEVER guess or calculate engineering geometry/dimensions. CAD geometry engines are the single source of truth.
