"""Build a reversible enclosure prototype. Does not edit any PCB or user configuration.

Run with requirements-cad.txt installed. STEP uses assembly coordinates (mm);
STL lid is flipped so its outside face is on the print bed. Component solids are
conservative XY envelopes with explicitly assumed Z heights, not vendor models.
"""
import argparse
import hashlib
import json
from pathlib import Path

import cadquery as cq
import trimesh

HERE = Path(__file__).resolve().parent


def box(x, y, z, dx, dy, dz):
    return cq.Workplane('XY').box(dx, dy, dz, centered=(False, False, False)).translate((x, y, z)).val()


def rounded(x, y, z, w, h, depth, radius):
    return cq.Workplane('XY').rect(w, h).extrude(depth).edges('|Z').fillet(radius).translate((x+w/2, y+h/2, z)).val()


def cylinder(x, y, z, r, h):
    return cq.Solid.makeCylinder(r, h, cq.Vector(x, y, z))


def volume_common(a, b):
    return a.intersect(b).Volume()


def mesh(shape):
    vertices, faces = shape.tessellate(.08, .15)
    return {'vertices': [[v.x, v.y, v.z] for v in vertices], 'faces': [list(f) for f in faces]}


def mesh_body_count(tm):
    # Vertex connectivity with no optional scipy/networkx dependency.
    parent=list(range(len(tm.vertices)))
    def root(i):
        while parent[i]!=i:
            parent[i]=parent[parent[i]]; i=parent[i]
        return i
    used=set()
    for face in tm.faces:
        a,b,c=map(int,face);used.update((a,b,c))
        parent[root(b)]=root(a);parent[root(c)]=root(a)
    return len({root(i) for i in used})


def build(out):
    p = json.loads((HERE/'parameters.json').read_text(encoding='utf-8'))
    r = json.loads((HERE/'pcb_reference.json').read_text(encoding='utf-8'))
    out.mkdir(parents=True, exist_ok=True)
    w, h = r['width'], r['length']
    ox, oy = p['board_offset_x'], p['board_offset_y']
    W, H = w+2*p['side_margin'], h+p['front_margin']+p['rear_margin']
    wall, bh, lt = p['wall'], p['base_height'], p['lid_thickness']
    bz = p['floor']+p['bottom_component_space']
    board_top = bz+r['thickness']
    comps = {c['ref']: c for c in r['components']}
    base = rounded(0, 0, 0, W, H, bh, p['corner_radius'])
    cavity = rounded(wall, wall, p['floor'], W-2*wall, H-2*wall, bh+1, p['corner_radius']-wall)
    base = base.cut(cavity)
    # Board rests on four narrow unpopulated edge patches; no PCB hole is consumed.
    for local_y in p['support_y']:
        cy = oy+local_y-p['support_length']/2
        base = base.fuse(box(wall-.2, cy, p['floor']-.1, ox+p['support_overlap']-wall+.2,
                             p['support_length'], bz-p['floor']+.1))
        base = base.fuse(box(ox+w-p['support_overlap'], cy, p['floor']-.1,
                             W-wall+.2-(ox+w-p['support_overlap']), p['support_length'], bz-p['floor']+.1))
    # Stops stay outside the outline and away from the central antenna keepout.
    for x in [ox-.35-.8, ox+w+.35]:
        base = base.fuse(box(x, oy+29.5, p['floor']-.1, .8, 3, bz+r['thickness']+.6-p['floor']))
    for x in [ox, ox+w-1.8]:
        for y in [oy-.35-.8, oy+h+.35]:
            base = base.fuse(box(x, y, p['floor']-.1, 1.8, .8, bz+r['thickness']+.6-p['floor']))
    # M2 bosses lie outside the PCB. Front pair and rear pair are below antenna zone.
    screws = [(x, y) for x in [p['boss_x_inset'], W-p['boss_x_inset']] for y in p['boss_y']]
    for x, y in screws:
        base = base.fuse(cylinder(x, y, p['floor']-.1, p['boss_radius'], bh-p['floor']+.1))
        base = base.cut(cylinder(x, y, bh-p['screw_pilot_depth'], p['screw_pilot_diameter']/2, p['screw_pilot_depth']+.2))
    ports = []
    # U notches allow already soldered pigtails to drop into the base from above.
    # Lid fingers fill the upper notch; assembled free opening is nominally 4.4 mm.
    for port in r['wirePorts']:
        y, size = oy+port['y'], p['sensor_port_width']
        x = -.5 if port['side']=='left' else W-wall-.5
        zc = p['sensor_port_bottom']+size/2
        cut = cq.Solid.makeCylinder(size/2, wall+1, cq.Vector(x,y,zc), cq.Vector(1,0,0))
        cut = cut.fuse(box(x, y-size/2, zc, wall+1, size, bh-zc+1))
        base = base.cut(cut)
        ports.append({**port, 'x':x, 'yWorld':y, 'width':size, 'zBottom':p['sensor_port_bottom']})
    power_x = ox+comps['J9']['x']
    size = p['power_port_width']; zc = p['power_port_bottom']+size/2
    cut = cq.Solid.makeCylinder(size/2, wall+1, cq.Vector(power_x,-.5,zc), cq.Vector(0,1,0))
    base = base.cut(cut.fuse(box(power_x-size/2, -.5, zc, size, wall+1, bh-zc+1)))

    lid = rounded(0, 0, bh, W, H, lt, p['corner_radius'])
    # Locating lip: 0.25 mm radial assembly gap; openings occur below it.
    gap = p['lid_location_clearance']; inset = wall+gap
    ring = rounded(inset, inset, bh-1.6, W-2*inset, H-2*inset, 1.8, p['corner_radius']-inset)
    inner = rounded(inset+1, inset+1, bh-1.8, W-2*(inset+1), H-2*(inset+1), 2.2, .9)
    ring = ring.cut(inner)
    for x,y in screws:
        ring = ring.cut(cylinder(x,y,bh-2,p['boss_radius']+gap,3))
    lid = lid.fuse(ring)
    for port in ports:
        sz = port['width']; z = p['sensor_port_bottom']+sz
        xx = .2 if port['side']=='left' else W-wall+.2
        lid = lid.fuse(box(xx, port['yWorld']-sz/2+gap, z, wall-.4, sz-2*gap, bh-z+.1))
    z = p['power_port_bottom']+p['power_port_width']
    lid = lid.fuse(box(power_x-size/2+gap, .2, z, size-2*gap, wall-.4, bh-z+.1))
    # Retainers hover 0.25 mm over the PCB edge, not over ICs or solder joints.
    stop_z = board_top+p['board_retention_gap']
    for local_y in p['support_y']:
        for xx in [ox-.3, ox+w-p['support_overlap']]:
            lid = lid.fuse(box(xx, oy+local_y-1.5, stop_z, p['support_overlap']+.3, 3, bh-stop_z+.1))
    for x, y in screws:
        lid = lid.cut(cylinder(x,y,bh-2,p['lid_screw_diameter']/2,lt+4))
        lid = lid.cut(cylinder(x,y,bh+lt-p['lid_head_recess'],p['lid_head_diameter']/2,p['lid_head_recess']+1))
    # Entire switch body exposed from above; actual actuator reach remains a fit check.
    sw = comps['SW1']; swx, swy = ox+sw['x'], oy+sw['y']
    lid = lid.cut(rounded(swx-5.75, swy-3.5, bh-2, 11.5, 7, lt+4, 1))
    # Engraved text preserves a flat outside print face. No metallic antenna label.
    label = cq.Workplane('XY').text('AI DOLL', 4, .6, combine=True).translate((W/2, H*.58, bh+lt-.3)).val()
    lid = lid.cut(label)
    base, lid = base.clean(), lid.clean()
    # Accurate board outline in XY; thickness is an explicit prototype assumption.
    pcb = cq.Workplane('XY').polyline(r['outline']).close().extrude(r['thickness']).translate((ox,oy,bz)).val()
    for cx in [160,400,950,1190]:
        pcb = pcb.cut(cylinder(ox+cx*.0254,oy+120*.0254,bz-.1,1, r['thickness']+.2))
    components = []
    for c in r['components']:
        if c['ref'].startswith(('J','TP')): continue
        bb = c['bbox']; x,y = ox+bb['minX'],oy+bb['minY']
        dx,dy = bb['maxX']-bb['minX'],bb['maxY']-bb['minY']
        if c['ref']=='U1':
            dx,dy = p['module_width'],p['module_length']; x=ox+w/2-dx/2; y=oy+bb['maxY']-dy
            z,height,color = board_top,p['module_height_above_main_pcb'],'#243347'
        elif c['side']=='bottom':
            height = p['bottom_body_height']; z=bz-height; color='#52515c'
        else:
            height=p['switch_height'] if c['ref']=='SW1' else p['other_top_body_height']
            z=board_top;color='#73665b' if c['ref']=='SW1' else '#bca284'
        components.append((c['ref'],box(x,y,z,dx,dy,height),color,c['side']))
    # Physical collision checks are scoped to declared 2D envelopes + assumed Z.
    collision=[]
    for name,shape,color,side in [('PCB',pcb,'#22736c','board')]+components:
        for case_name, case_shape in [('base',base),('lid',lid)]:
            overlap=volume_common(shape,case_shape)
            if overlap>1e-5:collision.append({'part':name,'case':case_name,'overlapMm3':overlap})
    shapes = {'base':base,'lid':lid}
    meshes=[]; checks={}
    for name, shape in shapes.items():
        if not shape.isValid() or len(shape.Solids())!=1:raise ValueError(name+' invalid or disconnected solid')
        cq.exporters.export(shape,str(out/(name+'.step')))
        printing = shape if name=='base' else shape.rotate((0,0,0),(1,0,0),180).translate((0,H,bh+lt+.3))
        bb=printing.BoundingBox(); printing=printing.translate((-bb.xmin,-bb.ymin,-bb.zmin))
        cq.exporters.export(printing,str(out/(name+'.stl')),tolerance=.04,angularTolerance=.12)
        tm=trimesh.load_mesh(out/(name+'.stl'))
        body_count=mesh_body_count(tm)
        checks[name]={'validBrep':shape.isValid(),'solidCount':len(shape.Solids()),'volumeMm3':shape.Volume(),
                       'meshWatertight':bool(tm.is_watertight),'meshWindingConsistent':bool(tm.is_winding_consistent),
                       'meshBodyCount':body_count,'printBoundsMm':tm.bounds.tolist()}
        if not tm.is_watertight or not tm.is_winding_consistent or body_count!=1:raise ValueError(name+' STL invalid')
        meshes.append({'name':name,'color':'#bdc8bb' if name=='base' else '#e5eadf','geometry':mesh(shape)})
    # A low tray is faster to print first; confirms board edge and bottom clearance only.
    fit=base.intersect(box(-1,-1,-1,W+2,H+2,bz+1.4))
    cq.exporters.export(fit,str(out/'fit_tray.stl'),tolerance=.04,angularTolerance=.12)
    assy=cq.Assembly(name=p['revision'])
    assy.add(base,name='Base',color=cq.Color(.72,.77,.70));assy.add(lid,name='Lid',color=cq.Color(.88,.90,.85))
    assy.add(pcb,name='PCB_reference',color=cq.Color(.1,.39,.32))
    for name,shape,color,side in components:assy.add(shape,name=name+'_ASSUMED_HEIGHT',color=cq.Color(.24,.25,.29))
    assy.save(str(out/'assembly_reference.step'))
    meshes.append({'name':'PCB','color':'#22736c','geometry':mesh(pcb)})
    for name,shape,color,side in components:meshes.append({'name':name,'color':color,'geometry':mesh(shape)})
    preview={'dimensions':{'width':W,'length':H,'height':bh+lt},'parts':meshes}
    (out/'meshes.json').write_text(json.dumps(preview,separators=(',',':')),encoding='utf-8')
    report={'revision':p['revision'],'units':'mm','manufacturingReady':False,'printedOrFitTested':False,
            'sourcePcbSha256':r['pcbSemanticSha256'],'dimensionsMm':preview['dimensions'],
            'boardBottomZ':bz,'boardTopZ':board_top,'topInternalRoofZ':bh,'checks':checks,
            'baseLidOverlapMm3':volume_common(base,lid),'componentEnvelopeCollisions':collision,
            'ports':ports,'supportContact':'0.6 mm board edge patches at local y=4 and 31 mm',
            'scope':'BRep + STL topology and case-vs-reference intersections. Component heights, PCB thickness and cable sizes are assumed, not physical measurements.',
            'pending':['assembled heights and USB removal access','wire bundle diameter and bend radius','switch actuator reach','printed lid fit and screw pilot','RF and thermal test','SuperMini hand-solder footprint adaptation']}
    (out/'audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    if collision or report['baseLidOverlapMm3']>1e-5:raise ValueError('Collision: see output/audit.json')
    print(json.dumps({k:v for k,v in report.items() if k in ['dimensionsMm','checks','componentEnvelopeCollisions','baseLidOverlapMm3']},ensure_ascii=False))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,default=HERE/'output');args=ap.parse_args();build(args.out)
