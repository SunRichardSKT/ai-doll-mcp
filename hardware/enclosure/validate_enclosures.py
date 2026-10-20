"""Independent exported-model checks for both 103450 enclosure candidates.

Use the pinned requirements-cad.txt environment. This checks exported geometry,
not snap material life, real battery tolerances, or a physically assembled board.
"""
import argparse
import hashlib
import json
from pathlib import Path

import cadquery as cq
import trimesh

HERE = Path(__file__).resolve().parent
MODELS = ('ordered-v2-prototype', 'v22-prototype')


def box(origin, size):
    return cq.Workplane('XY').box(*size, centered=(False, False, False)).translate(origin).val()


def connected_bodies(mesh):
    parent = list(range(len(mesh.vertices)))
    def root(n):
        while parent[n] != n:
            parent[n] = parent[parent[n]]
            n = parent[n]
        return n
    used = set()
    for face in mesh.faces:
        a, b, c = map(int, face)
        used.update((a, b, c))
        parent[root(b)] = root(a)
        parent[root(c)] = root(a)
    return len({root(n) for n in used})


def validate(folder):
    output = folder / 'output'
    parameters = json.loads((folder / 'parameters.json').read_text(encoding='utf-8'))
    audit = json.loads((output / 'audit.json').read_text(encoding='utf-8'))
    data = json.loads((output / 'meshes.json').read_text(encoding='utf-8'))
    solids, checks = {}, {}
    for name in ('base', 'lid'):
        shape = cq.importers.importStep(str(output / (name + '.step'))).val()
        assert shape.isValid() and len(shape.Solids()) == 1, f'{folder.name}: invalid {name} STEP'
        mesh = trimesh.load_mesh(output / (name + '.stl'))
        assert mesh.is_watertight and mesh.is_winding_consistent, f'{name}: invalid STL'
        assert connected_bodies(mesh) == 1 and mesh.volume > 0, f'{name}: disconnected STL'
        assert abs(shape.Volume() - mesh.volume) / shape.Volume() < .005, f'{name}: export mismatch'
        solids[name] = shape
        checks[name] = dict(step_valid=True, step_solids=1, stl_watertight=True,
                            stl_single_body=True, stl_positive_volume=True,
                            stl_step_relative_volume_error=abs(shape.Volume()-mesh.volume)/shape.Volume())
    overlap = solids['base'].intersect(solids['lid']).Volume()
    assert overlap < 1e-5, f'{folder.name}: base/lid collision {overlap}'
    battery = next(p for p in data['parts'] if p['name'] == 'Battery_103450_reference')
    vertices = battery['geometry']['vertices']
    low = [min(v[i] for v in vertices) for i in range(3)]
    high = [max(v[i] for v in vertices) for i in range(3)]
    dimensions = [high[i]-low[i] for i in range(3)]
    assert all(abs(a-b) < .02 for a, b in zip(dimensions, (50, 34, 10))), dimensions
    nominal = box(low, dimensions)
    clear_origin = (low[0]-1, low[1]-1, parameters['floor'])
    clearance = box(clear_origin, (52, 36, 12))
    connector_data = parameters['connector_allowance']
    if isinstance(connector_data, dict):
        connector_origin = [connector_data[k] for k in ('x','y','z')]
        connector_size = [connector_data[k] for k in ('width','length','height')]
    else:
        connector_origin = parameters['connector_allowance_origin']
        connector_size = connector_data
    assert all(a >= b for a,b in zip(connector_size,(12,8,10))), connector_size
    connector = box(connector_origin, connector_size)
    wire_origin = (high[0]+1, low[1], parameters['floor'])
    wire_size = (6, 34, 12)
    wire_space = box(wire_origin, wire_size)
    collisions = {}
    for name, case in solids.items():
        collisions[name] = dict(nominal_battery_mm3=case.intersect(nominal).Volume(),
                                battery_clearance_mm3=case.intersect(clearance).Volume(),
                                connector_clearance_mm3=case.intersect(connector).Volume(),
                                wire_end_clearance_mm3=case.intersect(wire_space).Volume())
        assert max(collisions[name].values()) < 1e-5, f'{folder.name}: battery/connector obstruction {collisions}'
    tray = trimesh.load_mesh(output / 'fit_tray.stl')
    assert tray.is_watertight and tray.is_winding_consistent and connected_bodies(tray) == 1
    # Rendering metadata must describe these exported shapes, rather than an old revision.
    bbs = [s.BoundingBox() for s in solids.values()]
    extents = [max(getattr(b, k+'max') for b in bbs)-min(getattr(b, k+'min') for b in bbs) for k in ('x','y','z')]
    expected = [data['dimensions'][k] for k in ('width','length','height')]
    assert all(abs(a-b) < .02 for a,b in zip(extents, expected)), (extents, expected)
    assert not audit['componentEnvelopeCollisions'], audit['componentEnvelopeCollisions']
    snap = audit.get('snaps', audit.get('snapLid', {}))
    snap_count = snap.get('count', len(snap.get('positions', [])))
    assert snap_count == 4, 'Both candidates use four removable lid clips'
    window = audit['ledWindow']
    window_size = window.get('sizeMm', window.get('openingMm'))
    assert window_size and min(window_size) >= 8, 'LED observation opening missing'
    return dict(revision=audit['revision'], passed=True, exported_dimensions_mm=extents,
                checks=checks, base_lid_overlap_mm3=overlap,
                battery_nominal_mm=dimensions, battery_clearance_mm=[52,36,12],
                battery_clearance_origin_mm=list(clear_origin), connector_clearance_mm=connector_size,
                connector_origin_mm=connector_origin, snap_count=snap_count, led_window=window,
                wire_end_reserved_origin_mm=list(wire_origin), wire_end_reserved_mm=list(wire_size),
                wire_end_to_wall_mm=data['dimensions']['width']-parameters['wall']-high[0],
                clearance_collisions=collisions, fit_tray_watertight=True,
                physical_fit_tested=False, snap_life_tested=False,
                files={name:hashlib.sha256((output/name).read_bytes()).hexdigest()
                       for name in ('base.stl','lid.stl','base.step','lid.step','assembly_reference.step')})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, default=HERE/'validation_103450.json')
    args = parser.parse_args()
    report = dict(models={name:validate(HERE/name) for name in MODELS},
                  scope='Exported STEP/STL geometry and nominal rectangular clearance; no physical snap or battery certification')
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
