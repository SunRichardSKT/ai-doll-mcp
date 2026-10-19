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
    wall,lt = p['wall'],p['lid_thickness']
    bh=p['floor']+p['bottom_component_space']+r['thickness']+p['module_height_above_main_pcb']+p['top_clearance']
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
        base = base.fuse(box(x,oy+29.5,p['floor']-.1,.8,3,board_top-p['floor']+.1))
    for x in [ox, ox+w-1.8]:
        for y in [oy-.35-.8, oy+h+.35]:
            base = base.fuse(box(x,y,p['floor']-.1,1.8,.8,board_top-p['floor']+.1))
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
    power_y = oy+comps['J9']['y']
    size = p['power_port_width']; zc = p['power_port_bottom']+size/2
    cut = cq.Solid.makeCylinder(size/2, wall+1, cq.Vector(W-wall-.5,power_y,zc), cq.Vector(1,0,0))
    base = base.cut(cut.fuse(box(W-wall-.5,power_y-size/2,zc,wall+1,size,bh-zc+1)))
    # The ordered board has NO mounting/strain-relief holes. Put tie passages in
    # the shell floor, outside the PCB outline, not through the user's board.
    tie_anchors=[]
    for side,xx in [('left',3.9),('right',W-3.9)]:
        ys=sorted(port['yWorld'] for port in ports if port['side']==side)
        for yy in [(ys[0]+ys[1])/2,(ys[2]+ys[3])/2]:tie_anchors.append((xx,yy))
    tie_anchors.append((W-3.9,power_y))
    for xx,yy in tie_anchors:
        for dy in [-2,2]:base=base.cut(box(xx-.65,yy+dy-1.25,-.1,1.3,2.5,p['floor']+.2))

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
    lid = lid.fuse(box(W-wall+.2,power_y-size/2+gap,z,wall-.4,size-2*gap,bh-z+.1))
    # Retainers hover 0.25 mm over the PCB edge, not over ICs or solder joints.
    stop_z = board_top+p['board_retention_gap']
    for local_y in p['support_y']:
        for xx,end in [(wall+gap,ox+p['support_overlap']),(ox+w-p['support_overlap'],W-wall-gap)]:
            rib=box(xx,oy+local_y-p['support_length']/2,stop_z,end-xx,p['support_length'],bh-stop_z+.1)
            for sx,sy in screws:rib=rib.cut(cylinder(sx,sy,stop_z-.1,p['boss_radius']+gap,bh-stop_z+.3))
            lid=lid.fuse(rib)
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
    # Original manufactured PCB is rectangular and has no mounting cutouts.
    components = []
    module_envelope = None
    for c in r['components']:
        if c['ref'].startswith(('J','TP')): continue
        bb = c['bbox']; x,y = ox+bb['minX'],oy+bb['minY']
        dx,dy = bb['maxX']-bb['minX'],bb['maxY']-bb['minY']
        if c['ref']=='U1':
            dx,dy = p['module_width'],p['module_length']; x=ox+c['x']-dx/2; y=oy+c['y']-dy/2
            z,height = board_top,p['module_height_above_main_pcb']
            module_envelope=box(x,y,z,dx,dy,height)
            stand=height-4.8
            if stand<=0:raise ValueError('module height must include standoff + PCB + USB')
            # Symbolic physical stack. XY pin-row centers follow actual 15.24 mm
            # spacing; all Z dimensions and USB/button shapes remain assumptions.
            components.append(('U1_module_PCB',box(x,y,z+stand,dx,dy,1.6),'#243347','top'))
            for hx in [ox+c['x']-7.62,ox+c['x']+7.62]:
                components.append(('U1_socket_'+str(hx),box(hx-1.27,oy+c['y']-10.16,z,2.54,20.32,stand),'#41474b','top'))
            components.append(('USB_symbolic',box(ox+c['x']-4.5,y-.5,z+stand+1.6,9,6.5,3.2),'#a1abae','top'))
            for bx in [-2.8,2.8]:
                components.append(('Button_symbolic_'+str(bx),box(ox+c['x']+bx-1.8,y+7,z+stand+1.6,3.6,2.8,1.7),'#b1b7ad','top'))
            components.append(('Antenna_symbolic',box(ox+c['x']-3,y+dy-2.8,z+stand+1.6,6,2,1.2),'#bc917c','top'))
            continue
        elif c['side']=='bottom':
            height = p['bottom_body_height']; z=bz-height; color='#52515c'
        else:
            height=p['switch_height'] if c['ref']=='SW1' else p['other_top_body_height']
            z=board_top;color='#73665b' if c['ref']=='SW1' else '#bca284'
        components.append((c['ref'],box(x,y,z,dx,dy,height),color,c['side']))
    for tail in r['solderTailReference']:
        components.append((tail['name']+'_tail',cylinder(ox+tail['x'],oy+tail['y'],
                            bz-tail['protrusion'],tail['radius'],tail['protrusion']), '#aaa491','bottom'))
    # Physical collision checks are scoped to declared 2D envelopes + assumed Z.
    collision=[]
    for name,shape,color,side in [('PCB',pcb,'#22736c','board'),('U1_conservative_Z_envelope',module_envelope,'','top')]+components:
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
            'sourcePcbIdentity':r['sourcePcbIdentity'],'sourceHashes':r['sourceHashes'],'dimensionsMm':preview['dimensions'],
            'boardBottomZ':bz,'boardTopZ':board_top,'topInternalRoofZ':bh,'checks':checks,
            'moduleHeightInput':p.get('user_measurement'),
            'topAllowanceMm':p['top_clearance'],
            'baseLidOverlapMm3':volume_common(base,lid),'componentEnvelopeCollisions':collision,
            'ports':ports,'powerPort':{'side':'right','yLocal':comps['J9']['y'],'width':size},
            'tieAnchors':[{'x':x,'y':y} for x,y in tie_anchors],
            'supportContact':'0.45 mm board edge patches at local y=12.827 and 30 mm; 1.4 mm along edge',
            'scope':'BRep + STL topology and case-vs-reference intersections. Module total height uses user approximate 8 mm measurement; sub-part heights, PCB thickness, solder tails and cable sizes remain assumptions.',
            'pending':['physical fit of approximate module height and assumed solder tails','USB plug and removal access','wire bundle diameter and bend radius','switch actuator reach','printed lid fit and screw pilot','RF and thermal test']}
    (out/'audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    if collision or report['baseLidOverlapMm3']>1e-5:raise ValueError('Collision: see output/audit.json')
    print(json.dumps({k:v for k,v in report.items() if k in ['dimensionsMm','checks','componentEnvelopeCollisions','baseLidOverlapMm3']},ensure_ascii=False))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,default=HERE/'output');args=ap.parse_args();build(args.out)
