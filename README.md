# design-tips — 平面设计软件实战技巧库

平面设计软件（Figma / Illustrator / …）实操技巧速查，**按软件分区**。
内容经官方文档核实 + 实际验证，每篇含 **场景 → 做法 → 坑**。只收验证过的内容。

## 入口

- [docs/index.md](docs/index.md) — 人工导航（全量页面见 [生成索引](docs/_generated/index.md)）
- [AGENTS.md](AGENTS.md) — AI / 维护者入口：软件路由、关键坑、命令
- [DEVELOPMENT.md](DEVELOPMENT.md) — 目录架构、增长协议与关键问题记录
- [CHANGELOG.md](CHANGELOG.md) — 版本历史

## 软件索引

### Figma（4 篇）→ docs/figma/

| # | 主题 | 一句话 |
|---|---|---|
| 1 | [编辑模式：文字链接导航](docs/figma/编辑模式文字链接导航.md) | 给文字加链接指向"本文件画板/页面"，编辑模式下点击直接跳，不用进原型 |
| 2 | [编辑模式：快速定位](docs/figma/编辑模式快速定位.md) | `Ctrl+/` 输名字跳 / 左栏点击跳 / Section 做目录 / `Shift+2` 缩放定位 |
| 3 | [评论排布](docs/figma/评论排布技巧.md) | 评论贴太近会自动叠成"簇"，无关闭开关，错位摆放拉开间距即可分散 |
| 4 | [导航速查](docs/figma/导航速查.md) | 导航/跳转完整汇总 |

### Illustrator（2 篇）→ docs/illustrator/

| # | 主题 | 一句话 |
|---|---|---|
| 1 | [SVG 还原为带分层的 AI](docs/illustrator/svg还原分层AI.md) | 扁平 SVG + 同名 PDF → 可编辑带图层 .ai：pattern 失真修复 / 位图抽取 / 光效按类型处理 / 无头转换 + 画布收边 + 像素级验证 |
| 2 | [无头脚本自动化速查](docs/illustrator/无头脚本自动化速查.md) | 一条命令让 Illustrator 跑 JSX 脚本、零弹窗零点击：同盘暂存规则 / 安全警告开关 / 三条启动通道 / 排错速查 |

## 脚本 scripts/<软件>/

- `scripts/illustrator/`：分层 SVG 构建器（通用版 `build_layered.py` 自动识别 pattern/filter/mask/混合模式 +
  命令感知 path 解析 + 按区域分组；`build_layered_svg.py` 为首份稿的手写参考实现）+ 光效透明底渲染
  `render_glow.py` + AI 无头转换 JSX + 图层结构核验 JSX。逐脚本说明见
  [scripts/illustrator/README.md](scripts/illustrator/README.md)。

## 维护规则

写新条目或改动结构前，先读 [DEVELOPMENT.md](DEVELOPMENT.md)「目录架构」的同步规则与 [AGENTS.md](AGENTS.md) 的核心约束；规则只在那里维护，本页不重复。

## 校验

```bash
python -m pip install -r requirements.txt
python tools/repo-kit/check_repo.py --root .
python tools/repo-kit/generate.py --root . --check
pwsh tools/update-repo-kit.ps1 -Check
```
