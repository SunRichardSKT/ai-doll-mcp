"""Inline charger housing. Millimetres; USB faces -Y.

Two printed parts: base and snap lid with an integral insulated-wire grip.
The supplied module drawing supplies an envelope, not a detailed PCB model.
"""
import hashlib
import json
from itertools import combinations
from pathlib import Path
import cadquery as cq
import trimesh

HERE = Path(__file__).resolve().parent
OUT = HERE/'output'


def box(x,y,z,w,l,h):
    return cq.Workplane('XY').box(w,l,h,centered=False).translate((x,y,z)).val()


def rounded(x,y,z,w,l,h,r):
    return (cq.Workplane('XY').rect(w,l).extrude(h).edges('|Z').fillet(r)
            .translate((x+w/2,y+l/2,z)).val())


def cyl(radius,length,point,direction=(0,0,1)):
    return cq.Solid.makeCylinder(radius,length,cq.Vector(*point),cq.Vector(*direction))


def overlap(a,b):
    return max(0.0,a.intersect(b).Volume())


def mesh(shape):
    vertices,faces=shape.tessellate(.05,.1)
    return dict(vertices=[[v.x,v.y,v.z] for v in vertices],faces=[list(f) for f in faces])


def body_count(tm):
    # Count connected vertex components without optional scipy/networkx engines.
    parent=list(range(len(tm.vertices)))
    def root(i):
        while parent[i]!=i:
            parent[i]=parent[parent[i]]
            i=parent[i]
        return i
    used=set()
    for face in tm.faces:
        a,b,c=map(int,face); used.update((a,b,c))
        parent[root(b)]=root(a); parent[root(c)]=root(a)
    return len({root(i) for i in used})


def build():
    OUT.mkdir(parents=True,exist_ok=True)
    p=json.loads((HERE/'parameters.json').read_text(encoding='utf-8'))
    c,m,u,w,sn=(p[k] for k in ('case','module','usb','wires','snap'))
    W,L,H,t=c['width'],c['length'],c['height'],c['wall']
    roof=H-c['lid']; px=(W-m['width'])/2; py=m['front_y']; pz=m['bottom_z']
    pcbtop=pz+m['pcb_thickness']; end_y=py+m['length']
    base=rounded(0,0,0,W,L,roof,c['radius'])
    base=base.cut(rounded(t,t,c['floor'],W-2*t,L-2*t,roof+1,c['radius']-t))
    seats=[(px,3.0),(px,15.4),(px+m['width']-.45,3.0),(px+m['width']-.45,15.4)]
    for xx,yy in seats:
        ax=t-.1 if xx<W/2 else xx
        aw=xx+.45-ax if xx<W/2 else W-t+.1-ax
        base=base.fuse(box(ax,yy,c['floor']-.05,aw,1.2,pz-c['floor']+.05))
    # A broad floor-backed rear stop replaces four isolated sub-millimetre posts.
    base=base.fuse(box(px-.2,end_y+.18,c['floor']-.05,
                      m['width']+.4,p['print_structure']['rear_stop_length'],pcbtop-c['floor']+.05))
    # An open-top U notch avoids a long unsupported roof in the upright base.
    base=base.cut(box((W-u['cutout_width'])/2,-.5,u['cutout_bottom'],u['cutout_width'],t+1.5,roof-u['cutout_bottom']+1))
    cy,cl,bedtop=w['clamp_y'],w['clamp_length'],w['bed_top']
    base=base.fuse(box(1.65,cy,c['floor']-.05,W-3.3,cl,bedtop-c['floor']+.05))
    bar=box(1.8,cy,w['bar_bottom'],W-3.6,cl,w['bar_thickness'])
    for xx in w['centers_x']:
        base=base.cut(cyl(w['groove_radius'],cl+.2,(xx,cy-.1,bedtop),(0,1,0)))
        bar=bar.cut(cyl(w['groove_radius'],cl+.2,(xx,cy-.1,w['bar_groove_center_z']),(0,1,0)))
        base=base.cut(cyl(w['exit_diameter']/2,t+.8,(xx,L-t-.2,bedtop),(0,1,0)))
    for xx in w['centers_x']:
        for end,dy in [(cy,1),(cy+cl,-1)]:
            for which,zc in [('base',bedtop),('bar',w['bar_groove_center_z'])]:
                flare=cq.Solid.makeCone(1.1,w['groove_radius'],1.1,cq.Vector(xx,end,zc),cq.Vector(0,dy,0))
                if which=='base': base=base.cut(flare)
                else: bar=bar.cut(flare)
    bartop=w['bar_bottom']+w['bar_thickness']
    lid=rounded(0,0,roof,W,L,c['lid'],c['radius'])
    lip_z=u['cutout_bottom']+u['cutout_height']
    lid=lid.fuse(box((W-u['cutout_width'])/2+.2,.2,lip_z,
                     u['cutout_width']-.4,t-.4,roof-lip_z+.1))
    inset=t+.2
    ring=rounded(inset,inset,roof-1,W-2*inset,L-2*inset,1.1,c['radius']-inset)
    guide=p['print_structure']['guide_wall']
    ring=ring.cut(rounded(inset+guide,inset+guide,roof-1.1,W-2*(inset+guide),L-2*(inset+guide),1.4,c['radius']-inset-guide))
    snaps=[]
    for yy in sn['centers_y']:
        for right in [False,True]:
            xx=W-t-.2 if right else -.2
            base=base.cut(box(xx,yy-sn['width']/2-.2,sn['window_bottom'],t+.4,sn['width']+.4,sn['window_top']-sn['window_bottom']))
            ring=ring.cut(box(W-4 if right else -.1,yy-sn['width']/2-.35,roof-1.2,4.1,sn['width']+.7,1.5))
            inside,thick,tip,hook=sn['inside_x'],sn['thickness'],sn['tip_x'],sn['hook_top']
            pts=[(inside+thick,roof-sn['length']),(inside,roof-sn['length']),
                 (inside,hook-1.1),(tip,hook-1),(tip,hook),(inside,hook),
                 (inside,roof+.1),(inside+thick,roof+.1)]
            shape=(cq.Workplane('XZ').polyline(pts).close().extrude(sn['width']).translate((0,yy+sn['width']/2,0)).val())
            if right: shape=shape.mirror('YZ',(W/2,0,0))
            snaps.append((shape,right))
    lid=lid.fuse(ring)
    for shape,_ in snaps: lid=lid.fuse(shape)
    # A sloped root increases the joint area without thickening the flexing tip.
    for yy in sn['centers_y']:
        for right in (False,True):
            x=sn['inside_x']+sn['thickness'];g=p['print_structure']['clip_root_gusset']
            root=(cq.Workplane('XZ').polyline([(x-.05,roof-1.6),(x+g,roof+.1),(x-.05,roof+.1)])
                  .close().extrude(sn['width']).translate((0,yy+sn['width']/2,0)).val())
            if right:root=root.mirror('YZ',(W/2,0,0))
            lid=lid.fuse(root)
    for xx,yy in seats:
        ax=inset if xx<W/2 else xx
        aw=xx+.4-ax if xx<W/2 else W-inset-ax
        length=p['print_structure']['pressure_pad_length']
        lid=lid.fuse(box(ax,yy-.3,pcbtop+.15,aw,length,roof-pcbtop-.05))
    led=p['led_window']
    lid=lid.cut(rounded((W-led['width'])/2,led['center_y']-led['length']/2,roof-.2,led['width'],led['length'],c['lid']+.4,.65))
    for xx in [6,9,12]: lid=lid.cut(box(xx,14,roof-.2,1,3,c['lid']+.4))
    # A continuous grip block prints from the lid face without a suspended bridge.
    lid=lid.fuse(box(1.8,cy,bartop-.1,W-3.6,cl,roof-bartop+.2))
    lid=lid.fuse(bar)
    # The continuous lid guide and full-width clamp replace the fragile .35 mm fins.
    # Independent insulated-wire bypass lanes avoid the snap arms. They also
    # allow two wires to be stacked vertically on one side if actual pads require it.
    ch=p['side_wire_channels']
    for xx in [ch['left_center_x'],W-ch['left_center_x']]:
        lane=box(xx-ch['width']/2,ch['front_y'],ch['bottom_z'],ch['width'],
                 ch['rear_y']-ch['front_y'],ch['top_z']-ch['bottom_z'])
        base=base.cut(lane);lid=lid.cut(lane)
    for group in p['wire_groups']:
        label=cq.Workplane('XY').text(group['label'],2.4,.35,font='Arial',kind='bold',combine=True).translate((sum(group['centers_x'])/2,29,H-.25)).val()
        lid=lid.cut(label)
    shapes=dict(base=base.clean(),lid=lid.clean())
    pcb=box(px,py,pz,m['width'],m['length'],m['pcb_thickness'])
    components=box(px+m['edge_margin'],py+2.2,pcbtop,m['width']-2*m['edge_margin'],m['length']-2.2,m['total_height']-m['pcb_thickness'])
    usb=box((W-u['shell_width'])/2,py-u['protrusion'],pz+u['shell_bottom_above_pcb_bottom'],u['shell_width'],6,u['shell_height'])
    refs=dict(PCB_reference=pcb,component_envelope=components,USB_reference=usb)
    intersections={a+'/'+b:overlap(shapes[a],shapes[b]) for a,b in combinations(shapes,2)}
    refhits={r+'/'+n:overlap(shape,shapes[n]) for r,shape in refs.items() for n in shapes}
    release=[]
    for shape,right in snaps:
        retracted=shape.translate((-.5 if right else .5,0,0))
        release.append({n:overlap(retracted,target) for n,target in [('base',base),('PCB',pcb),('components',components)]})
    assert max(list(intersections.values())+list(refhits.values()))<1e-5,(intersections,refhits)
    assert all(max(q.values())<1e-5 for q in release),release
    assert pz+m['total_height']<roof,'Module exceeds roof'
    checks={}; meshes=[]
    colors=dict(base='#a8bdb0',lid='#e3e8df')
    for name,shape in shapes.items():
        assert shape.isValid() and len(shape.Solids())==1,(name,'invalid or disconnected BREP')
        cq.exporters.export(shape,str(OUT/(name+'.step')))
        printing=shape.rotate((0,0,0),(1,0,0),180) if name=='lid' else shape
        bb=printing.BoundingBox(); printing=printing.translate((-bb.xmin,-bb.ymin,-bb.zmin))
        cq.exporters.export(printing,str(OUT/(name+'.stl')),tolerance=.03,angularTolerance=.1)
        tm=trimesh.load_mesh(OUT/(name+'.stl'))
        back=cq.importers.importStep(str(OUT/(name+'.step'))).val()
        checks[name]=dict(validBrep=shape.isValid(),solids=len(shape.Solids()),meshWatertight=bool(tm.is_watertight),meshWindingConsistent=bool(tm.is_winding_consistent),meshBodies=body_count(tm),volumeMm3=shape.Volume(),stepRoundtripVolumeError=abs(back.Volume()-shape.Volume()),stlRelativeVolumeError=abs(tm.volume-shape.Volume())/shape.Volume())
        assert tm.is_watertight and tm.is_winding_consistent and body_count(tm)==1 and tm.volume>0,checks[name]
        assert back.isValid() and checks[name]['stepRoundtripVolumeError']<1e-4,checks[name]
        meshes.append(dict(name=name,color=colors[name],geometry=mesh(shape)))
    assy=cq.Assembly(name=p['revision'])
    for name,shape in {**shapes,**refs}.items(): assy.add(shape,name=name)
    assy.save(str(OUT/'assembly_reference.step'))
    for name,shape in refs.items(): meshes.append(dict(name=name,color='#335f61' if name=='PCB_reference' else '#7b8588',geometry=mesh(shape)))
    for i,xx in enumerate(w['centers_x']):
        wire=cyl(w['nominal_insulation_diameter']/2,L-cy+7,(xx,cy,bedtop),(0,1,0))
        meshes.append(dict(name='wire_'+str(i),color='#bc5448' if i%2==0 else '#363e42',geometry=mesh(wire)))
    for i,xx in enumerate([ch['left_center_x'],W-ch['left_center_x']]):
        route=cyl(w['nominal_insulation_diameter']/2,16,(xx,3.0,ch['reference_wire_center_z']),(0,1,0))
        for part,case in shapes.items(): assert overlap(route,case)<1e-5,('side wire',i,part)
        meshes.append(dict(name='output_route_reference_'+str(i),color='#bc5448' if i==0 else '#363e42',geometry=mesh(route)))
    dims=dict(width=W,length=L,height=H)
    (OUT/'meshes.json').write_text(json.dumps(dict(dimensions=dims,parts=meshes),separators=(',',':')),encoding='utf-8')
    audit=dict(revision=p['revision'],dimensionsMm=dims,checks=checks,partIntersectionsMm3=intersections,moduleIntersectionsMm3=refhits,retractedClipChecksMm3=release,moduleToRoofMm=roof-pz-m['total_height'],boardBelowClearanceMm=pz-c['floor'],nominalWireDiameterMm=w['nominal_insulation_diameter'],clampMinimumChannelHeightMm=w['bar_groove_center_z']+w['groove_radius']-(bedtop-w['groove_radius']),physicalFitTested=False,status='offline-verified',electricalStatus=p['electrical_status'],sideWireChannels=ch,source=p['measurement_status'],scope='BREP/STL topology, STEP roundtrip and declared rigid envelopes; excludes unmeasured component placement, plug, wire grip, thermal and fatigue tests.')
    audit['printStructure']=dict(p['print_structure'],clipThicknessMm=sn['thickness'],clipWidthMm=sn['width'],clipLengthMm=sn['length'])
    (OUT/'audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    files=sorted(OUT.glob('*.stl'))+sorted(OUT.glob('*.step'))
    (HERE/'SHA256SUMS.txt').write_text(''.join(hashlib.sha256(f.read_bytes()).hexdigest()+'  output/'+f.name+'\n' for f in files),encoding='utf-8')
    print(json.dumps(dict(revision=p['revision'],dimensions=dims,checks=checks,physicalFitTested=False),indent=2))


if __name__=='__main__': build()
