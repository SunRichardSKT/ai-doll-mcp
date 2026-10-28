"""Three printable parts, unchanged original XY footprint, battery below PCB.

The removable insulating tray is necessary to shield the pouch from 5 mm pins.
No electrical or PCB manufacturing files are changed. All dimensions are mm.
"""
import hashlib
import json
from pathlib import Path

import cadquery as cq
import trimesh

HERE = Path(__file__).resolve().parent
OUT = HERE / 'output'


def box(x, y, z, dx, dy, dz):
    return cq.Workplane('XY').box(dx, dy, dz, centered=False).translate((x, y, z)).val()


def rounded(x, y, z, w, h, depth, radius):
    return (cq.Workplane('XY').rect(w, h).extrude(depth).edges('|Z').fillet(radius)
            .translate((x+w/2, y+h/2, z)).val())


def common(a, b):
    return a.intersect(b).Volume()


def well_taper(cx, cy, z, width, length, top_z, top_width, top_length, offset_y):
    """Planar tapered opening; lower outline stays clear of the module."""
    return (cq.Workplane('XY').workplane(offset=z).center(cx, cy).rect(width, length)
            .workplane(offset=top_z-z).center(0,offset_y).rect(top_width, top_length).loft(ruled=True).val())


def mesh(shape):
    vertices, faces = shape.tessellate(.07, .12)
    return dict(vertices=[[v.x, v.y, v.z] for v in vertices], faces=[list(f) for f in faces])


def connected(tm):
    parent = list(range(len(tm.vertices)))
    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    used = set()
    for face in tm.faces:
        a, b, c = map(int, face)
        used.update((a, b, c))
        parent[root(b)] = root(a)
        parent[root(c)] = root(a)
    return len({root(i) for i in used})


def declared(data):
    return box(*(data[k] for k in ('x', 'y', 'z', 'width', 'length', 'height')))


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    p = json.loads((HERE/'parameters.json').read_text(encoding='utf-8'))
    r = json.loads((HERE/'pcb_reference.json').read_text(encoding='utf-8'))
    W, H = p['outer_width'], p['outer_length']
    wall, floor, lt = p['wall'], p['floor'], p['lid_thickness']
    ox, oy = p['board_offset']
    bw, bl, bt = r['width'], r['length'], r['thickness']
    tray_z = floor+p['battery_clear_height']
    tray_top = tray_z+p['tray_thickness']
    tip_z = tray_top+p['pin_to_tray_gap']
    bz = tip_z+p['bottom_pin_length']
    top_z = bz+bt
    switch_top = tip_z+p['pin_tip_to_switch_top']
    module_top = top_z+p['module_height_above_pcb']
    roof = max(switch_top, module_top)+p['roof_clearance']
    total_height = roof+lt
    comps = {c['ref']: c for c in r['components']}
    base = rounded(0, 0, 0, W, H, roof, p['corner_radius'])
    base = base.cut(rounded(wall, wall, floor, W-2*wall, H-2*wall,
                            roof+1, p['corner_radius']-wall))

    # Side rails support the loose tray without entering the full cell clearance.
    for y in [5.0, 25.0, 45.0]:
        base = base.fuse(box(wall-.15, y, floor-.1, 2.7, 5, tray_z-floor+.1))
        base = base.fuse(box(W-wall-2.55, y, floor-.1, 2.7, 5, tray_z-floor+.1))
    tray = rounded(wall+.35, wall+.35, tray_z, W-2*(wall+.35),
                   H-2*(wall+.35), p['tray_thickness'], 1.25)
    # Open notch is outside the PCB outline: insulated cell leads rise here.
    wr = p['wire_riser']
    tray = tray.cut(box(wr['x'], wr['y'], tray_z-.1, wr['width'],
                        H-wr['y'], p['tray_thickness']+.2))
    # The PCB carrier lifts out with the tray. Fixed inward PCB ledges would
    # obstruct insertion of the 34 mm cell through the upper compartment.
    for sy in p['support_y']:
        yy = oy+sy-p['support_length']/2
        for xx, dx in [(wall+.35, ox+p['support_overlap']-wall-.35),
                       (ox+bw-p['support_overlap'], W-wall-.35-(ox+bw-p['support_overlap']))]:
            post = box(xx, yy, tray_z, dx, p['support_length'], bz-tray_z)
            tray = tray.fuse(post)
    stops = []
    for yy, xs in [(oy-1.15, [ox, ox+bw/2]), (oy+bl+.35, [ox, ox+bw-1.8])]:
        for xx in xs:
            stops.append((xx, yy, 1.8, .8))
    for xx in [ox-1.15, ox+bw+.35]:
        stops.append((xx, oy+29.5, .8, 3.0))
    for xx, yy, dx, dy in stops:
        # Stops join the removable tray and transfer load to the shell rails.
        if xx < W/2:
            web_x, web_dx = wall+.35, xx+dx-wall-.35
        else:
            web_x, web_dx = xx, W-wall-.35-xx
        tray = tray.fuse(box(web_x, yy, tray_z, web_dx, dy, top_z-tray_z))

    ports = []
    port_bottom = top_z+.3
    def wire_cut(side, y, size):
        xx = -.3 if side == 'left' else W-wall-.3
        zc = port_bottom+size/2
        cut = cq.Solid.makeCylinder(size/2, wall+.6, cq.Vector(xx,y,zc), cq.Vector(1,0,0))
        return cut.fuse(box(xx,y-size/2,zc,wall+.6,size,roof-zc+1))
    for port in r['wirePorts']:
        yy, size = oy+port['y'], p['sensor_port_width']
        base = base.cut(wire_cut(port['side'], yy, size))
        ports.append(dict(**port, yWorld=yy, width=size, zBottom=port_bottom))
    power_y = oy+comps['J9']['y']
    base = base.cut(wire_cut('right', power_y, p['power_port_width']))

    # Clips on FRONT/BACK walls keep eight close-spaced side wire ports intact.
    clips = [(x, side) for side in ('front', 'back') for x in p['snap_x']]
    window_z = roof-12.2
    for xx, side in clips:
        yy = -.2 if side == 'front' else H-wall-.2
        base = base.cut(box(xx-p['snap_width']/2-.35, yy, window_z,
                            p['snap_width']+.7, wall+.4, 5.8))
    lid = rounded(0, 0, roof, W, H, lt, p['corner_radius'])
    inset = wall+p['lid_guide_clearance']
    ring_radius=p['corner_radius']-inset
    ring = rounded(inset,inset,roof-1.6,W-2*inset,H-2*inset,1.8,ring_radius)
    ring = ring.cut(rounded(inset+1,inset+1,roof-1.8,W-2*(inset+1),H-2*(inset+1),2.2,ring_radius-1))
    for xx, side in clips:
        yy = wall if side == 'front' else H-wall-3
        ring = ring.cut(box(xx-p['snap_width']/2-.6,yy,roof-2,p['snap_width']+1.2,3,3))
    lid = lid.fuse(ring)
    for port in ports+[dict(side='right',yWorld=power_y,width=p['power_port_width'])]:
        sz, yy = port['width'], port['yWorld']
        xx = .2 if port['side']=='left' else W-wall+.2
        zz = port_bottom+sz
        lid = lid.fuse(box(xx,yy-sz/2+.25,zz,wall-.4,sz-.5,roof-zz+.1))
    for sy in p['support_y']:
        yy = oy+sy-p['support_length']/2
        for xx, end in [(wall+.25,ox+p['support_overlap']),
                        (ox+bw-p['support_overlap'], W-wall-.25)]:
            zz = top_z+p['board_retention_gap']
            lid = lid.fuse(box(xx,yy,zz,end-xx,p['support_length'],roof-zz+.1))
    # Four small fingers retain only the loose insulating tray; no cell pressure.
    for xx in [3.5, W-3.5]:
        for yy in [4.0, H-4.0]:
            zz = tray_top+.25
            lid = lid.fuse(box(xx-.55,yy-.7,zz,1.1,1.4,roof-zz+.1))
    snap_shapes = []
    for xx, side in clips:
        inside = wall+p['snap_clearance']
        thick = p['snap_thickness']
        hook = window_z+5.8-p['snap_vertical_clearance']
        pts = [(inside+thick,roof-p['snap_length']), (inside,roof-p['snap_length']),
               (p['snap_tip_inset'],hook-1.5),(p['snap_tip_inset'],hook),
               (inside,hook),(inside,roof+.15),(inside+thick,roof+.15)]
        snap = (cq.Workplane('XZ').polyline(pts).close().extrude(p['snap_width'])
                .translate((0,p['snap_width']/2,0)).val()
                .rotate((0,0,0),(0,0,1),90).translate((xx,0,0)))
        if side=='back':
            snap = snap.rotate((xx,H/2,0),(xx,H/2,1),180)
        snap_shapes.append(snap)
        lid = lid.fuse(snap)

    # Lower the floor without moving the PCB. The mouth flares above the module,
    # so the finger has room while the narrow lower cup retains module clearance.
    sw = comps['SW1']; well = p['switch_well']
    swx, swy = ox+sw['x'], oy+sw['y']
    wx, wy = swx+well['offset_x']-well['outer_width']/2, swy-well['outer_length']/2
    well_floor_top = switch_top-well['actuator_above_well_floor']
    well_bottom = well_floor_top-well['floor_thickness']
    cx,cy=swx+well['offset_x'],swy
    mouth_cy=cy+well['mouth_offset_y']
    flare_z=switch_top+well['flare_bottom_above_actuator']
    outer_stem=box(wx,wy,well_bottom,well['outer_width'],well['outer_length'],flare_z-well_bottom+.1)
    outer_flare=well_taper(cx,cy,flare_z,well['outer_width'],well['outer_length'],
                            roof+.2,well['mouth_width'],well['mouth_length'],well['mouth_offset_y'])
    # Cut through the original lid before attaching the hollow well; the top
    # opening stays inside the old base rim for a lid-only replacement.
    lid=lid.cut(box(cx-well['mouth_width']/2,mouth_cy-well['mouth_length']/2,well_bottom-.1,
                    well['mouth_width'],well['mouth_length'],total_height-well_bottom+1))
    collar=box(cx-well['mouth_width']/2-.15,mouth_cy-well['mouth_length']/2-.15,
                roof+.1,well['mouth_width']+.3,well['mouth_length']+.3,lt-.1)
    cup=outer_stem.fuse(outer_flare).fuse(collar)
    inner_width=well['outer_width']-2*well['wall']
    inner_length=well['outer_length']-2*well['wall']
    inner_stem=box(wx+well['wall'],wy+well['wall'],well_floor_top,
                   inner_width,inner_length,flare_z-well_floor_top+.1)
    mouth_width=well['mouth_width']-2*well['wall']
    mouth_length=well['mouth_length']-2*well['wall']
    inner_flare=well_taper(cx,cy,flare_z,inner_width,inner_length,
                            roof+.2,mouth_width,mouth_length,well['mouth_offset_y'])
    mouth=box(cx-mouth_width/2,mouth_cy-mouth_length/2,roof+.1,
              mouth_width,mouth_length,total_height-roof+1)
    cup=cup.cut(inner_stem.fuse(inner_flare).fuse(mouth))
    cup = cup.cut(rounded(swx-well['hole_width']/2,swy-well['hole_length']/2,well_bottom-.2,
                          well['hole_width'],well['hole_length'],total_height-well_bottom+1,.4))
    lid = lid.fuse(cup)
    lid=lid.cut(mouth)
    root_edges = []
    for edge in lid.Edges():
        bb=edge.BoundingBox()
        if bb.ylen<1e-5 and bb.zlen<1e-5 and abs(bb.zmin-roof)<1e-5 and abs(bb.xlen-p['snap_width'])<1e-5:
            if any(abs(bb.ymin-yy)<1e-5 for yy in [wall+p['snap_clearance']+p['snap_thickness'],
                                                    H-wall-p['snap_clearance']-p['snap_thickness']]):
                root_edges.append(edge)
    assert len(root_edges)==4, f'Snap root edges: {len(root_edges)}'
    lid = lid.fillet(p['snap_root_radius'], root_edges)
    led = p['led_window']
    lx = ox+comps['U1']['x']+led['offset_x']
    ly = oy+comps['U1']['y']+led['offset_y']
    lid = lid.cut(rounded(lx-led['width']/2,ly-led['length']/2,roof-2,
                          led['width'],led['length'],lt+4,1.2))
    label = cq.Workplane('XY').text('AI DOLL',3.0,.5,combine=True).translate((W/2,21,roof+lt-.25)).val()
    lid = lid.cut(label)
    base, tray, lid = base.clean(), tray.clean(), lid.clean()
    pcb = cq.Workplane('XY').polyline(r['outline']).close().extrude(bt).translate((ox,oy,bz)).val()
    components = []
    for c in r['components']:
        if c['ref'].startswith(('J','TP')) or c['ref']=='U1':
            continue
        bb=c['bbox']; xx,yy=ox+bb['minX'],oy+bb['minY']
        height = 2.8 if c['side']=='bottom' else (switch_top-top_z if c['ref']=='SW1' else 2.6)
        zz = bz-height if c['side']=='bottom' else top_z
        components.append((c['ref'],box(xx,yy,zz,bb['maxX']-bb['minX'],bb['maxY']-bb['minY'],height),'#7c8076'))
    # Module envelope follows the retained previous approx. 8 mm measurement.
    u=comps['U1']; ux,uy=ox+u['x']-9,oy+u['y']-11.25
    module = box(ux,uy,top_z,18,22.5,p['module_height_above_pcb'])
    stand = p['module_height_above_pcb']-4.8
    for xx in [ox+u['x']-7.62,ox+u['x']+7.62]:
        components.append(('U1_socket_'+str(xx),box(xx-1.27,oy+u['y']-10.16,top_z,2.54,20.32,stand),'#444b50'))
    components.append(('U1_module_PCB',box(ux,uy,top_z+stand,18,22.5,1.6),'#273e4d'))
    components.append(('USB_symbolic',box(ox+u['x']-4.5,uy-.5,top_z+stand+1.6,9,6.5,3.2),'#adb6b9'))
    components.append(('Antenna_symbolic',box(ox+u['x']-3,uy+19.7,top_z+stand+1.6,6,2,1.2),'#b98270'))
    for tail in r['solderTailReference']:
        shape=cq.Solid.makeCylinder(tail['radius'],p['bottom_pin_length'],
                                    cq.Vector(ox+tail['x'],oy+tail['y'],tip_z))
        components.append((tail['name']+'_5mm_tail',shape,'#b6b2a2'))
    battery, reserve = declared(p['battery']), declared(p['battery_reserved'])
    connector, wire = declared(p['connector_allowance']), declared(p['wire_riser'])
    shapes={'base':base,'tray':tray,'lid':lid}
    refs=[('PCB',pcb),('module_envelope',module),('Battery_103450_reference',battery)]+[(n,s) for n,s,c in components]
    collisions=[]
    for name,shape in refs:
        for part,case in shapes.items():
            overlap=common(shape,case)
            if overlap>1e-5:collisions.append(dict(reference=name,part=part,mm3=overlap))
    clearances={}
    for name,shape in [('battery_36x52x12',reserve),('PH2_allowance_12x8x10',connector),('wire_riser',wire)]:
        clearances[name]={part:common(shape,case) for part,case in shapes.items()}
    for name,shape in [('PCB',pcb),('module',module)]+[(n,s) for n,s,c in components]:
        for label,region in [('battery',reserve),('connector',connector),('wire',wire)]:
            overlap=common(shape,region)
            if overlap>1e-5:collisions.append(dict(reference=label,part=name,mm3=overlap))
    assembly_overlaps={a+'/'+b:common(shapes[a],shapes[b]) for a,b in [('base','tray'),('base','lid'),('tray','lid')]}
    snap_checks=[]
    for (xx,side),snap in zip(clips,snap_shapes):
        delta=wall+.1-p['snap_tip_inset']
        released=snap.translate((0,delta if side=='front' else -delta,0))
        targets=[('base',base),('tray',tray),('battery_clearance',reserve),('PCB',pcb),('module',module)]
        checked={name:common(released,s) for name,s in targets}
        checked['base_sampled_lift_0_to_13mm']=max(common(released.translate((0,0,d)),base) for d in range(14))
        snap_checks.append(checked)
    issues=collisions or any(v>1e-5 for v in assembly_overlaps.values()) or any(v>1e-5 for c in clearances.values() for v in c.values()) or any(v>1e-5 for c in snap_checks for v in c.values())
    checks={}; meshes=[]
    for name,shape in shapes.items():
        assert shape.isValid() and len(shape.Solids())==1, f'{name} disconnected or invalid'
        cq.exporters.export(shape,str(OUT/(name+'.step')))
        printing=shape.rotate((0,0,0),(1,0,0),180) if name=='lid' else shape
        bb=printing.BoundingBox()
        printing=printing.translate((-bb.xmin,-bb.ymin,-bb.zmin))
        cq.exporters.export(printing,str(OUT/(name+'.stl')),tolerance=.04,angularTolerance=.12)
        tm=trimesh.load_mesh(OUT/(name+'.stl'))
        back=cq.importers.importStep(str(OUT/(name+'.step'))).val()
        checks[name]=dict(validBrep=shape.isValid(),solids=len(shape.Solids()),meshWatertight=bool(tm.is_watertight),
                          meshWindingConsistent=bool(tm.is_winding_consistent),meshBodies=connected(tm),
                          volumeMm3=shape.Volume(),stepRoundtripVolumeError=abs(back.Volume()-shape.Volume()),
                          stlRelativeVolumeError=abs(tm.volume-shape.Volume())/shape.Volume())
        assert tm.is_watertight and tm.is_winding_consistent and connected(tm)==1 and tm.volume>0, checks[name]
        assert back.isValid() and len(back.Solids())==1 and checks[name]['stepRoundtripVolumeError']<1e-5, name
        meshes.append(dict(name=name,color={'base':'#bdc8bb','tray':'#c7af8a','lid':'#e5eadf'}[name],geometry=mesh(shape)))
    assy=cq.Assembly(name=p['revision'])
    for name,shape in list(shapes.items())+refs:
        assy.add(shape,name=name)
    assy.save(str(OUT/'assembly_reference.step'))
    meshes += [dict(name='PCB',color='#22736c',geometry=mesh(pcb)),
               dict(name='Battery_103450_reference',color='#dfbc5e',geometry=mesh(battery))]
    meshes += [dict(name=n,color=c,geometry=mesh(s)) for n,s,c in components]
    dimensions=dict(width=W,length=H,height=total_height)
    (OUT/'meshes.json').write_text(json.dumps(dict(dimensions=dimensions,parts=meshes),separators=(',',':')),encoding='utf-8')
    report=dict(revision=p['revision'],units='mm',dimensionsMm=dimensions,physicalFitTested=False,
                sourcePcbIdentity=r['sourcePcbIdentity'],sourceHashes=r['sourceHashes'],userMeasurement=p['user_measurement'],
                heightStackMm=dict(floorTop=floor,batteryReferenceTop=p['battery']['z']+10,batteryReserveTop=tray_z,
                                   trayBottom=tray_z,trayTop=tray_top,pinTip=tip_z,pcbBottom=bz,pcbTop=top_z,
                                   switchActuatorTip=switch_top,moduleTop=module_top,roofBottom=roof,lidTop=total_height),
                printedParts=['base','tray','lid'],footprintUnchangedFromNoBattery=p['original_no_battery_footprint_mm']==[W,H],
                checks=checks,componentEnvelopeCollisions=collisions,partIntersectionsMm3=assembly_overlaps,
                reservedClearancesMm3=clearances,snapRetractedChecksMm3=snap_checks,
                battery=dict(nominalMm=[34,50,10],clearanceMm=[36,52,12],orientation='long axis +Y, leads +Y then upward through tray notch',
                             wireExitEndGapMm=H-wall-p['battery']['y']-50,cellToTrayGapMm=tray_z-p['battery']['z']-10,
                             cellToLowestPinMm=tip_z-p['battery']['z']-10,wireBendTested=False),
                tray=dict(thicknessMm=p['tray_thickness'],bottomPinClearanceMm=tip_z-tray_top,
                          removable=True,pressureOnBattery=False),
                switchWell=dict(centerMm=[swx,swy],floorTopMm=well_floor_top,actuatorTipMm=switch_top,
                                actuatorAboveLocalFloorMm=switch_top-well_floor_top,
                                actuatorBelowOuterTopMm=total_height-switch_top,
                                openingMm=[well['hole_width'],well['hole_length']],
                                fingerMouthMm=[mouth_width,mouth_length],flareBottomMm=flare_z,
                                moduleClearanceAtFlareMm=flare_z-module_top,
                                reachPhysicallyTested=False,description='Recessed finger well, no claim actuator protrudes above the whole roof'),
                ledWindow=dict(centerMm=[lx,ly],sizeMm=[led['width'],led['length']],physicalAlignmentTested=False),
                snaps=dict(count=4,walls=['front','back'],deflectionMm=wall+.1-p['snap_tip_inset'],
                           hookEngagementMm=wall-p['snap_tip_inset'],verticalPlayMm=p['snap_vertical_clearance'],
                           guideClearancePerSideMm=p['lid_guide_clearance'],elasticTested=False),
                connectorAllowance=p['connector_allowance'],wireRiser=p['wire_riser'],
                scope='Exported topology, declared rigid clearances and sampled clip envelope. Not stress, continuous insertion, thermal or RF validation.',
                pending=['actual pin and switch measurements','battery seam and upward lead bend','connector and wire route above PCB',
                         'switch lever finger access','PETG snap fit and fatigue','RF with battery below antenna','temperature and drop test'])
    (OUT/'audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    assert not issues, f'Geometry collision: {collisions}; parts={assembly_overlaps}; clearances={clearances}; snaps={snap_checks}'
    files=['base.step','base.stl','tray.step','tray.stl','lid.step','lid.stl','assembly_reference.step']
    (OUT/'validation.json').write_text(json.dumps(dict(passed=True,checks=checks,physicalFitTested=False,
        files={n:hashlib.sha256((OUT/n).read_bytes()).hexdigest() for n in files}),indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(dimensions=dimensions,heightStack=report['heightStackMm'],checks=checks,collisions=collisions),indent=2))


if __name__=='__main__':
    build()
