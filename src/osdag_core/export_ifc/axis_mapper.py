"""
axis_mapper.py  –  Osdag IFC Enhancement (Apr 2026)
====================================================
Defines the **global world coordinate system** and **module-specific local
placement axes** that are written into every IFC file produced by Osdag.

Global axis convention (IS 800 / structural engineering):
  • Z  – vertical, pointing up   (0, 0, 1)
  • X  – primary horizontal axis (1, 0, 0)
  • Y  – secondary horizontal    (0, 1, 0)  (right-hand rule)

Per the IFC specification every IfcProduct carries an
IfcLocalPlacement whose RelativePlacement is an IfcAxis2Placement3D
(Location + Axis + RefDirection).  This module provides the helpers
that construct those placements for the four target modules:

  1. BCEndplate             – Beam-to-Column End Plate
  2. CCSpliceCoverPlateCAD  – Column-to-Column Cover Plate Welded
  3. BBCad                  – Beam-to-Beam Cover Plate Bolted
  4. TensionMember          – Tension Member bolted to end gusset
"""

import numpy as np


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _unit(v):
    """Return a unit vector."""
    v = np.asarray(v, dtype=float)
    n = np.linalg.norm(v)
    return v if n == 0 else v / n


def _orthogonal_ref(z_axis, x_hint=(1.0, 0.0, 0.0)):
    """
    Return a RefDirection perpendicular to *z_axis*.
    Falls back to Y-axis hint when z_axis is nearly parallel to x_hint.
    """
    z = _unit(z_axis)
    x = np.asarray(x_hint, dtype=float)
    if abs(np.dot(z, _unit(x))) > 0.99:
        x = np.array([0.0, 1.0, 0.0])
    ref = np.cross(z, np.cross(x, z))
    return _unit(ref)


# ---------------------------------------------------------------------------
# Global coordinate system
# ---------------------------------------------------------------------------

GLOBAL_ORIGIN = (0.0, 0.0, 0.0)
GLOBAL_Z_AXIS = (0.0, 0.0, 1.0)   # structural vertical
GLOBAL_X_AXIS = (1.0, 0.0, 0.0)   # primary horizontal


def create_global_placement(ifc_file):
    """
    Build the IfcAxis2Placement3D that is used as the
    WorldCoordinateSystem for the IfcGeometricRepresentationContext.

    Returns the IfcAxis2Placement3D entity.
    """
    loc = ifc_file.createIfcCartesianPoint(list(GLOBAL_ORIGIN))
    axis = ifc_file.createIfcDirection(list(GLOBAL_Z_AXIS))
    ref = ifc_file.createIfcDirection(list(GLOBAL_X_AXIS))
    return ifc_file.createIfcAxis2Placement3D(
        Location=loc, Axis=axis, RefDirection=ref
    )


# ---------------------------------------------------------------------------
# Module-specific local placements
# ---------------------------------------------------------------------------

def _module_local_placement(ifc_file, owner_history, origin, z_axis, x_axis,
                              parent_placement=None):
    """
    Create an IfcLocalPlacement for a structural connection module.

    Parameters
    ----------
    ifc_file        : ifcopenshell.file
    owner_history   : IfcOwnerHistory
    origin          : (x, y, z)  – connection reference point in mm
    z_axis          : (dx, dy, dz)  – 'up' direction of the local frame
    x_axis          : (dx, dy, dz)  – principal horizontal direction
    parent_placement: optional IfcLocalPlacement to relate to

    Returns
    -------
    IfcLocalPlacement
    """
    z = _unit(z_axis)
    x = _unit(x_axis)

    # Ensure orthogonality
    if abs(np.dot(z, x)) > 0.01:
        y = np.cross(z, x)
        x = np.cross(y, z)
        x = _unit(x)

    loc = ifc_file.createIfcCartesianPoint([float(c) for c in origin])
    axis_ifc = ifc_file.createIfcDirection([float(c) for c in z])
    ref_ifc = ifc_file.createIfcDirection([float(c) for c in x])
    axis2 = ifc_file.createIfcAxis2Placement3D(
        Location=loc, Axis=axis_ifc, RefDirection=ref_ifc
    )
    return ifc_file.createIfcLocalPlacement(
        PlacementRelTo=parent_placement,
        RelativePlacement=axis2
    )


# ------------------------------------------------------------------
# 1.  BCEndplate  –  Beam-to-Column End Plate
# ------------------------------------------------------------------
# Convention:
#   • Origin  = centre of end-plate face at the column flange
#   • Local Z = column axis (pointing up, i.e. structural vertical)
#   • Local X = beam axis  (pointing away from column toward span)
#
# If no CAD object is supplied the default placement at world origin
# (Z-up, X-horizontal) is returned.
# ------------------------------------------------------------------

def bc_endplate_local_placement(ifc_file, owner_history,
                                 cad_obj=None, parent_placement=None):
    """
    Local placement for a Beam-to-Column End Plate connection.

    The column is vertical (local Z = global Z).
    The beam runs horizontally (local X = global X or extracted from CAD).
    """
    origin = [0.0, 0.0, 0.0]
    z_axis = [0.0, 0.0, 1.0]   # column axis = world vertical
    x_axis = [1.0, 0.0, 0.0]   # beam axis

    if cad_obj is not None:
        # Extract column position from its sec_origin or origin attribute
        col = getattr(cad_obj, 'column', None)
        if col is not None:
            col_origin = (getattr(col, 'sec_origin', None)
                          or getattr(col, 'origin', None))
            if col_origin is not None:
                origin = [float(c) for c in col_origin]

        # Column axis is wDir of column object
        col_wdir = getattr(col, 'wDir', None) if col else None
        if col_wdir is not None:
            z_axis = [float(c) for c in col_wdir]

        # Beam axis is wDir of beam object
        beam = getattr(cad_obj, 'beam', None)
        beam_wdir = getattr(beam, 'wDir', None) if beam else None
        if beam_wdir is not None:
            x_axis = [float(c) for c in beam_wdir]

    return _module_local_placement(
        ifc_file, owner_history, origin, z_axis, x_axis, parent_placement
    )


# ------------------------------------------------------------------
# 2.  CCSpliceCoverPlateCAD  –  Column-to-Column Cover Plate Welded
# ------------------------------------------------------------------
# Convention:
#   • Origin  = midpoint of the splice (between the two column ends)
#   • Local Z = column axis (vertical)
#   • Local X = flange width direction
# ------------------------------------------------------------------

def cc_splice_local_placement(ifc_file, owner_history,
                               cad_obj=None, parent_placement=None):
    """
    Local placement for a Column-to-Column Cover Plate Welded connection.
    """
    origin = [0.0, 0.0, 0.0]
    z_axis = [0.0, 0.0, 1.0]
    x_axis = [1.0, 0.0, 0.0]

    if cad_obj is not None:
        col1 = getattr(cad_obj, 'column1', getattr(cad_obj, 'column', None))
        col2 = getattr(cad_obj, 'column2', None)

        col1_orig = None
        col2_orig = None

        if col1 is not None:
            col1_orig = (getattr(col1, 'sec_origin', None)
                         or getattr(col1, 'origin', None))
            wdir = getattr(col1, 'wDir', None)
            if wdir is not None:
                z_axis = [float(c) for c in wdir]
            udir = getattr(col1, 'uDir', None)
            if udir is not None:
                x_axis = [float(c) for c in udir]

        if col2 is not None:
            col2_orig = (getattr(col2, 'sec_origin', None)
                         or getattr(col2, 'origin', None))

        # Origin = midpoint of the two column origins (splice centre)
        if col1_orig is not None and col2_orig is not None:
            origin = [
                (float(col1_orig[i]) + float(col2_orig[i])) / 2.0
                for i in range(3)
            ]
        elif col1_orig is not None:
            origin = [float(c) for c in col1_orig]

    return _module_local_placement(
        ifc_file, owner_history, origin, z_axis, x_axis, parent_placement
    )


# ------------------------------------------------------------------
# 3.  BBCad  –  Beam-to-Beam Cover Plate Bolted
# ------------------------------------------------------------------
# Convention:
#   • Origin  = midpoint of the splice (between the two beam ends)
#   • Local Z = global vertical (0, 0, 1)
#   • Local X = beam span direction
# ------------------------------------------------------------------

def bb_coverplate_local_placement(ifc_file, owner_history,
                                   cad_obj=None, parent_placement=None):
    """
    Local placement for a Beam-to-Beam Cover Plate Bolted connection.
    """
    origin = [0.0, 0.0, 0.0]
    z_axis = [0.0, 0.0, 1.0]   # world vertical for horizontal beams
    x_axis = [1.0, 0.0, 0.0]   # beam span direction

    if cad_obj is not None:
        b1 = getattr(cad_obj, 'beamLeft', getattr(cad_obj, 'beam1', None))
        b2 = getattr(cad_obj, 'beamRight', getattr(cad_obj, 'beam2', None))

        b1_orig = None
        b2_orig = None

        if b1 is not None:
            b1_orig = (getattr(b1, 'sec_origin', None)
                       or getattr(b1, 'origin', None))
            wdir = getattr(b1, 'wDir', None)
            if wdir is not None:
                # Beam wDir is the extrusion direction (span direction) → local X
                x_axis = [float(c) for c in wdir]

        if b2 is not None:
            b2_orig = (getattr(b2, 'sec_origin', None)
                       or getattr(b2, 'origin', None))

        if b1_orig is not None and b2_orig is not None:
            origin = [
                (float(b1_orig[i]) + float(b2_orig[i])) / 2.0
                for i in range(3)
            ]
        elif b1_orig is not None:
            origin = [float(c) for c in b1_orig]

    return _module_local_placement(
        ifc_file, owner_history, origin, z_axis, x_axis, parent_placement
    )


# ------------------------------------------------------------------
# 4.  TensionMember  –  Tension Member bolted to end gusset
# ------------------------------------------------------------------
# Convention:
#   • Origin  = gusset plate connection point (sec_origin of the gusset)
#   • Local Z = member axis direction (wDir of member)
#   • Local X = perpendicular horizontal to the member
# ------------------------------------------------------------------

def tension_member_local_placement(ifc_file, owner_history,
                                    cad_obj=None, parent_placement=None):
    """
    Local placement for a Tension Member bolted to end gusset.
    """
    origin = [0.0, 0.0, 0.0]
    z_axis = [0.0, 0.0, 1.0]
    x_axis = [1.0, 0.0, 0.0]

    if cad_obj is not None:
        # Gusset plate gives the anchor point
        gusset = (getattr(cad_obj, 'plate1', None)
                  or getattr(cad_obj, 'plate2', None))
        if gusset is not None:
            g_orig = (getattr(gusset, 'sec_origin', None)
                      or getattr(gusset, 'origin', None))
            if g_orig is not None:
                origin = [float(c) for c in g_orig]

        # Member axis
        member = (getattr(cad_obj, 'member1', None)
                  or getattr(cad_obj, 'member2', None)
                  or getattr(cad_obj, 'sec', None))
        if member is not None:
            m_orig = (getattr(member, 'sec_origin', None)
                      or getattr(member, 'origin', None))
            if m_orig is not None and gusset is None:
                origin = [float(c) for c in m_orig]

            wdir = getattr(member, 'wDir', None)
            if wdir is not None:
                z_axis = [float(c) for c in wdir]
            udir = getattr(member, 'uDir', None)
            if udir is not None:
                x_axis = [float(c) for c in udir]

    return _module_local_placement(
        ifc_file, owner_history, origin, z_axis, x_axis, parent_placement
    )


# ------------------------------------------------------------------
# Dispatch map: class name → placement factory
# ------------------------------------------------------------------

#: Maps each CAD class name to the appropriate local-placement factory.
#: Each factory signature:  f(ifc_file, owner_history, cad_obj, parent) -> IfcLocalPlacement
MODULE_PLACEMENT_MAP = {
    # Beam-to-Column End Plate
    'CADGroove':         bc_endplate_local_placement,
    'CADFillet':         bc_endplate_local_placement,
    'CADcolwebGroove':   bc_endplate_local_placement,
    'CADColWebFillet':   bc_endplate_local_placement,

    # Column-to-Column Cover Plate Welded
    'CCSpliceCoverPlateWeldedCAD': cc_splice_local_placement,
    'CCSpliceCoverPlateBoltedCAD': cc_splice_local_placement,

    # Beam-to-Beam Cover Plate Bolted
    'BBCoverPlateBoltedCAD':     bb_coverplate_local_placement,
    'BBSpliceCoverPlateWeldedCAD': bb_coverplate_local_placement,

    # Tension Member – bolted to end gusset
    'TensionAngleBoltCAD':    tension_member_local_placement,
    'TensionChannelBoltCAD':  tension_member_local_placement,
    'TensionAngleWeldCAD':    tension_member_local_placement,
    'TensionChannelWeldCAD':  tension_member_local_placement,
}


def get_connection_local_placement(ifc_file, owner_history,
                                    cad_obj, parent_placement=None):
    """
    Return the appropriate IfcLocalPlacement for *cad_obj*.

    Falls back to a default world-origin placement if the class is not
    found in MODULE_PLACEMENT_MAP.
    """
    class_name = type(cad_obj).__name__
    factory = MODULE_PLACEMENT_MAP.get(class_name)
    if factory is not None:
        return factory(ifc_file, owner_history, cad_obj, parent_placement)

    # Default: world origin, Z-up
    return _module_local_placement(
        ifc_file, owner_history,
        origin=GLOBAL_ORIGIN,
        z_axis=GLOBAL_Z_AXIS,
        x_axis=GLOBAL_X_AXIS,
        parent_placement=parent_placement
    )
