# After Effects 规则与关键坑

> 从 AGENTS.md 拆出（2026-11-24）。完整流程、16 条坑表与验收数据见
> [SVG 导入 AE 分层](../docs/after-effects/SVG导入AE分层.md)；本文件只放判断入口，不复制坑表。

## 先判断

1. **脚本 ≠ UI**：AE 2026 的 UI 支持 SVG 的 footage / 合成导入，但本机脚本对 SVG 设置
   `importAs = FOOTAGE/COMP` 会抛错、默认 `importFile` 返回 `null`。批量任务先做
   `canImportAs` / `importFile` 探针，再决定是否走浏览器光栅化。
2. **文字能否可编辑，先数 `<text>`**：本批 20 个 SVG 的 `<text>` 为 0，只能从 path id
   还原原文，不能得到文本层；含文本的 SVG 走 UI 的 footage + Create Shapes and Text
   才可能转成可编辑文本层。
3. **被遮挡对象不预裁**：完整层 + 轨道遮罩（`TrackMatteType.ALPHA`，遮罩层在被遮层正上方），
   遮罩可随时关闭；不要为了静态截图好看把遮挡烘焙进素材。
4. **锚点顺序**：先写文本/裁边，再取 `sourceRectAtTime` 或素材宽高，最后设 Position；
   反过来会整体偏移。
5. **隔离渲染会丢混合上下文**：`mix-blend-mode: hard-light` 组单独出层会偏亮；
   要求严格一致就与背景一起烘焙，接受该层不可单独动画。

## FAQ 路由

- “SVG 批量导入 AE 没分层 / 没文本 / 脚本报错” → 页面结论 1 与坑 1
- “文本标点乱序 / 左对齐失效” → 页面坑 2
- “文字太粗 / 字重不对 / 字距调不动” → 页面坑 3–5
- “音乐卡被遮罩裁掉 / 遮罩怎么加” → 页面坑 8
- “aerender 文件名多 00000 / 模板名无效” → 页面坑 10–11
- “顶栏/底栏缩放乱飞” → 页面坑 13
