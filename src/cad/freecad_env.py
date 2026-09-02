"""FreeCAD environment setup helper.

Ensures FreeCAD DLLs and Python modules are registered on Windows.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Tuple

DEFAULT_FREECAD_PATHS = [
    # Windows standard locations
    r"C:\Program Files\FreeCAD 1.1",
    r"C:\Program Files\FreeCAD 1.0",
    r"C:\Program Files\FreeCAD 0.21",
    r"C:\Program Files\FreeCAD 0.20",
    r"C:\Program Files\FreeCAD",
    r"C:\Program Files (x86)\FreeCAD",
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\FreeCAD 1.1"),
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\FreeCAD 1.0"),
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\FreeCAD"),
    # Linux standard locations
    "/usr/lib/freecad",
    "/usr/lib/freecad-python3",
    "/usr/share/freecad",
    "/usr/local/lib/freecad",
    # macOS standard locations
    "/Applications/FreeCAD.app/Contents/Resources",
]


def load_env_file(env_path: Path | None = None) -> None:
    """Load key-value pairs from .env into os.environ if not already present."""
    p = env_path or (Path(__file__).resolve().parent.parent.parent / ".env")
    if p.exists():
        try:
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("'\"")
                    if k and k not in os.environ:
                        os.environ[k] = v
        except Exception:
            pass


load_env_file()


def init_freecad_env(custom_path: str | None = None) -> Tuple[str, str]:
    """Initialize environment for FreeCAD Python bindings.

    Returns a tuple of (freecad_bin_path, freecad_lib_path).
    """
    freecad_root: Path | None = None

    if custom_path:
        p = Path(custom_path)
        if p.exists():
            freecad_root = p

    if not freecad_root:
        # Check environment variable
        env_root = os.getenv("FREECAD_PATH")
        if env_root and Path(env_root).exists():
            freecad_root = Path(env_root)

    if not freecad_root:
        # Check default paths
        for candidate in DEFAULT_FREECAD_PATHS:
            p = Path(candidate)
            if p.exists():
                freecad_root = p
                break

    if not freecad_root:
        raise RuntimeError(
            "Could not locate FreeCAD installation. "
            "Please set FREECAD_PATH environment variable to your FreeCAD root directory "
            "(e.g. C:\\Program Files\\FreeCAD 1.1)."
        )

    bin_path = str(freecad_root / "bin")
    lib_path = str(freecad_root / "lib")

    # Add DLL directory for Windows (required for Python >= 3.8)
    if sys.platform == "win32" and hasattr(os, "add_dll_directory"):
        if os.path.exists(bin_path):
            os.add_dll_directory(bin_path)

    # Add bin and lib to sys.path if not present
    for path in [bin_path, lib_path]:
        if os.path.exists(path) and path not in sys.path:
            sys.path.insert(0, path)

    return bin_path, lib_path


def get_freecad_python() -> str:
    """Returns the path to a Python executable compatible with FreeCAD."""
    # 1. Check FREECAD_PYTHON env var
    env_py = os.getenv("FREECAD_PYTHON")
    if env_py and Path(env_py).exists():
        return str(Path(env_py).resolve())

    # 2. Check within FREECAD_PATH / bin
    env_root = os.getenv("FREECAD_PATH")
    if env_root:
        root = Path(env_root)
        for cand in [root / "bin" / "python.exe", root / "bin" / "python", root / "python.exe"]:
            if cand.exists():
                return str(cand.resolve())

    # 3. Check FreeCAD default installation dirs
    for candidate in DEFAULT_FREECAD_PATHS:
        p = Path(candidate)
        for sub in [p / "bin" / "python.exe", p / "bin" / "python", p / "python.exe"]:
            if sub.exists():
                return str(sub.resolve())

    # 4. Check system Python 3.11 locations on Windows
    sys_311 = Path(os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python311\python.exe"))
    if sys_311.exists():
        return str(sys_311.resolve())

    # 5. Fallback to sys.executable
    return sys.executable


# Initialize on import if possible (ignore DLL version conflicts in parent web server process)
try:
    init_freecad_env()
except Exception:
    pass

