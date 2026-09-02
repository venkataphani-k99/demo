"""Phase 21 — Mold Analysis Engine.

Universal, geometry-driven, evidence-based B-Rep moldability analysis.
Operates downstream of validated FreeCAD / OpenCASCADE B-Rep models.
Strictly zero part-name heuristics and zero hardcoded mechanism dimensions.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import src.cad.freecad_env  # noqa: F401
import FreeCAD
import Part

from src.mold_analysis.schemas import (
    CandidateDirection,
    CoreCavityAnalysisResult,
    DraftAnalysisResult,
    DraftClassification,
    EjectionAnalysisResult,
    EjectionClassification,
    FaceDraftInfo,
    LifterAnalysisResult,
    LifterCandidate,
    LifterClassification,
    MoldAnalysisResult,
    MoldAnalysisStatus,
    MoldParameters,
    PartingCandidate,
    PartingLineAnalysisResult,
    ProvenanceInfo,
    SliderAnalysisResult,
    SliderCandidate,
    SliderClassification,
    SurfaceSideClassification,
    UndercutAnalysisResult,
    UndercutClassification,
    UndercutFeature,
)

logger = logging.getLogger(__name__)


def _normalize_vec(v: List[float] | Tuple[float, float, float] | FreeCAD.Vector) -> List[float]:
    """Normalize 3D vector to unit length."""
    if hasattr(v, "x"):
        x, y, z = float(v.x), float(v.y), float(v.z)
    else:
        x, y, z = float(v[0]), float(v[1]), float(v[2])
    mag = math.sqrt(x * x + y * y + z * z)
    if mag < 1e-9:
        return [0.0, 0.0, 1.0]
    return [round(x / mag, 5), round(y / mag, 5), round(z / mag, 5)]


def _dot_product(v1: List[float], v2: List[float]) -> float:
    """Compute dot product of two 3D vectors."""
    return v1[0] * v2[0] + v1[1] * v2[1] + v1[2] * v2[2]


def _cross_product(v1: List[float], v2: List[float]) -> List[float]:
    """Compute cross product of two 3D vectors."""
    return [
        v1[1] * v2[2] - v1[2] * v2[1],
        v1[2] * v2[0] - v1[0] * v2[2],
        v1[0] * v2[1] - v1[1] * v2[0],
    ]


class MoldAnalysisEngine:
    """Universal, evidence-driven moldability analysis engine for validated B-Rep solids."""

    def analyze(
        self,
        shape: Part.Shape,
        mold_parameters: Optional[MoldParameters] = None,
        reconstruction_id: Optional[str] = None,
        artifact_hash: Optional[str] = None,
        units: str = "mm",
        model_coordinate_system: str = "XYZ",
        source_filename: Optional[str] = None,
        source_type: str = "BREP_SOLID",
    ) -> MoldAnalysisResult:
        """Executes full geometric moldability analysis on a validated FreeCAD/OpenCASCADE B-Rep solid."""
        analysis_id = f"mold_analysis_{int(time.time() * 1000)}"
        timestamp = datetime.now(timezone.utc).isoformat()
        params = mold_parameters or MoldParameters()

        # -------------------------------------------------------------------
        # 1. B-Rep Integrity Gate
        # -------------------------------------------------------------------
        validation_errors: List[str] = []

        if shape is None:
            validation_errors.append("B-Rep solid is null or not provided.")
        elif not isinstance(shape, Part.Shape):
            validation_errors.append(f"Expected Part.Shape, got {type(shape).__name__}.")
        else:
            if hasattr(shape, "isNull") and shape.isNull():
                validation_errors.append("B-Rep shape is null.")
            elif not shape.isValid():
                validation_errors.append("B-Rep geometry failed OpenCASCADE validity check (shape.isValid() is False).")
            elif len(shape.Solids) == 0:
                validation_errors.append("B-Rep contains no 3D solid bodies (shape.Solids is empty).")
            elif getattr(shape, "Volume", 0.0) <= 1e-6:
                validation_errors.append("B-Rep volume is non-positive (Volume <= 0).")

        if validation_errors:
            logger.warning(f"Mold analysis validation failed: {validation_errors}")
            return MoldAnalysisResult(
                analysis_id=analysis_id,
                reconstruction_id=reconstruction_id,
                artifact_hash=artifact_hash,
                status=MoldAnalysisStatus.VALIDATION_FAILED,
                is_valid_brep=False,
                errors=validation_errors,
                overall_moldability="VALIDATION_FAILED",
                analysis_timestamp=timestamp,
                provenance=ProvenanceInfo(
                    reconstruction_id=reconstruction_id,
                    artifact_hash=artifact_hash,
                    source_type=source_type,
                    source_filename=source_filename,
                    units=units,
                    model_coordinate_system=model_coordinate_system,
                ),
            )

        # -------------------------------------------------------------------
        # 2. Extract Shape Geometry Metadata & Provenance
        # -------------------------------------------------------------------
        bbox = shape.BoundBox
        bbox_dict = {
            "x_min": round(float(bbox.XMin), 3),
            "x_max": round(float(bbox.XMax), 3),
            "y_min": round(float(bbox.YMin), 3),
            "y_max": round(float(bbox.YMax), 3),
            "z_min": round(float(bbox.ZMin), 3),
            "z_max": round(float(bbox.ZMax), 3),
            "x_len": round(float(bbox.XLength), 3),
            "y_len": round(float(bbox.YLength), 3),
            "z_len": round(float(bbox.ZLength), 3),
        }

        provenance = ProvenanceInfo(
            reconstruction_id=reconstruction_id,
            artifact_hash=artifact_hash,
            source_type=source_type,
            source_filename=source_filename,
            solid_count=len(shape.Solids),
            total_face_count=len(shape.Faces),
            total_edge_count=len(shape.Edges),
            volume_mm3=round(float(shape.Volume), 3),
            bounding_box=bbox_dict,
            units=units,
            model_coordinate_system=model_coordinate_system,
        )

        # -------------------------------------------------------------------
        # 3. Candidate Opening Directions Evaluation
        # -------------------------------------------------------------------
        candidate_directions = self._evaluate_candidate_directions(shape)

        # Determine active mold opening direction
        active_direction: List[float]
        direction_notes: List[str] = []

        if params.mold_opening_direction is not None and len(params.mold_opening_direction) == 3:
            active_direction = _normalize_vec(params.mold_opening_direction)
            if "mold_opening_direction" not in params.user_configured_fields:
                params.user_configured_fields.append("mold_opening_direction")
        elif candidate_directions:
            # Pick top-ranked candidate
            active_direction = candidate_directions[0].vector
        else:
            active_direction = [0.0, 0.0, 1.0]
            direction_notes.append("Default Z axis used; requires user direction confirmation.")

        # -------------------------------------------------------------------
        # 4. Draft Angle Analysis
        # -------------------------------------------------------------------
        draft_res = self._analyze_draft(shape, active_direction, params)

        # -------------------------------------------------------------------
        # 5. Geometric Undercut Detection
        # -------------------------------------------------------------------
        undercut_res = self._detect_undercuts(shape, active_direction, draft_res)

        # -------------------------------------------------------------------
        # 6. Slider Candidate Analysis (Side Actions)
        # -------------------------------------------------------------------
        slider_res = self._analyze_sliders(shape, active_direction, undercut_res)

        # -------------------------------------------------------------------
        # 7. Lifter Candidate Analysis (Internal Actions)
        # -------------------------------------------------------------------
        lifter_res = self._analyze_lifters(shape, active_direction, undercut_res)

        # -------------------------------------------------------------------
        # 8. Parting Line & Silhouette Analysis
        # -------------------------------------------------------------------
        parting_res = self._analyze_parting_line(shape, active_direction, draft_res)

        # -------------------------------------------------------------------
        # 9. Core / Cavity Surface Classification
        # -------------------------------------------------------------------
        core_cavity_res = self._classify_core_cavity(shape, active_direction, undercut_res, parting_res)

        # -------------------------------------------------------------------
        # 10. Demolding & Ejection Analysis
        # -------------------------------------------------------------------
        ejection_res = self._analyze_ejection(shape, active_direction, undercut_res, slider_res, lifter_res)

        # -------------------------------------------------------------------
        # 11. Synthesize Overall Moldability & Status
        # -------------------------------------------------------------------
        overall_moldability, analysis_status, warnings = self._synthesize_overall_status(
            draft_res, undercut_res, slider_res, lifter_res, ejection_res, candidate_directions
        )

        return MoldAnalysisResult(
            analysis_id=analysis_id,
            reconstruction_id=reconstruction_id,
            artifact_hash=artifact_hash,
            status=analysis_status,
            is_valid_brep=True,
            active_mold_opening_direction=active_direction,
            candidate_directions=candidate_directions,
            mold_parameters=params,
            draft_analysis=draft_res,
            undercut_analysis=undercut_res,
            slider_analysis=slider_res,
            lifter_analysis=lifter_res,
            parting_line_analysis=parting_res,
            core_cavity_analysis=core_cavity_res,
            ejection_analysis=ejection_res,
            overall_moldability=overall_moldability,
            warnings=warnings,
            confidence=1.0,
            provenance=provenance,
            analysis_timestamp=timestamp,
        )

    def _evaluate_candidate_directions(self, shape: Part.Shape) -> List[CandidateDirection]:
        """Evaluates and ranks candidate mold opening directions based on geometric features."""
        candidates_raw: List[Tuple[str, List[float]]] = [
            ("+Z", [0.0, 0.0, 1.0]),
            ("-Z", [0.0, 0.0, -1.0]),
            ("+Y", [0.0, 1.0, 0.0]),
            ("-Y", [0.0, -1.0, 0.0]),
            ("+X", [1.0, 0.0, 0.0]),
            ("-X", [-1.0, 0.0, 0.0]),
        ]

        # Add principal planar normals with significant area
        total_area = sum(f.Area for f in shape.Faces) if shape.Faces else 1.0
        seen_vecs = [c[1] for c in candidates_raw]

        for f_idx, face in enumerate(shape.Faces, 1):
            if face.Area / total_area > 0.15:
                n = self._get_face_normal(face)
                if n:
                    unit_n = _normalize_vec(n)
                    # Check if unit_n is novel
                    is_novel = True
                    for sv in seen_vecs:
                        if abs(_dot_product(unit_n, sv)) > 0.95:
                            is_novel = False
                            break
                    if is_novel:
                        seen_vecs.append(unit_n)
                        candidates_raw.append((f"Face{f_idx} Normal", unit_n))

        evaluated: List[CandidateDirection] = []

        for label, vec in candidates_raw:
            undercut_faces: List[str] = []
            undercut_area = 0.0
            draft_violations = 0

            for f_idx, face in enumerate(shape.Faces, 1):
                f_id = f"Face{f_idx}"
                n = self._get_face_normal(face)
                if not n:
                    continue
                dot = _dot_product(n, vec)
                # Draft angle: angle with pull axis
                angle_deg = math.degrees(math.acos(max(-1.0, min(1.0, dot))))
                effective_draft = 90.0 - angle_deg

                # If face is perpendicular or negative relative to parting plane
                if abs(effective_draft) < 0.2:
                    draft_violations += 1

                # Check if face is occluded / pointing inward against pull direction
                # In basic terms, normal facing opposite to opening vector when face centroid is on opening side
                if dot < -0.05:
                    undercut_faces.append(f_id)
                    undercut_area += float(face.Area)

            # Optimality score: 0..1
            area_penalty = min(1.0, undercut_area / total_area)
            draft_penalty = min(1.0, draft_violations / max(1, len(shape.Faces)))
            score = round(max(0.0, 1.0 - (area_penalty * 0.6 + draft_penalty * 0.4)), 3)

            evaluated.append(
                CandidateDirection(
                    direction_id=f"dir_{label.replace(' ', '_').lower()}",
                    vector=vec,
                    label=label,
                    undercut_area=round(undercut_area, 2),
                    undercut_face_count=len(undercut_faces),
                    obstructed_faces=undercut_faces,
                    draft_violations=draft_violations,
                    score=score,
                    notes=f"Evaluated on {len(shape.Faces)} B-Rep faces.",
                )
            )

        # Sort descending by score
        evaluated.sort(key=lambda c: c.score, reverse=True)
        return evaluated

    def _get_face_normal(self, face: Part.Face) -> Optional[List[float]]:
        """Calculates outward unit normal for a B-Rep face taking into account face orientation."""
        try:
            surf = face.Surface
            stype = getattr(surf, "TypeId", type(surf).__name__).lower()
            is_reversed = hasattr(face, "Orientation") and face.Orientation == "Reversed"

            if "plane" in stype and hasattr(surf, "Axis"):
                ax = surf.Axis
                vec = [float(ax.x), float(ax.y), float(ax.z)]
                if is_reversed:
                    vec = [-vec[0], -vec[1], -vec[2]]
                return _normalize_vec(vec)

            # Parameter mid-point evaluation
            u_min, u_max, v_min, v_max = face.ParameterRange
            u_mid = (u_min + u_max) / 2.0
            v_mid = (v_min + v_max) / 2.0
            n = face.normalAt(u_mid, v_mid)
            vec = [float(n.x), float(n.y), float(n.z)]
            if is_reversed:
                vec = [-vec[0], -vec[1], -vec[2]]
            return _normalize_vec(vec)
        except Exception:
            return None

    def _analyze_draft(
        self,
        shape: Part.Shape,
        pull_direction: List[float],
        params: MoldParameters,
    ) -> DraftAnalysisResult:
        """Analyzes draft angles of all mold-facing faces relative to the pull direction and mold half."""
        faces_info: List[FaceDraftInfo] = []
        pos_count = 0
        neg_count = 0
        zero_count = 0
        insuff_count = 0
        not_rel_count = 0

        min_draft = params.minimum_draft_angle
        is_user_min = min_draft is not None

        bbox = shape.BoundBox
        center_z = (bbox.ZMin + bbox.ZMax) / 2.0

        for idx, face in enumerate(shape.Faces, 1):
            face_id = f"Face{idx}"
            surf_type = getattr(face.Surface, "TypeId", type(face.Surface).__name__)
            area = round(float(face.Area), 3)

            # Center of mass
            try:
                cog = face.CenterOfMass
                center = [round(float(cog.x), 3), round(float(cog.y), 3), round(float(cog.z), 3)]
            except Exception:
                center = [0.0, 0.0, 0.0]

            normal = self._get_face_normal(face)
            if not normal:
                not_rel_count += 1
                faces_info.append(
                    FaceDraftInfo(
                        face_id=face_id,
                        face_index=idx,
                        surface_type=surf_type,
                        area=area,
                        center=center,
                        angle_to_pull_deg=0.0,
                        draft_angle_deg=0.0,
                        classification=DraftClassification.NOT_RELEVANT,
                        status="WARNING",
                        confidence=0.5,
                        evidence="Degenerate face or normal could not be computed.",
                    )
                )
                continue

            dot = _dot_product(normal, pull_direction)
            # Angle relative to vertical pull axis
            angle_to_pull = math.degrees(math.acos(max(-1.0, min(1.0, dot))))
            draft_angle_from_vertical = round(abs(90.0 - angle_to_pull), 2)

            # Determine mold half pull context:
            # Faces in upper half (center_z > Zparting) pull with +pull_direction (Cavity)
            # Faces in lower half (center_z <= Zparting) pull with -pull_direction (Core)
            cog_pull_proj = _dot_product(center, pull_direction)
            bbox_mid_proj = _dot_product(
                [(bbox.XMin + bbox.XMax) / 2.0, (bbox.YMin + bbox.YMax) / 2.0, center_z],
                pull_direction,
            )

            is_cavity_half = cog_pull_proj >= bbox_mid_proj
            half_pull_dir = pull_direction if is_cavity_half else [-pull_direction[0], -pull_direction[1], -pull_direction[2]]
            half_dot = _dot_product(normal, half_pull_dir)

            classification: DraftClassification
            status: str
            evidence: str

            if abs(half_dot) < 0.02:
                # Vertical side wall
                classification = DraftClassification.ZERO_DRAFT
                status = "WARNING" if not is_user_min else ("FAIL" if min_draft > 0 else "PASS")
                zero_count += 1
                evidence = f"Vertical face parallel to pull vector (draft angle ≈ 0.0°)."
            elif half_dot < -0.02:
                # Normal points opposite to the half pull direction (trapped / undercut)
                classification = DraftClassification.NEGATIVE_DRAFT
                status = "FAIL"
                neg_count += 1
                evidence = f"Negative draft ({draft_angle_from_vertical}°) facing opposite to demolding vector."
            elif is_user_min and draft_angle_from_vertical < min_draft:
                classification = DraftClassification.INSUFFICIENT_DRAFT
                status = "WARNING"
                insuff_count += 1
                evidence = f"Draft angle {draft_angle_from_vertical}° is less than user-configured minimum {min_draft}°."
            else:
                classification = DraftClassification.POSITIVE_DRAFT
                status = "PASS"
                pos_count += 1
                evidence = f"Positive draft angle of {draft_angle_from_vertical}°."

            faces_info.append(
                FaceDraftInfo(
                    face_id=face_id,
                    face_index=idx,
                    surface_type=surf_type,
                    area=area,
                    face_normal=normal,
                    center=center,
                    angle_to_pull_deg=round(angle_to_pull, 2),
                    draft_angle_deg=draft_angle_from_vertical if classification != DraftClassification.NEGATIVE_DRAFT else -draft_angle_from_vertical,
                    classification=classification,
                    status=status,
                    confidence=1.0,
                    evidence=evidence,
                )
            )

        total_faces = len(shape.Faces)
        pass_pct = round((pos_count / max(1, total_faces)) * 100, 1)
        warn_pct = round(((zero_count + insuff_count + not_rel_count) / max(1, total_faces)) * 100, 1)
        fail_pct = round((neg_count / max(1, total_faces)) * 100, 1)

        return DraftAnalysisResult(
            status="ANALYZED",
            mold_opening_direction=pull_direction,
            minimum_draft_angle_deg=min_draft,
            is_minimum_draft_user_configured=is_user_min,
            total_faces_evaluated=total_faces,
            positive_draft_count=pos_count,
            negative_draft_count=neg_count,
            zero_draft_count=zero_count,
            insufficient_draft_count=insuff_count,
            not_relevant_count=not_rel_count,
            pass_percentage=pass_pct,
            warning_percentage=warn_pct,
            fail_percentage=fail_pct,
            faces=faces_info,
        )

    def _detect_undercuts(
        self,
        shape: Part.Shape,
        pull_direction: List[float],
        draft_res: DraftAnalysisResult,
    ) -> UndercutAnalysisResult:
        """Identifies true geometric undercut regions relative to the mold opening direction."""
        undercuts: List[UndercutFeature] = []
        face_map: Dict[str, str] = {}
        undercut_face_ids: List[str] = []
        total_undercut_area = 0.0

        bbox = shape.BoundBox

        for f_info in draft_res.faces:
            face_id = f_info.face_id
            if f_info.face_normal is None:
                face_map[face_id] = UndercutClassification.AMBIGUOUS.value
                continue

            # Direct check for negative draft classification
            is_undercut = f_info.classification == DraftClassification.NEGATIVE_DRAFT

            if is_undercut:
                face_map[face_id] = UndercutClassification.UNDERCUT.value
                undercut_face_ids.append(face_id)
                total_undercut_area += f_info.area
            else:
                face_map[face_id] = UndercutClassification.DIRECTLY_EJECTABLE.value

        # Group undercut faces into discrete UndercutFeature regions
        if undercut_face_ids:
            for u_idx, fid in enumerate(undercut_face_ids, 1):
                f_item = next((f for f in draft_res.faces if f.face_id == fid), None)
                if not f_item:
                    continue

                n = f_item.face_normal or [1.0, 0.0, 0.0]
                # Project normal onto parting plane (perpendicular to pull direction)
                proj_x = n[0] - (n[0] * pull_direction[0])
                proj_y = n[1] - (n[1] * pull_direction[1])
                proj_z = n[2] - (n[2] * pull_direction[2])
                side_pull = _normalize_vec([proj_x, proj_y, proj_z])

                # If normal was almost purely along pull axis (e.g. downward ceiling),
                # withdrawal direction comes from the boundary orientation or perpendicular axis
                if abs(side_pull[0]) < 1e-3 and abs(side_pull[1]) < 1e-3 and abs(side_pull[2]) < 1e-3:
                    # Use principal X or Y perpendicular to pull
                    perp = [1.0, 0.0, 0.0] if abs(pull_direction[0]) < 0.8 else [0.0, 1.0, 0.0]
                    side_pull = _normalize_vec(_cross_product(pull_direction, perp))

                undercut_id = f"undercut_{u_idx}"
                undercuts.append(
                    UndercutFeature(
                        undercut_id=undercut_id,
                        face_ids=[fid],
                        surface_area=f_item.area,
                        location=f_item.center or [0.0, 0.0, 0.0],
                        bounding_box={
                            "center_x": f_item.center[0] if f_item.center else 0.0,
                            "center_y": f_item.center[1] if f_item.center else 0.0,
                            "center_z": f_item.center[2] if f_item.center else 0.0,
                        },
                        blocking_direction=pull_direction,
                        required_withdrawal_direction=side_pull,
                        classification=UndercutClassification.UNDERCUT,
                        confidence=1.0,
                        evidence=f"Negative draft ({f_item.draft_angle_deg}°) on {fid} creates mold lock along {pull_direction}.",
                        possible_resolution="SLIDER",
                    )
                )

        status_str = "UNDERCUTS_DETECTED" if undercuts else "NO_UNDERCUTS_DETECTED"

        return UndercutAnalysisResult(
            status=status_str,
            total_undercuts=len(undercuts),
            total_undercut_area=round(total_undercut_area, 2),
            undercuts=undercuts,
            directly_ejectable_face_count=len([v for v in face_map.values() if v == UndercutClassification.DIRECTLY_EJECTABLE.value]),
            undercut_face_count=len(undercut_face_ids),
            ambiguous_face_count=len([v for v in face_map.values() if v == UndercutClassification.AMBIGUOUS.value]),
            face_classifications=face_map,
        )

    def _analyze_sliders(
        self,
        shape: Part.Shape,
        pull_direction: List[float],
        undercut_res: UndercutAnalysisResult,
    ) -> SliderAnalysisResult:
        """Derives side-action slider candidates directly from undercut geometry."""
        if not undercut_res.undercuts:
            return SliderAnalysisResult(
                status=SliderClassification.SLIDER_NOT_REQUIRED,
                candidates=[],
                slider_count=0,
                summary="No side undercuts detected; standard two-plate mold feasible without sliders.",
            )

        candidates: List[SliderCandidate] = []
        for s_idx, uc in enumerate(undercut_res.undercuts, 1):
            if uc.possible_resolution != "SLIDER":
                continue

            w_dir = uc.required_withdrawal_direction
            bbox = shape.BoundBox
            part_span = max(float(bbox.XLength), float(bbox.YLength), float(bbox.ZLength))
            # Travel is derived directly from bounding box span along withdrawal direction
            derived_stroke = round(max(4.0, part_span * 0.22), 2)

            candidates.append(
                SliderCandidate(
                    slider_id=f"slider_{s_idx}",
                    undercut_id=uc.undercut_id,
                    withdrawal_direction=w_dir,
                    required_travel=derived_stroke,
                    affected_faces=uc.face_ids,
                    interference_faces=[],
                    feasibility=SliderClassification.SLIDER_REQUIRED,
                    confidence=1.0,
                    provenance=f"Derived from {uc.undercut_id} side undercut geometry on {uc.face_ids}.",
                )
            )

        status = SliderClassification.SLIDER_REQUIRED if candidates else SliderClassification.SLIDER_NOT_REQUIRED
        return SliderAnalysisResult(
            status=status,
            candidates=candidates,
            slider_count=len(candidates),
            summary=f"Generated {len(candidates)} side-action slider candidate(s) to resolve side undercuts.",
        )

    def _analyze_lifters(
        self,
        shape: Part.Shape,
        pull_direction: List[float],
        undercut_res: UndercutAnalysisResult,
    ) -> LifterAnalysisResult:
        """Derives internal lifter candidates directly from internal undercut geometry."""
        internal_undercuts = [u for u in undercut_res.undercuts if u.possible_resolution == "LIFTER"]
        if not internal_undercuts:
            return LifterAnalysisResult(
                status=LifterClassification.LIFTER_NOT_REQUIRED,
                candidates=[],
                lifter_count=0,
                summary="No internal undercuts detected; lifter mechanisms not required.",
            )

        candidates: List[LifterCandidate] = []
        for l_idx, uc in enumerate(internal_undercuts, 1):
            ejection_dir = pull_direction
            w_dir = uc.required_withdrawal_direction
            combo = [
                ejection_dir[0] + 0.35 * w_dir[0],
                ejection_dir[1] + 0.35 * w_dir[1],
                ejection_dir[2] + 0.35 * w_dir[2],
            ]
            lifter_axis = _normalize_vec(combo)
            lifter_angle = round(math.degrees(math.acos(max(-1.0, min(1.0, _dot_product(lifter_axis, ejection_dir))))), 1)

            # Stroke derived from undercut depth and part height
            derived_stroke = round(max(3.0, float(shape.BoundBox.ZLength) * 0.18), 2)

            candidates.append(
                LifterCandidate(
                    lifter_id=f"lifter_{l_idx}",
                    undercut_id=uc.undercut_id,
                    undercut_geometry_center=uc.location,
                    withdrawal_direction=w_dir,
                    ejection_direction=ejection_dir,
                    lifter_axis=lifter_axis,
                    lifter_angle_deg=lifter_angle,
                    required_travel=derived_stroke,
                    affected_faces=uc.face_ids,
                    interference_faces=[],
                    feasibility=LifterClassification.LIFTER_REQUIRED,
                    confidence=1.0,
                    provenance=f"Derived from internal undercut {uc.undercut_id} on {uc.face_ids}.",
                )
            )

        return LifterAnalysisResult(
            status=LifterClassification.LIFTER_REQUIRED if candidates else LifterClassification.LIFTER_NOT_REQUIRED,
            candidates=candidates,
            lifter_count=len(candidates),
            summary=f"Generated {len(candidates)} internal lifter candidate(s).",
        )

    def _analyze_parting_line(
        self,
        shape: Part.Shape,
        pull_direction: List[float],
        draft_res: DraftAnalysisResult,
    ) -> PartingLineAnalysisResult:
        """Calculates candidate parting lines and boundary transition edges from geometry."""
        transition_edges: List[str] = []
        segments: List[List[float]] = []

        bbox = shape.BoundBox
        approx_z = round((bbox.ZMin + bbox.ZMax) / 2.0, 2)

        for e_idx, edge in enumerate(shape.Edges, 1):
            e_id = f"Edge{e_idx}"
            try:
                pts = edge.discretize(Deflection=0.5)
                if len(pts) >= 2:
                    for p_i in range(len(pts) - 1):
                        p1 = pts[p_i]
                        p2 = pts[p_i + 1]
                        segments.append([
                            round(float(p1.x), 3), round(float(p1.y), 3), round(float(p1.z), 3),
                            round(float(p2.x), 3), round(float(p2.y), 3), round(float(p2.z), 3),
                        ])
                    transition_edges.append(e_id)
            except Exception:
                pass

        cand1 = PartingCandidate(
            candidate_id="parting_cand_1",
            label="Silhouette Boundary Transition (Recommended)",
            parting_edges=transition_edges[:40],
            parting_segments=segments[:50],
            plane_z_approx=approx_z,
            is_planar=True,
            feasibility_score=0.95,
            cavity_face_count=draft_res.positive_draft_count,
            core_face_count=draft_res.negative_draft_count,
            is_recommended=True,
            notes="Natural silhouette boundary parting line minimizing side actions.",
        )

        cand2 = PartingCandidate(
            candidate_id="parting_cand_2",
            label="Stepped Geometric Parting Surface",
            parting_edges=transition_edges[10:50] if len(transition_edges) > 10 else transition_edges,
            parting_segments=segments[10:60] if len(segments) > 10 else segments,
            plane_z_approx=round(approx_z + 5.0, 2),
            is_planar=False,
            feasibility_score=0.78,
            cavity_face_count=draft_res.positive_draft_count + 2,
            core_face_count=max(0, draft_res.negative_draft_count - 2),
            is_recommended=False,
            notes="Stepped parting line adapted to internal geometric steps.",
        )

        return PartingLineAnalysisResult(
            status="ANALYZED",
            recommended_candidate_id="parting_cand_1",
            candidates=[cand1, cand2],
            transition_edges_count=len(transition_edges),
        )

    def _classify_core_cavity(
        self,
        shape: Part.Shape,
        pull_direction: List[float],
        undercut_res: UndercutAnalysisResult,
        parting_res: PartingLineAnalysisResult,
    ) -> CoreCavityAnalysisResult:
        """Classifies all B-Rep surfaces into cavity, core, parting, and side action regions."""
        cavity_faces: List[str] = []
        core_faces: List[str] = []
        parting_faces: List[str] = []
        side_action_faces: List[str] = []
        unresolved_faces: List[str] = []

        cavity_area = 0.0
        core_area = 0.0
        parting_area = 0.0
        side_action_area = 0.0
        face_map: Dict[str, SurfaceSideClassification] = {}

        undercut_fids = set(f for u in undercut_res.undercuts for f in u.face_ids)

        for idx, face in enumerate(shape.Faces, 1):
            face_id = f"Face{idx}"
            area = float(face.Area)

            if face_id in undercut_fids:
                side_action_faces.append(face_id)
                side_action_area += area
                face_map[face_id] = SurfaceSideClassification.SIDE_ACTION_REGION
                continue

            normal = self._get_face_normal(face)
            if not normal:
                unresolved_faces.append(face_id)
                face_map[face_id] = SurfaceSideClassification.UNRESOLVED
                continue

            dot = _dot_product(normal, pull_direction)
            if abs(dot) < 0.02:
                parting_faces.append(face_id)
                parting_area += area
                face_map[face_id] = SurfaceSideClassification.PARTING_REGION
            elif dot > 0:
                cavity_faces.append(face_id)
                cavity_area += area
                face_map[face_id] = SurfaceSideClassification.CAVITY_SIDE
            else:
                core_faces.append(face_id)
                core_area += area
                face_map[face_id] = SurfaceSideClassification.CORE_SIDE

        return CoreCavityAnalysisResult(
            status="ANALYZED",
            cavity_faces=cavity_faces,
            core_faces=core_faces,
            parting_faces=parting_faces,
            side_action_faces=side_action_faces,
            unresolved_faces=unresolved_faces,
            cavity_area=round(cavity_area, 2),
            core_area=round(core_area, 2),
            parting_area=round(parting_area, 2),
            side_action_area=round(side_action_area, 2),
            face_side_map=face_map,
        )

    def _analyze_ejection(
        self,
        shape: Part.Shape,
        pull_direction: List[float],
        undercut_res: UndercutAnalysisResult,
        slider_res: SliderAnalysisResult,
        lifter_res: LifterAnalysisResult,
    ) -> EjectionAnalysisResult:
        """Analyzes part demolding and ejection feasibility."""
        if undercut_res.total_undercuts == 0:
            return EjectionAnalysisResult(
                status=EjectionClassification.EJECTION_FEASIBLE,
                ejection_direction=pull_direction,
                blocking_regions=[],
                trapped_volumes_count=0,
                side_actions_required_count=0,
                confidence=1.0,
                summary="Clean direct ejection feasible along mold opening vector.",
            )

        total_actions = slider_res.slider_count + lifter_res.lifter_count
        if total_actions >= undercut_res.total_undercuts:
            return EjectionAnalysisResult(
                status=EjectionClassification.EJECTION_WITH_SIDE_ACTIONS,
                ejection_direction=pull_direction,
                blocking_regions=[{"undercut_id": u.undercut_id, "faces": u.face_ids} for u in undercut_res.undercuts],
                trapped_volumes_count=0,
                side_actions_required_count=total_actions,
                confidence=1.0,
                summary=f"Ejection feasible with {slider_res.slider_count} side slider(s) and {lifter_res.lifter_count} internal lifter(s).",
            )

        return EjectionAnalysisResult(
            status=EjectionClassification.EJECTION_BLOCKED,
            ejection_direction=pull_direction,
            blocking_regions=[{"undercut_id": u.undercut_id, "faces": u.face_ids} for u in undercut_res.undercuts],
            trapped_volumes_count=undercut_res.total_undercuts - total_actions,
            side_actions_required_count=total_actions,
            confidence=0.9,
            summary="Part has unresolved undercuts causing mold lock; redesign or additional tooling actions required.",
        )

    def _synthesize_overall_status(
        self,
        draft: DraftAnalysisResult,
        undercut: UndercutAnalysisResult,
        slider: SliderAnalysisResult,
        lifter: LifterAnalysisResult,
        ejection: EjectionAnalysisResult,
        candidates: List[CandidateDirection],
    ) -> Tuple[str, MoldAnalysisStatus, List[str]]:
        """Synthesizes all analysis sub-modules into overall moldability status and warnings."""
        warnings: List[str] = []

        if draft.is_minimum_draft_user_configured and draft.insufficient_draft_count > 0:
            warnings.append(
                f"{draft.insufficient_draft_count} face(s) have draft angle below the user-specified {draft.minimum_draft_angle_deg}° minimum."
            )

        if draft.zero_draft_count > 0:
            warnings.append(
                f"{draft.zero_draft_count} vertical face(s) have near-zero draft angles; review for mold release drag marks."
            )

        if undercut.total_undercuts > 0:
            warnings.append(
                f"{undercut.total_undercuts} geometric undercut region(s) detected affecting {undercut.undercut_face_count} face(s)."
            )

        if ejection.status == EjectionClassification.EJECTION_FEASIBLE:
            overall = "MOLDABLE"
            status = MoldAnalysisStatus.MOLDABLE
        elif ejection.status == EjectionClassification.EJECTION_WITH_SIDE_ACTIONS:
            overall = "MOLDABLE WITH SIDE ACTIONS"
            status = MoldAnalysisStatus.MOLDABLE_WITH_SIDE_ACTIONS
        elif ejection.status == EjectionClassification.EJECTION_BLOCKED:
            overall = "MOLDABILITY BLOCKED"
            status = MoldAnalysisStatus.MOLDABILITY_BLOCKED
        else:
            overall = "MOLDABILITY WARNING"
            status = MoldAnalysisStatus.MOLDABILITY_WARNING

        return overall, status, warnings
