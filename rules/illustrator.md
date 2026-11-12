# Illustrator 规则与关键坑

> 从 AGENTS.md 拆出（2026-11-12）。只写代码/界面里看不出的结论；完整流程见
> `docs/illustrator/svg还原分层AI.md`，脚本在 `scripts/illustrator/`。

## 关键坑（结论先行）

1. Figma 扁平 SVG 直接导入 AI "和 SVG 不一样"：先看体积分布——大体积多在 `<defs>` 里
   **pattern 包裹的 base64 图片**，AI 对 `patternContentUnits="objectBoundingBox"` 导入必失真。
2. 正解是"**矢量用 SVG、位图用同名 PDF**"：PDF 图片带精确变换矩阵；模糊阴影已被 Figma
   栅格化成图片（AI 不支持 SVG 滤镜）；渐隐蒙版已烘焙进 SMask alpha。
3. 解析 path 时 **`H`/`V` 单坐标命令会让朴素数字配对错位**——bbox 必须按命令感知解析器算。
4. 分层 = 自己重建：按区域分组（bbox 真实位置判定）、层内保持原始文档顺序（堆叠语义）。
5. **脚本必须与 AI 同盘**（跨盘 → 模态 "File not found" 阻塞，脚本永不开始）；
   启动前复制到 `%SystemDrive%\ai\jobs\` 再启动。AI 无头：`Illustrator.exe -r script.jsx`；
   图层配对**按组名**、只遍历 `layer.pageItems`（`doc.groupItems` 含嵌套组且顺序≠文档顺序）。
   启动时的两次弹窗要分清：**"File not found" 是噪音（脚本照跑，别关窗口）**；
   "是否允许运行脚本"是外部脚本安全警告，用 `suppress-external-warning.jsx` 一次性关闭（官方做法）。
   判据只看日志有没有 `done`。
6. **超出画布的对象用"画板矩形剪切组"收边**（`convert-to-ai.jsx` 的 `CANVAS_CLIP`，默认开）：
   每层内容收进裁剪组、画板矩形置组内最上层，`GroupItem.clipped = true`；不裁像素、可逆。
   两个实测坑（2026-11-02）：**SVG 顶层命名组加 `clip-path` 会让 AI 导入后组名变空**
   （按名配对全挂，moved:0）→ SVG 只留 id、收边放 JSX；
   **`executeMenuCommand("Clipping Mask")` 无头必报 BKey 错（1112237433）** → 只用 `GroupItem.clipped`。
7. **光效按类型分开处理**（2026-11-11 实测）：
   - 模糊光晕 → 用**本机无头浏览器**渲染该 filter 组（透明底 2x）；PDF 那张偏白，会把光晕洗淡；
   - 投影类 `*_d`（feOffset）→ PDF 位图**只含阴影**，矢量主体要叠回去，否则图标本体消失；
   - `mix-blend-mode`（soft-light / color-dodge，发光常用）→ SVG 里包 `id="blend-<mode>"` 组，
     导入后按组名设 `blendingMode`；渲染位图时要先剥掉，否则对着透明底混合、灯光变死白亮斑；
   - `<mask>` 是实心矩形时 → 转等效 `clipPath`，直接删会露出本来被裁掉的元素。
8. **一次 AI 会话只能开一个 SVG**：`doc.close()` 后再 `app.open` 第二个必报 `271` → 一稿一启动。
9. 带中文图层名的 `.jsx` 必须存成**带 UTF-8 BOM**，否则 ExtendScript 按 ANSI 读、组名对不上。

## FAQ 路由

- "无头跑 AI 脚本 / 弹窗 / 脚本不执行 / 怎么等它跑完" → `docs/illustrator/无头脚本自动化速查.md`
- "SVG 转 AI 后样子不对 / 没图层 / 图层乱" → `docs/illustrator/svg还原分层AI.md`（脚本在 `scripts/illustrator/`）
- "SVG 转 AI 后对象超出画布 / 要按画布收边加蒙版" → 同上（结论先行动5 + 坑⑪⑫；`convert-to-ai.jsx` 的 `CANVAS_CLIP`）
- "转 AI 后灯光/发光变白、光晕不对、混合模式丢了 / 第二个文件报 271" → 同上（结论先行动6/7 + 坑⑬~⑰）
