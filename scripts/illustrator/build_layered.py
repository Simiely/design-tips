# -*- coding: utf-8 -*-
"""
build_layered.py — 通用版分层 SVG 构建器（Figma 扁平 SVG + 同名 PDF → 带命名分组的分层 SVG）

相对 build_layered_svg.py（首份稿的手写参考实现）的区别：**不需要逐元素写映射**。
自动识别、自动落位，换稿只改顶部 CONFIG 的路径与区域阈值：

  1) 矢量全部取自 SVG（含转曲文字、图标、路线），层内保持原始文档顺序（堆叠语义不变）
  2) AI 无法忠实导入的内容改由位图承担，按类型自动处理：
     - <pattern> 填充矩形   -> <image>（复用 SVG 里的 base64 原图，按 pattern 的 use 变换精确落位）
     - <filter> 模糊组      -> 本机无头浏览器渲染该组（透明底 2x，见 render_glow.py）
     - <filter> 投影组      -> PDF 已栅格化的阴影位图 + 保留矢量主体（PDF 位图只含阴影）
     - <mask> 矩形 alpha 遮罩 -> 等效 clipPath（直接删 mask 会露出本来被裁掉的元素）
     - mix-blend-mode       -> 包一层 id="blend-<mode>" 的命名组，由 convert-to-ai.jsx 还原
  3) 按"变换后真实 bbox 中心点"归入语义区域，输出 <g id="区域名">，堆叠顺序 = ORDER 数组顺序

依赖：pillow、pymupdf、本机 Edge/Chrome（渲染光效）
用法：python build_layered.py 006 007        # 参数 = 不带扩展名的文件名
"""
import xml.etree.ElementTree as ET
import re, math, base64, io, os, sys, copy

from PIL import Image
import pymupdf
from render_glow import render_filter

SVGNS = '{http://www.w3.org/2000/svg}'
XLINK = '{http://www.w3.org/1999/xlink}'
ET.register_namespace('', 'http://www.w3.org/2000/svg')
ET.register_namespace('xlink', 'http://www.w3.org/1999/xlink')

# ====== CONFIG ======
# 源目录：放 <名字>.svg 与同名 <名字>.pdf；中间产物（光效位图、分层 SVG）写到 WORK
BASE = r"D:/path/to/export"
WORK = r"D:/path/to/work"
# 图层名 = 区域名，数组顺序 = 堆叠顺序（第一个在最底）
ORDER = ['背景', '顶部状态栏', '左侧信息面板', '地图区域', '底部导航栏']
# 区域判定：先用"宽高都超过整幅"判背景，再按中心点 y/x 落框。
# 换稿时必须改这里（阈值来自 2560x1440 的车载 HMI；别的版式量一下自己的分栏边界）
RULE = dict(bg_w=1500, bg_h=1300, top_y=140, bottom_y=1240, left_x=950)
# ====================


NUM = re.compile(r'-?(?:\d+\.?\d*|\.\d+)')


def L(t):
    return t.split('}')[-1]


# ---------------- geometry ----------------
def mmul(m1, m2):
    a1, b1, c1, d1, e1, f1 = m1
    a2, b2, c2, d2, e2, f2 = m2
    return [a1 * a2 + c1 * b2, b1 * a2 + d1 * b2,
            a1 * c2 + c1 * d2, b1 * c2 + d1 * d2,
            a1 * e2 + c1 * f2 + e1, b1 * e2 + d1 * f2 + f1]


def apply(m, x, y):
    return (m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5])


def parse_tf(s):
    m = [1, 0, 0, 1, 0, 0]
    if not s:
        return m
    for name, args in re.findall(r'(\w+)\(([^)]*)\)', s):
        v = [float(x) for x in re.split(r'[\s,]+', args.strip()) if x]
        if name == 'translate':
            t = [1, 0, 0, 1, v[0], v[1] if len(v) > 1 else 0]
        elif name == 'scale':
            t = [v[0], 0, 0, v[1] if len(v) > 1 else v[0], 0, 0]
        elif name == 'rotate':
            a = math.radians(v[0]); ca, sa = math.cos(a), math.sin(a)
            t = [ca, sa, -sa, ca, 0, 0]
            if len(v) == 3:
                t = mmul([1, 0, 0, 1, v[1], v[2]], mmul(t, [1, 0, 0, 1, -v[1], -v[2]]))
        elif name == 'matrix':
            t = v
        else:
            t = [1, 0, 0, 1, 0, 0]
        m = mmul(m, t)
    return m


def path_points(d):
    """命令感知的 path 取点（M/L/H/V/C/S/Q/T/A/Z 含相对命令）"""
    seq = []
    for c, n in re.findall(r'([MmLlHhVvCcSsQqTtAaZz])|(-?(?:\d+\.?\d*|\.\d+))', d):
        if c:
            seq.append((c, None))
        elif n:
            seq.append((None, float(n)))
    pts = []; cx = cy = 0.0; sx = sy = 0.0; cmd = None; i = 0; N = len(seq)

    def num():
        nonlocal i
        v = seq[i][1]; i += 1; return v

    while i < N:
        k, val = seq[i]
        if k is not None:
            cmd = k; i += 1
            if cmd in 'Zz':
                cx, cy = sx, sy
            continue
        if cmd is None:
            break
        c = cmd
        if c == 'M':
            cx, cy = num(), num(); sx, sy = cx, cy; pts.append((cx, cy)); cmd = 'L'
        elif c == 'm':
            cx += num(); cy += num(); sx, sy = cx, cy; pts.append((cx, cy)); cmd = 'l'
        elif c == 'L':
            cx, cy = num(), num(); pts.append((cx, cy))
        elif c == 'l':
            cx += num(); cy += num(); pts.append((cx, cy))
        elif c == 'H':
            cx = num(); pts.append((cx, cy))
        elif c == 'h':
            cx += num(); pts.append((cx, cy))
        elif c == 'V':
            cy = num(); pts.append((cx, cy))
        elif c == 'v':
            cy += num(); pts.append((cx, cy))
        elif c == 'C':
            x1 = num(); y1 = num(); x2 = num(); y2 = num(); cx, cy = num(), num()
            pts += [(x1, y1), (x2, y2), (cx, cy)]
        elif c == 'c':
            x1 = cx + num(); y1 = cy + num(); x2 = cx + num(); y2 = cy + num(); cx += num(); cy += num()
            pts += [(x1, y1), (x2, y2), (cx, cy)]
        elif c == 'S':
            x2 = num(); y2 = num(); cx, cy = num(), num(); pts += [(x2, y2), (cx, cy)]
        elif c == 's':
            x2 = cx + num(); y2 = cy + num(); cx += num(); cy += num(); pts += [(x2, y2), (cx, cy)]
        elif c == 'Q':
            x1 = num(); y1 = num(); cx, cy = num(), num(); pts += [(x1, y1), (cx, cy)]
        elif c == 'q':
            x1 = cx + num(); y1 = cy + num(); cx += num(); cy += num(); pts += [(x1, y1), (cx, cy)]
        elif c == 'T':
            cx, cy = num(), num(); pts.append((cx, cy))
        elif c == 't':
            cx += num(); cy += num(); pts.append((cx, cy))
        elif c == 'A':
            num(); num(); num(); num(); num(); cx, cy = num(), num(); pts.append((cx, cy))
        elif c == 'a':
            num(); num(); num(); num(); num(); cx += num(); cy += num(); pts.append((cx, cy))
        else:
            i += 1
    return pts


def _f(el, k, d=0.0):
    v = el.get(k)
    if v is None or v == '':
        return d
    try:
        return float(v)
    except ValueError:
        return d


def local_points(el):
    """元素在自身坐标系里的关键点（不含父级 transform）"""
    t = L(el.tag)
    if t == 'rect':
        x = _f(el, 'x'); y = _f(el, 'y'); w = _f(el, 'width'); h = _f(el, 'height')
        return [(x, y), (x + w, y), (x, y + h), (x + w, y + h)]
    if t == 'image':
        x = _f(el, 'x'); y = _f(el, 'y'); w = _f(el, 'width'); h = _f(el, 'height')
        return [(x, y), (x + w, y), (x, y + h), (x + w, y + h)]
    if t in ('ellipse', 'circle'):
        cx = _f(el, 'cx'); cy = _f(el, 'cy')
        if el.get('r') is not None:
            rx = ry = _f(el, 'r')
        else:
            rx = _f(el, 'rx'); ry = _f(el, 'ry', rx)
        return [(cx - rx, cy), (cx + rx, cy), (cx, cy - ry), (cx, cy + ry)]
    if t == 'line':
        return [(_f(el, 'x1'), _f(el, 'y1')), (_f(el, 'x2'), _f(el, 'y2'))]
    if t in ('polygon', 'polyline'):
        v = [float(x) for x in NUM.findall(el.get('points') or '')]
        return [(v[i], v[i + 1]) for i in range(0, len(v) - 1, 2)]
    if t == 'path':
        return path_points(el.get('d') or '')
    return []


def bbox_with(el, pm):
    """元素在画布坐标系里的 bbox [x0,x1,y0,y1]；组则递归并集（pm = 父级矩阵）"""
    m = mmul(pm, parse_tf(el.get('transform')))
    pts = []
    if L(el.tag) == 'g':
        for c in list(el):
            bb = bbox_with(c, m)
            if bb:
                pts += [(bb[0], bb[2]), (bb[1], bb[3])]
    else:
        raw = local_points(el)
        pts = [apply(m, x, y) for x, y in raw]
    if not pts:
        return None
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    return [min(xs), max(xs), min(ys), max(ys)]


# ---------------- SVG helpers ----------------
def fill_of(el):
    v = el.get('fill')
    if v:
        return v
    st = el.get('style') or ''
    m = re.search(r'fill:\s*([^;]+)', st)
    return m.group(1).strip() if m else ''


def clip_of(el):
    v = el.get('clip-path')
    if v:
        return v
    st = el.get('style') or ''
    m = re.search(r'clip-path:\s*([^;]+)', st)
    return m.group(1).strip() if m else ''


def ref_id(v):
    m = re.search(r'url\(#([^)]+)\)', v or '')
    return m.group(1) if m else None


def blend_of(el):
    """取 mix-blend-mode（Figma 会写在 style 里）：soft-light / color-dodge …"""
    for src in (el.get('style') or '', el.get('mix-blend-mode') or ''):
        m = re.search(r'mix-blend-mode\s*:\s*([a-z-]+)', src)
        if m:
            return m.group(1).strip()
    return ''


# ---------------- PDF rasters ----------------
def pdf_images(pdf_path):
    doc = pymupdf.open(pdf_path)
    page = doc[0]
    smasks = {im[0]: im[1] for im in page.get_images(full=True)}
    out = []
    for info in page.get_image_info(xrefs=True):
        xref = info['xref']
        if xref == 0:
            continue
        bb = info['bbox']
        out.append(dict(xref=xref, bbox=[bb[0], bb[1], bb[2], bb[3]],
                        w=info['width'], h=info['height'],
                        cx=(bb[0] + bb[2]) / 2.0, cy=(bb[1] + bb[3]) / 2.0))
    return doc, out, smasks


def extract_png(doc, smasks, xref, path):
    pix = pymupdf.Pixmap(doc, xref)
    sm = smasks.get(xref, 0)
    if sm:
        mask = pymupdf.Pixmap(doc, sm)
        pix = pymupdf.Pixmap(pix, mask)
    if pix.n == 3:  # RGB -> RGBA 补齐
        pix = pymupdf.Pixmap(pymupdf.csRGB, pix, False)
    pix.save(path)
    return path


def png_data_uri(path, keep_alpha=True):
    im = Image.open(path)
    buf = io.BytesIO()
    if keep_alpha:
        im.convert('RGBA').save(buf, 'PNG', optimize=True)
        return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()
    im.convert('RGB').save(buf, 'JPEG', quality=94)
    return 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode()


# ---------------- build ----------------
def build(tag):
    src = os.path.join(BASE, tag + '.svg')
    pdf = os.path.join(BASE, tag + '.pdf')
    out_svg = os.path.join(WORK, tag + '.layered.svg')
    rdir = os.path.join(WORK, 'raster', tag)
    os.makedirs(rdir, exist_ok=True)

    tree = ET.parse(src)
    root = tree.getroot()
    defs = [c for c in list(root) if L(c.tag) == 'defs'][0]

    patterns = {c.get('id'): c for c in list(defs) if L(c.tag) == 'pattern'}
    filters = {c.get('id'): c for c in list(defs) if L(c.tag) == 'filter'}
    clipdefs = {c.get('id'): c for c in list(defs) if L(c.tag) == 'clipPath'}
    masks = {el.get('id'): el for el in root.iter() if L(el.tag) == 'mask' and el.get('id')}
    images = {}
    for c in list(defs):
        if L(c.tag) == 'image':
            images[c.get('id')] = c

    def is_canvas_clip(cid):
        cp = clipdefs.get(cid)
        if not cp:
            return False
        kids = list(cp)
        return (len(kids) == 1 and L(kids[0].tag) == 'rect'
                and _f(kids[0], 'width') >= 2555 and _f(kids[0], 'height') >= 1435)

    # 去掉最外层"画布裁剪"（clip0/clip1 = 2560x1440）：交给 JSX 的 CANVAS_CLIP 做，
    # 避免 AI 导入时命名组带 clip-path 导致组名变空（design-tips 坑⑪）
    stripped = [0]

    def strip_canvas_clip(el):
        if L(el.tag) == 'g':
            cid = ref_id(clip_of(el))
            if cid and is_canvas_clip(cid):
                el.attrib.pop('clip-path', None)
                st = el.get('style')
                if st and 'clip-path' in st:
                    el.set('style', re.sub(r'clip-path:[^;]+;?', '', st))
                stripped[0] += 1
        for c in list(el):
            strip_canvas_clip(c)

    strip_canvas_clip(root)
    print('  stripped canvas clips:', stripped[0])

    # ---- 1. PDF 位图：排除三张 pattern 原图，其余按最近中心点分配给各 filter ----
    doc, infos, smasks = pdf_images(pdf)
    pat_sizes = {(2561, 1442), (1068, 1335), (545, 1346)}
    cand = [i for i in infos if (i['w'], i['h']) not in pat_sizes]
    filter_units = []      # (fid, cx, cy, group_el, parent, matrix)

    def collect_filters(el, pm):
        if L(el.tag) == 'defs':
            return
        m = mmul(pm, parse_tf(el.get('transform')))
        f = el.get('filter')
        if f and ref_id(f) in filters:
            fe = filters[ref_id(f)]
            fx, fy = _f(fe, 'x'), _f(fe, 'y')
            fw, fh = _f(fe, 'width'), _f(fe, 'height')
            drop = any(L(x.tag) == 'feOffset' for x in fe.iter())
            filter_units.append(dict(fid=ref_id(f), cx=fx + fw / 2, cy=fy + fh / 2,
                                     group=el, matrix=m, idx=len(filter_units),
                                     dropshadow=drop))
            return
        for c in list(el):
            collect_filters(c, m)

    for c in list(root):
        collect_filters(c, [1, 0, 0, 1, 0, 0])

    pairs = []
    for fi, fu in enumerate(filter_units):
        for ii, im in enumerate(cand):
            d = math.hypot(fu['cx'] - im['cx'], fu['cy'] - im['cy'])
            pairs.append((d, fi, ii))
    pairs.sort()
    assign_f, assign_i = {}, set()
    for d, fi, ii in pairs:
        if fi in assign_f or ii in assign_i:
            continue
        if d > 40:
            continue
        assign_f[fi] = (ii, d)
        assign_i.add(ii)
    missing = [filter_units[i]['fid'] for i in range(len(filter_units)) if i not in assign_f]
    if missing:
        raise RuntimeError('%s: 有 filter 未匹配到 PDF 位图: %s' % (tag, missing))

    for fi, (ii, d) in assign_f.items():
        fu = filter_units[fi]
        fe = filters[fu['fid']]
        if fu['dropshadow']:
            # 投影型（feOffset）：PDF 位图恰好只含阴影，矢量主体另外叠加
            im = cand[ii]
            p = os.path.join(rdir, 'shadow_%02d_x%d.png' % (fi, im['xref']))
            extract_png(doc, smasks, im['xref'], p)
            im['png'] = p
            im['uri'] = png_data_uri(p, keep_alpha=True)
            fu['place'] = im['bbox']
            fu['uri'] = im['uri']
            print('  filter#%d DROP-SHADOW <- pdf x%d bbox=%s' % (fi, im['xref'], [round(v, 1) for v in im['bbox']]))
        else:
            # 模糊型（feGaussianBlur）：用本机浏览器渲染该 filter 组（透明底 2x），
            # 与 SVG 自身外观一致；PDF 栅格图偏白，会把光晕洗淡
            fx, fy = _f(fe, 'x'), _f(fe, 'y')
            fw, fh = _f(fe, 'width'), _f(fe, 'height')
            p = os.path.join(rdir, 'glow_%02d.png' % fi)
            render_filter(src, fu['fid'], (fx, fy, fw, fh), p, scale=2, tmpdir=rdir)
            fu['place'] = [fx, fy, fx + fw, fy + fh]
            fu['uri'] = png_data_uri(p, keep_alpha=True)
            print('  filter#%d GLOW <- browser 2x bbox=%s' % (fi, [round(v, 1) for v in fu['place']]))

    # ---- 2. 遍历：把内容拆成"单位"（叶子 / 带 clip / opacity / blend 的组） ----
    def region_of(bb):
        if not bb:
            return ORDER[3]
        w = bb[1] - bb[0]; h = bb[3] - bb[2]
        cx = (bb[0] + bb[1]) / 2; cy = (bb[2] + bb[3]) / 2
        if w > RULE['bg_w'] and h > RULE['bg_h']:
            return ORDER[0]
        if cy < RULE['top_y']:
            return ORDER[1]
        if cy > RULE['bottom_y']:
            return ORDER[4]
        if cx < RULE['left_x']:
            return ORDER[2]
        return ORDER[3]

    units = []   # dict(region, kind='vector'|'bitmap', el=..., ...)

    def emit(el, m, kind='vector', extra=None):
        bb = bbox_with(el, m)
        u = dict(region=region_of(bb), kind=kind, el=el, bbox=bb)
        if extra:
            u.update(extra)
        units.append(u)

    def walk(parent, el, pm):
        t = L(el.tag)
        m = mmul(pm, parse_tf(el.get('transform')))
        if t in ('defs', 'mask', 'clippath'):
            return
        # pattern 填充 -> 位图单位
        if t == 'rect':
            pid = ref_id(fill_of(el))
            if pid in patterns:
                emit(el, pm, 'bitmap', dict(pattern=pid))
                return
        # filter 组 -> PDF 位图单位
        if t == 'g' and el.get('filter') and ref_id(el.get('filter')) in filters:
            emit(el, pm, 'bitmap', dict(filter=ref_id(el.get('filter')), blend=blend_of(el)))
            return
        # 带 clip / opacity / blend 的组：整体作为一个单位（保住裁剪与混合语义）
        keep = ((clip_of(el) != '') or (el.get('opacity') is not None)
                or (el.get('mask') is not None) or (blend_of(el) != ''))
        if t == 'g' and keep:
            emit(el, pm, 'vector', dict(blend=blend_of(el)))
            return
        if t == 'g':
            for c in list(el):
                walk(el, c, m)
            return
        emit(el, pm, 'vector', dict(blend=blend_of(el)))

    for c in list(root):
        if L(c.tag) == 'defs':
            continue
        walk(root, c, [1, 0, 0, 1, 0, 0])

    # ---- 3. 组装 ----
    def mk(tag_, attrib):
        e = ET.Element(SVGNS + tag_, {k: str(v) for k, v in attrib.items() if v is not None})
        return e

    def img_el(uri, x, y, w, h, extra=None):
        a = {'x': round(x, 4), 'y': round(y, 4), 'width': round(w, 4), 'height': round(h, 4),
             'preserveAspectRatio': 'none'}
        e = mk('image', a)
        e.set('href', uri)
        e.set(XLINK + 'href', uri)
        if extra:
            for k, v in extra.items():
                e.set(k, v)
        return e

    def pattern_image(pid, rect_el):
        pat = patterns[pid]
        use = [c for c in list(pat) if L(c.tag) == 'use'][0]
        href = use.get('href') or use.get(XLINK + 'href')
        iid = href[1:]
        im = images[iid]
        a, b, c, d, e_, f_ = parse_tf(use.get('transform'))
        if abs(b) > 1e-9 or abs(c) > 1e-9:
            raise RuntimeError('pattern %s 的 use 含旋转，需扩展实现' % pid)
        iw = _f(im, 'width'); ih = _f(im, 'height')
        bx = _f(rect_el, 'x'); by = _f(rect_el, 'y')
        bw = _f(rect_el, 'width'); bh = _f(rect_el, 'height')
        x = bx + e_ * bw; y = by + f_ * bh
        w = a * iw * bw; h = d * ih * bh
        uri = im.get('href') or im.get(XLINK + 'href')
        extra = {}
        tr = rect_el.get('transform')
        if tr:
            extra['transform'] = tr
        cp = clip_of(rect_el)
        if cp:
            extra['clip-path'] = cp
        return img_el(uri, x, y, w, h, extra), iid

    fmap = {fu['fid']: fu for fu in filter_units}

    # mask（alpha 矩形遮罩）-> 等效 clipPath：masks 里是实心 rect，硬边裁切
    mask_clip_id = {}
    extra_defs = []

    def mask_to_clip(mid):
        if mid in mask_clip_id:
            return mask_clip_id[mid]
        me = masks.get(mid)
        if me is None:
            return None
        cid = 'maskclip_' + mid
        cp = mk('clipPath', {'id': cid})
        for c in list(me):
            cp.append(copy.deepcopy(c))
        extra_defs.append(cp)
        mask_clip_id[mid] = cid
        return cid

    def wrap_blend(elements, mode):
        """mix-blend-mode 要在 AI 里还原：包一层带名字的组，JSX 按组名设 blendingMode"""
        if not mode:
            return elements
        g = ET.Element(SVGNS + 'g')
        g.set('id', 'blend-' + mode)
        g.set('style', 'mix-blend-mode:%s' % mode)   # 浏览器预览用；AI 侧按组名设 blendingMode
        for e in elements:
            # 避免混合模式被套两次：子元素上原有的 mix-blend-mode 去掉
            st = e.get('style')
            if st and 'mix-blend-mode' in st:
                st2 = re.sub(r'mix-blend-mode\s*:\s*[a-z-]+;?', '', st).strip(' ;')
                if st2:
                    e.set('style', st2)
                else:
                    e.attrib.pop('style', None)
            if e.get('mix-blend-mode'):
                e.attrib.pop('mix-blend-mode', None)
            g.append(e)
        return [g]

    buckets = {n: [] for n in ORDER}
    for u in units:
        if u['kind'] == 'bitmap':
            if 'pattern' in u:
                e, iid = pattern_image(u['pattern'], u['el'])
                buckets[u['region']].append(e)
            else:
                fu = fmap[u['filter']]
                bb = fu['place']
                im_e = img_el(fu['uri'], bb[0], bb[1], bb[2] - bb[0], bb[3] - bb[1])
                group = [im_e]
                # 投影型 filter（feOffset）：PDF 位图只含阴影，矢量主体要留在上面，
                # 否则图标本体丢失（006 的绿色充电标记实测）
                if fu['dropshadow']:
                    g = copy.deepcopy(u['el'])
                    g.attrib.pop('filter', None)
                    group.append(g)
                buckets[u['region']].extend(wrap_blend(group, u.get('blend')))
        else:
            e = u['el']
            mid = ref_id(e.get('mask') or '')
            if mid:
                cid = mask_to_clip(mid)
                e.attrib.pop('mask', None)
                if cid:
                    e.set('clip-path', 'url(#%s)' % cid)
            buckets[u['region']].extend(wrap_blend([e], u.get('blend')))

    newroot = ET.Element(root.tag, {k: v for k, v in root.attrib.items()})
    for n in ORDER:
        g = ET.Element(SVGNS + 'g'); g.set('id', n)
        for e in buckets[n]:
            g.append(e)
        newroot.append(g)

    # ---- 3b. 递归替换残留的 pattern 填充矩形（可能在保留的 clip 组里，如头像） ----
    replaced = [0]

    def replace_pass(parent):
        for child in list(parent):
            replace_pass(child)
            if L(child.tag) == 'rect':
                pid = ref_id(fill_of(child))
                if pid in patterns:
                    new_el, iid = pattern_image(pid, child)
                    idx = list(parent).index(child)
                    parent.remove(child)
                    parent.insert(idx, new_el)
                    replaced[0] += 1

    replace_pass(newroot)
    print('  pattern rect replaced:', replaced[0])

    # ---- 4. defs 保留被引用的（gradient / clipPath） + 自建 clipPath ----
    body = ET.tostring(newroot, encoding='unicode')
    newdefs = ET.Element(SVGNS + 'defs')
    keep_tags = ('linearGradient', 'radialGradient', 'clipPath')
    for c in list(defs):
        if L(c.tag) not in keep_tags:
            continue
        cid = c.get('id')
        if not cid:
            continue
        if ('#' + cid) in body:
            newdefs.append(c)
    for c in extra_defs:
        newdefs.append(c)
    newroot.append(newdefs)

    ET.ElementTree(newroot).write(out_svg, encoding='utf-8', xml_declaration=True)

    cnt = {n: len(buckets[n]) for n in ORDER}
    print('  区域元素数:', cnt)
    print('  output:', out_svg, round(os.path.getsize(out_svg) / 1048576.0, 2), 'MB')
    return out_svg, cnt


if __name__ == '__main__':
    for tag in (sys.argv[1:] or ['006', '007']):
        print('=' * 20, tag)
        build(tag)
