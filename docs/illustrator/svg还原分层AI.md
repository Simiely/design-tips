---
软件: Illustrator 2026
关联: Figma 导出的 SVG / PDF
验证日期: 2026-10-30
状态: 已验证（真实设计稿全流程跑通 + 像素级比对）
---

# SVG 还原为带分层的 AI 文件

## 场景

手里只有 Figma 导出的**扁平 SVG**（几百个元素挤在一个组、文字已转曲、无图层无分组 id），
需要还原成**可编辑、带图层**的 `.ai`。直接把 SVG 拖进 Illustrator 会遇到两个问题：
样子和 SVG 不一样、所有元素堆在一个图层里。本篇给出完整可复用流水线。

## 结论先行

1. **样子不对 ≠ 你的操作问题**。先看体积分布：本例 7MB 的 SVG 有 6.9MB 在 `<defs>` 里——
   4 张 base64 图片被包在 `<pattern patternContentUnits="objectBoundingBox">` 中（背景大图+照片位）。
   **Illustrator 对这种 pattern 的导入必然失真**（位置/比例错、丢图），这是"AI 打开和 SVG 不一样"的元凶。
2. **矢量用 SVG、位图用同名 PDF**。Figma 同名导出的 PDF 是完美搭档：页面尺寸=画布尺寸、
   `get_image_info` 给出每张图的精确变换矩阵；**模糊阴影已被 Figma 栅格化成图片**（AI 不支持 SVG 滤镜，
   这是唯一忠实还原路径）；渐隐蒙版已烘焙进图片的 SMask alpha 通道。
3. **"带分层"要自己重建**：先算每个元素的真实 bbox（**必须按 path 命令解析**，见坑①），
   按语义区域分组（背景/顶栏/面板/地图/底栏），层内保持原始文档顺序，再由脚本把组提升为真图层。
4. **AI 无头转换**：`Illustrator.exe -r script.jsx`；图层配对**按组名**、只遍历 `layer.pageItems`。

## 做法

完整流水线见 `scripts/illustrator/`（README 有逐脚本说明）：

1. `build_layered_svg.py` —— 解析原 SVG（命令感知 path bbox + transform 矩阵链）→ 按区域规则分组重建：
   pattern 矩形→内嵌 `<image preserveAspectRatio="none">`（保留旋转/裁剪）、滤镜阴影→PDF 栅格图、
   被裁剪的位图→按 PDF 矩阵从源图裁切。生成带命名分组的分层 SVG。
2. `convert-to-ai.jsx` —— Illustrator 无头打开分层 SVG → 按组名建真图层并移入（背景在最底）→
   删空壳图层 → 存 .ai → 导出 50% PNG24 核验图。
3. `verify-layers.jsx` —— dump 图层结构与 bounds，核对配对。
4. **双基准验证**：无头 Edge 渲染 SVG + AI 自身导出 PNG，PIL 做像素 diff
   （本例平均色差 ≈1/255，与"原图 vs PDF 渲染"的本底噪声同级）。

## 坑

1. **path 的 `d` 里有 `H`/`V` 单坐标命令**——"把所有数字按 x,y 配对"会整体错位，一个元素的 y 值
   会跑到 x 里，bbox 全乱。必须写按 `M/L/H/V/C/S/Q/T/A/Z`（含相对命令）解析的 bbox 计算器。
   这条曾让多版分组全错。
2. **pattern + base64 图必失真**：一律替换成 `<image>`。Python ElementTree 设 `xlink:href`
   必须用 `{http://www.w3.org/1999/xlink}href` 形式（同时保留 `href`），否则序列化出的 XML
   无命名空间声明，浏览器都打不开。
3. **ET 常量少一个字符全盘皆输**：`SVGNS='{http://www.w3.org/2000/svg}'` 丢了右花括号会
   序列化出 `<http://www.w3.org/2000/svgimage>` 这种鬼标签。
4. **被替换的元素要从父节点 remove**，否则原 pattern 矩形跟着旧容器泄漏进新结构（画面重影、
   图层里多幽灵元素）。
5. **重排绘制顺序 = 改变遮挡关系**：先 dump 原始文档顺序再定图层顺序；"本来最后画、在最上层"
   的元素（半透明面板、照片）分层后必须在更靠前的图层；层内保持原顺序。
6. **PDF 里会有"计划外"的图**（本例：一张 Midjourney 海报被裁剪到只露 64×64 头像）。
   用渲染裁剪 + 像素比对确认它对应 SVG 里哪个元素，别按名字猜。
7. **`doc.groupItems` 包含嵌套组且顺序 ≠ 文档顺序**——用索引配对会把"底部导航栏"塞进
   "照片图片"层。必须按组名配对，且只遍历 `layer.pageItems`。
8. **`-r` 偶发报一次 "File not found" 但脚本仍会执行**：多发生在旧实例未完全退出时。
   保险做法：taskkill 后轮询进程消失再启动。
9. **AI 导出的 PNG 带出血**（画板外扩几个像素），做像素比对前要先对齐裁剪。
10. **图片按需选格式**：不透明图转 JPEG（体积约 -60%），带 alpha（渐隐/阴影）保留 PNG。

## 官方参考

- Adobe Illustrator 脚本指南（ExtendScript / IllustratorSaveOptions / ExportOptionsPNG24）
- Figma 导出说明（SVG / PDF 同时导出时内容一致，仅图片承载方式不同）
