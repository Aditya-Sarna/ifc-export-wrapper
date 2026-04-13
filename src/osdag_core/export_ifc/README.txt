================================================================================
  Osdag IFC Wrapper Enhancement  –  README
  Author : Enhancement delivered April 2026
  Target : Osdag dev branch  |  Python 3.11+  |  IFC schema: IFC2X3
================================================================================

────────────────────────────────────────────────────────────────────────────────
1.  OVERVIEW
────────────────────────────────────────────────────────────────────────────────
This package enhances the existing IFC export wrapper in Osdag
(src/osdag_core/export_ifc/) to:

  A. Use the .ifc file to display the CAD model in the Osdag 3D viewer.
  B. Define a global world axis (Z-up, IS 800 structural convention).
  C. Add module-specific relative local axes for the four target connections:
       1. Beam-to-Column End Plate        (BCEndplate / CADGroove, CADFillet…)
       2. Column-to-Column Cover Plate    (CCSpliceCoverPlateWeldedCAD / BoltedCAD)
       3. Beam-to-Beam Cover Plate Bolted (BBCoverPlateBoltedCAD)
       4. Tension Member – bolted gusset  (TensionAngleBoltCAD / ChannelBoltCAD)
  D. Attach IfcLocalPlacement to every IFC product.
  E. Emit a Pset_OsdagAxisConvention property set on each IfcElementAssembly to
     document the axis convention used.
  F. Generate a Bill of Quantities (BOQ) importable into Revit.


────────────────────────────────────────────────────────────────────────────────
2.  FILES ADDED / MODIFIED
────────────────────────────────────────────────────────────────────────────────

NEW FILES
---------
src/osdag_core/export_ifc/axis_mapper.py
    Core module for axis convention management.
    • create_global_placement()       – Z-up world coordinate system.
    • bc_endplate_local_placement()   – Module 1: BC End Plate local axes.
    • cc_splice_local_placement()     – Module 2: CC Cover Plate local axes.
    • bb_coverplate_local_placement() – Module 3: BB Cover Plate local axes.
    • tension_member_local_placement()– Module 4: Tension Member local axes.
    • get_connection_local_placement()– Dispatch by CAD class name.
    • MODULE_PLACEMENT_MAP             – Maps each CAD class → factory function.

src/osdag_core/export_ifc/ifc_viewer.py
    IFC-based 3D display module.
    • display_ifc_model()             – Exports IFC → reads shapes → renders.
    • patch_common_logic_for_ifc_display() – Patches call_3DModel() at startup.
    Falls back transparently to the BREP pipeline when ifcopenshell.geom
    cannot produce OCC shapes (e.g. pythonocc-core missing).

MODIFIED FILES
--------------
src/osdag_core/export_ifc/ifc_generator.py
    • Imports axis_mapper for global and local placement.
    • _create_contexts() now uses create_global_placement() (Z-up WCS).
    • Added _create_world_local_placement() helper.
    • Added _get_connection_local_placement() that delegates to axis_mapper.
    • export_connection() now accepts optional cad_obj parameter.
    • All IfcProduct subclasses (IfcBeam, IfcColumn, IfcPlate, IfcFastener…)
      receive an ObjectPlacement linked to the connection-level local placement.
    • Emits Pset_OsdagAxisConvention on the IfcElementAssembly.
    • Fixed numpy array "truth value ambiguous" bug in bolt-hole boolean cuts.

src/osdag_core/export_ifc/subprocess_ifc_exporter.py
    • Reads _cad_class from the metadata payload.
    • Builds a DictToObj proxy (cad_proxy) with member/plate/beam attrs so
      axis_mapper can reconstruct local axes from serialised JSON.
    • Passes cad_proxy to export_connection(cad_obj=cad_proxy).

src/osdag_gui/ui/components/docks/output_dock.py
    • Injects meta['_cad_class'] = type(cad_obj).__name__ into the payload
      serialised to JSON before subprocess launch.

src/osdag_gui/__main__.py
    • Calls patch_common_logic_for_ifc_display() at GUI startup (with
      silent fallback if ifcopenshell.geom is unavailable).


────────────────────────────────────────────────────────────────────────────────
3.  AXIS CONVENTIONS
────────────────────────────────────────────────────────────────────────────────

GLOBAL AXIS  (IfcGeometricRepresentationContext → WorldCoordinateSystem)
    Z = (0, 0, 1)  – structural vertical (up)
    X = (1, 0, 0)  – primary horizontal
    Y = (0, 1, 0)  – secondary horizontal (right-hand rule)

MODULE LOCAL AXES  (IfcLocalPlacement → RelativePlacement)

  Module 1 – Beam-to-Column End Plate (BCEndplate)
    Origin : centre of end-plate face (column.sec_origin extracted from CAD)
    Local Z : column axis direction (wDir of column object, typically global Z)
    Local X : beam span direction   (wDir of beam object)

  Module 2 – Column-to-Column Cover Plate Welded (CCSpliceCoverPlateCAD)
    Origin : midpoint between column1.sec_origin and column2.sec_origin
    Local Z : column axis direction (wDir of column1)
    Local X : flange width direction (uDir of column1)

  Module 3 – Beam-to-Beam Cover Plate Bolted (BBCad)
    Origin : midpoint between beamLeft.sec_origin and beamRight.sec_origin
    Local Z : global vertical (0, 0, 1) – beams are horizontal
    Local X : beam span direction (wDir of beamLeft)

  Module 4 – Tension Member – bolted to end gusset (Tension)
    Origin : gusset plate connection point (plate1.sec_origin)
    Local Z : member axis direction (wDir of member1)
    Local X : member local X        (uDir of member1)

  All placements are strictly right-handed.  Axis orthogonality is enforced
  numerically in axis_mapper._module_local_placement().


────────────────────────────────────────────────────────────────────────────────
4.  IFC PROPERTY SETS (for Revit BOQ)
────────────────────────────────────────────────────────────────────────────────

Every exported IFC file contains the following property/quantity sets,
which allow Revit to generate a Bill of Quantities:

  Pset_OsdagDesignData       – MaterialGrade, SectionProfile, DesignCode,
                                ExportTime
  Pset_BeamCommon            – Reference (section designation)
  Pset_PlateCommon           – Material
  Pset_FastenerCommon        – Type, Grade, YieldStrength, UltimateStrength
  Pset_WeldCommon            – WeldType, Grade
  Qto_BeamBaseQuantities     – Length, Depth, Width, CrossSectionArea,
                                NetVolume, NetWeight
  Qto_PlateBaseQuantities    – Length, Width, Depth, GrossArea,
                                NetVolume, NetWeight
  Qto_FastenerBaseQuantities – Diameter, Length, Count, NetWeight
  Qto_WeldBaseQuantities     – Length, Depth
  Pset_OsdagAxisConvention   – GlobalAxisZ, GlobalAxisX, LocalAxisConvention
                                (on the root IfcElementAssembly)

Revit import: File → Import/Link → IFC → select the .ifc file.
In "Schedule/Quantities", select the category (Structural Framing for beams,
Structural Columns, etc.) and add the custom OsDAG parameter columns.


────────────────────────────────────────────────────────────────────────────────
5.  DEPENDENCIES
────────────────────────────────────────────────────────────────────────────────

  Required (already in Osdag conda env):
    ifcopenshell >= 0.7.0
    numpy >= 1.22

  Required for IFC-based 3D display:
    ifcopenshell with USE_PYTHON_OPENCASCADE support
    (pythonocc-core >= 7.7 – already present in the Osdag conda env)

  Optional (for validation):
    ifcopenshell.validate


────────────────────────────────────────────────────────────────────────────────
6.  SETUP & USAGE
────────────────────────────────────────────────────────────────────────────────

  1. Clone / pull the Osdag dev branch:
         git clone --branch dev https://github.com/osdag-admin/Osdag.git

  2. Set up the conda environment as per the Osdag website:
         conda env create -f Osdag/environment.yml
         conda activate osdag_env
         pip install -e Osdag/

  3. Run Osdag normally:
         python -m osdag_gui

  4. Load one of the provided .osi files, click Design, then:
       a. The 3D view will render from the IFC (if pythonocc bridge available).
       b. Use File → Export → IFC (*.ifc) to save the enhanced IFC file.

  5. Open the .ifc in Autodesk Revit (Student version):
       File → Open → IFC
       Use Schedules/Quantities panel for BOQ.


────────────────────────────────────────────────────────────────────────────────
7.  IFC FUNCTION REFERENCE
────────────────────────────────────────────────────────────────────────────────

  IfcProject                     – Root of the IFC hierarchy.
  IfcSite / IfcBuilding / IfcBuildingStorey – Spatial hierarchy.
  IfcGeometricRepresentationContext – 3D context with Z-up WCS.
  IfcAxis2Placement3D            – Defines origin + Z-axis + X-axis.
  IfcLocalPlacement              – Positions a product relative to a parent or world.
  IfcCartesianPoint              – 3D coordinate (mm).
  IfcDirection                   – Normalised direction vector.
  IfcArbitraryClosedProfileDef   – Generic 2D closed polyline profile (I-section, etc.).
  IfcRectangleProfileDef         – Rectangular plate profile.
  IfcCircleProfileDef            – Circular bolt-shaft profile.
  IfcLShapeProfileDef            – Standard L-section profile.
  IfcExtrudedAreaSolid           – Prismatic extrusion of a 2D profile.
  IfcRevolvedAreaSolid           – Revolved solid (quarter-cone anchor bolt).
  IfcOpeningElement              – Cylindrical void representing a bolt hole.
  IfcRelVoidsElement             – Associates an opening with a building element.
  IfcBooleanClippingResult       – Boolean subtraction (bolt holes in plates).
  IfcBeam / IfcColumn            – Structural member types.
  IfcPlate                       – Connection plate type.
  IfcFastener                    – Bolt, nut, washer, weld.
  IfcBuildingElementProxy        – Non-steel items (grout, concrete).
  IfcElementAssembly             – Groups the entire connection as one object.
  IfcRelAggregates               – Parent–child aggregation relationship.
  IfcRelContainedInSpatialStructure – Links assembly to the building storey.
  IfcPropertySet                 – Named set of typed properties (Pset_*).
  IfcPropertySingleValue         – Single key-value property.
  IfcElementQuantity (Qto_*)     – Quantity take-off set for BOQ.
  IfcQuantityLength / Area / Volume / Weight / Count – BOQ quantity types.
  IfcMappedItem                  – Re-use (instance) of geometry for bolts.
  IfcRepresentationMap           – Source geometry for mapped items.
  IfcCartesianTransformationOperator3D – Placement transform for mapped items.
  IfcOwnerHistory                – Audit trail (user, app, timestamp).
  IfcUnitAssignment              – SI unit definitions (mm, kg, radian).


────────────────────────────────────────────────────────────────────────────────
8.  METHODOLOGY
────────────────────────────────────────────────────────────────────────────────

  The enhancement follows a layered approach:

  Layer 1 – axis_mapper.py (new)
    A standalone, OCC-free module that maps Osdag CAD object attributes
    (sec_origin, wDir, uDir) to IFC placement entities.  Uses numpy for
    orthogonalisation.  Dispatches by Python class name.

  Layer 2 – ifc_generator.py (enhanced)
    Replaces the hardcoded WorldCoordinateSystem with axis_mapper's Z-up
    global placement.  All IFC products receive an ObjectPlacement.
    Accepts an optional cad_obj parameter that flows through to axis_mapper.

  Layer 3 – ifc_viewer.py (new)
    Provides an ifcopenshell.geom bridge to render IFC geometry directly
    in the existing PythonOCC 3D viewer, replacing the BREP pipeline.
    The monkey-patch approach requires zero changes to common_logic.py core.

  Layer 4 – GUI / subprocess glue (modified)
    output_dock.py injects the CAD class name into the JSON payload.
    subprocess_ifc_exporter.py reconstructs a cad_proxy from that data.
    __main__.py activates the IFC display patch at startup.


────────────────────────────────────────────────────────────────────────────────
9.  CHALLENGES ENCOUNTERED
────────────────────────────────────────────────────────────────────────────────

  1. IFC2X3 vs IFC4 API differences
     IfcPerson uses 'Id' in IFC2X3 and 'Identification' in IFC4.
     IfcQuantityLength has a different signature.
     Handled via schema-conditional code paths.

  2. ObjectPlacement not settable in createIfcElementAssembly (IFC2X3)
     Post-creation attribute assignment used with try/except fallback.

  3. numpy array in boolean `all(v is not None)` check
     `list.__contains__` triggers `__eq__` which returns an array for numpy.
     Fixed by using explicit `x is not None and y is not None …` checks.

  4. ifcopenshell.geom requiring pythonocc-core
     The base ifcopenshell pip package does not bundle pythonocc.
     The Osdag conda env has it. A graceful fallback chain was implemented.

  5. Subprocess isolation for IFC export
     Osdag already uses a subprocess for IFC export to avoid GL context
     conflicts.  The cad_obj proxy reconstruction in the subprocess needed
     careful attribute mapping from the serialised JSON.


────────────────────────────────────────────────────────────────────────────────
10. REFERENCES
────────────────────────────────────────────────────────────────────────────────

  • buildingSMART IFC2X3 specification:
    https://standards.buildingsmart.org/IFC/RELEASE/IFC2x3/TC1/HTML/

  • IfcOpenShell documentation:
    https://docs.ifcopenshell.org/

  • IS 800 : 2007 – Indian Standard Code for Steel Structures

  • Osdag source code:
    https://github.com/osdag-admin/Osdag/tree/dev

  • PythonOCC documentation:
    https://dev.opencascade.org/doc/overview/html/

  • Revit IFC Import guide:
    https://autodesk.com/support/revit/learn/ifc

================================================================================
