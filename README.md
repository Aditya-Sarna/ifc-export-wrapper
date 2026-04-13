# IFC Export Wrapper for Osdag

IFC export layer for [Osdag](https://osdag.fossee.in/) that converts PythonOCC 3D CAD models of steel connections into standards-compliant IFC files.

## What it does

- Exports Osdag 3D connection models to `.ifc` files (IFC2X3 / IFC4)
- Displays CAD models by reading them back from IFC (round-trip verification)
- Maintains correct Z-up spatial orientation per IS 800 structural convention
- Supports four connection types with module-specific local axis placements

## Repository Structure

```
src/
  osdag_core/export_ifc/
    axis_mapper.py              # Global + per-module local axis definitions
    ifc_generator.py            # IFC project hierarchy, geometry, export orchestration
    ifc_viewer.py               # IFC-to-OCC bridge for GUI display
    subprocess_ifc_exporter.py  # Subprocess-safe export with CAD proxy objects
  osdag_gui/
    __main__.py                 # IFC display patch activation at startup
    OS_safety_protocols/
      environment_config.py     # ifcopenshell environment setup
    ui/
      components/
        custom_buttons.py       # "Export IFC" toolbar button
        docks/
          input_dock.py         # IFC export trigger in input panel
          output_dock.py        # IFC status in output panel
      windows/
        template_page.py        # IFC hooks in design workflow
tests/
  test_axis.py                  # Unit tests for axis_mapper
  test_ifc_integration.py       # End-to-end IFC export pipeline test
  debug_clicks.py               # GUI click-path debugging utility
```

## Supported Connection Modules

| Module | CAD Classes | Local Axis Convention |
|--------|-------------|----------------------|
| Beam-to-Column End Plate | CADGroove, CADFillet, CADcolwebGroove, CADColWebFillet | Z = column axis, X = beam axis |
| Column-to-Column Cover Plate | CCSpliceCoverPlateWeldedCAD, CCSpliceCoverPlateBoltedCAD | Z = column axis, X = flange width |
| Beam-to-Beam Cover Plate | BBCoverPlateBoltedCAD, BBSpliceCoverPlateWeldedCAD | Z = global vertical, X = beam span |
| Tension Member | TensionAngleBoltCAD, TensionChannelBoltCAD, TensionAngleWeldCAD, TensionChannelWeldCAD | Z = member axis, X = perpendicular horizontal |

## Dependencies

- Python 3.11+
- [ifcopenshell](https://ifcopenshell.org/)
- [pythonocc-core](https://github.com/tpaviot/pythonocc-core) >= 7.x
- numpy

## How it works

1. **Axis Mapping** — Defines Z-up global coordinate system and per-module local placements extracted from live CAD objects (wDir, uDir, sec_origin)
2. **IFC Generation** — Builds full IFC hierarchy (Project → Site → Building → Storey) with deterministic GUIDs, SI millimetre units, and tessellated BREP geometry
3. **IFC Viewer** — Auto-exports to temp `.ifc`, reads shapes back via `ifcopenshell.geom` with `USE_PYTHON_OPENCASCADE`, renders with colour-coded materials
4. **Subprocess Export** — Isolates heavy IFC operations in a child process using JSON serialisation and proxy objects
5. **Fallback** — Every IFC operation falls back transparently to the original BREP display pipeline on failure

## Author

Aditya Sarna — April 2026

## License

Part of the [Osdag](https://osdag.fossee.in/) project.
