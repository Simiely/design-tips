# CHANGELOG.md

所有值得记录的变化都列在这里。

## [0.5.0] - 2026-11-02
### 新增
- convert-to-ai.jsx：**画布收边步骤**（`CANVAS_CLIP=true` 默认开）——移完图层后把每层内容收进
  "画板矩形剪切组"（`GroupItem.clipped`），超出画布的对象（背景出血 2~5px、渐变矩形溢出等
  Figma 导出常态）被裁回画布内；不裁像素、随时可逆。第 2 份真实设计稿实测：5/5 层
  clipRect=2560×1440，画板内保真度与位图重编码本底一致。
- verify-layers.jsx：新增每层裁剪蒙版核验输出（`CLIP` 行，clipRect 应=画板尺寸）。
### 实测坑（已写入主文档坑⑪⑫ / AGENTS 关键坑6）
- **SVG 顶层命名组加 `clip-path` → AI 2026 导入后 `GroupItem.name` 变空**，按名配对图层全挂
  （moved:0，命名层被当空壳删光）→ 收边必须放 JSX 做，SVG 侧只留 id。
- **无头环境 `executeMenuCommand("Clipping Mask")` 必报 `1112237433 ('BKey')`** →
  用 `GroupItem.clipped` 代替（组内 ≥2 对象、裁切框置组内最上层）。

## [0.4.0] - 2026-10-30
### 新增
- Illustrator 第 2 篇：docs/illustrator/无头脚本自动化速查.md —— 零弹窗跑通 JSX 的完整方法论：
  零弹窗三个必要条件（安全警告开关 / **脚本与 AI 同盘** / 不走"打开文件"逻辑）、三条启动通道对比、
  标准工作流四步、退出码对照、排错速查表、脚本必备要素。
- scripts/illustrator/template-job.jsx —— 空白任务模板（配置区 + 日志 + try/catch + app.quit）。
### 修复
- run-ai-headless.ps1：启动前把任务脚本**暂存到 Illustrator 所在盘**（%SystemDrive%\ai\jobs\）。
  实测跨盘路径会触发模态 "File not found" 并阻塞主线程（不点掉弹窗脚本永不开始）；
  同盘后实测零弹窗、16s 跑完真实转换，产物 md5 不变。
### 已知限制
- AI 2026 build 30 **不执行 Startup Scripts**（安装成功但派发器未被执行）→ 该通道仅留作其他版本备选。

## [0.3.0] - 2026-10-30
### 改造（Breaking）
- 仓库更名：figma-navigation-tips → **design-tips**，定位升级为「平面设计软件实战技巧库」。
- 结构分区：`docs/figma/`（原 4 篇迁入）、`docs/illustrator/`、`docs/common/`（预留）；
  脚本按 `scripts/<软件>/` 分区。旧链接 GitHub 自动重定向。
- 新增增长协议（DEVELOPMENT.md）：双入口索引同步、单软件 ≤12 篇平铺阈值、frontmatter 元数据、只收验证内容。

### 新增
- 新软件线 Illustrator：主题 1「SVG 还原为带分层的 AI」（docs/illustrator/svg还原分层AI.md）——
  扁平 SVG + 同名 PDF → 可编辑带图层 .ai 的完整流水线（pattern 失真修复 / PDF 位图抽取 /
  命令感知 path 解析 / 无头脚本转换 / 像素级验证）。
- 配套脚本 scripts/illustrator/：build_layered_svg.py（分层 SVG 构建器）、
  convert-to-ai.jsx（无头转换）、verify-layers.jsx（图层结构核验）。

## [0.2.0] - 2026-08-25
### 新增
- 仓库定位扩展为 「Figma 使用技巧速查」（原仅导航跳转）。
- 新增主题3：评论排布技巧（docs/figma/评论排布技巧.md）——评论贴太近会自动叠成"簇"，错误位摆放 + 拉开间距可分散，无原生关闭开关。

## [0.1.0] - 2026-08-25
### 新增
- 首个版本：整理 Figma 文档内"导航 / 跳转"技巧，含主题索引表与 2 个已验证主题独立文档。
- 核心结论：编辑模式内做跳转用**文字链接（Add links to text）**，快速定位用 `Ctrl+/` / 左栏 / Section。
- 原则：只收录实际用过并验证过的做法；原型连线、Overlay/Scroll To、连线治理等未验证，暂不收录（见 DEVELOPMENT.md TODO）。
