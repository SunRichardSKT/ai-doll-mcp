"""Package the two printable parts, CAD sources and local preview."""
import hashlib
import json
import zipfile
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
FILES=['POWER_WIRING.md','README.md','parameters.json','requirements-cad.txt','build_enclosure.py','render_preview.py','render_drawing.py','viewer.js','capture_preview.cjs','package.py','SHA256SUMS.txt',
       'output/base.stl','output/lid.stl','output/base.step','output/lid.step','output/assembly_reference.step',
       'output/preview.html','output/preview.png','output/assembled.png','output/inside.png','output/wiring.png','output/wiring.svg','output/drawing.svg','output/audit.json','output/preview_check.json']

def run():
    audit=json.loads((HERE/'output/audit.json').read_text(encoding='utf-8'))
    assert audit['revision']=='CHARGER-P02-FOUR-WIRE'
    assert set(audit['checks'])=={'base','lid'}
    for check in audit['checks'].values():
        assert check['validBrep'] and check['meshWatertight'] and check['meshBodies']==1
    for line in (HERE/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
        expected,name=line.split('  ',1)
        assert hashlib.sha256((HERE/name).read_bytes()).hexdigest()==expected,name
    assert json.loads((HERE/'output/preview_check.json').read_text(encoding='utf-8'))['passed']
    for name in FILES: assert (HERE/name).is_file(),name
    out=ROOT/'delivery'/'AI_Doll_Charger_Enclosure_P02.zip'
    out.parent.mkdir(parents=True,exist_ok=True)
    manifest={'revision':'CHARGER-P02-FOUR-WIRE','files':{'AI_Doll_Charger_P02/'+name:hashlib.sha256((HERE/name).read_bytes()).hexdigest() for name in FILES}}
    with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name in FILES: z.write(HERE/name,'AI_Doll_Charger_P02/'+name)
        z.writestr('MANIFEST.json',json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    with zipfile.ZipFile(out) as z:
        assert z.testzip() is None
        for name in FILES: assert z.read('AI_Doll_Charger_P02/'+name)==(HERE/name).read_bytes()
    out.with_suffix('.zip.sha256').write_text(hashlib.sha256(out.read_bytes()).hexdigest()+'  '+out.name+'\n',encoding='utf-8')
    print(json.dumps({'path':str(out),'files':len(FILES),'bytes':out.stat().st_size,'physicalFitTested':False},ensure_ascii=False))

if __name__=='__main__':run()
