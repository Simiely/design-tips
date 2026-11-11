# -*- coding: utf-8 -*-
"""
render_glow.py - 用无头 Edge 把 SVG 里单个 filter 组渲染成透明底 PNG（2x）
比 PDF 栅格图更贴近 SVG 自身外观（PDF 的模糊光晕会偏白）。
"""
import os, subprocess, sys, copy
import xml.etree.ElementTree as ET
from PIL import Image

SVGNS = '{http://www.w3.org/2000/svg}'
XLINK = '{http://www.w3.org/1999/xlink}'
ET.register_namespace('', 'http://www.w3.org/2000/svg')
ET.register_namespace('xlink', 'http://www.w3.org/1999/xlink')

EDGE = r"C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"


def L(t):
    return t.split('}')[-1]


def _f(el, k, d=0.0):
    v = el.get(k)
    try:
        return float(v) if v not in (None, '') else d
    except ValueError:
        return d


def render_filter(svg_path, filter_id, region, out_png, scale=2, tmpdir=None):
    """region = (x, y, w, h)；输出 PNG 尺寸 = w*scale x h*scale"""
    tmpdir = tmpdir or os.path.dirname(out_png)
    os.makedirs(tmpdir, exist_ok=True)
    src = ET.parse(svg_path)
    root = src.getroot()
    defs = [c for c in list(root) if L(c.tag) == 'defs'][0]

    # 找带该 filter 的元素（保留其祖先 transform 链：本设计里均为顶层，无 transform）
    holder = []

    def find(el, chain):
        for c in list(el):
            if L(c.tag) == 'defs':
                continue
            f = c.get('filter') or ''
            if filter_id in f:
                holder.append((c, chain))
                return True
            if find(c, chain + [c]):
                return True
        return False

    find(root, [])
    if not holder:
        raise RuntimeError('filter not found: ' + filter_id)
    grp, chain = holder[0]

    attrs = {k: v for k, v in root.attrib.items()}
    newroot = ET.Element(root.tag, attrs)
    wrap = newroot
    for anc in chain:
        w = ET.SubElement(wrap, SVGNS + 'g')
        for k, v in anc.attrib.items():
            w.set(k, v)
        wrap = w
    wrap.append(copy.deepcopy(grp))
    # 关键：单独渲染时必须去掉 mix-blend-mode —— 否则会对着"透明/白底"做混合，
    # 得到的位图偏亮；混合模式改由 AI 里的 blendingMode 还原
    import re as _re
    for el2 in wrap.iter():
        st = el2.get('style')
        if st and 'mix-blend-mode' in st:
            st2 = _re.sub(r'mix-blend-mode\s*:\s*[a-z-]+;?', '', st).strip(' ;')
            if st2:
                el2.set('style', st2)
            else:
                el2.attrib.pop('style', None)
        if el2.get('mix-blend-mode'):
            el2.attrib.pop('mix-blend-mode', None)
    nd = ET.SubElement(newroot, SVGNS + 'defs')
    for c in list(defs):
        if L(c.tag) in ('linearGradient', 'radialGradient', 'filter', 'clipPath', 'mask'):
            nd.append(copy.deepcopy(c))

    tmp_svg = os.path.join(tmpdir, '_glow_%s.svg' % filter_id)
    ET.ElementTree(newroot).write(tmp_svg, encoding='utf-8', xml_declaration=True)

    x, y, w, h = region
    raw = os.path.join(tmpdir, '_glow_%s_raw.png' % filter_id)
    if os.path.exists(raw):
        os.remove(raw)
    cmd = [EDGE, '--headless', '--disable-gpu', '--hide-scrollbars',
           '--default-background-color=00000000',
           '--force-device-scale-factor=%d' % scale,
           '--window-size=2560,1440',
           '--screenshot=' + raw,
           'file:///' + tmp_svg.replace('\\', '/')]
    subprocess.run(cmd, capture_output=True, timeout=120)
    if not os.path.exists(raw):
        raise RuntimeError('screenshot failed: ' + filter_id)
    im = Image.open(raw).convert('RGBA')
    im = im.crop((int(round(x * scale)), int(round(y * scale)),
                  int(round((x + w) * scale)), int(round((y + h) * scale))))
    im.save(out_png)
    os.remove(raw)
    return out_png
