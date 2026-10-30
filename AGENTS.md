# AGENTS.md — 给 AI / 未来的你：路由 + 关键坑速记

> 本仓库整理**平面设计软件**实战技巧，按软件分区：`docs/<软件>/`（跨软件通用在 `docs/common/`）。
> **只收录实际用过并验证过的做法**。回答相关问题前，先按下面的软件路由定位文档，再读该文档。

## 软件路由

- Figma → `docs/figma/`
- Illustrator → `docs/illustrator/`（配套脚本 `scripts/illustrator/`）
- 跨软件通用 → `docs/common/`

## Illustrator 关键坑（结论先行）

1. Figma 扁平 SVG 直接导入 AI "和 SVG 不一样"：先看体积分布——大体积多在 `<defs>` 里
   **pattern 包裹的 base64 图片**，AI 对 `patternContentUnits="objectBoundingBox"` 导入必失真。
2. 正解是"**矢量用 SVG、位图用同名 PDF**"：PDF 图片带精确变换矩阵；模糊阴影已被 Figma
   栅格化成图片（AI 不支持 SVG 滤镜）；渐隐蒙版已烘焙进 SMask alpha。
3. 解析 path 时 **`H`/`V` 单坐标命令会让朴素数字配对错位**——bbox 必须按命令感知解析器算。
4. 分层 = 自己重建：按区域分组（bbox 真实位置判定）、层内保持原始文档顺序（堆叠语义）。
5. **脚本必须与 AI 同盘**（跨盘 → 模态 "File not found" 阻塞，脚本永不开始）；
   启动前复制到 `%SystemDrive%\ai\jobs\` 再启动。AI 无头：`Illustrator.exe -r script.jsx`；图层配对**按组名**、只遍历 `layer.pageItems`
   （`doc.groupItems` 含嵌套组且顺序≠文档顺序）。启动时的两次弹窗要分清：
   **"File not found" 是噪音（脚本照跑，别关窗口）**；"是否允许运行脚本"是外部脚本安全警告，
   用 `suppress-external-warning.jsx` 一次性关闭（官方做法）。判据只看日志有没有 `done`。
6. 完整流程与脚本：`docs/illustrator/svg还原分层AI.md` + `scripts/illustrator/`。

## Figma 关键坑（结论先行）

1. 想"**编辑模式下点文字跳到文档内某块**"→ 用**文字链接（Add links to text）**。
   流程：双击选中字 → `Create link` / `Ctrl+Shift+U` → 粘贴「右键画板 → Copy link」→ 回车。
2. 点不跳 = 没退出文字编辑态 / 链接没生效（看下划线）/ 按着 Ctrl。
3. 快捷键失灵基本是**中文输入法**：先切英文再按。
4. 界面入口位置随版本变化——认图标（回形针/链条），别认死位置。
5. 评论叠成"簇"无关闭开关，靠**错位摆放 + 拉开间距**规避。

## FAQ 路由

- "无头跑 AI 脚本 / 弹窗 / 脚本不执行 / 怎么等它跑完" → docs/illustrator/无头脚本自动化速查.md
- "SVG 转 AI 后样子不对 / 没图层 / 图层乱" → docs/illustrator/svg还原分层AI.md（脚本在 scripts/illustrator/）
- "编辑模式点文字跳某块" → docs/figma/编辑模式文字链接导航.md
- "编辑时快速定位视图" → docs/figma/编辑模式快速定位.md
- "评论挤在一起 / 合并" → docs/figma/评论排布技巧.md
- "Figma 导航/跳转怎么都怎么选" → docs/figma/导航速查.md
- 未验证的做法不收录；若要使用请先在真实环境验证后补录，并同步 README 表与本路由。
