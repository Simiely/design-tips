# scripts/illustrator — SVG 还原为带分层 AI 的流水线脚本

配套文档：[docs/illustrator/svg还原分层AI.md](../../docs/illustrator/svg还原分层AI.md)（场景/结论/坑）。

按顺序使用，换一份设计稿只需改各脚本顶部的配置区（通用版连映射都不用写）。

## 0. build_layered.py — 通用版构建器（首选）

- 与 `build_layered_svg.py` 的区别：**不需要逐元素写映射**，换稿只改顶部 CONFIG：
  `BASE` / `WORK`（源目录、产物目录）、`ORDER`（图层名 = 堆叠顺序）、
  `RULE`（区域判定阈值：背景宽高、顶栏 y、底栏 y、左栏 x）。
- 自动处理四类"AI 导不进的东西"：
  | 源里的写法 | 处理 |
  |---|---|
  | `<rect fill="url(#pattern*)">` | 换成 `<image>`，位置按 pattern 的 `use` 变换反算（旋转/裁剪原样保留） |
  | `<g filter="…_f">` 模糊组 | 调 `render_glow.py` 用本机无头 Edge 渲染成透明底 2x PNG |
  | `<g filter="…_d">` 投影组 | PDF 的阴影位图在下 + 原矢量组（摘掉 filter）在上 |
  | `<g style="mix-blend-mode:…">` | 包一层 `id="blend-<mode>"` 的组，交给 JSX 还原 |
  | `<g mask="…">` 实心矩形遮罩 | 转成等效 `clipPath`（直接删会露出本来被裁掉的元素） |
- 依赖：`pillow`、`pymupdf`、本机 Edge/Chrome。
- 层内保持原始文档顺序（堆叠语义），区域判定用"变换后真实 bbox 中心点"。

```bash
python build_layered.py 006 007     # 参数 = 不带扩展名的文件名（同名 .svg/.pdf 需在同一目录）
```

## 0b. render_glow.py — 单 filter 组的透明底渲染

- `render_filter(svg, filter_id, region, out_png, scale=2)`：只把 `<filter>` 组的宿主元素拎出来，
  连同 defs 里的渐变/滤镜/裁剪重建一个最小 SVG，用 `--default-background-color=00000000`
  截透明底图，再按 filter 的 `x/y/w/h` 裁切。
- **必须剥掉 `mix-blend-mode`**：否则会对着透明底做混合，光晕被拉亮（见主文档坑⑬）。
- 为什么不用 PDF 那张：PDF 的栅格化结果偏白，一片光晕会被洗淡（坑⑮）。

## 1. build_layered_svg.py — 首份稿的手写参考实现

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
  **还原 `blendingMode`**（`blend-*` 命名组，soft-light / color-dodge 等）→
  **画布收边**（`CANVAS_CLIP=true` 默认开）→ 删空壳"图层 1" → `saveAs(IllustratorSaveOptions)` 存 .ai
  → 导出 PNG24 核验图 → 退出。
- ⚠️ **一次启动只转一个文件**：同一会话里 open 第二个 SVG 必报 `271`（主文档坑⑰）——
  多份稿就复制成多个 jsx（改 SRC/DST）分多次启动。
- **画布收边**：移完图层后把每层内容收进一个"画板矩形剪切组"（`GroupItem.clipped`）——
  超出画布的对象（背景出血 2~5px、渐变矩形溢出等 Figma 导出常态）被裁回画布内，
  **不裁像素、随时可逆**。两个实测坑（2026-11-02）：
  **别把 clip-path 写进分层 SVG**（AI 导入后组名变空，按名配对全挂，见主文档坑⑪）；
  **别用 `executeMenuCommand("Clipping Mask")`**（无头必报 `1112237433 ('BKey')`，见坑⑫）。
- 日志写文件（脚本内 File 写出），外层轮询日志判断完成，不要傻等进程。

> 相关技能：本仓的通用做法已沉淀为 WorkBuddy 技能 **illustrator-artboard-clip**
> （github.com/Simiely/workbuddy-skills），含溢出扫描 / 画板收边 / 零弹窗启动三脚本与 AI 2026 API 坑位清单。

## 2b. 三个启动器（按"弹窗数"排）

| 启动器 | 通道 | 弹窗 ① File not found | 弹窗 ② 安全警告 | 能确认执行成功 | 需管理员 |
|---|---|---|---|---|---|
| `run-ai-job.ps1` | AI 无参数启动 + Startup Scripts 派发 | **不弹** | 设过偏好后不弹 | 靠日志 | **是**（一次性安装） |（**实测本版本不触发，见下**） |
| `run-ai-headless.vbs` | COM `DoJavaScriptFile` | **不弹** | 设过偏好后不弹 | **可以** | 否 |
| `run-ai-headless.ps1` | `Illustrator.exe -r`（**先把脚本暂存到 AI 所在盘**） | **不弹**（实测同盘无阻塞） | 设过偏好后不弹 | 只能靠日志 | 否 |

- `run-ai-headless.ps1`：清旧实例 → 等进程消失 → **把脚本复制到 `%SystemDrive%\ai\jobs\`（AI 所在盘）** → 以该路径 `-r` 启动 → 轮询日志到 `done` → 退出码语义化。
  **为什么要暂存到 C 盘**：实测跨盘（D:）路径会弹**模态** "File not found" 并阻塞主线程，不点掉弹窗脚本就一直不开始；脚本与 AI 同盘则直接跑通、无弹窗。
  **超时默认不杀 AI**（杀进程才会真的腰斩脚本），需强制清理加 `-KillOnTimeout`。
- `run-ai-headless.vbs`：`cscript //nologo run-ai-headless.vbs <jsx> <log> <timeoutSec>`，
  内部 sleep 10s 等 AI 启动完（社区实测必需），再 `DoJavaScriptFile`，最后轮询日志。
- `run-ai-job.ps1` + `startup-dispatcher.jsx`：**本机实测 AI 2026 build 30 不执行 Startup Scripts**（派发器未被触发、派发日志为空）→ 本版本**不可用**，仅留作其他版本/环境的备选。
  机制：把任务 .jsx 排进 `%USERPROFILE%\Documents\Adobe\Scripts\_ai_job.jsx`（受信任目录），**不带参数**启动 AI → Startup Scripts 里的派发器自动拾取执行。
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

## 2d. template-job.jsx — 空白任务模板

新写无头任务时直接复制它、改顶部配置区即可。模板已内置四条必备规则：
`#targetengine "session"`、全绝对路径、顶层 try/catch 写日志、结尾 `app.quit()`。
完整方法论见 docs/illustrator/无头脚本自动化速查.md。

## 3. verify-layers.jsx — 结构核验

- 打开生成的 .ai，dump 每个图层的名称、可见性与每个 pageItem 的类型/bounds（UTF-8 日志），
  用于人工核对配对与坐标。
- 末尾输出**画布收边核验**（`CLIP layer ... clipRect=[...] w=... h=...`）：每个命名层应有一个
  clipped 组，clipRect 应等于画板尺寸；没有则说明 `CANVAS_CLIP` 没生效或被跳过。

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
- SVG 顶层命名组带 `clip-path` → AI 导入后组名变空，按名配对全挂 → 收边放 JSX 做（`CANVAS_CLIP`），SVG 只留 id。
- 无头 `executeMenuCommand("Clipping Mask")` 必报 `1112237433 ('BKey')` → 用 `GroupItem.clipped`（裁切框置组内最上层）。
- **`mix-blend-mode` 不还原 → 灯光变死白亮斑**；渲染位图时要剥掉它，导入后按 `blend-*` 组名设 `blendingMode`。
- **投影类 filter（`*_d`）的 PDF 位图只含阴影** → 阴影在下、矢量主体叠上，否则图标本体消失。
- **模糊光效别用 PDF 那张**（偏白）→ 本机无头浏览器渲染同组，2x 透明底。
- **`<mask>` 是实心矩形时不能直接删** → 转等效 `clipPath`，否则露出本来被裁掉的元素。
- **一次 AI 会话只能开一个 SVG**（第二个报 `271`）→ 一稿一启动。
- AI 导出 PNG 带出血 → 像素比对前先对齐裁剪。
- Windows PowerShell 5.1 读无 BOM 的 UTF-8 `.ps1` 会按 ANSI 解析 → `.ps1` / `.vbs` 一律纯 ASCII；
  同理**带中文图层名的 `.jsx` 必须存成带 UTF-8 BOM**，否则 ExtendScript 按 ANSI 读，组名对不上。
- 读 UTF-8 日志要 `Get-Content -Encoding UTF8`，否则终端显示乱码（文件本身正常）。
- 外部启动时 `$.fileName` 为空、位置参数不转发 → 脚本用绝对路径 + 顶部配置区，不依赖 arguments。
- COM 路线要先 sleep ~10 秒等 Illustrator 启动完，否则脚本可能不执行（社区实测）。
