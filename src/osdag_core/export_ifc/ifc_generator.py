import ifcopenshell
import ifcopenshell.guid
import uuid
import time

class OsdagIfcExporter:
    """
    Main generator class for exporting Osdag 3D models to IFC format.
    Maintains the file structure, project hierarchy, and orchestrates the mappers.

    Enhancement (Apr 2026):
      - Uses axis_mapper to apply a defined global axis (Z-up, IS 800 convention).
      - Creates per-module local placements for all four target connection types.
      - Attaches IfcLocalPlacement to every product for correct spatial positioning.
    """

    def __init__(self, filename="Osdag_Model.ifc", schema="IFC2X3"):
        """
        Initialize the IFC exporter.
        :param filename: Output path for the IFC file.
        :param schema: IFC schema to use ('IFC2X3' or 'IFC4').
        """
        self.filename = filename
        self.schema = schema

        # Source CAD object (set externally before calling export_connection)
        self._cad_obj = None

        # Initialize an empty IFC file with the chosen schema
        self.ifc_file = ifcopenshell.file(schema=self.schema)

        # IFC Header Setup
        self.setup_header()

        # Initialize Project Hierarchy
        self.project = None
        self.site = None
        self.building = None
        self.storey = None
        self.setup_project_hierarchy()

        # Initialize Mappers
        from .geometry_mapper import GeometryMapper
        from .metadata_mapper import MetadataMapper
        self.geom_mapper = GeometryMapper(self)
        self.meta_mapper = MetadataMapper(self)

    def generate_guid(self, osdag_id=None):
        """
        Generates a 22-character IFC standard GUID.
        If an osdag_id is provided, it can be used to generate a deterministic GUID.
        """
        if osdag_id is not None:
            # Deterministic GUID based on the element's unique Osdag ID
            # Use uuid5 with a namespace to consistently get the same uuid for the same ID
            namespace = uuid.UUID('6ba7b810-9dad-11d1-80b4-00c04fd430c8')
            element_uuid = uuid.uuid5(namespace, str(osdag_id))
            # Pack uuid to IFC base64
            guid = ifcopenshell.guid.compress(element_uuid.hex)
        else:
            # Random GUID
            guid = ifcopenshell.guid.new()
        return guid

    def setup_header(self):
        """Set up the IFC file header metadata."""
        owner_history = self.ifc_file.createIfcOwnerHistory()
        # To be populated fully in metadata_mapper if needed, but a basic one is required
        # IfcPerson: IFC2X3 uses 'Id', IFC4 renamed it to 'Identification'
        if self.schema == "IFC4":
            person = self.ifc_file.createIfcPerson(
                Identification="OsdagUser", FamilyName="User"
            )
            org = self.ifc_file.createIfcOrganization(
                Identification="Osdag", Name="Osdag"
            )
        else:  # IFC2X3
            person = self.ifc_file.createIfcPerson(
                Id="OsdagUser", FamilyName="User"
            )
            org = self.ifc_file.createIfcOrganization(
                Id="Osdag", Name="Osdag"
            )
        person_and_org = self.ifc_file.createIfcPersonAndOrganization(ThePerson=person, TheOrganization=org)
        
        app = self.ifc_file.createIfcApplication(
            ApplicationDeveloper=org,
            Version="1.0",
            ApplicationFullName="Osdag Structural Design",
            ApplicationIdentifier="OSDAG"
        )
        
        self.owner_history = self.ifc_file.createIfcOwnerHistory(
            OwningUser=person_and_org,
            OwningApplication=app,
            ChangeAction="ADDED",
            CreationDate=int(time.time())
        )

    def setup_project_hierarchy(self):
        """Create the Project -> Site -> Building -> Storey hierarchy."""
        
        # Create Units
        length_unit = self.ifc_file.createIfcSIUnit(
            UnitType="LENGTHUNIT",
            Prefix="MILLI",
            Name="METRE"
        )
        area_unit = self.ifc_file.createIfcSIUnit(
            UnitType="AREAUNIT",
            Name="SQUARE_METRE"
        )
        volume_unit = self.ifc_file.createIfcSIUnit(
            UnitType="VOLUMEUNIT",
            Name="CUBIC_METRE"
        )
        mass_unit = self.ifc_file.createIfcSIUnit(
            UnitType="MASSUNIT",
            Prefix="KILO",
            Name="GRAM"
        )
        angle_unit = self.ifc_file.createIfcSIUnit(
            UnitType="PLANEANGLEUNIT",
            Name="RADIAN"
        )
        unit_assignment = self.ifc_file.createIfcUnitAssignment(
            Units=[length_unit, area_unit, volume_unit, mass_unit, angle_unit]
        )
        
        # Create Project
        self.project = self.ifc_file.createIfcProject(
            GlobalId=self.generate_guid("osdag_project"),
            OwnerHistory=self.owner_history,
            Name="Osdag Connection Design",
            RepresentationContexts=self._create_contexts(),
            UnitsInContext=unit_assignment
        )
        
        # Create Site
        self.site = self.ifc_file.createIfcSite(
            GlobalId=self.generate_guid("osdag_site"),
            OwnerHistory=self.owner_history,
            Name="Site",
            CompositionType="COMPLEX"
        )
        self.ifc_file.createIfcRelAggregates(
            GlobalId=self.generate_guid(),
            OwnerHistory=self.owner_history,
            RelatingObject=self.project,
            RelatedObjects=[self.site]
        )
        
        # Create Building
        self.building = self.ifc_file.createIfcBuilding(
            GlobalId=self.generate_guid("osdag_building"),
            OwnerHistory=self.owner_history,
            Name="Building",
            CompositionType="COMPLEX"
        )
        self.ifc_file.createIfcRelAggregates(
            GlobalId=self.generate_guid(),
            OwnerHistory=self.owner_history,
            RelatingObject=self.site,
            RelatedObjects=[self.building]
        )
        
        # Create Storey
        self.storey = self.ifc_file.createIfcBuildingStorey(
            GlobalId=self.generate_guid("osdag_storey"),
            OwnerHistory=self.owner_history,
            Name="Level 1",
            CompositionType="COMPLEX",
            Elevation=0.0
        )
        self.ifc_file.createIfcRelAggregates(
            GlobalId=self.generate_guid(),
            OwnerHistory=self.owner_history,
            RelatingObject=self.building,
            RelatedObjects=[self.storey]
        )

    def _create_contexts(self):
        """Creates representation contexts for 3D modeling.

        Uses axis_mapper.create_global_placement() so the worldCoordinateSystem
        is always Z-up (structural convention, IS 800).
        """
        from .axis_mapper import create_global_placement
        wcs = create_global_placement(self.ifc_file)

        # 3-D model context (Z-up world)
        context3d = self.ifc_file.createIfcGeometricRepresentationContext(
            ContextType="Model",
            CoordinateSpaceDimension=3,
            Precision=1e-5,
            WorldCoordinateSystem=wcs,
            TrueNorth=self._create_direction((0.0, 1.0, 0.0))
        )

        # Optional Plan (2-D) sub-context for drawing extraction
        self.ifc_file.createIfcGeometricRepresentationSubContext(
            ContextIdentifier="FootPrint",
            ContextType="Model",
            ParentContext=context3d,
            TargetScale=None,
            TargetView="PLAN_VIEW",
            UserDefinedTargetView=None
        )

        return [context3d]

    def _create_placement(self, point=(0.0, 0.0, 0.0), dir_z=(0.0, 0.0, 1.0), dir_x=(1.0, 0.0, 0.0)):
        """Helper to create an IfcAxis2Placement3D."""
        point_ifc = self.ifc_file.createIfcCartesianPoint(list(point))
        axis = self.ifc_file.createIfcDirection(list(dir_z))
        ref_dir = self.ifc_file.createIfcDirection(list(dir_x))
        axis2placement = self.ifc_file.createIfcAxis2Placement3D(
            Location=point_ifc, Axis=axis, RefDirection=ref_dir
        )
        return axis2placement

    def _create_world_local_placement(self):
        """Return an IfcLocalPlacement at the world origin (no relative parent)."""
        axis2 = self._create_placement(
            (0.0, 0.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0)
        )
        return self.ifc_file.createIfcLocalPlacement(
            PlacementRelTo=None, RelativePlacement=axis2
        )

    def _get_connection_local_placement(self, cad_obj=None, parent_placement=None):
        """
        Return the module-specific IfcLocalPlacement for *cad_obj* using
        axis_mapper.  Falls back to world origin placement when cad_obj is None.
        """
        from .axis_mapper import get_connection_local_placement
        return get_connection_local_placement(
            self.ifc_file, self.owner_history, cad_obj, parent_placement
        )

    def _create_direction(self, dir_tuple):
        """Helper to create a direction."""
        return self.ifc_file.createIfcDirection(list(dir_tuple))

    def save(self):
        """Save the IFC file to disk."""
        self.ifc_file.write(self.filename)
        print(f"IFC file successfully saved to {self.filename}")

    def export_connection(self, connection_id, members, plates, bolts, welds=None,
                          metadata=None, others=None, cad_obj=None):
        """
        Orchestrates the export of an entire Osdag structural connection.

        :param connection_id: Unique string identifier for the connection
        :param members:  List of Osdag parameterized section objects (ISection, RHS…)
        :param plates:   List of Osdag Plate objects
        :param bolts:    List of Osdag Bolt/Nut/Washer objects
        :param welds:    Optional list of Osdag Weld objects
        :param metadata: Optional dict containing design loads, status, material
        :param others:   Optional list of non-steel elements (Grout, Concrete…)
        :param cad_obj:  Optional live CAD object used to derive the local axis.
                         When provided, the module-specific local axis from
                         axis_mapper is applied; otherwise world origin is used.
        """
        print(f"Starting IFC LOD 500 export for connection: {connection_id}")

        # If a live cad_obj was injected into the exporter, we prefer it.
        if cad_obj is None:
            cad_obj = self._cad_obj

        # ── Connection-level local placement (relative to world) ──────────────
        # This forms the IfcLocalPlacement of the IfcElementAssembly that
        # groups the entire connection.  All child element placements are
        # relative to *this* placement, establishing the local axes described
        # in the task specification.
        connection_placement = self._get_connection_local_placement(
            cad_obj=cad_obj, parent_placement=None
        )

        ifc_elements = []

        # 1. Map Members (Beams, Columns)
        for member in members:
            solid = self.geom_mapper.map_extruded_solid(member)
            if solid:
                m_name = getattr(member, 'ifc_name', 'Steel Member')
                if 'Column' in m_name:
                    ifc_element = self.ifc_file.createIfcColumn(
                        GlobalId=self.generate_guid(),
                        OwnerHistory=self.owner_history,
                        Name=m_name,
                        ObjectPlacement=connection_placement,
                        Representation=self._create_shape_representation(solid)
                    )
                else:
                    ifc_element = self.ifc_file.createIfcBeam(
                        GlobalId=self.generate_guid(),
                        OwnerHistory=self.owner_history,
                        Name=m_name,
                        ObjectPlacement=connection_placement,
                        Representation=self._create_shape_representation(solid)
                    )

                # Apply bolt hole boolean cuts to members (LOD 500)
                for fastener in bolts:
                    if (fastener.__class__.__name__ == 'Bolt'
                            or getattr(fastener, '_class_name', '') == 'Bolt'):
                        try:
                            _fo = getattr(fastener, 'origin', None)
                            f_origin = _fo if _fo is not None else getattr(fastener, 'sec_origin', None)
                            _sd = getattr(fastener, 'shaftDir', None)
                            shaft_dir = _sd if _sd is not None else getattr(fastener, 'uDir', None)
                            r = getattr(fastener, 'r', None)
                            h = getattr(fastener, 'H', None)
                            if f_origin is not None and shaft_dir is not None and r is not None and h is not None:
                                opening = self.geom_mapper.create_opening_element(
                                    f_origin, shaft_dir, r, h
                                )
                                self.geom_mapper.perform_boolean_cut(ifc_element, opening)
                        except Exception as e:
                            print(f"[IFC] Warning: bolt hole on {m_name}: {e}")

                self.meta_mapper.assign_osdag_design_data(ifc_element, member)
                self.meta_mapper.assign_member_boq(ifc_element, member, metadata)
                ifc_elements.append(ifc_element)

        # 2. Map Plates & Apply Boolean Cuts from Bolts
        for plate in plates:
            plate_solid = self.geom_mapper.map_extruded_solid(plate)
            if not plate_solid:
                continue

            p_name = getattr(plate, 'ifc_name', "Connection Plate")
            ifc_plate = self.ifc_file.createIfcPlate(
                GlobalId=self.generate_guid(),
                OwnerHistory=self.owner_history,
                Name=p_name,
                ObjectPlacement=connection_placement,
                Representation=self._create_shape_representation(plate_solid)
            )

            for fastener in bolts:
                if (fastener.__class__.__name__ == 'Bolt'
                        or getattr(fastener, '_class_name', '') == 'Bolt'):
                    try:
                        _fo = getattr(fastener, 'origin', None)
                        f_origin = _fo if _fo is not None else getattr(fastener, 'sec_origin', None)
                        _sd = getattr(fastener, 'shaftDir', None)
                        shaft_dir = _sd if _sd is not None else getattr(fastener, 'uDir', None)
                        r = getattr(fastener, 'r', None)
                        h = getattr(fastener, 'H', None)
                        if f_origin is not None and shaft_dir is not None and r is not None and h is not None:
                            opening = self.geom_mapper.create_opening_element(
                                f_origin, shaft_dir, r, h
                            )
                            self.geom_mapper.perform_boolean_cut(ifc_plate, opening)
                        else:
                            print(f"[IFC] Warning: bolt missing attrs for hole in {p_name}")
                    except Exception as e:
                        print(f"[IFC] Warning: bolt hole on {p_name}: {e}")

            self.meta_mapper.assign_osdag_design_data(ifc_plate, plate)
            self.meta_mapper.assign_plate_boq(ifc_plate, plate)
            ifc_elements.append(ifc_plate)

        # 3. Map Fasteners (Bolts, Nuts, Washers) via Instancing
        for bolt in bolts:
            mapped_item = self.geom_mapper.map_fastener(bolt)
            if mapped_item:
                ifc_fastener = self.ifc_file.createIfcFastener(
                    GlobalId=self.generate_guid(),
                    OwnerHistory=self.owner_history,
                    Name="Bolt Assembly",
                    ObjectPlacement=connection_placement,
                    Representation=self._create_shape_representation(
                        mapped_item, rep_type="MappedRepresentation"
                    )
                )
                self.meta_mapper.assign_fastener_boq(
                    ifc_fastener, bolt, bolt.__class__.__name__
                )
                ifc_elements.append(ifc_fastener)

        # 4. Map Welds
        if welds:
            for weld in welds:
                weld_solid = self.geom_mapper.map_weld(weld)
                if weld_solid:
                    ifc_weld = self.ifc_file.createIfcFastener(
                        GlobalId=self.generate_guid(),
                        OwnerHistory=self.owner_history,
                        Name=getattr(weld, 'designation', 'Weld Joint'),
                        ObjectType="WELD",
                        ObjectPlacement=connection_placement,
                        Representation=self._create_shape_representation(
                            weld_solid, rep_type="SweptSolid"
                        )
                    )
                    self.meta_mapper.assign_osdag_design_data(ifc_weld, weld)
                    self.meta_mapper.assign_weld_boq(ifc_weld, weld)
                    ifc_elements.append(ifc_weld)

        # 5. Map Others (Concrete, Grout) as BuildingElementProxies
        if others:
            for other_item in others:
                other_solid = self.geom_mapper.map_extruded_solid(other_item)
                if other_solid:
                    name = getattr(
                        other_item, '_class_name', other_item.__class__.__name__
                    )
                    ifc_other = self.ifc_file.createIfcBuildingElementProxy(
                        GlobalId=self.generate_guid(),
                        OwnerHistory=self.owner_history,
                        Name=name,
                        ObjectPlacement=connection_placement,
                        Representation=self._create_shape_representation(
                            other_solid, rep_type="SweptSolid"
                        )
                    )
                    ifc_elements.append(ifc_other)

        # 6. Group into IfcElementAssembly, attach local placement, link to Storey
        assembly = self.meta_mapper.create_element_assembly(
            f"Connection_{connection_id}", ifc_elements
        )

        # Assign the connection-level local placement to the assembly
        # (cannot be set in createIfcElementAssembly directly in IFC2X3, use edit)
        try:
            assembly.ObjectPlacement = connection_placement
        except Exception:
            pass  # Schema may not allow post-creation assignment; geometry is already set

        # Attach structural design metadata to the assembly
        if metadata:
            self.meta_mapper.assign_standard_pset(
                assembly, "Pset_OsdagDesignData", metadata
            )

        # Emit a Pset that records which global/local axis convention was used
        self.meta_mapper.assign_standard_pset(assembly, "Pset_OsdagAxisConvention", {
            "GlobalAxisZ": "0,0,1 (Vertical – IS 800)",
            "GlobalAxisX": "1,0,0 (Primary Horizontal)",
            "LocalAxisConvention": type(cad_obj).__name__ if cad_obj else "WorldOrigin",
        })

        self.ifc_file.createIfcRelContainedInSpatialStructure(
            GlobalId=self.generate_guid(),
            OwnerHistory=self.owner_history,
            RelatingStructure=self.storey,
            RelatedElements=[assembly]
        )

        print("Export orchestration completed.")

    def _create_shape_representation(self, geometric_item, rep_type="SweptSolid"):
        """Helper to wrap a solid/mapped item in an IfcProductDefinitionShape."""
        rep = self.ifc_file.createIfcShapeRepresentation(
            ContextOfItems=self.project.RepresentationContexts[0],
            RepresentationIdentifier="Body",
            RepresentationType=rep_type,
            Items=[geometric_item]
        )
        return self.ifc_file.createIfcProductDefinitionShape(Representations=[rep])
