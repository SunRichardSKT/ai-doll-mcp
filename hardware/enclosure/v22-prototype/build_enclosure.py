"""Build P02 snap enclosure with isolated 103450 cell bay. Does not edit PCB data.

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


def y_prism(points, y, width):
    """Extrude an X/Z polygon in +Y, centered on y."""
    return cq.Workplane('XZ').polyline(points).close().extrude(width).translate((0, y+width/2, 0)).val()


def slot_y(x, y, z, dx, dy, dz, radius):
    return cq.Workplane('XZ').rect(dx, dz).extrude(dy).edges('|Y').fillet(radius).translate((x+dx/2,y+dy,z+dz/2)).val()


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
    # A fixed, nonconductive wall separates the cell from board/solder joints.
    partition=box(wall-.1,p['partition_y'],p['floor']-.1,W-2*wall+.2,
                  p['partition_thickness'],p['partition_top_z']-p['floor']+.1)
    wire_slot=slot_y(p['wire_slot_x'],p['partition_y']-.1,p['wire_slot_bottom_z'],
                     p['wire_slot_width'],p['partition_thickness']+.2,p['wire_slot_height'],1.5)
    wire_slot=wire_slot.fuse(box(p['wire_slot_x'],p['partition_y']-.1,
                           p['wire_slot_bottom_z']+p['wire_slot_height']/2,p['wire_slot_width'],
                           p['partition_thickness']+.2,p['partition_top_z']+1))
    base=base.fuse(partition.cut(wire_slot))
    # Four externally accessible windows receive the lid's flexible hooks.
    snap_windows=[]
    for y in p['snap_y']:
        for side in ['left','right']:
            wx=-.1 if side=='left' else W-wall-.1
            wz=p['snap_bottom_z']-.1
            wd=p['snap_hook_top_z']-wz+p['snap_window_clearance']
            wy=y-p['snap_width']/2-p['snap_window_clearance']
            base=base.cut(box(wx,wy,wz,wall+.2,p['snap_width']+2*p['snap_window_clearance'],wd))
            snap_windows.append({'side':side,'centerY':y,'bottomZ':wz,'topZ':wz+wd})
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
    # Right-side power exit avoids routing the J9 lead across the cell pouch.
    power_y=p['power_port_y'];size=p['power_port_width'];zc=p['power_port_bottom']+size/2
    cut=cq.Solid.makeCylinder(size/2,wall+1,cq.Vector(W-wall-.5,power_y,zc),cq.Vector(1,0,0))
    base=base.cut(cut.fuse(box(W-wall-.5,power_y-size/2,zc,wall+1,size,bh-zc+1)))

    lid = rounded(0, 0, bh, W, H, lt, p['corner_radius'])
    # Locating lip: 0.4 mm radial assembly gap, independent of elastic hooks.
    gap = p['lid_location_clearance']; inset = wall+gap
    ring = rounded(inset, inset, bh-1.6, W-2*inset, H-2*inset, 1.8, p['corner_radius']-inset)
    inner = rounded(inset+1, inset+1, bh-1.8, W-2*(inset+1), H-2*(inset+1), 2.2, .9)
    ring = ring.cut(inner)
    lid = lid.fuse(ring)
    for port in ports:
        sz = port['width']; z = p['sensor_port_bottom']+sz
        xx = .2 if port['side']=='left' else W-wall+.2
        lid = lid.fuse(box(xx, port['yWorld']-sz/2+gap, z, wall-.4, sz-2*gap, bh-z+.1))
    z = p['power_port_bottom']+p['power_port_width']
    lid = lid.fuse(box(W-wall+.2,power_y-size/2+gap,z,wall-.4,size-2*gap,bh-z+.1))
    snap_arms=[]
    for y in p['snap_y']:
        ax=wall+gap;th=p['snap_arm_thickness'];bottom=p['snap_bottom_z']
        left=box(ax,y-p['snap_width']/2,bottom,th,p['snap_width'],bh-bottom+.1)
        hook=y_prism([(ax+.1,bottom),(p['snap_hook_outside_x'],p['snap_hook_ramp_z']),
                      (p['snap_hook_outside_x'],p['snap_hook_top_z']),(ax+.1,p['snap_hook_top_z'])],
                     y,p['snap_width'])
        # Concave root round: added material outside a radius-0.8 cylinder.
        root=box(ax+th,y-p['snap_width']/2,bh-.8,.8,p['snap_width'],.9)
        root=root.cut(cq.Solid.makeCylinder(.8,p['snap_width']+.2,
                     cq.Vector(ax+th+.8,y-p['snap_width']/2-.1,bh-.8),cq.Vector(0,1,0)))
        left=left.fuse(hook).fuse(root)
        right=left.mirror('YZ',(W/2,0,0))
        lid=lid.fuse(left).fuse(right)
        snap_arms.extend([('left',y,left),('right',y,right)])
    # Retainers hover 0.25 mm over the PCB edge, not over ICs or solder joints.
    stop_z = board_top+p['board_retention_gap']
    for local_y in p['support_y']:
        for xx in [ox-.3, ox+w-p['support_overlap']]:
            lid = lid.fuse(box(xx, oy+local_y-1.5, stop_z, p['support_overlap']+.3, 3, bh-stop_z+.1))
    # Entire switch body exposed from above; actual actuator reach remains a fit check.
    sw = comps['SW1']; swx, swy = ox+sw['x'], oy+sw['y']
    lid = lid.cut(rounded(swx-5.75, swy-3.5, bh-2, 11.5, 7, lt+4, 1))
    ledx,ledy=p['led_window_center'];ledw,ledh=p['led_window_size']
    lid=lid.cut(rounded(ledx-ledw/2,ledy-ledh/2,bh-2,ledw,ledh,lt+4,p['led_window_radius']))
    # Engraved text preserves a flat outside print face. No metallic antenna label.
    label = cq.Workplane('XY').text('AI DOLL', 4, .6, combine=True).translate((W/2, 20, bh+lt-.3)).val()
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
    battery=box(*p['battery_reference_origin'],*p['battery_nominal'])
    bay_clearance=box(*p['battery_bay_origin'],*p['battery_bay_clearance'])
    connector_clearance=box(*p['connector_allowance_origin'],*p['connector_allowance'])
    battery_wire_end=box(*p['battery_wire_end_origin'],*p['battery_wire_end_allowance'])
    # Physical collision checks are scoped to declared 2D envelopes + assumed Z.
    collision=[]
    refs=[('PCB',pcb,'#22736c','board')]+components
    for name,shape,color,side in refs+[('Battery_103450_reference',battery,'#e9ba45','reference'),
                                      ('Battery_bay_clearance',bay_clearance,'#e9ba45','clearance'),
                                      ('Battery_wire_end_clearance',battery_wire_end,'#e9ba45','clearance'),
                                      ('Connector_allowance',connector_clearance,'#e9ba45','clearance')]:
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
        reread=cq.importers.importStep(str(out/(name+'.step'))).val()
        checks[name]={'validBrep':shape.isValid(),'solidCount':len(shape.Solids()),'volumeMm3':shape.Volume(),
                       'stepReadbackValid':reread.isValid(),'stepReadbackSolidCount':len(reread.Solids()),
                       'stepReadbackVolumeMm3':reread.Volume(),
                       'meshWatertight':bool(tm.is_watertight),'meshWindingConsistent':bool(tm.is_winding_consistent),
                       'meshBodyCount':body_count,'printBoundsMm':tm.bounds.tolist()}
        if not tm.is_watertight or not tm.is_winding_consistent or body_count!=1:raise ValueError(name+' STL invalid')
        if not reread.isValid() or len(reread.Solids())!=1 or abs(reread.Volume()-shape.Volume())>1e-4:
            raise ValueError(name+' STEP readback invalid')
        meshes.append({'name':name,'color':'#bdc8bb' if name=='base' else '#e5eadf','geometry':mesh(shape)})
    # A low tray is faster to print first; confirms board edge and bottom clearance only.
    fit=base.intersect(box(-1,-1,-1,W+2,H+2,bz+1.4))
    cq.exporters.export(fit,str(out/'fit_tray.stl'),tolerance=.04,angularTolerance=.12)
    assy=cq.Assembly(name=p['revision'])
    assy.add(base,name='Base',color=cq.Color(.72,.77,.70));assy.add(lid,name='Lid',color=cq.Color(.88,.90,.85))
    assy.add(pcb,name='PCB_reference',color=cq.Color(.1,.39,.32))
    assy.add(battery,name='Battery_103450_reference',color=cq.Color(.92,.73,.27))
    for name,shape,color,side in components:assy.add(shape,name=name+'_ASSUMED_HEIGHT',color=cq.Color(.24,.25,.29))
    assy.save(str(out/'assembly_reference.step'))
    meshes.append({'name':'PCB','color':'#22736c','geometry':mesh(pcb)})
    meshes.append({'name':'Battery_103450_reference','color':'#e9ba45','geometry':mesh(battery)})
    for name,shape,color,side in components:meshes.append({'name':name,'color':color,'geometry':mesh(shape)})
    preview={'dimensions':{'width':W,'length':H,'height':bh+lt},'parts':meshes}
    (out/'meshes.json').write_text(json.dumps(preview,separators=(',',':')),encoding='utf-8')
    battery_reference_collisions=[]
    for name,shape,color,side in refs:
        overlap=volume_common(shape,battery)
        if overlap>1e-5:battery_reference_collisions.append({'part':name,'overlapMm3':overlap})
    snap_checks=[]
    for side,y,arm in snap_arms:
        dx=p['snap_release_deflection']*(1 if side=='left' else -1)
        # Rigid lower-arm sweep only bounds free release space, not flexure mechanics.
        lower=arm.intersect(box(-1,y-4,-1,W+2,8,bh-1.8))
        blocked=[]
        for fraction in [.25,.5,.75,1]:
            moved=lower.translate((dx*fraction,0,0))
            for name,shape,color,ref_side in refs+[('Battery_103450_reference',battery,'','')]:
                if volume_common(moved,shape)>1e-5:blocked.append({'fraction':fraction,'part':name})
            if volume_common(moved,base)>1e-5:blocked.append({'fraction':fraction,'part':'base'})
        snap_checks.append({'side':side,'centerY':y,'boundedReleaseTravelMm':abs(dx),
                            'blockedPositions':blocked,'elasticStrainVerified':False})
    min_power_gap=min(abs(port['yWorld']-power_y)-port['width']/2-size/2
                      for port in ports if port['side']=='right')
    report={'revision':p['revision'],'date':'2026-10-20','units':'mm','manufacturingReady':False,'printedOrFitTested':False,
            'sourcePcbSha256':r['pcbSemanticSha256'],'dimensionsMm':preview['dimensions'],
            'boardBottomZ':bz,'boardTopZ':board_top,'topInternalRoofZ':bh,'checks':checks,
            'baseLidOverlapMm3':volume_common(base,lid),'componentEnvelopeCollisions':collision,
            'batteryReferenceCollisions':battery_reference_collisions,
            'batteryBay':{'origin':p['battery_bay_origin'],'clearanceMm':p['battery_bay_clearance'],
                          'nominalBatteryMm':p['battery_nominal'],'referenceOrigin':p['battery_reference_origin'],
                          'wireEndSide':p['battery_wire_end_side'],
                          'wireEndClearanceMm':round(W-wall-(p['battery_reference_origin'][0]+p['battery_nominal'][0]),3),
                          'wireEndAllowance':{'origin':p['battery_wire_end_origin'],'sizeMm':p['battery_wire_end_allowance']},
                          'wireRoute':'Factory lead end toward +X; loose bend in end allowance, then above the cell to the top-open partition notch. No lead pinched by lid/lip or flex arms.',
                          'partitionY':p['partition_y'],'partitionThicknessMm':p['partition_thickness'],
                          'partitionTopZ':p['partition_top_z'],'wireSlotMm':[p['wire_slot_width'],p['wire_slot_height']],
                          'wireSlotTopOpen':True,'batteryHeldByLidCompression':False},
            'connectorAllowance':{'origin':p['connector_allowance_origin'],'sizeMm':p['connector_allowance']},
            'ledWindow':{'centerMm':p['led_window_center'],'openingMm':p['led_window_size'],
                         'positionStatus':'approximate SuperMini GPIO8 blue LED; verify actual module before final print'},
            'snapLid':{'count':4,'armThicknessMm':p['snap_arm_thickness'],
                       'armLengthMm':bh-p['snap_bottom_z'],'rootRadiusMm':.8,
                       'locationClearanceMm':gap,'windows':snap_windows,'releaseSpaceChecks':snap_checks,
                       'installationSweepVerified':False,'fatigueOrRetentionForceVerified':False},
            'powerExit':{'side':'right','centerY':power_y,'widthMm':size,
                         'minimumWallToAdjacentSensorNotchMm':min_power_gap},
            'ports':ports,'supportContact':'0.6 mm board edge patches at local y=4 and 31 mm',
            'scope':'BRep + STEP readback + STL topology, static case/PCB/component/cell/bay/connector intersections and bounded free lower-arm release travel. No elastic snap or lid insertion sweep analysis.',
            'pending':['actual battery pack edge seal and connector fit','lid insertion and elastic retention/release test',
                       'assembled heights and USB removal access','wire bundle bend radius and strain relief',
                       'actual LED position and side-wall print strength','RF and thermal test',
                       'SuperMini hand-solder footprint adaptation']}
    (out/'audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    if collision or battery_reference_collisions or report['baseLidOverlapMm3']>1e-5:
        raise ValueError('Collision: see output/audit.json')
    if any(s['blockedPositions'] for s in snap_checks):raise ValueError('Snap release envelope blocked')
    print(json.dumps({k:v for k,v in report.items() if k in ['dimensionsMm','checks','componentEnvelopeCollisions','baseLidOverlapMm3']},ensure_ascii=False))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,default=HERE/'output');args=ap.parse_args();build(args.out)
