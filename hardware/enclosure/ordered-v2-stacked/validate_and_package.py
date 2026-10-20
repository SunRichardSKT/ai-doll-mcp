"""Independently read the exported solids, check access, then make a public ZIP."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

import cadquery as cq
import trimesh

HERE=Path(__file__).resolve().parent
OUT=HERE/'output'
NAMES=('base','tray','lid')


def region(d):
    return cq.Workplane('XY').box(*(d[k] for k in ('width','length','height')),centered=False).translate(
        tuple(d[k] for k in ('x','y','z'))).val()


def body_count(mesh):
    parent=list(range(len(mesh.vertices)))
    def root(i):
        while parent[i]!=i:
            parent[i]=parent[parent[i]]
            i=parent[i]
        return i
    used=set()
    for a,b,c in mesh.faces:
        a,b,c=map(int,(a,b,c));used.update((a,b,c))
        parent[root(b)]=root(a);parent[root(c)]=root(a)
    return len({root(i) for i in used})


def validate():
    p=json.loads((HERE/'parameters.json').read_text(encoding='utf-8'))
    audit=json.loads((OUT/'audit.json').read_text(encoding='utf-8'))
    solids={}; checks={}
    for name in NAMES:
        solid=cq.importers.importStep(str(OUT/(name+'.step'))).val()
        tm=trimesh.load_mesh(OUT/(name+'.stl'))
        assert solid.isValid() and len(solid.Solids())==1,name
        assert tm.is_watertight and tm.is_winding_consistent and body_count(tm)==1 and tm.volume>0,name
        difference=abs(tm.volume-solid.Volume())/solid.Volume()
        assert difference<.005,name
        solids[name]=solid
        checks[name]=dict(validSingleStep=True,watertightSingleStl=True,relativeVolumeError=difference)
    bbs=[s.BoundingBox() for s in solids.values()]
    dims=[max(getattr(b,k+'max') for b in bbs)-min(getattr(b,k+'min') for b in bbs) for k in ('x','y','z')]
    assert all(abs(a-b)<.01 for a,b in zip(dims,[46.29,56.45,35.2])),dims
    intersections={a+'/'+b:solids[a].intersect(solids[b]).Volume() for a,b in [('base','tray'),('base','lid'),('tray','lid')]}
    assert max(intersections.values())<1e-5,intersections
    clearances={}
    for key in ('battery','battery_reserved','connector_allowance','wire_riser'):
        shape=region(p[key])
        clearances[key]={name:shape.intersect(solid).Volume() for name,solid in solids.items()}
        assert max(clearances[key].values())<1e-5,clearances[key]
    # With the lid and PCB carrier removed, the full cell reserve must be able to
    # enter from above, not merely fit once buried below fixed board supports.
    battery=region(p['battery_reserved'])
    insertion=[battery.translate((0,0,z)).intersect(solids['base']).Volume() for z in range(37)]
    tray_lift=[solids['tray'].translate((0,0,z)).intersect(solids['base']).Volume() for z in range(37)]
    assert max(insertion)<1e-5,insertion
    assert max(tray_lift)<1e-5,tray_lift
    # Actual mesh reference tails must all end 1 mm above the continuous shield.
    meshes=json.loads((OUT/'meshes.json').read_text(encoding='utf-8'))
    tails=[part for part in meshes['parts'] if part['name'].endswith('_5mm_tail')]
    assert len(tails)==len(json.loads((HERE/'pcb_reference.json').read_text(encoding='utf-8'))['solderTailReference'])
    tail_checks=[]
    for part in tails:
        vv=part['geometry']['vertices']
        bottom=min(v[2] for v in vv); top=max(v[2] for v in vv)
        assert abs(top-bottom-5)<.01
        x=sum((min(v[0] for v in vv),max(v[0] for v in vv)))/2
        y=sum((min(v[1] for v in vv),max(v[1] for v in vv)))/2
        shield_top=13.8+1.4
        assert abs(bottom-shield_top-1)<.01
        probe=cq.Solid.makeCylinder(.2,1.3,cq.Vector(x,y,13.85))
        assert abs(probe.intersect(solids['tray']).Volume()-probe.Volume())<1e-5,part['name']
        tail_checks.append(dict(name=part['name'],heightMm=top-bottom,gapMm=bottom-shield_top))
    # Through-hole at switch and open LED sight-line, independent of audit booleans.
    sw=audit['switchWell']; sx,sy=sw['centerMm']
    switch_path=cq.Solid.makeCylinder(.5,8,cq.Vector(sx,sy,29))
    lx,ly=audit['ledWindow']['centerMm']
    led_path=cq.Solid.makeCylinder(.5,10,cq.Vector(lx,ly,30))
    assert switch_path.intersect(solids['lid']).Volume()<1e-5
    assert led_path.intersect(solids['lid']).Volume()<1e-5
    assert not audit['componentEnvelopeCollisions']
    files={n:hashlib.sha256((OUT/n).read_bytes()).hexdigest() for n in
           [*(name+ext for name in NAMES for ext in ('.stl','.step')),'assembly_reference.step']}
    report=dict(passed=True,revision=p['revision'],dimensionsMm=dims,checks=checks,
                partIntersectionsMm3=intersections,reservedIntersectionsMm3=clearances,
                batteryInsertionMaxCollisionMm3=max(insertion),trayLiftMaxCollisionMm3=max(tray_lift),
                movementCheck=dict(sampleStepMm=1,rangeMm=[0,36],continuousSweep=False),
                tailChecks=tail_checks,switchAndLedSightLinesClear=True,files=files,
                physicalFitTested=False,wireBendTested=False,elasticStressTested=False,
                scope='Exported BRep/STL and rigid vertical access. No real print, pouch tolerance, RF or electrical validation.')
    (OUT/'independent_validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return report


def package(target, report):
    source=['README.md','parameters.json','pcb_reference.json','requirements-cad.txt','build_enclosure.py',
            'render_preview.py','validate_and_package.py','capture_preview.cjs']
    exported=[*(name+ext for name in NAMES for ext in ('.stl','.step')),'assembly_reference.step',
              'audit.json','validation.json','independent_validation.json','meshes.json','preview.html',
              'preview.png','assembled.png','side.png','tray.png','stack.svg','stack.png','preview_check.json']
    files={name:(HERE/name).read_bytes() for name in source}
    files.update({'output/'+name:(OUT/name).read_bytes() for name in exported})
    for name,digest in report['files'].items():
        assert hashlib.sha256(files['output/'+name]).hexdigest()==digest,name
    manifest=dict(revision=report['revision'],physicalFitTested=False,
                  files={name:hashlib.sha256(raw).hexdigest() for name,raw in files.items()})
    sums=''.join(digest+'  '+name+'\n' for name,digest in sorted(manifest['files'].items()))
    (HERE/'SHA256SUMS.txt').write_text(sums,encoding='utf-8')
    files['SHA256SUMS.txt']=sums.encode('utf-8')
    manifest['files']['SHA256SUMS.txt']=hashlib.sha256(files['SHA256SUMS.txt']).hexdigest()
    files['MANIFEST.json']=json.dumps(manifest,ensure_ascii=False,indent=2).encode('utf-8')
    target.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as archive:
        for name,raw in sorted(files.items()):archive.writestr(name,raw)
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
        assert set(archive.namelist())==set(manifest['files'])|{'MANIFEST.json'}
        for name,digest in manifest['files'].items():
            assert hashlib.sha256(archive.read(name)).hexdigest()==digest,name
    digest=hashlib.sha256(target.read_bytes()).hexdigest()
    target.with_suffix(target.suffix+'.sha256').write_text(digest+'  '+target.name+'\n',encoding='ascii')
    print(json.dumps(dict(file=str(target),sha256=digest,files=len(files)),ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--validate-only',action='store_true')
    parser.add_argument('--output',type=Path,default=HERE.parents[2]/'delivery/AI_Doll_Enclosure_Stacked_103450_20261020.zip')
    args=parser.parse_args()
    result=validate()
    print(json.dumps(dict(passed=result['passed'],dimensionsMm=result['dimensionsMm'],tailCount=len(result['tailChecks'])),ensure_ascii=False))
    if not args.validate_only:package(args.output,result)
