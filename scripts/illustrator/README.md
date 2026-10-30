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

## 2b. 三个启动器（按"弹窗数"排）

| 启动器 | 通道 | 弹窗 ① File not found | 弹窗 ② 安全警告 | 能确认执行成功 | 需管理员 |
|---|---|---|---|---|---|
| `run-ai-job.ps1` | AI 无参数启动 + Startup Scripts 派发 | **不弹** | 设过偏好后不弹 | 靠日志 | **是**（一次性安装） |
| `run-ai-headless.vbs` | COM `DoJavaScriptFile` | **不弹** | 设过偏好后不弹 | **可以** | 否 |
| `run-ai-headless.ps1` | `Illustrator.exe -r` | 会弹（噪音，脚本照跑） | 设过偏好后不弹 | 只能靠日志 | 否 |

- `run-ai-headless.ps1`：清旧实例 → 等进程消失 → 启动 → 轮询日志到 `done` → 退出码语义化。
  **超时默认不杀 AI**（杀进程才会真的腰斩脚本），需强制清理加 `-KillOnTimeout`。
- `run-ai-headless.vbs`：`cscript //nologo run-ai-headless.vbs <jsx> <log> <timeoutSec>`，
  内部 sleep 10s 等 AI 启动完（社区实测必需），再 `DoJavaScriptFile`，最后轮询日志。
- `run-ai-job.ps1`：把任务 .jsx 排进 `%USERPROFILE%\Documents\Adobe\Scripts\_ai_job.jsx`
  （受信任目录），**不带参数**启动 AI → Startup Scripts 里的 `startup-dispatcher.jsx` 自动拾取执行。
  一次性安装：`install-startup-dispatcher.ps1`（写 `C:\Program Files\...\Startup Scripts\`，需管理员）。
  派发器用 `_ai_job.done` 标记**幂等去重**（社区实测启动脚本可能执行两次）。
- `install-ai-startup-dispatcher.cmd`：**一键安装包**（与 `startup-dispatcher.jsx` 放同一目录后双击）。
  自动：UAC 自提权 → 写入 Startup Scripts → 建任务目录 → 拉起一次 AI 自检（45 秒，
  看派发日志有没有 `no job queued - skip`）→ 打印 PASS/FAIL。纯 ASCII，cmd 不乱码。

## 2c. suppress-external-warning.jsx — 一次性关闭外部脚本安全警告

- 官方做法（Adobe 帮助中心 / UserVoice 官方工程师回复）：
  `app.preferences.setBooleanPreference("ShowExternalJSXWarning", false)`
- 用法：Illustrator → 文件 > 脚本 > 其他脚本… → 选本文件 → 运行（**只需一次**）。
- 效果：之后 `-r` / COM 外部调用都不再弹"是否允许运行脚本"。`-r` 路线仍剩一次
  "File not found" 噪音（点掉无害，别关窗口即可）。
- 确认是否生效：脚本内 `app.preferences.getBooleanPreference("ShowExternalJSXWarning")`
  返回 false 即可；也可查偏好文件
  `%APPDATA%\Adobe\Adobe Illustrator <版本> Settings\<语言>\x64\Adobe Illustrator 首选项`
  里的 `/ShowExternalJSXWarning 0`（偏好在 AI 正常退出时落盘，勿强杀进程）。

## 3. verify-layers.jsx — 结构核验

- 打开生成的 .ai，dump 每个图层的名称、可见性与每个 pageItem 的类型/bounds（UTF-8 日志），
  用于人工核对配对与坐标。

## 启动方式怎么选（弹窗数按"零点击方案"计）

| 方式 | 命令 | 弹窗 ① File not found | 弹窗 ② 外部脚本安全警告 | 能否确认执行成功 | 能否等完成 |
|---|---|---|---|---|---|
| **A. `-r` 命令行** | `Illustrator.exe -r x.jsx` | **会弹**（噪音，实测三路径均如此，脚本照跑） | 首次弹；设过偏好后不弹 | 只能靠日志 | 不能 |
| **B. COM `DoJavaScriptFile`** | `cscript //nologo run-ai-headless.vbs x.jsx log 600` | **不弹**（不经命令行传路径） | 设过偏好后不弹 | **可以** | **可以** |
| **C. Startup Scripts 目录** | 放进 AI 安装目录 `Startup Scripts` | 不弹 | 不弹 | 靠日志 | 不需要等 |

> 第三方实测文档明确：`exe -r` 方式「无法获知脚本是否执行成功，无法等待脚本执行完成」，
> 所以走 A 时**判据只能是日志**（文件是否生成、是否出现 `done`）。

**零点击三步**（一次性）：
1. `File > 脚本 > 其他脚本…` 运行一次 `suppress-external-warning.jsx` → 关闭 ②（官方做法：
   `app.preferences.setBooleanPreference("ShowExternalJSXWarning", false)`）；
2. 批处理改用 **B（run-ai-headless.vbs）** → ① 也不弹，且能等完成；
3. 或把脚本放进 `%USERPROFILE%\Documents\Adobe\Scripts`（受信任目录）→ 该目录下不触发 ②。

## 已知坑速记

- `doc.groupItems` 含嵌套组且顺序≠文档顺序 → 按组名配对，勿用索引。
- `-r` 启动的 "File not found"：**是噪音，脚本照常执行**（实测 + 官方社区一致）。
  **别因此关 Illustrator 窗口**——杀进程才会真的中断脚本。判据只看日志有没有 `done`。
- AI 导出 PNG 带出血 → 像素比对前先对齐裁剪。
- Windows PowerShell 5.1 读无 BOM 的 UTF-8 `.ps1` 会按 ANSI 解析 → `.ps1` / `.vbs` 一律纯 ASCII。
- 读 UTF-8 日志要 `Get-Content -Encoding UTF8`，否则终端显示乱码（文件本身正常）。
- 外部启动时 `$.fileName` 为空、位置参数不转发 → 脚本用绝对路径 + 顶部配置区，不依赖 arguments。
- COM 路线要先 sleep ~10 秒等 Illustrator 启动完，否则脚本可能不执行（社区实测）。
