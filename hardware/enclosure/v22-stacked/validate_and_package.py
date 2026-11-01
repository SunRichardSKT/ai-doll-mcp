"""Read back V2.2 stacked STEP/STL, check assembly/access and package this model."""
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

def bodies(mesh):
    parent=list(range(len(mesh.vertices)))
    def root(i):
        while parent[i]!=i:
            parent[i]=parent[parent[i]];i=parent[i]
        return i
    used=set()
    for face in mesh.faces:
        a,b,c=map(int,face);used.update((a,b,c));parent[root(b)]=root(a);parent[root(c)]=root(a)
    return len({root(i) for i in used})

def validate():
    p=json.loads((HERE/'parameters.json').read_text(encoding='utf-8'))
    r=json.loads((HERE/'pcb_reference.json').read_text(encoding='utf-8'))
    audit=json.loads((OUT/'audit.json').read_text(encoding='utf-8'))
    solids={};checks={}
    for name in NAMES:
        solid=cq.importers.importStep(str(OUT/(name+'.step'))).val()
        mesh=trimesh.load_mesh(OUT/(name+'.stl'))
        assert solid.isValid() and len(solid.Solids())==1,name
        assert mesh.is_watertight and mesh.is_winding_consistent and bodies(mesh)==1 and mesh.volume>0,name
        error=abs(mesh.volume-solid.Volume())/solid.Volume()
        assert error<.005,(name,error)
        solids[name]=solid
        checks[name]=dict(validSingleStep=True,watertightSingleStl=True,relativeVolumeError=error)
    bbs=[s.BoundingBox() for s in solids.values()]
    dims=[max(getattr(b,k+'max') for b in bbs)-min(getattr(b,k+'min') for b in bbs) for k in ('x','y','z')]
    assert all(abs(a-b)<.01 for a,b in zip(dims,[46.29,56.45,33.0])),dims
    intersections={a+'/'+b:solids[a].intersect(solids[b]).Volume() for a,b in [('base','tray'),('base','lid'),('tray','lid')]}
    assert max(intersections.values())<1e-5,intersections
    reserves={key:{name:region(p[key]).intersect(solid).Volume() for name,solid in solids.items()}
              for key in ('battery','battery_reserved','connector_allowance','wire_riser')}
    assert max(v for values in reserves.values() for v in values.values())<1e-5,reserves
    sweep_range=range(0,33)
    battery=region(p['battery_reserved'])
    insertion=max(battery.translate((0,0,z)).intersect(solids['base']).Volume() for z in sweep_range)
    tray_lift=max(solids['tray'].translate((0,0,z)).intersect(solids['base']).Volume() for z in sweep_range)
    assert max(insertion,tray_lift)<1e-5,(insertion,tray_lift)
    # Reconstruct real PCB XY and the bottom-component envelopes independently.
    stack=audit['heightStackMm'];ox,oy=p['board_offset']
    bottom_checks=[]
    for c in r['components']:
        if c['side']!='bottom' or c['ref'].startswith(('J','TP')):continue
        b=c['bbox']
        body=region(dict(x=ox+b['minX'],y=oy+b['minY'],z=stack['pcbBottom']-p['bottom_component_height'],
                         width=b['maxX']-b['minX'],length=b['maxY']-b['minY'],height=p['bottom_component_height']))
        overlap={name:body.intersect(solid).Volume() for name,solid in solids.items()}
        assert max(overlap.values())<1e-5,(c['ref'],overlap)
        assert abs(stack['bottomComponentBottom']-stack['trayTop']-1)<.01
        bottom_checks.append(c['ref'])
    sw=audit['switchWell'];sx,sy=sw['centerMm'];well=p['switch_well']
    roof=stack['roofBottom'];cx=sx+well['offset_x'];cy=sy+well['mouth_offset_y']
    probes={
        'mouth_14x11mm':region(dict(x=cx-7,y=cy-5.5,z=roof+.25,width=14,length=11,height=1.4)),
        'finger_8mm':cq.Solid.makeCylinder(4,5,cq.Vector(sx,sy,sw['actuatorTipMm']-.15)),
    }
    access={key:probe.intersect(solids['lid']).Volume() for key,probe in probes.items()}
    lx,ly=audit['ledWindow']['centerMm']
    access['led_sightline']=cq.Solid.makeCylinder(.5,10,cq.Vector(lx,ly,stack['moduleTop'])).intersect(solids['lid']).Volume()
    assert max(access.values())<1e-5,access
    front_probe=region(dict(x=sx-4,y=-.1,z=sw['actuatorTipMm']-2,
                            width=8,length=sy+.1,height=4))
    front_access={name:front_probe.intersect(solids[name]).Volume() for name in ('base','lid')}
    assert max(front_access.values())<1e-5,front_access
    assert abs(sw['actuatorAboveLocalFloorMm']-2.4)<.01
    assert audit['snaps']['guideClearancePerSideMm']==.15
    assert abs(audit['snaps']['hookEngagementMm']-.55)<.01
    assert not audit['componentEnvelopeCollisions']
    files={name:hashlib.sha256((OUT/name).read_bytes()).hexdigest()
           for name in [*(part+ext for part in NAMES for ext in ('.stl','.step')),'assembly_reference.step']}
    report=dict(passed=True,revision=p['revision'],dimensionsMm=dims,checks=checks,files=files,
                partIntersectionsMm3=intersections,reservedIntersectionsMm3=reserves,
                batteryInsertionMaxCollisionMm3=insertion,trayLiftMaxCollisionMm3=tray_lift,
                movementSampleStepMm=1,bottomComponentChecks=bottom_checks,
                switchAndLedAccessIntersectionsMm3=access,frontSwitchAccessIntersectionsMm3=front_access,
                physicalFitTested=False,
                scope='Exported BRep/STL, rigid clearances and sampled insertion. No elastic, thermal, RF or real-print validation.')
    (OUT/'independent_validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return report

def package(target,report):
    source=['README.md','parameters.json','pcb_reference.json','requirements-cad.txt',
            'build_enclosure.py','render_preview.py','capture_preview.cjs','validate_and_package.py']
    exports=[*(name+ext for name in NAMES for ext in ('.stl','.step')),'assembly_reference.step',
             'audit.json','validation.json','independent_validation.json','meshes.json','preview.html',
             'preview.png','assembled.png','side.png','tray.png','lid.png','stack.svg','stack.png','preview_check.json']
    files={name:(HERE/name).read_bytes() for name in source}
    files.update({'output/'+name:(OUT/name).read_bytes() for name in exports})
    for name,digest in report['files'].items():assert hashlib.sha256(files['output/'+name]).hexdigest()==digest,name
    sums=''.join(hashlib.sha256(raw).hexdigest()+'  '+name+'\n' for name,raw in sorted(files.items()))
    (HERE/'SHA256SUMS.txt').write_text(sums,encoding='utf-8',newline='\n')
    files['SHA256SUMS.txt']=sums.encode('utf-8')
    manifest=dict(revision=report['revision'],physicalFitTested=False,
                  files={name:hashlib.sha256(raw).hexdigest() for name,raw in files.items()})
    files['MANIFEST.json']=json.dumps(manifest,ensure_ascii=False,indent=2).encode('utf-8')
    target.parent.mkdir(exist_ok=True,parents=True)
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
        for name,raw in sorted(files.items()):z.writestr(name,raw)
    with zipfile.ZipFile(target) as z:
        assert z.testzip() is None
        assert set(z.namelist())==set(files)
        for name,digest in manifest['files'].items():assert hashlib.sha256(z.read(name)).hexdigest()==digest,name
    digest=hashlib.sha256(target.read_bytes()).hexdigest()
    target.with_suffix(target.suffix+'.sha256').write_text(digest+'  '+target.name+'\n',encoding='ascii')
    print(json.dumps(dict(file=str(target),sha256=digest,files=len(files)),ensure_ascii=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--validate-only',action='store_true')
    parser.add_argument('--output',type=Path,default=HERE.parents[2]/'delivery/AI_Doll_V22_Stacked_Enclosure_P03.zip')
    args=parser.parse_args();report=validate()
    print(json.dumps(dict(passed=report['passed'],dimensionsMm=report['dimensionsMm']),ensure_ascii=False))
    if not args.validate_only:package(args.output,report)
