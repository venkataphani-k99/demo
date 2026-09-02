# Engineering Findings & Technical Notes

## FreeCAD 1.1 Python Binding Nuances
1. **Python ABI Compatibility**:
   - FreeCAD 1.1 binaries on Windows are compiled with MSVC against Python 3.11.
   - Using Python 3.12 or 3.13 causes C-extension ABI mismatch (`ImportError: Module use of python311.dll conflicts with this version of Python`).
   - Use either a Python 3.11 conda environment or FreeCAD's bundled `python.exe` at `C:\Program Files\FreeCAD 1.1\bin\python.exe`.

2. **DLL Loading on Windows (Python 3.8+)**:
   - `os.add_dll_directory(r"C:\Program Files\FreeCAD 1.1\bin")` must be called to ensure `FreeCADBase.dll`, `FreeCADApp.dll`, and OCCT DLLs can be found.
   - FreeCAD module paths: `bin` directory for `FreeCAD.pyd`, `lib` directory for `Part.pyd`, `Import.pyd`.

3. **Units & Precision**:
   - FreeCAD stores lengths internally in millimeters (`mm`) by default.
   - Internal calculations must retain floating-point double precision (64-bit float). Rounding is strictly for display/formatting.
