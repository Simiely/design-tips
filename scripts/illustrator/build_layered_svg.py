# -*- coding: utf-8 -*-
# build_layered_svg.py — 分层 SVG 构建器（参考实现，2026-10-30 真实设计稿验证）
# 配套文档：docs/illustrator/svg还原分层AI.md
#
# 换设计稿需改的都在 CONFIG 区：源/输出路径、区域框(region_of 的坐标与名称)、
# 位图替换映射(BITMAP/替换分支)、PDF 抽图目录。
# 要点：path 的 d 含 H/V 单坐标命令，朴素数字配对必错位 —— bbox 一律走命令感知的
# path_points()；分组判定用"变换后真实位置"；层内保持原始文档顺序（堆叠语义）。
# 依赖：pillow、pymupdf（PDF 抽图）

# -*- coding: utf-8 -*-
# Build v4: region-based grouping per user's boxes
import xml.etree.ElementTree as ET, re, math, base64, io, os
from PIL import Image

SVGNS='{http://www.w3.org/2000/svg}'; XLINK='{http://www.w3.org/1999/xlink}'
ET.register_namespace('','http://www.w3.org/2000/svg'); ET.register_namespace('xlink','http://www.w3.org/1999/xlink')
IMGDIR="D:/workbuddy/2026-10-30-10-34-27/pdfimg/"
NUM=re.compile(r'-?(?:\d+\.?\d*|\.\d+)')

# ---------- geometry helpers ----------
def mmul(m1,m2):
    a1,b1,c1,d1,e1,f1=m1; a2,b2,c2,d2,e2,f2=m2
    return [a1*a2+c1*b2, b1*a2+d1*b2, a1*c2+c1*d2, b1*c2+d1*d2, a1*e2+c1*f2+e1, b1*e2+d1*f2+f1]
def apply(m,x,y): return (m[0]*x+m[2]*y+m[4], m[1]*x+m[3]*y+m[5])
def parse_tf(s):
    m=[1,0,0,1,0,0]
    if not s: return m
    for name,args in re.findall(r'(\w+)\(([^)]*)\)', s):
        v=[float(x) for x in re.split(r'[\s,]+',args.strip()) if x]
        if name=='translate': t=[1,0,0,1,v[0], v[1] if len(v)>1 else 0]
        elif name=='scale': t=[v[0],0,0, v[1] if len(v)>1 else v[0],0,0]
        elif name=='rotate':
            a=math.radians(v[0]); ca,sa=math.cos(a),math.sin(a)
            t=[ca,sa,-sa,ca,0,0]
            if len(v)==3: t=mmul([1,0,0,1,v[1],v[2]], mmul(t,[1,0,0,1,-v[1],-v[2]]))
        elif name=='matrix': t=v
        else: t=[1,0,0,1,0,0]
        m=mmul(m,t)
    return m

def path_points(d):
    """Command-aware path point extraction (conservative bbox: endpoints + control pts)."""
    seq=[]
    for c,n in re.findall(r'([MmLlHhVvCcSsQqTtAaZz])|(-?(?:\d+\.?\d*|\.\d+))', d):
        if c: seq.append((c,None))
        elif n: seq.append((None,float(n)))
    pts=[]; cx=cy=0.0; sx=sy=0.0; cmd=None; i=0; N=len(seq)
    def num():
        nonlocal i
        v=seq[i][1]; i+=1; return v
    while i<N:
        k,val=seq[i]
        if k is not None:
            cmd=k; i+=1
            if cmd in 'Zz': cx,cy=sx,sy
            continue
        if cmd is None: break
        c=cmd
        if c=='M': cx,cy=num(),num(); sx,sy=cx,cy; pts.append((cx,cy)); cmd='L'
        elif c=='m': cx+=num(); cy+=num(); sx,sy=cx,cy; pts.append((cx,cy)); cmd='l'
        elif c=='L': cx,cy=num(),num(); pts.append((cx,cy))
        elif c=='l': cx+=num(); cy+=num(); pts.append((cx,cy))
        elif c=='H': cx=num(); pts.append((cx,cy))
        elif c=='h': cx+=num(); pts.append((cx,cy))
        elif c=='V': cy=num(); pts.append((cx,cy))
        elif c=='v': cy+=num(); pts.append((cx,cy))
        elif c=='C':
            x1=num();y1=num();x2=num();y2=num();cx,cy=num(),num()
            pts+=[(x1,y1),(x2,y2),(cx,cy)]
        elif c=='c':
            x1=cx+num();y1=cy+num();x2=cx+num();y2=cy+num();cx+=num();cy+=num()
            pts+=[(x1,y1),(x2,y2),(cx,cy)]
        elif c=='S': x2=num();y2=num();cx,cy=num(),num(); pts+=[(x2,y2),(cx,cy)]
        elif c=='s': x2=cx+num();y2=cy+num();cx+=num();cy+=num(); pts+=[(x2,y2),(cx,cy)]
        elif c=='Q': x1=num();y1=num();cx,cy=num(),num(); pts+=[(x1,y1),(cx,cy)]
        elif c=='q': x1=cx+num();y1=cy+num();cx+=num();cy+=num(); pts+=[(x1,y1),(cx,cy)]
        elif c=='T': cx,cy=num(),num(); pts.append((cx,cy))
        elif c=='t': cx+=num();cy+=num(); pts.append((cx,cy))
        elif c=='A': num();num();num();num();num(); cx,cy=num(),num(); pts.append((cx,cy))
        elif c=='a': num();num();num();num();num(); cx+=num();cy+=num(); pts.append((cx,cy))
        else: i+=1
    return pts

def elem_points(el):
    t=L(el.tag)
    if t=='rect':
        x=float(el.get('x',0)); y=float(el.get('y',0)); w=float(el.get('width',0)); h=float(el.get('height',0))
        return [(x,y),(x+w,y),(x,y+h),(x+w,y+h)]
    if t in ('ellipse','circle'):
        cx=float(el.get('cx',0)); cy=float(el.get('cy',0))
        r=float(el.get('r',el.get('rx',0))); ry=float(el.get('ry',r))
        return [(cx-r,cy),(cx+r,cy),(cx,cy-ry),(cx,cy+ry)]
    if t=='line':
        return [(float(el.get('x1',0)),float(el.get('y1',0))),(float(el.get('x2',0)),float(el.get('y2',0)))]
    if t in ('polygon','polyline'):
        v=[float(x) for x in NUM.findall(el.get('points') or '')]
        return [(v[i],v[i+1]) for i in range(0,len(v)-1,2)]
    return path_points(el.get('d') or '')

def bbox_of(el,m):
    raw=elem_points(el)
    pts=[apply(m,x,y) for x,y in raw] if m!=[1,0,0,1,0,0] else raw
    xs=[p[0] for p in pts]; ys=[p[1] for p in pts]
    if not xs: return None
    return [min(xs),max(xs),min(ys),max(ys)]

# ---------- load & number elements ----------
tree=ET.parse("D:/download/Group 2147229404.svg"); root=tree.getroot()
def L(t): return t.split('}')[-1]
collected=[]; idx=[0]
def walk(parent, el, pm):
    t=L(el.tag)
    if t in ('defs','mask','clippath','clipPath'): return
    my=idx[0]; idx[0]+=1
    m=mmul(pm, parse_tf(el.get('transform')))
    collected.append((my,parent,el,m,t))
    if t=='g':
        for c in list(el): walk(el,c,m)
for ch in list(root): walk(root,ch,[1,0,0,1,0,0])
defs_el=[c for c in list(root) if L(c.tag)=='defs'][0]

# ---------- region classification ----------
BITMAP={2,19,62,83,85,87}
DROP={63,84,86}
def region_of(my,el,m):
    bb=bbox_of(el,m)
    if bb is None: return '地图区域'
    w=bb[1]-bb[0]; h=bb[3]-bb[2]; cx=(bb[0]+bb[1])/2; cy=(bb[2]+bb[3])/2
    if w>1500 and h>1300: return '背景'
    if cy<140: return '顶部状态栏'
    if cy>1240: return '底部导航栏'
    if cx<950: return '左侧信息面板'
    return '地图区域'
for my,parent,el,m,t in collected:
    if my in DROP: parent.remove(el)
assign={}
table=[]
for my,parent,el,m,t in collected:
    if t=='g' or my in DROP: continue
    r=region_of(my,el,m)
    assign[my]=(r, parent, el, my in BITMAP)
    table.append((my,r,my in BITMAP,el))
cnt={}
for my,r,b,el in table: cnt[r]=cnt.get(r,0)+1
print("region counts:", cnt)
for my,r,b,el in table:
    if b: print(f"  bitmap #{my} -> {r}")

# ---------- images ----------
def data_uri(png_path, allow_jpeg=True):
    im=Image.open(png_path)
    a=im.getchannel('A') if im.mode=='RGBA' else None
    opaque = a is None or a.getextrema()==(255,255)
    buf=io.BytesIO()
    if opaque and allow_jpeg: im.convert('RGB').save(buf,'JPEG',quality=92); mime='image/jpeg'
    else: im.save(buf,'PNG'); mime='image/png'
    return f"data:{mime};base64,"+base64.b64encode(buf.getvalue()).decode()
src=Image.open(IMGDIR+"rgba36.png"); W,H=src.size
px0,py0,pw,ph=1018.9318,1219.7405,189.6776,237.1615
box=((1128-px0)/pw*W,(1328-py0)/ph*H,(1192-px0)/pw*W,(1392-py0)/ph*H)
avatar=src.crop(box); av_opaque=avatar.getchannel('A').getextrema()==(255,255)
b2=io.BytesIO()
if av_opaque: avatar.convert('RGB').save(b2,'JPEG',quality=92); avatar_uri="data:image/jpeg;base64,"+base64.b64encode(b2.getvalue()).decode()
else: avatar.save(b2,'PNG'); avatar_uri="data:image/png;base64,"+base64.b64encode(b2.getvalue()).decode()
uri_bg=data_uri(IMGDIR+"rgba50.png"); uri_ph2=data_uri(IMGDIR+"rgba12.png",False)
uri_ph3=data_uri(IMGDIR+"rgba8.png"); uri_sh1=data_uri(IMGDIR+"rgba32.png",False); uri_sh2=data_uri(IMGDIR+"rgba18.png",False)

# ---------- build new tree ----------
def mk(tag,attrib):
    e=ET.Element(SVGNS+tag)
    for k,v in attrib.items():
        if v is None: continue
        e.set(k,v)
    return e
def img(href,x,y,w,h,extra=None):
    a={'x':str(x),'y':str(y),'width':str(w),'height':str(h),'preserveAspectRatio':'none','href':href,XLINK+'href':href}
    if extra: a.update(extra)
    return mk('image',a)

ORDER=['背景','顶部状态栏','左侧信息面板','地图区域','底部导航栏']
newroot=ET.Element(root.tag,root.attrib)
clip19=None
tops={n:ET.Element(SVGNS+'g') for n in ORDER}
for n in ORDER: tops[n].set('id',n)

for my,parent,el,m,t in collected:
    if my in DROP: continue
    if my==2:
        tops['背景'].append(img(uri_bg,-3.73828,-3.11328,2566.79,1445.16)); continue
    if my==19:
        cid="clipAvatar19"; cp=mk('clipPath',{'id':cid}); pth=mk('path',{'d':el.get('d')})
        if el.get('clip-rule'): pth.set('clip-rule',el.get('clip-rule'))
        cp.append(pth); clip19=cp
        parent.remove(el)
        tops['底部导航栏'].append(img(avatar_uri,1128,1328,64,64,{'clip-path':f'url(#{cid})'})); continue
    if my==62:   # filter0 shadow raster (map area)
        parent.remove(el)
        tops['地图区域'].append(img(uri_sh1,1162.2891,768.2539,409.7109,267.6758)); continue
    if my in (83,85,87):
        parent.remove(el)
        if my==83: im=img(uri_ph2,977.734,819.662,239.342,288.294,{'transform':'rotate(-20.0512 977.734 819.662)'})
        elif my==85: im=img(uri_sh2,1123.9883,692.3047,90.457,147.7891)
        else: im=img(uri_ph3,el.get('x'),el.get('y'),el.get('width'),el.get('height'),{'transform':el.get('transform')})
        tops['地图区域'].append(im); continue
    if t=='g': continue
    parent.remove(el)
    tops[assign[my][0]].append(el)

# nest vector/bitmap subgroups for 地图区域 and 底部导航栏 (order: shadow -> vector -> photos / vector -> bitmap)
def split_and_nest(top, vector_tag='矢量'):
    kids=list(top)
    vectors=[k for k in kids if k.tag!=SVGNS+'image']
    images=[k for k in kids if k.tag==SVGNS+'image']
    for k in kids: top.remove(k)
    if images:
        gv=ET.SubElement(top,'g'); gv.set('id',vector_tag)
        for k in vectors: gv.append(k)
        gi=ET.SubElement(top,'g'); gi.set('id','位图')
        for k in images: gi.append(k)
    else:
        for k in kids: top.append(k)

# 地图区域: need 3-way split (shadow1 behind road). Reorder children by original index:
# we appended in original order: shadow1(62) ... vector(78,81,82) ... photos(83,85,87)
# Implement custom nesting for 地图区域:
map_top=tops['地图区域']; mk_ids=[]
# tag children by tracing: rebuild using assign info is complex; instead re-split by document order groups:
kids=list(map_top)
for k in kids: map_top.remove(k)
# classify children: first image = shadow1; then vectors until first of (photo2/shadow2/photo3 images after vectors)
shadow1=[kids[0]] if kids and kids[0].tag==SVGNS+'image' else []
rest=kids[1:] if shadow1 else kids
# photos are the images appearing AFTER the road vector in rest
photo_idx=[i for i,k in enumerate(rest) if k.tag==SVGNS+'image']
vecs=[k for i,k in enumerate(rest) if k.tag!=SVGNS+'image']
photos=[k for i,k in enumerate(rest) if k.tag==SVGNS+'image']
g1=ET.SubElement(map_top,'g'); g1.set('id','位图-阴影')
for k in shadow1: g1.append(k)
g2=ET.SubElement(map_top,'g'); g2.set('id','矢量')
for k in vecs: g2.append(k)
g3=ET.SubElement(map_top,'g'); g3.set('id','位图-照片')
for k in photos: g3.append(k)

# 底部导航栏: vector first, avatar bitmap after
split_and_nest(tops['底部导航栏'])

for n in ORDER: newroot.append(tops[n])
newdefs=mk('defs',{})
for ch in list(defs_el):
    t=L(ch.tag)
    if t in ('linearGradient','radialGradient','clipPath'):
        if t=='clipPath' and (ch.get('id') or '').startswith('clip0'): continue
        newdefs.append(ch)
if clip19 is not None: newdefs.append(clip19)
newroot.append(newdefs)
out="D:/download/Group 2147229404.layered.svg"
ET.ElementTree(newroot).write(out,encoding='utf-8',xml_declaration=True)
print("v4 size:",os.path.getsize(out))
s=open(out,encoding='utf-8').read()
print("images:", s.count('<image'), "| pattern refs:", s.count('url(#pattern'))
# print top-level + nested structure
import xml.etree.ElementTree as ET2
rr=ET2.parse(out).getroot()
def show(el,ind=""):
    t=el.tag.split('}')[-1]
    if ind=="" or t=='g':
        print(ind, t, el.get('id') or '', len(list(el)))
        if ind=="": 
            for c in el: show(c, ind+"  ")
for c in rr:
    if c.tag.endswith('g'):
        print("TOP", c.get('id'), len(list(c)))
        for cc in c:
            print("   -", cc.tag.split('}')[-1], cc.get('id') or '', len(list(cc)) if cc.tag.endswith('g') else '')
