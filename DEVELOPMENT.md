# DEVELOPMENT.md — 目录架构与关键问题记录

本仓库是平面设计软件的实战技巧库：只收录真实环境验证过的做法，按软件分区，文档与配套脚本同仓。

## 项目概览

- 目标读者：需要查"这个界面/脚本到底怎么做"的自己与 AI 助手
- 解决什么问题：软件界面与旧教程差异大、踩过的坑容易忘；把验证结论固化成可检索的短页
- 不做什么：不做通用设计教程、不收录未验证操作、不写第二份软件官方文档

## 目录架构

```text
design-tips/
├── README.md            # 门面：软件索引（人）
├── AGENTS.md            # 生成：AI/维护者入口（路由 + 核心约束 + @rules）
├── DEVELOPMENT.md       # 本文件：架构、增长协议、关键问题
├── CHANGELOG.md         # 版本记录
├── docs/
│   ├── index.md         # 人工导航
│   ├── _template.md     # 新条目模板（frontmatter + 场景/做法/坑）
│   ├── _generated/      # 生成：索引、反链、踩坑索引，勿手改
│   ├── figma/           # 按软件分区
│   └── illustrator/
├── rules/               # AI 细则：figma.md / illustrator.md（从 AGENTS 拆出）
├── scripts/<软件>/      # 与文档配套的工具脚本
├── schema/              # taxonomy / frontmatter 契约 / sources / kit.lock
└── tools/repo-kit/      # 校验与生成器（由 update-repo-kit.ps1 安装）
```

**增长协议**

- 目录即命名空间：新条目放 `docs/<软件>/`，跨软件通用放 `docs/common/`（出现内容再建）。
- 单软件 `docs/<软件>/` ≤12 篇平铺；超出后按主题域开二级目录（如 `docs/illustrator/自动化/`）并补该目录 `索引.md`。
- 新增条目同步三处：`README.md` 软件表、`docs/index.md`、`AGENTS.md` 路由（`rules/` 里的 FAQ 同步）。
- 坑位策略：用文档内「坑」段 + `rules/<软件>.md` 总表，**不建独立 `kind: pitfall` 页**；
  因此 `docs/_generated/pitfalls.md` 当前为空表（生成器固定产出 5 件，保留即可）；
  当某软件坑位 ≥10 条且需要单独检索时再拆页。
- 知识流：单仓库的坑写在对应文档「坑」段或本文件；跨项目复用的，收尾时提炼到 knowledge-base 用户库。

## 关键问题与方案

### 问题：Figma 编辑模式点文字不跳转（2026-08）

**TL;DR**：正确姿势是「Add links to text」，且必须先退出文字编辑态。

- 问题：给导航文字加链接后点击无反应
- 根因：仍在文字编辑态 / 链接没生效（无下划线）/ 按着 Ctrl
- 解决：双击选中字 → `Create link` → 粘贴画板链接 → 回车，退出编辑态再点
- 预防：认图标（回形针/链条）不认位置；详见 `docs/figma/编辑模式文字链接导航.md`

### 问题：AI 无头脚本永不开始，卡在 "File not found"（2026-10-30）

**TL;DR**：脚本必须与 Illustrator 同盘；跨盘触发模态阻塞。

- 问题：`-r script.jsx` 启动后日志一直没有 `done`
- 根因：跨盘路径触发模态 "File not found"，主线程被阻塞
- 解决：启动前把脚本暂存到 `%SystemDrive%\ai\jobs\`，同盘后再启动
- 预防：判据只看日志有无 `done`；该弹窗是噪音，不代表脚本失败

### 问题：SVG 顶层命名组加 `clip-path` → AI 导入后组名为空（2026-11-02）

**TL;DR**：收边不能写在 SVG 里，必须放到 JSX 用 `GroupItem.clipped`。

- 问题：按组名配对的图层全部 `moved:0`，命名层被当空壳删光
- 根因：AI 2026 导入带 `clip-path` 的顶层命名组后 `GroupItem.name` 丢失
- 解决：SVG 侧只留 id，画布收边在 `convert-to-ai.jsx` 中用裁剪组实现
- 预防：无头环境不用 `executeMenuCommand("Clipping Mask")`（必报 BKey 错）

### 问题：光效在 AI 里变白/丢失（2026-11-11）

**TL;DR**：模糊、投影、混合模式、实心遮罩要分别处理，不能统一替换成 PDF 位图。

- 问题：发光变死白亮斑、图标本体消失、光晕被洗淡
- 根因：`mix-blend-mode` 不在 SVG 导入范围内；投影位图只含阴影；PDF 的 blur 偏白
- 解决：模糊用浏览器渲染透明底图、投影叠回矢量主体、混合模式按组名补设、实心 mask 转 clipPath
- 预防：见 `docs/illustrator/svg还原分层AI.md` 结论先行 6/7 与坑⑬~⑰

## 历史沿革

- 2026-08：创建时定位「Figma 导航跳转技巧」；08-25 扩展为「Figma 使用技巧速查」。
- 2026-10-30：改造为多软件库 `design-tips`，docs 按软件分区，首个 Illustrator 主题入库。
- 2026-11-12：接入 repo-kit `knowledge` profile，统一页面契约与生成索引，AGENTS 拆出 `rules/`。

## 官方参考源

- Figma Add links to text：https://help.figma.com/hc/en-us/articles/360045942953
- Figma Move or edit comments：https://help.figma.com/hc/en-us/articles/360041547853
- Adobe Install and run scripts：https://helpx.adobe.com/in/illustrator/desktop/automate-visualize-data/automate-actions/install-and-run-scripts.html

## TODO

- Figma：原型连线跳转 / 板内 Overlay / Scroll To 验证后补录，并按同步规则更新索引。
- Illustrator：导出预设 / 脚本面板 / 颜色管理等主题验证后补录。
- 收尾时把跨项目通用的坑（无头脚本、SVG→AI 分层）提炼到 knowledge-base 用户库。
