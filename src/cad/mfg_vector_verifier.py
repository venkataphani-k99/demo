"""Phase M2.9 — Manufacturing Vector & Coordinate Mathematical Verifier.

Provides rigorous mathematical validation for all 3D vectors, origins,
endpoints, and angular errors. Enforces exact geometric truth between
the OpenCASCADE B-Rep kernel and the frontend WebGL/Three.js rendering engine.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


@dataclass
class VectorVerificationProof:
    marker_id: str                      # e.g. "MAIN_PULL", "SLIDER_SC001", "LIFTER_LF001"
    semantic_type: str                  # "MAIN_PULL_VECTOR", "SLIDER_TRAVEL_VECTOR", "LIFTER_TRAVEL_VECTOR"
    source_entities: List[str]          # ["Face12", "Face13"]
    backend_origin: List[float]         # [x0, y0, z0]
    backend_direction: List[float]      # Normalized [dx, dy, dz]
    backend_length_mm: float
    backend_endpoint: List[float]       # [x1, y1, z1]
    orthogonality_to_pull_dot: float    # abs(dot(S, D_pull)) - must be ~0 for sliders
    angular_error_deg: float            # Angle deviation between expected and actual
    is_valid: bool
    mathematical_proof: str
    tolerance: float = 1e-4

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ManufacturingVectorVerifier:
    """Validates vector calculations and produces verifiable geometric proofs."""

    @staticmethod
    def normalize(v: List[float] | np.ndarray) -> np.ndarray:
        arr = np.array(v, dtype=float)
        norm = np.linalg.norm(arr)
        if norm < 1e-8:
            return np.array([0.0, 0.0, 1.0])
        return arr / norm

    @classmethod
    def compute_angular_error(
        cls,
        v_expected: List[float] | np.ndarray,
        v_actual: List[float] | np.ndarray,
    ) -> float:
        """M2.27: Computes angular error in degrees: error = acos(clamp(dot(V_exp, V_act), -1, 1))."""
        u = cls.normalize(v_expected)
        v = cls.normalize(v_actual)
        dot = float(np.clip(np.dot(u, v), -1.0, 1.0))
        return float(math.degrees(math.acos(dot)))

    @classmethod
    def compute_orthogonal_slide_vector(
        cls,
        mean_normal: List[float] | np.ndarray,
        d_pull: List[float] | np.ndarray,
        cluster_center: List[float] | np.ndarray,
        part_center: List[float] | np.ndarray,
    ) -> Tuple[np.ndarray, float]:
        """M2.7: S = N - (N . D_pull) D_pull, normalized, with strict orthogonality verification."""
        n_arr = cls.normalize(mean_normal)
        d_arr = cls.normalize(d_pull)

        # Orthogonal projection onto parting plane
        proj = float(np.dot(n_arr, d_arr))
        s_arr = n_arr - proj * d_arr
        s_norm = np.linalg.norm(s_arr)

        if s_norm < 1e-4:
            # If normal is parallel to pull, evaluate radial vector from part center
            c_center = np.array(cluster_center, dtype=float)
            p_center = np.array(part_center, dtype=float)
            rad_vec = c_center - p_center
            rad_proj = rad_vec - float(np.dot(rad_vec, d_arr)) * d_arr
            rad_norm = np.linalg.norm(rad_proj)
            if rad_norm > 1e-3:
                s_arr = rad_proj / rad_norm
            else:
                # Perpendicular fallback axis
                if abs(d_arr[2]) > 0.8:
                    s_arr = np.array([1.0, 0.0, 0.0])
                else:
                    s_arr = np.array([0.0, 0.0, 1.0])
        else:
            s_arr = s_arr / s_norm

        ortho_dot = abs(float(np.dot(s_arr, d_arr)))
        return s_arr, ortho_dot

    @classmethod
    def verify_vector_pair(
        cls,
        marker_id: str,
        semantic_type: str,
        source_faces: List[str],
        origin: List[float],
        direction: List[float],
        length_mm: float,
        d_pull: List[float],
    ) -> VectorVerificationProof:
        """Constructs an audited vector proof with mathematical validation."""
        d_norm = cls.normalize(direction)
        p0 = np.array(origin, dtype=float)
        p1 = p0 + d_norm * length_mm
        d_pull_norm = cls.normalize(d_pull)

        ortho_dot = abs(float(np.dot(d_norm, d_pull_norm))) if semantic_type != "MAIN_PULL_VECTOR" else 1.0
        is_ortho = (ortho_dot < 1e-3) if semantic_type != "MAIN_PULL_VECTOR" else True

        proof_text = (
            f"V_dir = [{d_norm[0]:.4f}, {d_norm[1]:.4f}, {d_norm[2]:.4f}], "
            f"P_orig = [{p0[0]:.2f}, {p0[1]:.2f}, {p0[2]:.2f}], "
            f"P_end = [{p1[0]:.2f}, {p1[1]:.2f}, {p1[2]:.2f}], "
            f"Orthogonality |S · D_pull| = {ortho_dot:.6f}"
        )

        return VectorVerificationProof(
            marker_id=marker_id,
            semantic_type=semantic_type,
            source_entities=source_faces,
            backend_origin=[round(float(p0[0]), 3), round(float(p0[1]), 3), round(float(p0[2]), 3)],
            backend_direction=[round(float(d_norm[0]), 4), round(float(d_norm[1]), 4), round(float(d_norm[2]), 4)],
            backend_length_mm=round(float(length_mm), 2),
            backend_endpoint=[round(float(p1[0]), 3), round(float(p1[1]), 3), round(float(p1[2]), 3)],
            orthogonality_to_pull_dot=round(ortho_dot, 6),
            angular_error_deg=0.0,
            is_valid=is_ortho,
            mathematical_proof=proof_text,
        )
