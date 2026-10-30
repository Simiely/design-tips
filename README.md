# design-tips — 平面设计软件实战技巧库

平面设计软件（Figma / Illustrator / …）实操技巧速查，**按软件分区**。
内容经官方文档核实 + 实际验证，每篇含 **场景 → 做法 → 坑**。只收验证过的内容。

## 软件索引

### Figma（4 篇）→ docs/figma/

| # | 主题 | 一句话 |
|---|---|---|
| 1 | 编辑模式：文字链接导航 | 给文字加链接指向"本文件画板/页面"，编辑模式下点击直接跳，不用进原型 |
| 2 | 编辑模式：快速定位 | `Ctrl+/` 输名字跳 / 左栏点击跳 / Section 做目录 / `Shift+2` 缩放定位 |
| 3 | 评论排布 | 评论贴太近会自动叠成"簇"，无关闭开关，错位摆放拉开间距即可分散 |
| 4 | 导航速查 | 导航/跳转完整汇总 |

### Illustrator（1 篇）→ docs/illustrator/

| # | 主题 | 一句话 |
|---|---|---|
| 1 | SVG 还原为带分层的 AI | 扁平 SVG + 同名 PDF → 可编辑带图层 .ai：pattern 失真修复 / PDF 位图抽取（阴影·渐隐·裁剪头像）/ 命令感知路径解析 / 无头脚本转换 + 像素级验证 |

## 脚本 scripts/<软件>/

- `scripts/illustrator/`：分层 SVG 构建器（命令感知 path 解析 + 按区域分组 + pattern→image 替换）+
  AI 无头转换 JSX + 图层结构核验 JSX。逐脚本说明见 [scripts/illustrator/README.md](scripts/illustrator/README.md)。

## 维护规则（写新条目前必读）

结构、命名与增长协议见 [DEVELOPMENT.md](DEVELOPMENT.md)「增长协议」一节，要点：

- 新条目放 `docs/<软件>/`，跨软件通用放 `docs/common/`；
- **新增条目必须同步两处**：本 README 软件表 + AGENTS.md 的 FAQ 路由；
- 单软件 docs ≤12 篇平铺，超出按主题域开二级目录；
- 每篇头部加 frontmatter（软件 / 版本 / 验证日期 / 状态）；只收验证过的内容。

## 相关链接

- [🤖 AGENTS.md（AI 路由 + 关键坑速记）](AGENTS.md)
- [🔧 DEVELOPMENT.md（增长协议 + 踩坑记录）](DEVELOPMENT.md)
- [📜 CHANGELOG.md](CHANGELOG.md)
