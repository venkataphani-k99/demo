"""Gemini-Assisted 2D-to-3D CAD Reconstruction Engine.

Uses Gemini as the intelligent CAD reasoning brain to interpret orthographic 2D drawings,
produce a strict, evidence-backed CAD reconstruction plan, and execute it through controlled
FreeCAD / OpenCASCADE parametric solid primitives.
"""
from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import src.cad.freecad_env  # noqa: F401
from src.cad.mesh_exporter import extract_mesh_from_shape
from src.drawing.cad_reconstruction_engine import CADReconstructionExecutor
from src.drawing.reconstruction_schemas import (
    CADBoundingBox,
    CADCoordinateSystem,
    CADOperationStep,
    CADPartMetadata,
    CADReconstructionPlan,
    CADValidationCheck,
    DrawingEvidence,
)
from src.drawing.renderer import build_manifest


GEMINI_CAD_RECONSTRUCTION_PROMPT = """\
You are an expert mechanical CAD reconstruction engine.

Analyze the uploaded 2D engineering drawing and reconstruct the exact 3D mechanical part represented by the orthographic views.

Your output will be executed by a FreeCAD/OpenCASCADE backend and displayed as an interactive 3D model.

IMPORTANT:
1. Do not redesign the part.
2. Do not create a visually similar part.
3. Do not add artistic or decorative geometry.
4. Do not use generic mechanical-part templates.
5. Replicate only geometry supported by the drawing.
6. Correlate the front, top, side, section and detail views into one common 3D coordinate system.
7. Use explicit dimensions as the source of truth.
8. Every hole, pocket, boss, slot, cutout, fillet and chamfer must be mapped to evidence in the drawing.
9. If a critical dimension is missing, mark that feature as AMBIGUOUS instead of guessing.
10. Prefer exact parametric CAD operations over approximate meshes.

The reconstruction must follow this order:
1. Create the primary base geometry.
2. Reconstruct the outer shape from orthographic projections.
3. Apply major cuts and pockets.
4. Add protrusions and bosses.
5. Create holes and slots.
6. Add only explicitly supported fillets and chamfers.
7. Validate the final bounding dimensions against all views.

You MUST choose operations ONLY from the controlled CAD toolset:
- create_box(feature_id, length_x, width_y, height_z, origin)
- create_cylinder(feature_id, radius, height, origin, axis)
- create_cone(feature_id, radius1, radius2, height, origin, axis)
- create_arbitrary_profile(feature_id, points, extrude_vector, is_spline)
- extrude_polygon(feature_id, points, extrude_vector)
- rotational_pattern(source_id, count, angle_step_deg, center, axis)
- linear_pattern(source_id, count, spacing, direction)
- revolve_profile(feature_id, points, axis_origin, axis_direction, angle_deg)
- cut_feature(target_id, tool_id)
- union_feature(target_id, tool_id)
- drill_hole(feature_id, diameter, depth, center, axis, through_all)
- apply_fillet(edge_indices, radius)
- apply_chamfer(edge_indices, distance)

Return ONLY a JSON object matching this exact JSON schema:
{
  "part_metadata": {
    "part_name": "PART_NAME",
    "drawing_units": "mm",
    "material": "Steel / Aluminium / etc.",
    "overall_confidence": 0.95
  },
  "bounding_box": {
    "x_length": 100.0,
    "y_length": 60.0,
    "z_length": 20.0
  },
  "coordinate_system": {
    "origin_description": "Bottom-left corner of base solid or rotation center",
    "front_view_plane": "XZ",
    "top_view_plane": "XY"
  },
  "reconstruction_steps": [
    {
      "step_id": "step_1_base",
      "order": 1,
      "operation": "create_box",
      "parameters": {
        "feature_id": "base_plate",
        "length_x": 100.0,
        "width_y": 60.0,
        "height_z": 20.0,
        "origin": [0.0, 0.0, 0.0]
      },
      "drawing_evidence": {
        "source_view": "Front & Top Views",
        "callout_dimension": "100 x 60 x 20",
        "confidence": 1.0,
        "ambiguity_note": null
      }
    }
  ],
  "validation_checks": [
    {
      "view": "Top View",
      "expected_dimension": 100.0,
      "measured_axis": "X",
      "tolerance": 0.5
    }
  ],
  "is_fully_constrained": true,
  "ambiguous_features": []
}
"""


def _strip_json_fence(text: str) -> str:
    """Remove markdown code fences from JSON output."""
    t = text.strip()
    if t.startswith("```json"):
        t = t[7:]
    elif t.startswith("```"):
        t = t[3:]
    if t.endswith("```"):
        t = t[:-3]
    return t.strip()


class GeminiCADReconstructionEngine:
    """End-to-end engine orchestrating Gemini vision reasoning and FreeCAD solid generation."""

    def __init__(
        self,
        gemini_key: Optional[str] = None,
        gemini_model: Optional[str] = None,
        workspace_root: Optional[Path] = None,
    ):
        self._gemini_key = gemini_key or os.getenv("GEMINI_API_KEY", "")
        self._gemini_model = gemini_model or os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        self.workspace_root = workspace_root or (Path("workspaces") / "drawing_projects")

    def generate_reconstruction_plan(
        self,
        project_id: str,
        png_path: Path,
        output_dir: Optional[Path] = None,
    ) -> CADReconstructionPlan:
        """Sends drawing PNG and any cropped views to Gemini and parses the strict CAD reconstruction plan."""
        out_dir = output_dir or (self.workspace_root / project_id)
        out_dir.mkdir(parents=True, exist_ok=True)
        plan_path = out_dir / "gemini_cad_reconstruction_plan.json"

        if not self._gemini_key:
            raise ValueError("GEMINI_API_KEY is not configured.")

        # Prepare multimodal content parts
        parts = []

        # 1. Full Drawing Sheet
        img_data = png_path.read_bytes()
        img_b64 = base64.standard_b64encode(img_data).decode("ascii")
        parts.append({
            "inline_data": {
                "mime_type": "image/png",
                "data": img_b64,
            }
        })

        # 2. Attach any high-resolution cropped views available
        cropped_views = list(out_dir.glob("view_*.png"))
        for cv in cropped_views[:4]:  # attach up to 4 key cropped views
            cv_bytes = cv.read_bytes()
            cv_b64 = base64.standard_b64encode(cv_bytes).decode("ascii")
            parts.append({
                "inline_data": {
                    "mime_type": "image/png",
                    "data": cv_b64,
                }
            })

        # 3. Prompt Text
        parts.append({"text": GEMINI_CAD_RECONSTRUCTION_PROMPT})

        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "temperature": 0.0,
                "response_mime_type": "application/json",
            },
        }

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self._gemini_model}:generateContent?key={self._gemini_key}"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Gemini CAD API HTTP {e.code}: {body}")
        except Exception as e:
            raise RuntimeError(f"Gemini CAD API request failed: {e}")

        # Extract text response
        candidates = resp_data.get("candidates", [])
        if not candidates:
            raise RuntimeError("Gemini returned no candidates for CAD reconstruction.")
        
        raw_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "{}")
        clean_json = _strip_json_fence(raw_text)
        data = json.loads(clean_json)

        plan = CADReconstructionPlan.model_validate(data)
        plan_path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
        return plan

    def execute_and_export(
        self,
        project_id: str,
        plan: CADReconstructionPlan,
        output_dir: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Execute the CAD reconstruction plan using controlled FreeCAD / OCCT tools and export STEP + Mesh."""
        out_dir = output_dir or (self.workspace_root / project_id)
        out_dir.mkdir(parents=True, exist_ok=True)

        executor = CADReconstructionExecutor(doc_name=f"Reconstruct_{project_id[:8]}")
        try:
            exec_res = executor.execute_plan(plan)
            shape = exec_res["shape"]

            # Save STEP file
            step_file = out_dir / "reconstructed_step.step"
            shape.exportStep(str(step_file))

            # Extract 3D Three.js mesh
            mesh_data = extract_mesh_from_shape(shape, tolerance=0.15)
            mesh_data["project_id"] = project_id
            mesh_data["filename"] = f"{project_id}.step"
            mesh_data["bounding_box"] = exec_res["bounding_box"]
            mesh_data["topology"] = {
                "solids": exec_res["solids_count"],
                "faces": exec_res["faces_count"],
                "edges": exec_res["edges_count"],
                "vertices": exec_res["vertices_count"],
            }
            mesh_data["validation_results"] = exec_res["validation_results"]
            mesh_data["execution_log"] = exec_res["execution_log"]

            # Cache mesh JSON
            mesh_file = out_dir / "reconstructed_mesh.json"
            mesh_file.write_text(json.dumps(mesh_data, indent=2), encoding="utf-8")

            return {
                "project_id": project_id,
                "status": "SUCCESS" if exec_res["success"] else "FAILED",
                "step_path": str(step_file),
                "mesh_file": str(mesh_file),
                "mesh_data": mesh_data,
                "execution_result": exec_res,
            }
        finally:
            executor.close()
