import sys
sys.path.insert(0, 'Osdag/src')
from osdag_core.export_ifc.axis_mapper import (
    create_global_placement, bc_endplate_local_placement,
    cc_splice_local_placement, bb_coverplate_local_placement,
    tension_member_local_placement, get_connection_local_placement
)
import ifcopenshell

ifc = ifcopenshell.file(schema='IFC2X3')
person = ifc.createIfcPerson(Id='Test', FamilyName='Test')
org = ifc.createIfcOrganization(Id='Test', Name='Test')
pao = ifc.createIfcPersonAndOrganization(ThePerson=person, TheOrganization=org)
app = ifc.createIfcApplication(ApplicationDeveloper=org, Version='1.0', ApplicationFullName='Test', ApplicationIdentifier='TST')
oh = ifc.createIfcOwnerHistory(OwningUser=pao, OwningApplication=app, ChangeAction='ADDED', CreationDate=0)

gp = create_global_placement(ifc)
print('Global placement:', gp)

bp = bc_endplate_local_placement(ifc, oh)
print('BC Endplate placement:', bp)

cp = cc_splice_local_placement(ifc, oh)
print('CC Splice placement:', cp)

bbp = bb_coverplate_local_placement(ifc, oh)
print('BB Coverplate placement:', bbp)

tp = tension_member_local_placement(ifc, oh)
print('Tension Member placement:', tp)

class CADGroove:
    pass
p = get_connection_local_placement(ifc, oh, CADGroove())
print('Dispatch (CADGroove):', p)

class TensionAngleBoltCAD:
    pass
p2 = get_connection_local_placement(ifc, oh, TensionAngleBoltCAD())
print('Dispatch (TensionAngleBoltCAD):', p2)

print('\nAll axis_mapper tests PASSED')
