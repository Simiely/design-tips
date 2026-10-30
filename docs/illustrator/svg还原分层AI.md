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

## 职责划分：SVG 管矢量，PDF 管位图

两个文件各司其职，**谁的内容谁负责**，不交叉：

| 内容 | 负责 | 处理方式 |
|---|---|---|
| 全部矢量元素（图标、转曲文字、公路线、色块） | **SVG** | 原样保留，文档顺序 = 堆叠顺序 |
| 背景大图、照片位 | **PDF** | 抽内嵌图（SMask alpha 已含渐隐），把 pattern 填充替换为 `<image preserveAspectRatio="none">`，保留旋转/裁剪 |
| 模糊阴影（feGaussianBlur） | **PDF** | Figma 导出 PDF 时已栅格化成图片，按 PDF 变换矩阵摆放（AI 不支持 SVG 滤镜） |
| 渐隐蒙版（mask） | **PDF** | 已烘焙进图片 alpha；AI 不认 SVG mask |
| 渐变（linearGradient）、裁剪路径（clipPath） | **SVG** | AI 能正确导入，保留在 defs |
| 分组依据 | **截图标记** | 按区域框归属（见下方示意图） |

## 分组依据（示意图）

元素按**变换后真实位置**落框归属到 5 个图层；背景是整张底图单独一组，各区域内再按「矢量 / 位图」分子组：

![分组示意图](assets/grouping-map.jpg)

对应关系：顶部状态栏 → `顶部状态栏`；左框 → `左侧信息面板`；右框 → `地图区域`（子组 位图-阴影 / 矢量 / 位图-照片）；下框 → `底部导航栏`（子组 矢量 / 位图）；整张底图 → `背景`。

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

## 启动时的两次弹窗：来源、判定与消除

外部启动 Illustrator 脚本时通常弹**两次**确认。两次来源不同、性质不同，处理方式也不同：

| # | 弹窗 | 官方定性 | 能否消除 |
|---|---|---|---|
| ① | `File not found: /xxx.jsx`（路径显示还丢盘符） | 命令行传 `.jsx` 时 Illustrator 会**把它当文档打开**，`.jsx` 不是可打开的图形格式 → 报"文件不存在"，而脚本派发本身是成功的 | **把脚本放到 Illustrator 所在盘（实测 C:）即可不弹**（见下"本机实测"）；或改用 **COM `DoJavaScriptFile`** |
| ② | "是否允许运行该脚本"（外部脚本安全警告） | Illustrator 的**外部脚本安全特性**，用于提示"有外部程序在驱动 Illustrator 执行脚本" | 官方给的消除法：运行 JSX 设 `app.preferences.setBooleanPreference("ShowExternalJSXWarning", false)`；或把脚本放进**受信任目录** `%USERPROFILE%\Documents\Adobe\Scripts` |

#### 本机实测（Illustrator 2026 / build 30 / Windows，2026-10-30）

| 场景 | 结果 |
|---|---|
| `-r "D://workbuddy//...//pdfimg//x.jsx"`（脚本在 D 盘） | **弹模态 "File not found"，阻塞主线程** → 不点掉弹窗脚本就一直不开始（实测 240s 无产出） |
| `-r "C://ai//probe.jsx"`（脚本在 **AI 所在盘**） | **直接执行、无阻塞**，14s 跑完整个转换（产物 md5 与前次完全一致） |
| 把 D 盘路径镜像复制到 C 盘同名位置后再 `-r "D://..."` | 仍不通 → 说明**不是"剥掉盘符后能在 C 盘找到"**，而是**跨盘路径本身**触发那个报错 |
| `Startup Scripts` 目录派发（AI 安装目录 `Startup Scripts\`） | **不触发**——派发器完全没被执行（目录与派发器均已正确安装、任务目录已建，派发日志为空）。**本版本不适用** |

**落地规则**：启动前先把任务脚本复制到 **Illustrator 所在盘**（`%SystemDrive%`，本机 `C://ai//jobs//`），
再以该路径启动 → 弹窗消失、脚本自动执行。`run-ai-headless.ps1` 已内置这一步（输出 `[run] staged script -> ...`）。

**注意**：① 是**模态阻塞**的——不点掉它，脚本不会开始跑；看到弹窗请随手点"确定"，或按上面的规则从根上避免。

### 零点击方案（推荐：首次 1 次点击，之后 0 点击）

1. **一次性关掉安全警告（官方做法）**
   Illustrator → 文件 > 脚本 > 其他脚本… → 选 `scripts/illustrator/suppress-external-warning.jsx` → 运行。
   这一步会写入偏好 `ShowExternalJSXWarning=false`，**之后所有外部调用都不再弹 ②**。
   （本仓库的 `convert-to-ai.jsx` / `verify-layers.jsx` 开头也会自动设置该偏好，属于自我加固：
   首次运行仍会弹一次，因为警告发生在脚本执行之前。）
2. **改用 COM 路线跑批处理**（`scripts/illustrator/run-ai-headless.vbs`）→ 连 ① 也不弹，且**能真正等到脚本完成**：

```bat
cscript //nologo scripts\illustrator\run-ai-headless.vbs D:\path\to\convert-to-ai.jsx D:\path\to\_ailog.txt 600
```

   COM 路线要点（社区实测）：`CreateObject("Illustrator.Application")` → **必须先 sleep ~10 秒**等 Illustrator
   启动完成，否则脚本不执行 → `appRef.DoJavaScriptFile path, Array()` → 轮询日志到 `done`。
3. **备选：受信任目录**——把脚本放进 `%USERPROFILE%\Documents\Adobe\Scripts`，该目录下的脚本不触发 ②
   （Adobe JavaScript Tools Guide 说明该目录为受信任位置）。适合不想改全局偏好的场景。

#### 想把 ① 也彻底去掉：Startup Scripts 派发（无需 COM）

官方 Scripting Guide 的 **Startup scripts** 机制：把 `.jsx` 放进名为 `Startup Scripts` 的文件夹，
**AI 启动时会自动执行**它——命令行根本不传文件参数，所以 ① 不会存在：

| 类型 | Windows 路径 |
|---|---|
| 应用级（推荐） | `C:\Program Files\Adobe\Adobe Illustrator <版本>\Startup Scripts\`（文件夹需自建） |
| 通用级（所有 CC 应用） | `C:\Program Files\Common Files\Adobe\Startup Scripts CC\Illustrator\` |

本仓库提供的三件套：

```powershell
# ① 一次性安装（需管理员；脚本会自提权）
powershell -ExecutionPolicy Bypass -File scripts\illustrator\install-startup-dispatcher.ps1

# ② 排队并运行（AI 无参数启动 → 派发器自动拾取任务 → 全程零弹窗）
powershell -ExecutionPolicy Bypass -File scripts\illustrator\run-ai-job.ps1 `
    -Job "D:\path\to\convert-to-ai.jsx" -Log "D:\path\to\_ailog.txt" -TimeoutSec 540
```

**更省事：一键安装包**（自提权 + 自动自检）——把 `install-ai-startup-dispatcher.cmd` 与
`startup-dispatcher.jsx` 放同一目录，双击即可：会弹 UAC → 写入 Startup Scripts →
创建任务目录 → **自动拉起一次 AI 做自检**（等 45 秒看派发日志里有没有
`no job queued - skip`，有就说明 Startup Scripts 真的被触发）→ 打印 PASS/FAIL。

- **任务文件放在 `%USERPROFILE%\Documents\Adobe\Scripts\_ai_job.jsx`**——该目录是 Adobe 受信任目录，
  派发器 `$.evalFile` 执行它不会再触发安全警告；`run-ai-job.ps1` 负责拷贝任务、清去重标记、轮询日志、清理。
- **必须幂等**：社区实测启动脚本**可能被执行不止一次**（macOS 上出现过两次），因此派发器用 `_ai_job.done`
  标记去重，任务方排队前先清标记。
- **注意**：`Startup Scripts` 里的脚本会在**每次启动 AI 时**都运行，所以派发器必须"没任务就什么都不做"。

#### 试过但不管用的做法

- **相对路径 + 指定工作目录**：`Start-Process -WorkingDirectory <脚本目录> -ArgumentList "-r","convert.jsx"`
  → AI 按**自身**工作目录解析，脚本根本没执行（无日志）。命令行传参必须给**可解析的绝对路径**。
- **把脚本放进 AI 安装目录的 `Scripts\`（脚本菜单目录）**：那只是让脚本出现在菜单里，
  不会让 `-r` 启动免掉弹窗。

#### 怎么确认偏好真的生效了

- **脚本内自查**（最直接）：
  ```jsx
  app.preferences.getBooleanPreference("ShowExternalJSXWarning")   // false = 已关闭
  ```
- **看偏好文件**（Windows）：`%APPDATA%\Adobe\Adobe Illustrator <版本号> Settings\<语言>\x64\Adobe Illustrator 首选项`
  里有一行 `/ShowExternalJSXWarning 0`（0=不弹、1=弹）。
  注意：偏好在 Illustrator 正常退出时才落盘，所以改完要**让 AI 正常退出**（脚本里 `app.quit()`），
  强杀进程可能导致不落盘。
- 关闭后，`-r` 路线只剩 ①（File not found 噪音，可无视）；走 COM 路线则**两次点击都不需要**。

### 判据与处置

| 现象 | 含义 | 正确动作 |
|---|---|---|
| 弹 ①，但日志继续生成 | **正常噪音**，脚本在跑 | 弹窗可无视（点 OK 无害）；**但不要关 Illustrator 窗口** |
| 弹 ①，日志始终不生成 | 脚本路径确实找不到（文件不存在 / 路径写错 / `-Log` 与脚本内 `LOG` 不一致） | 核对文件是否存在、两个路径是否一致 |
| 弹 ② | 首次授权 | 点"允许"；或用上面的 `suppress-external-warning.jsx` 一次性关掉 |
| 日志有内容但一直没有 `done` | 脚本还在跑（打开大 SVG、渲染导出） | 加长超时；**不要杀进程** |
| 日志出现 `ERROR:` | 脚本内部异常 | 按日志内容修脚本 |

- **最容易造成误判的坑：手动关窗口 / 杀进程**。实测中脚本被腰斩（日志永远到不了 `done`），
  原因不是弹窗，而是"以为卡死了就把 AI 关掉"。**弹窗可以无视，窗口不能关。**
- **`-r` 路线的固有限制**（第三方实测文档明确写出）：用 `exe -r` 跑脚本**无法获知脚本是否执行成功、
  无法等待执行完成** → 判据只能是日志；需要"确认成功/等完成"就走 COM 路线。
- **正确姿势**：结束旧实例 → **等进程真正消失** → 启动 → **轮询日志**，全程不干预 Illustrator。
  PowerShell 版启动器：`scripts/illustrator/run-ai-headless.ps1`（清场 + 启动 + 轮询 + 退出码）。

```powershell
powershell -ExecutionPolicy Bypass -File scripts/illustrator/run-ai-headless.ps1 `
    -Jsx "D:\path\to\convert-to-ai.jsx" -Log "D:\path\to\_ailog.txt" -TimeoutSec 900
```

### 外部调用规范（Adobe Illustrator Scripting 参考「外部调用与参数传递」）

- 外部启动时 **`$.fileName` 为空** → 脚本里一律用绝对路径，不要从 `$.fileName` 推导资源位置。
- **位置参数不会转发**（`arguments[0]` 是 `[object BridgeTalk]` 或空）→ 要传参就用 sidecar 文件
  （已知绝对路径）或环境变量；本仓库脚本改用**顶部配置区**。
- `#targetengine "session"` 可让脚本在多次调用之间保留变量。
- 批处理必须 `app.userInteractionLevel = UserInteractionLevel.DONTDISPLAYALERTS`。

### 读日志 / 编码

- **读日志要指定编码**：日志是 UTF-8，Windows PowerShell 5.1 默认按 ANSI 读会把中文显示成乱码
  （文件本身正常）——用 `Get-Content -Encoding UTF8` 或直接 `cat`。
- **.ps1 / .vbs 保持纯 ASCII**：Windows PowerShell 5.1 读无 BOM 的 UTF-8 脚本会按 ANSI 解析，
  非 ASCII 字符串可能直接造成语法错误（本次实测报"字符串缺少终止符"）。

### 参考来源

- Adobe 帮助中心「Install and run scripts」（抑制警告的官方做法）：<https://helpx.adobe.com/in/illustrator/desktop/automate-visualize-data/automate-actions/install-and-run-scripts.html>
- Adobe UserVoice（官方工程师回复，指明这是外部脚本安全特性并给出同样解法）：<https://illustrator.uservoice.com/users/6201597489-sonia-vivo>
- Adobe 社区：<https://community.adobe.com/questions-652/ignore-this-file-not-found-error-dialog-in-illustrator-804027>
- Adobe 社区（COM 调用方式与 sleep 10 秒）：<https://community.adobe.com/questions-652/run-existing-script-from-command-line-or-any-other-automated-way-795723>
- Adobe 社区「Script warning」（受信任目录 `Documents/Adobe/Scripts`）：<https://community.adobe.com/questions-652/script-warning-778797>
- 第三方实测文档（`-r` 与接口方式的能力差异）：<https://www.getquicker.net/KC/Help/Doc/adobesoftscontrol>

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
8. **`-r` 启动弹 "File not found"：是噪音，不是失败**（实测三种路径写法都会弹，但脚本都完整执行）。
   **千万别因此关窗口/杀进程**——那才会真的把脚本腰斩。判据只看日志：是否生成、是否出现 `done`。
   完整处置见上文「常见故障」章节。
9. **AI 导出的 PNG 带出血**（画板外扩几个像素），做像素比对前要先对齐裁剪。
10. **图片按需选格式**：不透明图转 JPEG（体积约 -60%），带 alpha（渐隐/阴影）保留 PNG。

## 官方参考

- Adobe Illustrator 脚本指南（ExtendScript / IllustratorSaveOptions / ExportOptionsPNG24）
- Figma 导出说明（SVG / PDF 同时导出时内容一致，仅图片承载方式不同）
