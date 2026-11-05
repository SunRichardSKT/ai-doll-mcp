"""Independently reread STEP/STL, test removal envelopes and bundle the socket case."""
import hashlib,json,zipfile
from pathlib import Path
import cadquery as cq
import trimesh
HERE=Path(__file__).resolve().parent;OUT=HERE/'output'
NAMES=('base','tray','lid')
def box(x,y,z,w,l,h):return cq.Workplane('XY').box(w,l,h,centered=False).translate((x,y,z)).val()
def region(d):return box(*(d[k] for k in ('x','y','z','width','length','height')))
def run():
 p=json.loads((HERE/'parameters.json').read_text(encoding='utf-8'));r=json.loads((HERE/'pcb_reference.json').read_text(encoding='utf-8'));a=json.loads((OUT/'audit.json').read_text(encoding='utf-8'))
 solids={name:cq.importers.importStep(str(OUT/(name+'.step'))).val() for name in NAMES};checks={}
 for name,s in solids.items():
  tm=trimesh.load_mesh(OUT/(name+'.stl'));assert s.isValid() and len(s.Solids())==1
  assert tm.is_watertight and tm.is_winding_consistent and tm.volume>0
  error=abs(tm.volume-s.Volume())/s.Volume();assert error<.005
  checks[name]=dict(validSingleStep=True,watertightStl=True,relativeVolumeError=error)
 battery=region(p['battery_reserved']); insertion=[];tray_lift=[]
 for z in range(0,41,2):
  insertion.append(battery.translate((0,0,z)).intersect(solids['base']).Volume())
  tray_lift.append(solids['tray'].translate((0,0,z)).intersect(solids['base']).Volume())
 assert max(insertion)<1e-5 and max(tray_lift)<1e-5
 ox,oy=p['board_offset'];top=a['heightStackMm']['pcbTop'];bottom=a['heightStackMm']['pcbBottom']
 heads=[]
 for c in r['components']:
  if c['ref'] not in ['J'+str(i) for i in range(1,9)]:continue
  b=c['bbox'];heads.append(box(ox+b['minX'],oy+b['minY'],top,b['maxX']-b['minX'],b['maxY']-b['minY'],p['header_height']))
 assert len(heads)==8
 carrier=cq.Compound.makeCompound([solids['tray'],box(ox,oy,bottom,r['width'],r['length'],r['thickness']),*heads]);carrier_lift=[]
 for z in range(0,41,2):carrier_lift.append(carrier.translate((0,0,z)).intersect(solids['base']).Volume())
 assert max(carrier_lift)<1e-5,carrier_lift
 assert not a['componentEnvelopeCollisions'] and max(a['partIntersectionsMm3'].values())<1e-5
 report=dict(passed=True,revision=p['revision'],dimensionsMm=a['dimensionsMm'],checks=checks,batteryInsertionSampleMm=2,batteryInsertionMm3=insertion,trayLiftMm3=tray_lift,populatedCarrierLiftMm3=carrier_lift,headerCount=8,physicalFitTested=False,scope='Independent exports and sampled rigid vertical insertion/removal; no connector mating force, continuous sweep, fatigue or physical assembly proof.',files={name+ext:hashlib.sha256((OUT/(name+ext)).read_bytes()).hexdigest() for name in NAMES for ext in ('.stl','.step')})
 (OUT/'independent_validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 source=['README.md','parameters.json','pcb_reference.json','requirements-cad.txt','build_enclosure.py','render_preview.py','capture_preview.cjs','validate_and_package.py']
 exports=[*(name+ext for name in NAMES for ext in ('.stl','.step')),'assembly_reference.step','audit.json','validation.json','independent_validation.json','preview.html','preview.png','assembled.png','side.png','tray.png','lid.png','stack.svg','stack.png','preview_check.json']
 files={name:(HERE/name).read_bytes() for name in source};files.update({'output/'+name:(OUT/name).read_bytes() for name in exports})
 sums=''.join(hashlib.sha256(raw).hexdigest()+'  '+name+'\n' for name,raw in sorted(files.items()));(HERE/'SHA256SUMS.txt').write_text(sums,encoding='utf-8');files['SHA256SUMS.txt']=sums.encode('utf-8')
 manifest=dict(revision=p['revision'],files={name:hashlib.sha256(raw).hexdigest() for name,raw in files.items()});files['MANIFEST.json']=(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
 target=HERE.parents[2]/'delivery/AI_Doll_C3_Socket_Enclosure_P01.zip';target.parent.mkdir(parents=True,exist_ok=True)
 with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
  for name,raw in files.items():z.writestr(name,raw)
 with zipfile.ZipFile(target) as z:
  assert z.testzip() is None
  for name,raw in files.items():assert z.read(name)==raw
 target.with_suffix('.zip.sha256').write_text(hashlib.sha256(target.read_bytes()).hexdigest()+'  '+target.name+'\n',encoding='utf-8')
 print(json.dumps(dict(passed=True,dimensionsMm=report['dimensionsMm'],path=str(target),files=len(files)),ensure_ascii=False))
if __name__=='__main__':run()
