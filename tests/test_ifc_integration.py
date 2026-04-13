"""
Integration test for the enhanced Osdag IFC wrapper.
Tests all 4 target modules with synthetic data.
"""
import sys
import os
sys.path.insert(0, '/Users/adityasarna/osd/Osdag/src')

import numpy as np
import ifcopenshell

from osdag_core.export_ifc.ifc_generator import OsdagIfcExporter

class FakeMember:
    """Minimal Osdag ISection member stub."""
    _class_name = 'ISection'
    ifc_name = 'Beam'
    sec_origin = [0.0, 0.0, 0.0]
    uDir = np.array([1.0, 0.0, 0.0])
    wDir = np.array([0.0, 0.0, 1.0])
    B = 250.0; D = 450.0; t = 9.8; T = 14.2; R1 = 15.0; R2 = 7.5; alpha = 90.0
    length = 2000.0
    material = 'E250'
    designation = 'ISMB 450'

class FakeColumn(FakeMember):
    ifc_name = 'Column'
    sec_origin = [0.0, 0.0, 0.0]
    wDir = np.array([0.0, 0.0, 1.0])
    B = 200.0; D = 200.0; t = 9.0; T = 12.5; R1 = 12.0; R2 = 6.0; alpha = 90.0
    length = 3000.0
    designation = 'ISHB 200'

class FakePlate:
    """Minimal Plate stub."""
    _class_name = 'Plate'
    ifc_name = 'End Plate'
    sec_origin = [0.0, 0.0, 0.0]
    uDir = np.array([1.0, 0.0, 0.0])
    wDir = np.array([0.0, 0.0, 1.0])
    vDir = np.array([0.0, 1.0, 0.0])
    L = 400.0; W = 250.0; T = 16.0
    material = 'E250'
    parent_connection_type = ''

class FakeBolt:
    """Minimal Bolt stub."""
    _class_name = 'Bolt'
    ifc_name = 'Bolt'
    origin = np.array([50.0, 0.0, 50.0])
    sec_origin = np.array([50.0, 0.0, 50.0])
    uDir = np.array([1.0, 0.0, 0.0])
    wDir = np.array([0.0, 0.0, 1.0])
    shaftDir = np.array([0.0, 1.0, 0.0])
    R = 12.0; r = 9.0; T = 8.0; H = 50.0
    parent_connection_type = ''

class FakeWeld:
    """Minimal FilletWeld stub."""
    _class_name = 'FilletWeld'
    ifc_name = 'Weld'
    sec_origin = np.array([0.0, 0.0, 200.0])
    uDir = np.array([0.0, 1.0, 0.0])
    wDir = np.array([0.0, 0.0, 1.0])
    b = 6.0; h = 6.0; L = 200.0
    parent_connection_type = ''


# ─── Fake CAD objects for each module ─────────────────────────────────────────

class FakeBCEndplate:
    """Beam-to-Column End Plate CAD stub."""
    column = FakeColumn()
    beam = FakeMember()

class FakeCCSplice:
    """Column-to-Column Cover Plate Welded stub."""
    column1 = FakeColumn()
    column2 = FakeColumn()

class FakeBBCad:
    """Beam-to-Beam Cover Plate Bolted stub."""
    beamLeft = FakeMember()
    beamRight = FakeMember()

class FakeTension:
    """Tension Member – Angle bolted to end gusset stub."""
    member1 = FakeMember()
    plate1 = FakePlate()


MODULES = [
    ('BCEndplate',   FakeBCEndplate,   'CADGroove'),
    ('CCSplice',     FakeCCSplice,     'CCSpliceCoverPlateWeldedCAD'),
    ('BBCad',        FakeBBCad,        'BBCoverPlateBoltedCAD'),
    ('TensionMember',FakeTension,      'TensionAngleBoltCAD'),
]

from osdag_core.export_ifc.axis_mapper import MODULE_PLACEMENT_MAP

outdir = '/tmp/osdag_ifc_test'
os.makedirs(outdir, exist_ok=True)

for name, cad_cls, class_name in MODULES:
    out_path = os.path.join(outdir, f'{name}.ifc')
    print(f'\n=== Testing {name} [{class_name}] ===')

    # Build exporter
    exp = OsdagIfcExporter(filename=out_path, schema='IFC2X3')

    cad_obj = cad_cls()
    # Monkey-patch __class__.__name__ to match the dispatch map
    cad_obj.__class__.__name__ = class_name

    members = [FakeColumn(), FakeMember()] if name == 'BCEndplate' else [FakeMember()]
    members[0].ifc_name = 'Column' if name == 'BCEndplate' else 'Beam'

    exp.export_connection(
        connection_id=name,
        members=members,
        plates=[FakePlate()],
        bolts=[FakeBolt()],
        welds=[FakeWeld()] if name in ('BCEndplate', 'CCSplice') else None,
        metadata={'Module': name, 'DesignCode': 'IS 800:2007'},
        cad_obj=cad_obj
    )
    exp.save()

    # Verify the file was created and contains expected keywords
    assert os.path.exists(out_path), f"IFC file not created: {out_path}"
    content = open(out_path).read()
    assert 'IFCLOCALPLACEMENT' in content, "Missing IfcLocalPlacement"
    assert 'IFCAXIS2PLACEMENT3D' in content, "Missing IfcAxis2Placement3D"
    assert 'IFCELEMENTASSEMBLY' in content, "Missing IfcElementAssembly"
    assert 'PST_OSDAGAXISCONVENTION' not in content  # case insensitive check
    assert 'PSET_OSDAGAXISCONVENTION' in content.upper(), "Missing axis convention Pset"
    assert 'IS 800:2007' in content, "Missing IS 800 reference"
    print(f'  ✓ {out_path} ({os.path.getsize(out_path)} bytes)')

print('\n\nAll integration tests PASSED.')
