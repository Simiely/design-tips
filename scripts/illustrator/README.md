# scripts/illustrator — SVG 还原为带分层 AI 的流水线脚本

配套文档：[docs/illustrator/svg还原分层AI.md](../../docs/illustrator/svg还原分层AI.md)（场景/结论/坑）。

三个脚本按顺序使用，换一份设计稿只需改各脚本顶部的配置区。

## 1. build_layered_svg.py — 生成"分层 SVG"

- 解析原 SVG：**命令感知的 path bbox 计算器**（处理 M/L/H/V/C/S/Q/T/A/Z 及相对命令，
  注意 `H`/`V` 单坐标命令会让朴素数字配对错位）+ transform 矩阵链（translate/rotate/matrix）。
- 按"区域规则"（bbox 中心点落框）把元素分到语义组（背景/顶部状态栏/…/底部导航栏），
  区域框坐标、区域名、替换映射都在脚本顶部 CONFIG 区，换稿即改。
- 替换：pattern 填充矩形 → 内嵌 `<image preserveAspectRatio="none">`（JPEG/PNG 按是否有 alpha 自动选择）；
  `<filter>` 模糊阴影 → PDF 栅格化阴影图（按 PDF 变换矩阵摆放）；被裁剪位图 → 按矩阵从源图裁切。
- 输出带命名分组的分层 SVG（组顺序 = 堆叠顺序，组内保持原始文档顺序）。
- 依赖：`pillow`、`pymupdf`（抽 PDF 图）。

```bash
python build_layered_svg.py
```

## 2. convert-to-ai.jsx — 无头转换为 .ai

- `Illustrator.exe -r convert-to-ai.jsx`（改顶部 SRC/DST/图层名配置）。
- 打开分层 SVG → 按**组名**创建真图层并移入（`layer.pageItems` 遍历，天然排除嵌套组）→
  删空壳"图层 1" → `saveAs(IllustratorSaveOptions)` 存 .ai → 导出 50% PNG24 核验图 → 退出。
- 日志写文件（脚本内 File 写出），外层轮询日志判断完成，不要傻等进程。

## 2b. run-ai-headless.ps1 — 稳妥启动（推荐用它，别裸调 -r）

解决启动时弹一次 `File not found` / 旧实例占位导致脚本不执行的问题：
结束旧实例 → 等进程真正消失 → 启动 → 轮询日志到 `done` → 退出码语义化。

```powershell
powershell -ExecutionPolicy Bypass -File run-ai-headless.ps1 `
    -Jsx "D:\path\to\convert-to-ai.jsx" -Log "D:\path\to\_ailog.txt" -TimeoutSec 600
```

退出码：`0` 成功 / `2` 参数或文件不存在 / `3` 旧实例未退出 / `4` 脚本内部 ERROR / `5` 超时。

## 3. verify-layers.jsx — 结构核验

- 打开生成的 .ai，dump 每个图层的名称、可见性与每个 pageItem 的类型/bounds（UTF-8 日志），
  用于人工核对配对与坐标。

## 已知坑速记

- `doc.groupItems` 含嵌套组且顺序≠文档顺序 → 按组名配对，勿用索引。
- `-r` 旧实例未退出时报一次 "File not found" 但脚本仍执行 → 先确认无 Illustrator 进程再启动。
- AI 导出 PNG 带出血 → 像素比对前先对齐裁剪。
