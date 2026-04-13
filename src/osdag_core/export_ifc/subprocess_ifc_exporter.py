import sys
import json
import os
import argparse
from types import SimpleNamespace

# Make sure we can import osdag_core
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from osdag_core.export_ifc.ifc_generator import OsdagIfcExporter

class DictToObj(SimpleNamespace):
    def __init__(self, dictionary, **kwargs):
        super().__init__(**kwargs)
        for key, value in dictionary.items():
            if isinstance(value, dict):
                setattr(self, key, DictToObj(value))
            elif isinstance(value, list) and len(value) > 0 and isinstance(value[0], dict):
                setattr(self, key, [DictToObj(v) for v in value])
            else:
                setattr(self, key, value)
    
    @property
    def __class__(self):
        # We need this to fake the class name for geometry_mapper
        class FakeClass:
            __name__ = getattr(self, '_class_name', 'Unknown')
        return FakeClass

def run_export(json_path, ifc_path, connection_id):
    print(f"[Subprocess] Loading JSON data from {json_path}")
    with open(json_path, 'r') as f:
        data = json.load(f)
        
    members = [DictToObj(m) for m in data.get('members', [])]
    plates = [DictToObj(p) for p in data.get('plates', [])]
    bolts = [DictToObj(b) for b in data.get('bolts', [])]
    welds = [DictToObj(w) for w in data.get('welds', [])]
    others = [DictToObj(o) for o in data.get('others', [])]
    metadata = data.get('metadata', {})

    print(f"[Subprocess] Metadata payload received: {metadata}")

    # Build a lightweight CAD-proxy so axis_mapper can infer local axes
    # from the serialised geometry without needing the live PythonOCC objects.
    cad_proxy = None
    cad_class = metadata.get('_cad_class', '')
    if cad_class:
        cad_proxy = DictToObj({'_class_name': cad_class})
        # Inject the first member and beam/column objects so axis_mapper
        # can extract origin and direction vectors from the proxy.
        if members:
            first_col = next(
                (m for m in members if 'Column' in getattr(m, 'ifc_name', '')), None
            )
            first_beam = next(
                (m for m in members if 'Beam' in getattr(m, 'ifc_name', '')), None
            )
            if first_col:
                setattr(cad_proxy, 'column', first_col)
                setattr(cad_proxy, 'column1', first_col)
            if first_beam:
                setattr(cad_proxy, 'beam', first_beam)
                setattr(cad_proxy, 'beamLeft', first_beam)
                setattr(cad_proxy, 'beam1', first_beam)
        if plates:
            setattr(cad_proxy, 'plate1', plates[0])

    print(f"[Subprocess] Exporting to IFC: {ifc_path}")
    exporter = OsdagIfcExporter(filename=ifc_path)
    exporter.export_connection(
        connection_id=connection_id,
        members=members,
        plates=plates,
        bolts=bolts,
        welds=welds if welds else None,
        others=others if others else None,
        metadata=metadata,
        cad_obj=cad_proxy
    )
    exporter.save()
    print(f"[Subprocess] IFC Success.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export serialized OSDAG CAD objects to IFC via subprocess")
    parser.add_argument("--json", required=True, help="Input serialized JSON file")
    parser.add_argument("--ifc", required=True, help="Output IFC file path")
    parser.add_argument("--id", required=True, help="Connection ID")
    
    args = parser.parse_args()
    
    try:
        run_export(args.json, args.ifc, args.id)
        sys.exit(0)
    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)
