"""
ifc_viewer.py  –  Osdag IFC Enhancement (Apr 2026)
====================================================
Provides a bridge between the IFC export pipeline and the PythonOCC-based
3D viewer already embedded in the Osdag GUI.

After the user clicks "Design", this module:
  1. Auto-exports a temporary .ifc file using the enhanced pipeline.
  2. Reads the .ifc back using ifcopenshell.geom (with USE_PYTHON_OPENCASCADE).
  3. Converts each IfcProduct to an OCC TopoDS_Shape.
  4. Calls osdag_display_shape() to render each shape with the same colour
     coding already used in common_logic.py.

This satisfies the requirement:
  "The CAD should use .ifc file to display the CAD"

Usage (from common_logic.py):
-------------------------------
    from osdag_core.export_ifc.ifc_viewer import display_ifc_model

    # After create3DModel() and before / instead of display_3DModel():
    display_ifc_model(
        display_obj   = self.display,
        cad_obj       = self.CPObj,          # the live Osdag CAD object
        connection_id = 'BCEndplate_preview',
        tmp_dir       = '/tmp'               # optional temp dir
    )
"""

import os
import tempfile

# Colour constants (defined to avoid hard PySide/OCC dependency at import time)
_MEMBER_COLOR  = None   # Default / steel grey
_PLATE_COLOR   = None   # Blue
_BOLT_COLOR    = None   # Brown/brass
_WELD_COLOR    = None   # Red

def _lazy_colors():
    """Lazy-import OCC colour constants to avoid import errors when OCC is not present."""
    global _MEMBER_COLOR, _PLATE_COLOR, _BOLT_COLOR, _WELD_COLOR
    if _MEMBER_COLOR is not None:
        return
    try:
        from OCC.Core.Quantity import (
            Quantity_NOC_ALUMINIUM,
            Quantity_NOC_BLUE1,
            Quantity_NOC_SADDLEBROWN,
            Quantity_NOC_RED,
        )
        _MEMBER_COLOR = Quantity_NOC_ALUMINIUM
        _PLATE_COLOR  = Quantity_NOC_BLUE1
        _BOLT_COLOR   = Quantity_NOC_SADDLEBROWN
        _WELD_COLOR   = Quantity_NOC_RED
    except ImportError:
        pass


def _export_to_tmp_ifc(cad_obj, connection_id, tmp_dir):
    """
    Internally export the live Osdag CAD object to a temporary .ifc file.
    Returns the path to the generated file or None on failure.
    """
    import sys
    # Ensure osdag_core is importable (should be, since we are inside it)
    try:
        from osdag_core.export_ifc.cad_extraction import extract_cad_items, extract_metadata
        from osdag_core.export_ifc.ifc_generator import OsdagIfcExporter
    except ImportError:
        print("[IFCViewer] ERROR: Could not import IFC pipeline. Falling back to BREP display.")
        return None

    try:
        members, plates, bolts, welds, others = extract_cad_items(cad_obj)
    except Exception as e:
        print(f"[IFCViewer] CAD extraction failed: {e}")
        return None

    ifc_path = os.path.join(tmp_dir, f"_osdag_preview_{connection_id}.ifc")
    try:
        exp = OsdagIfcExporter(filename=ifc_path, schema="IFC2X3")
        exp.export_connection(
            connection_id=connection_id,
            members=members,
            plates=plates,
            bolts=bolts,
            welds=welds if welds else None,
            others=others if others else None,
            metadata={'_preview': True},
            cad_obj=cad_obj
        )
        exp.save()
        return ifc_path
    except Exception as e:
        print(f"[IFCViewer] IFC export failed: {e}")
        return None


def _read_ifc_shapes(ifc_path):
    """
    Open an IFC file and return a list of (entity_type, name, occ_shape) tuples.
    Uses ifcopenshell.geom with USE_PYTHON_OPENCASCADE.

    Returns empty list if ifcopenshell or OCC are unavailable.
    """
    try:
        import ifcopenshell
        import ifcopenshell.geom
    except ImportError:
        print("[IFCViewer] ifcopenshell not installed: cannot read IFC shapes.")
        return []

    try:
        settings = ifcopenshell.geom.settings()
        settings.set(settings.USE_PYTHON_OPENCASCADE, True)
    except AttributeError:
        print("[IFCViewer] ifcopenshell.geom.USE_PYTHON_OPENCASCADE not available. "
              "Ensure pythonocc-core ≥ 7.x is installed in this environment.")
        return []

    try:
        ifc_file = ifcopenshell.open(ifc_path)
    except Exception as e:
        print(f"[IFCViewer] Failed to open IFC file {ifc_path}: {e}")
        return []

    shapes = []
    # Types we want to display
    display_types = [
        'IfcBeam', 'IfcColumn', 'IfcPlate', 'IfcFastener',
        'IfcBuildingElementProxy', 'IfcMember'
    ]
    for ifc_type in display_types:
        for product in ifc_file.by_type(ifc_type):
            if product.Representation is None:
                continue
            try:
                shape = ifcopenshell.geom.create_shape(settings, product)
                if shape and hasattr(shape, 'geometry'):
                    occ_shape = shape.geometry
                    shapes.append((ifc_type, product.Name or ifc_type, occ_shape))
            except Exception as e:
                print(f"[IFCViewer] Shape creation failed for {ifc_type} "
                      f"'{product.Name}': {e}")
    return shapes


def display_ifc_model(display_obj, cad_obj, connection_id='Connection',
                      tmp_dir=None, cleanup_tmp=True):
    """
    Main entry point: export cad_obj → IFC → re-render in the OCC viewer.

    Parameters
    ----------
    display_obj   : OCC qtDisplay / display handle (as used in common_logic.py)
    cad_obj       : Live Osdag CAD object (CPObj, TObj, …)
    connection_id : String identifier used for the temporary file name
    tmp_dir       : Directory for the temp IFC file (defaults to system temp)
    cleanup_tmp   : Remove the temp IFC file after display (default True)

    Returns
    -------
    True   – shapes were read from the IFC and rendered.
    False  – fallback: call the normal BREP / OCC display pipeline instead.
    """
    _lazy_colors()

    if tmp_dir is None:
        tmp_dir = tempfile.gettempdir()

    # 1. Export to temporary IFC
    print(f"[IFCViewer] Generating IFC preview for '{connection_id}'…")
    ifc_path = _export_to_tmp_ifc(cad_obj, connection_id, tmp_dir)
    if ifc_path is None:
        return False

    # 2. Read OCC shapes back from the IFC
    shapes = _read_ifc_shapes(ifc_path)
    if cleanup_tmp:
        try:
            os.remove(ifc_path)
        except OSError:
            pass

    if not shapes:
        print("[IFCViewer] No shapes extracted from IFC – using BREP fallback.")
        return False

    # 3. Render each shape
    try:
        from OCC.Core.Graphic3d import Graphic3d_NOM_ALUMINIUM
        from osdag.cad.items import osdag_display_shape
    except ImportError:
        print("[IFCViewer] OCC display utilities not available.")
        return False

    display_obj.EraseAll()
    display_obj.View_Iso()
    display_obj.set_bg_gradient_color([51, 51, 102], [150, 150, 170])

    for ifc_type, name, occ_shape in shapes:
        # Assign colour by element category
        if ifc_type in ('IfcBeam', 'IfcColumn'):
            # Structural members – default steel appearance
            osdag_display_shape(display_obj, occ_shape,
                                material=Graphic3d_NOM_ALUMINIUM, update=False)
        elif ifc_type == 'IfcPlate':
            # Connection plates – blue
            osdag_display_shape(display_obj, occ_shape,
                                color=_PLATE_COLOR, update=False)
        elif ifc_type == 'IfcFastener':
            # Bolts and welds – brown vs red based on name
            c = _WELD_COLOR if ('weld' in (name or '').lower()) else _BOLT_COLOR
            osdag_display_shape(display_obj, occ_shape, color=c, update=False)
        else:
            osdag_display_shape(display_obj, occ_shape, update=False)

    display_obj.FitAll()
    display_obj.View.Redraw()

    print(f"[IFCViewer] Displayed {len(shapes)} shapes from IFC.")
    return True


# ---------------------------------------------------------------------------
# Hook into common_logic.py  –  Monkey-patch helper
# ---------------------------------------------------------------------------

def patch_common_logic_for_ifc_display():
    """
    Installs the IFC viewer into the Osdag display pipeline as a thin
    wrapper around display_3DModel().

    Call this function once at application startup (e.g. from __main__.py)
    to activate the IFC-based CAD display feature.  If ifcopenshell.geom
    cannot produce shapes (OCC not installed in that env) the original
    BREP display is transparently used as a fallback.

    Example usage in __main__.py or osdag_gui/__init__.py:
        from osdag_core.export_ifc.ifc_viewer import patch_common_logic_for_ifc_display
        patch_common_logic_for_ifc_display()
    """
    try:
        from osdag.cad import common_logic as _cl
    except ImportError:
        print("[IFCViewer] common_logic not importable – patch skipped.")
        return

    _original_call_3DModel = _cl.CommonDesignLogic.call_3DModel

    def _patched_call_3DModel(self, flag, module_class):
        """Wrapper: try IFC display first, fall back to BREP."""
        if flag is True:
            # Determine the live CAD object attribute name
            possible = ['CPObj', 'CEPObj', 'BPObj', 'TObj', 'ColObj',
                        'FObj', 'connectivityObj']
            cad_obj = None
            for attr in possible:
                cad_obj = getattr(self, attr, None)
                if cad_obj is not None:
                    break

            if cad_obj is not None:
                conn_id = getattr(module_class, '__name__', 'Connection')
                ok = display_ifc_model(
                    display_obj=self.display,
                    cad_obj=cad_obj,
                    connection_id=conn_id
                )
                if ok:
                    return   # IFC display succeeded – skip BREP path

        # Fallback to original implementation
        _original_call_3DModel(self, flag, module_class)

    _cl.CommonDesignLogic.call_3DModel = _patched_call_3DModel
    print("[IFCViewer] common_logic.call_3DModel patched for IFC display.")
