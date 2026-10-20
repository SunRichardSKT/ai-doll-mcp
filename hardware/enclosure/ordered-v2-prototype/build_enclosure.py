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
    W, H = p['outer_width'], h+p['front_margin']+p['rear_margin']
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
    for y,xs in [(oy-.35-.8,[ox,ox+w/2]),(oy+h+.35,[ox,ox+w-1.8])]:
        for x in xs:
            base = base.fuse(box(x,y,p['floor']-.1,1.8,.8,board_top-p['floor']+.1))
    # A full-height insulating divider separates the pouch cell from all PCB
    # solder tails. The narrow top-entry slot is for insulated leads only.
    divider_y=p['battery_divider_y']; divider_h=p['battery_clear_height']
    divider=box(wall-.1,divider_y,p['floor']-.1,W-2*wall+.2,p['battery_divider_thickness'],divider_h+.1)
    slot_x=p['battery_wire_slot_x']; slot_w=p['battery_wire_slot_width']; slot_z=p['battery_wire_slot_bottom']
    slot=cq.Solid.makeCylinder(slot_w/2,p['battery_divider_thickness']+.4,
           cq.Vector(slot_x,divider_y-.2,slot_z+slot_w/2),cq.Vector(0,1,0))
    slot=slot.fuse(box(slot_x-slot_w/2,divider_y-.2,slot_z+slot_w/2,slot_w,p['battery_divider_thickness']+.4,bh))
    divider=divider.cut(slot)
    base=base.fuse(divider)
    clips=[]
    for side in ['left','right']:
        for yy in p['snap_y']:
            clips.append({'side':side,'y':yy})
            xx=-.2 if side=='left' else W-wall-.2
            base=base.cut(box(xx,yy-p['snap_width']/2-p['snap_clearance'],p['snap_window_bottom'],
                            wall+.4,p['snap_width']+2*p['snap_clearance'],p['snap_window_height']))
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
    for clip in clips:
        # Isolate each cantilever from the locating ring below its lid root.
        xx=wall if clip['side']=='left' else W-wall-3
        ring=ring.cut(box(xx,clip['y']-p['snap_width']/2-.6,bh-2,3,p['snap_width']+1.2,3))
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
            lid=lid.fuse(rib)
    snap_shapes=[]
    for clip in clips:
        # Inward-flexing PETG leg with an insertion ramp and a flat retaining
        # shoulder. Access windows expose the recessed hook for manual release.
        yy=clip['y']; inside=wall+p['snap_clearance']; thick=p['snap_thickness']
        z0=bh-p['snap_length']; hook_top=p['snap_hook_top']; hook_tip=p['snap_hook_tip_x']
        points=[(inside+thick,z0),(inside,z0),(hook_tip,hook_top-1.5),
                (hook_tip,hook_top),(inside,hook_top),(inside,bh+.15),(inside+thick,bh+.15)]
        if clip['side']=='right':points=[(W-x,z) for x,z in points][::-1]
        snap=cq.Workplane('XZ').polyline(points).close().extrude(p['snap_width']).translate((0,yy+p['snap_width']/2,0)).val()
        lid=lid.fuse(snap); snap_shapes.append(snap)
    # Entire switch body exposed from above; actual actuator reach remains a fit check.
    sw = comps['SW1']; swx, swy = ox+sw['x'], oy+sw['y']
    lid = lid.cut(rounded(swx-5.75, swy-3.5, bh-2, 11.5, 7, lt+4, 1))
    led=p['led_window']; led_x=ox+comps['U1']['x']+led['offset_x']; led_y=oy+comps['U1']['y']+led['offset_y']
    lid=lid.cut(rounded(led_x-led['width']/2,led_y-led['length']/2,bh-2,
                       led['width'],led['length'],lt+4,1.2))
    # Engraved text preserves a flat outside print face. No metallic antenna label.
    label = cq.Workplane('XY').text('AI DOLL', 4, .6, combine=True).translate((W/2, 22, bh+lt-.3)).val()
    lid = lid.cut(label)
    # Rounded inner roots lower the stress concentration without extending
    # outward into the base wall. Elastic life is still a physical print test.
    root_edges=[]
    for edge in lid.Edges():
        bb=edge.BoundingBox()
        if bb.xlen<1e-5 and bb.zlen<1e-5 and abs(bb.zmin-bh)<1e-5 and abs(bb.ylen-p['snap_width'])<1e-5:
            if any(abs(bb.xmin-xx)<1e-5 for xx in [wall+p['snap_clearance']+p['snap_thickness'],W-wall-p['snap_clearance']-p['snap_thickness']]):
                root_edges.append(edge)
    if len(root_edges)!=4:raise ValueError('Four snap inner root edges required')
    lid=lid.fillet(p['snap_root_radius'],root_edges)
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
    battery=p['battery']; battery_shape=box(battery['x'],battery['y'],battery['z'],battery['length'],battery['width'],battery['thickness'])
    reserve=p['battery_reserved']; reserve_shape=box(reserve['x'],reserve['y'],reserve['z'],reserve['length'],reserve['width'],reserve['height'])
    connector=p['connector_allowance']; connector_shape=box(connector['x'],connector['y'],connector['z'],connector['width'],connector['length'],connector['height'])
    turn=p['battery_wire_turn']; turn_shape=box(turn['x'],turn['y'],turn['z'],turn['width'],turn['length'],turn['height'])
    # Physical collision checks are scoped to declared 2D envelopes + assumed Z.
    collision=[]
    for name,shape,color,side in [('PCB',pcb,'#22736c','board'),('U1_conservative_Z_envelope',module_envelope,'','top'),('Battery_103450_reference',battery_shape,'#dfbc5e','battery')]+components:
        for case_name, case_shape in [('base',base),('lid',lid)]:
            overlap=volume_common(shape,case_shape)
            if overlap>1e-5:collision.append({'part':name,'case':case_name,'overlapMm3':overlap})
    for name,shape,color,side in [('PCB',pcb,'','board'),('U1_envelope',module_envelope,'','top')]+components:
        overlap=volume_common(battery_shape,shape)
        if overlap>1e-5:collision.append({'part':'battery','case':name,'overlapMm3':overlap})
    clearance_checks={name:{case_name:volume_common(shape,case_shape) for case_name,case_shape in [('base',base),('lid',lid)]}
                      for name,shape in [('battery52x36x12',reserve_shape),('connector12x8x10',connector_shape),('wireTurn5x14x12',turn_shape)]}
    for name,result in clearance_checks.items():
        if any(v>1e-5 for v in result.values()):raise ValueError('Reserved clearance collision: '+str(clearance_checks))
    clip_envelope_checks=[]
    for clip,snap in zip(clips,snap_shapes):
        inward=(wall+.1-p['snap_hook_tip_x'])*(1 if clip['side']=='left' else -1)
        released=snap.translate((inward,0,0))
        obstacles=[('base',base),('PCB',pcb),('module',module_envelope),('battery',reserve_shape),('connector',connector_shape)]
        result={name:volume_common(released,shape) for name,shape in obstacles}
        # Rigid fully-retracted leg sampled along vertical lid removal. This is
        # a geometry envelope check, not a simulation of bending or latch force.
        result['maxBaseOverlapDuringSampledLift']=max(volume_common(released.translate((0,0,float(dz))),base) for dz in range(14))
        if any(v>1e-5 for v in result.values()):raise ValueError('Retracted snap clearance collision: '+str(result))
        clip_envelope_checks.append(result)
    shapes = {'base':base,'lid':lid}
    meshes=[]; checks={}
    for name, shape in shapes.items():
        if not shape.isValid() or len(shape.Solids())!=1:raise ValueError(name+' invalid or disconnected solid')
        cq.exporters.export(shape,str(out/(name+'.step')))
        printing = shape if name=='base' else shape.rotate((0,0,0),(1,0,0),180).translate((0,H,bh+lt+.3))
        bb=printing.BoundingBox(); printing=printing.translate((-bb.xmin,-bb.ymin,-bb.zmin))
        cq.exporters.export(printing,str(out/(name+'.stl')),tolerance=.04,angularTolerance=.12)
        tm=trimesh.load_mesh(out/(name+'.stl'))
        step_back=cq.importers.importStep(str(out/(name+'.step'))).val()
        body_count=mesh_body_count(tm)
        checks[name]={'validBrep':shape.isValid(),'solidCount':len(shape.Solids()),'volumeMm3':shape.Volume(),
                       'meshWatertight':bool(tm.is_watertight),'meshWindingConsistent':bool(tm.is_winding_consistent),
                       'meshBodyCount':body_count,'printBoundsMm':tm.bounds.tolist(),
                       'stepReadbackValid':step_back.isValid(),'stepReadbackSolids':len(step_back.Solids()),
                       'stepVolumeDifferenceMm3':abs(step_back.Volume()-shape.Volume())}
        if not tm.is_watertight or not tm.is_winding_consistent or body_count!=1:raise ValueError(name+' STL invalid')
        if not step_back.isValid() or len(step_back.Solids())!=1 or abs(step_back.Volume()-shape.Volume())>1e-5:
            raise ValueError(name+' STEP roundtrip invalid')
        meshes.append({'name':name,'color':'#bdc8bb' if name=='base' else '#e5eadf','geometry':mesh(shape)})
    # A low tray is faster to print first; confirms board edge and bottom clearance only.
    fit=base.intersect(box(-1,-1,-1,W+2,H+2,bz+1.4))
    cq.exporters.export(fit,str(out/'fit_tray.stl'),tolerance=.04,angularTolerance=.12)
    fit_mesh=trimesh.load_mesh(out/'fit_tray.stl')
    if not fit_mesh.is_watertight or not fit_mesh.is_winding_consistent or mesh_body_count(fit_mesh)!=1:
        raise ValueError('fit_tray STL invalid')
    assy=cq.Assembly(name=p['revision'])
    assy.add(base,name='Base',color=cq.Color(.72,.77,.70));assy.add(lid,name='Lid',color=cq.Color(.88,.90,.85))
    assy.add(pcb,name='PCB_reference',color=cq.Color(.1,.39,.32))
    assy.add(battery_shape,name='Battery_103450_reference_NOT_FOR_PRINT',color=cq.Color(.9,.72,.25))
    for name,shape,color,side in components:assy.add(shape,name=name+'_ASSUMED_HEIGHT',color=cq.Color(.24,.25,.29))
    assy.save(str(out/'assembly_reference.step'))
    meshes.append({'name':'PCB','color':'#22736c','geometry':mesh(pcb)})
    meshes.append({'name':'Battery_103450_reference','color':'#dfbc5e','geometry':mesh(battery_shape)})
    for name,shape,color,side in components:meshes.append({'name':name,'color':color,'geometry':mesh(shape)})
    preview={'dimensions':{'width':W,'length':H,'height':bh+lt},'parts':meshes}
    (out/'meshes.json').write_text(json.dumps(preview,separators=(',',':')),encoding='utf-8')
    report={'revision':p['revision'],'units':'mm','manufacturingReady':False,'printedOrFitTested':False,
            'sourcePcbIdentity':r['sourcePcbIdentity'],'sourceHashes':r['sourceHashes'],'dimensionsMm':preview['dimensions'],
            'boardBottomZ':bz,'boardTopZ':board_top,'topInternalRoofZ':bh,'checks':checks,
            'moduleHeightInput':p.get('user_measurement'),
            'batteryBay':{'nominalBatteryMm':[50,34,10],'innerBoundsMm':[[wall,wall,p['floor']],[W-wall,divider_y,p['floor']+divider_h]],
                'minimumReservedClearanceMm':[52,36,12],'reservedClearanceOriginMm':[reserve['x'],reserve['y'],reserve['z']],
                'batteryBoundsMm':[[battery['x'],battery['y'],battery['z']],[battery['x']+50,battery['y']+34,battery['z']+10]],
                'lidGapAboveBatteryMm':bh-battery['z']-10,'dividerThicknessMm':p['battery_divider_thickness'],
                'connectorAllowanceMm':p['connector_allowance'],'wireSlot':{'centerX':slot_x,'width':slot_w,'bottomZ':slot_z},
                'wireEndClearanceMm':W-wall-battery['x']-battery['length'],'wireTurnAllowanceMm':turn,
                'wireRoute':'Orient cell short-edge leads toward +X; bend gently upward in the end allowance, route above the cell then over the open divider notch to connector bay. No lead pinching at foil seam.',
                'reservedVolumeCaseIntersectionsMm3':clearance_checks,'referenceOnly':True,'electricalConnectionDesigned':False},
            'ledWindow':{'centerMm':[led_x,led_y],'sizeMm':[led['width'],led['length']],
                'alignment':'Broad U1 USB/middle observation window; LED exact point requires user module fit check.'},
            'snaps':{'positions':clips,'widthMm':p['snap_width'],'lengthMm':p['snap_length'],
                'thicknessMm':p['snap_thickness'],'clearanceMm':p['snap_clearance'],
                'innerRootRadiusMm':p['snap_root_radius'],
                'requiredInwardDeflectionMm':wall+.1-p['snap_hook_tip_x'],
                'batterySnapIntersectionsMm3':[volume_common(battery_shape,s) for s in snap_shapes],
                'fullyRetractedLegEnvelopeChecksMm3':clip_envelope_checks,
                'sampledLiftStepMm':1,'sampledLiftRangeMm':[0,13],
                'sweepAndStressValidated':False},
            'topAllowanceMm':p['top_clearance'],
            'baseLidOverlapMm3':volume_common(base,lid),'componentEnvelopeCollisions':collision,
            'ports':ports,'powerPort':{'side':'right','yLocal':comps['J9']['y'],'width':size},
            'tieAnchors':[{'x':x,'y':y} for x,y in tie_anchors],
            'supportContact':'0.45 mm board edge patches at local y=12.827 and 30 mm; 1.4 mm along edge',
            'scope':'BRep + STL topology and case-vs-reference intersections. Module total height uses user approximate 8 mm measurement; sub-part heights, PCB thickness, solder tails and cable sizes remain assumptions.',
            'pending':['physical fit of approximate module height and assumed solder tails','USB plug and removal access','wire bundle diameter and bend radius','switch actuator reach','PETG snap fit, release force, flex fatigue and insertion sweep','battery pack actual seam/protection board/connector size','LED alignment on actual module','RF and thermal test']}
    (out/'audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    if collision or report['baseLidOverlapMm3']>1e-5:raise ValueError('Collision: see output/audit.json')
    exported={'revision':p['revision'],'date':'2026-10-20',
              'stepRoundtrip':{name:{'valid':value['stepReadbackValid'],'volumeMm3':value['volumeMm3'],
                                    'solidCount':value['stepReadbackSolids'],'volumeDifferenceMm3':value['stepVolumeDifferenceMm3']}
                               for name,value in checks.items()},
              'fitTrayWatertight':bool(fit_mesh.is_watertight),'fitTrayWindingConsistent':bool(fit_mesh.is_winding_consistent),
              'fitTrayBodyCount':mesh_body_count(fit_mesh),'userHeightInput':p['user_measurement'],
              'physicallyFitTested':False,'elasticStressTested':False}
    (out/'export_check.json').write_text(json.dumps(exported,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k in ['dimensionsMm','checks','componentEnvelopeCollisions','baseLidOverlapMm3']},ensure_ascii=False))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,default=HERE/'output');args=ap.parse_args();build(args.out)
