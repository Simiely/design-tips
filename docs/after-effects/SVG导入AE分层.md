---
id: docs.after-effects.svg-to-ae-layers
title: Figma SVG 导入 AE 分层：语义分组、去透明边、居中锚点与可编辑文本
summary: 5120×1600 的 20 帧 Figma SVG，按语义拆层导入 AE：浏览器隔离渲染透明 PNG、按空隙拆簇、裁透明边、锚点居中、文本层还原，并用像素 diff + 墨量比验收。
type: how-to
kind: note
status: active
owner: "@simiely"
tier: normal
confidence: high
topics: [after-effects, automation]
source_type: doc
source: docs/index.md
last_reviewed: 2026-11-24
review_days: 365
related: []
---
# Figma SVG 导入 AE 分层：语义分组、去透明边、居中锚点与可编辑文本

> 适用环境：After Effects 2026（26.0x67，Windows）＋ Edge + Playwright（Python）＋ Pillow / NumPy；素材为 Figma 导出的 20 帧 SVG（5120×1600）。本页做法全部在本机跑通并做过像素验收；复核日期 2026-11-24。
> 目标：导入后每帧是一个合成，图层按内容语义拆分；被遮挡对象保持完整；每个对象裁掉透明边、锚点在对象中心；文字是可编辑文本层。

## 结论先行

1. **不用 SVG 直接入 AE，改浏览器光栅化分层**。AE 2026 的 UI 已支持 SVG 的 footage / 合成两种导入（Adobe 官方帮助）；但本机 AE 2026 的脚本接口对 SVG 设置 `importAs = FOOTAGE` 或 `COMP` 会抛错、默认 `importFile` 返回 `null`，批处理走不通。本批 20 个 SVG 的 `<text>` 数为 0、`<path>` 数为 1939（本次复核），文字已转曲；工程还依赖 `mix-blend-mode`、渐变遮罩等浏览器渲染语义。用无头浏览器把每个语义分组**隔离渲染成透明 PNG**，位置像素即最终位置，一致性最好。
2. **分组按「内容模块」而不是按 Figma 图层树**：背景、底栏、音乐卡、地图、空调卡、续航卡、顶栏、语音助手各一层；一块内容内部再按语义拆（如顶栏左右两簇）。
3. **被遮挡 ≠ 可裁切**。做动效要用的对象必须保留完整几何，遮挡用 AE 轨道遮罩（Track Matte）实现，不能预先裁掉。
4. **锚点 = 对象中心**：图片层裁掉透明边后，锚点取素材宽高的一半；文本层锚点取 `sourceRectAtTime` 包围盒中心（本机 AE 2026 实测可用；脚本指南未列该 ExtendScript 方法）。
5. **Figma 转曲文字不用 OCR**：本批 SVG 的 `<text>` 数量为 0，但每个 path 的 `id` 属性就是原文，按字节解码即可拿到准确文本。
6. **AE 文本必须显式设 `direction = LEFT_TO_RIGHT`**，否则按 RTL 基方向排版，`?`、`…` 等标点会被双向算法换位、左对齐失效。
7. **字重/灰度用墨量（alpha 积分）比对校准**，不要凭肉眼：源文本是 80% 不透明黑字，AE 用图层 Opacity=80；提问气泡是更轻的 45 Light 字重。

> 边界：本页只证明「本工程的批处理路线不适合直接入 SVG」，不证明 AE 原生合成导入不可用；UI 路线的批量还原度未验证，标为暂未验证。

## 场景

- 设计稿是多帧 HMI 界面（5120×1600），需要在 AE 里做转场、卡片进出、文字逐条出现等动效。
- 甲方/设计给的是 Figma 导出的 SVG：文字转曲、图层名是 `Group 2090052246` 这类无语义名，但保留了 `id` 原文。
- 要求：导入 AE 后分组可读、可单独做动画；静态帧与源 SVG 像素级一致。

## 做法

### 0. 依赖与目录

```text
python -m pip install playwright pillow numpy
python -m playwright install msedge   # 或使用系统已装 Edge：channel="msedge"
```

目录约定（示例；`work/` 是临时目录，实际路径任意）：

```text
project/
├── Figma_UI_20frames.aep            # 交付工程
├── assets/<帧名>/*.png              # 裁边后的分层素材
└── assets/manifest.json             # 画布/帧/层清单
work/
├── wrap/*.html                      # SVG 包一层 html（viewport=画布尺寸）
├── out/<帧名>/*.png                 # 未裁边的整画布透明层
└── *.py / *.jsx / *.ps1             # 渲染、组装、验收脚本
```

### 1. 语义分组规则

在浏览器里先算每个顶层组的 `getBoundingClientRect()`，再按规则归类（顺序即优先级）：

| 分组 | 判定（示意） | 说明 |
|---|---|---|
| `BG` | 顶层 `<rect>`、`#bg`、`#asr`、Mask group | 背景/光晕，合成最底层并锁定 |
| `TOP` | `bb.top < 250 && bb.bottom < 400` | 顶栏；再按 x 空隙拆左右簇 |
| `BOTTOM` | `bb.top >= 1400` | 底栏；同样按空隙拆簇 |
| `MUSIC` | id 含 `music` 或内含 `g#music` | 完整卡片，不预裁 |
| `MATTE` | 音乐卡外的渐变矩形 | 单独出层，作为 MUSIC 的轨道遮罩 |
| `MAP` / `CARD_AC` / `CARD_RANGE` | `#navi` / 含「外循环」 / `#car` | 内容卡片 |
| `ASSIST` | `#Group 2090052246` 等 | 语音助手，内部文字单独拆 |
| `WEATHER` / `CLOCK` / `PANEL` | 按 id 或区域 | 其余语义块 |

命名统一为 `[模块] 中文名`，并给 AE 图层标签色（背景 8、文本 12、遮罩 14 等），便于时间线扫读。

### 2. 浏览器隔离渲染（核心）

1. 把 SVG 原文去掉 XML 声明，包进固定 `viewport = 5120×1600` 的 HTML；`html,body{margin:0;background:transparent;overflow:hidden}`。
2. 等所有 `<img>` `decode()` 完成，避免截图时图片未加载。
3. 隔离某组：给「目标节点 + 其祖先链」以外的所有兄弟节点打 `display:none`，目标组整棵子树保留。
4. `page.screenshot(omit_background=True)` 得到整画布透明 PNG；位置与最终合成一一对应，**不需要在 AE 里再对位**。
5. 文字拆分同理：给文字 path 打 `data-text-split`，渲染所属模块前统一隐藏；再单独渲染每条文字，用于和 AE 文本层做比对。

要点：不要用 `svg` 的 `viewBox` 缩放截图，保持 1:1 像素；否则裁边中心和 AE 位置会引入舍入误差。

### 3. 跨度过大的栏位按空隙拆簇

顶栏、底栏在 SVG 里是**一个组**，但左右元素相距几千像素（本例顶栏 4931px、底栏 4898px），整层锚点没有意义。做法：

- 收集该组的直接子对象包围盒，按 x 排序；
- 相邻对象的水平空隙 **> 300px** 即断簇；
- 每簇单独出层（`TOP_L` / `TOP_R`、`BOTTOM_L` / `BOTTOM_R`），各自裁边居中。

本例结果：`TOP_L 120×120 @ (160,108)`、`TOP_R 659×169 @ (4701.5,129.5)`、`BOTTOM_L 160×77 @ (191,1508.5)`、`BOTTOM_R 85×76 @ (4966.5,1508)`。

### 4. 裁透明边 + 居中锚点

```python
a = np.asarray(im)[..., 3]
ys, xs = np.where(a > 0)
x0, y0, x1, y1 = xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
im.crop((x0, y0, x1, y1)).save(dst)
center = ((x0 + x1) / 2.0, (y0 + y1) / 2.0)
```

AE 里：`Position = center`，`Anchor Point = [w/2, h/2]`（即素材几何中心）。这样缩放、旋转、位移都以对象自身为中心，不会绕画布原点。

### 5. 文本层还原（不识别、不描摹）

1. **取原文**：从 SVG `path[id]` 解出 UTF-8。Figma 把原文按 UTF-8 字节写进 id，读取时被当成 Latin-1；要按 `&#\d+;` 解析成字节再 `TextDecoder('utf-8')`。**不要用 `html.unescape`**：HTML5 会把 `&#154;` 映射成 CP1252 的 U+0160，导致乱码。
2. **建层**：`comp.layers.addText()`；设 `font`、`fontSize`、`fillColor`、`applyFill`、`tracking`、`leading`，再 `td.setValue(doc)`。
3. **方向**：`doc.direction = ParagraphDirection.DIRECTION_LEFT_TO_RIGHT` + `justification = LEFT_JUSTIFY`；AE 24+ 可读写，本机实测读回 `direction=10212`。
4. **居中锚点**：`sourceRectAtTime(0,false)` 求包围盒中心，写入 Anchor Point，再把 Position 设为目标中心。
5. **颜色/透明度**：黑字 + 源 `opacity=0.8` → `fillColor=[0,0,0]` + 图层 Opacity=80；蓝色按钮字 `rgb(0,98,255)`、100%。

### 6. AE 无头组装与渲染

- 启动：`Start-Process AfterFX.exe -ArgumentList @('-noui','-r',$jsx)`；脚本末尾 `app.project.save()` 并写日志 `saved`。
- 判读：只轮询日志出现 `saved` / `ERR `；出现退出确认弹窗时用 `WScript.Shell.SendKeys('{ESC}')` 关掉。
- 渲染校验：`aerender -project x.aep -comp "01_C4-3" -s 0 -e 0 -OMtemplate "_HIDDEN X-Factor 8" -output out.png`；本机实测实际文件名会追加 `00000`，需改名。
- 轨道遮罩：遮罩层放在被遮对象**正上方**，`layer.trackMatteType = TrackMatteType.ALPHA`；遮罩层本身可随时关闭，完整卡片仍在。

### 7. 验收（两把尺子）

1. **像素 diff**：AE 渲染帧 vs 浏览器整帧 `FULL.png`，看 mean / max / 超阈值像素占比。
2. **文本墨量比**：文字区域 alpha 积分 `inkAE / inkREF`，越接近 1 字重越准；同时看最佳平移量（应为 dx=dy=0）。

本工程 01 帧结果：

| 指标 | 数值 |
|---|---|
| 整体 mean / max | 0.4777 / 255，max 209 |
| 像素差 >8 / >32 | 0.2857% / 0.2382% |
| 提问 / 回复 / 执行 区域 mean | 9.919 / 18.525 / 9.625 |
| 墨量比（提问/回复/执行） | 1.028 / 1.046 / 1.018 |
| 最佳平移 | 三处文本均 dx=0, dy=0 |

残差集中在文字笔画抗锯齿，无布局/对象级差异。其余 19 帧按本页规范重做后复验结果：mean 0.068–0.680/255；02–05 含文本层（mean 0.500–0.680、max 209，文本行位置与参考相差 ≤1px，墨量比 1.03–1.05），06–20 纯图片层（mean 0.068–0.304、max ≤43）。唯一可见残差在 06/08/09 顶栏右侧的半透明气泡（06/08 max 43、09 max 34，>8 像素 0.85–0.87%），原因是该组内含 `mix-blend-mode: hard-light`，隔离渲染后失去与背景的混合上下文；肉眼不可辨，若需严格一致只能连同背景烘焙（会牺牲该层可动画性），故保留。

## 坑

一坑一条：症状 → 根因 → 规避。

| # | 症状 | 根因 | 规避 |
|---|---|---|---|
| 1 | 脚本批量导入 SVG 失败、没有语义分层/文本 | 本机 AE 2026 对 SVG 设置 `importAs = FOOTAGE/COMP` 抛错，默认 `importFile` 返回 `null`；UI 的导入选项不等于脚本接口 | 先做 `canImportAs` / `importFile` 探针；批处理改浏览器隔离渲染透明 PNG |
| 2 | 文本 `?` 跑到句首、`…` 位置不对、第二行整体右对齐 | AE 文本按 RTL 基方向排版，双向算法重排边界标点 | `doc.direction = ParagraphDirection.DIRECTION_LEFT_TO_RIGHT`，再设左对齐 |
| 3 | 调 `doc.tracking` 字宽几乎不变 | AE 对亚像素字距做量化，`tracking=10` 时宽度仅差 0.5px | 用 `fontSize` 微调（本例 40→40.6 补齐 6px 宽差） |
| 4 | AE 文字比源图明显更粗 | 源文本是 80% 不透明黑字，AE 默认 100% | 图层 Opacity=80；不要靠改字重去凑 |
| 5 | 提问气泡同字号仍偏粗 | 源文件用的是更轻的 45 Light 字重 | 安装 Alibaba PuHuiTi 2.0 45 Light（PostScript 名 `AlibabaPuHuiTi_2_45_Light`） |
| 6 | 官方字体 CDN 403 | 缺 Referer/UA 校验 | 请求头带 `Referer: https://www.alibabafonts.com/` + 浏览器 UA |
| 7 | 从 path id 解出的中文乱码 | Figma 把 UTF-8 字节写进 id，按 Latin-1 读出；`html.unescape` 还会做 CP1252 重映射 | 手动解析 `&#\d+;` 为字节 → UTF-8 解码 |
| 8 | 音乐卡被渐变遮罩裁掉，动效没素材 | 静态截图时把遮挡「烘焙」进素材 | 卡片出完整层 + 独立遮罩层（轨道遮罩），遮罩随时可关 |
| 9 | 脚本删图层报错 | 背景层被锁定 | 先 `layer.locked = false`，再 `remove()` |
| 10 | `-OMtemplate` 传中文模板名无效 | 本机 aerender 命令行只认英文模板名 | 用 `_HIDDEN X-Factor 8`（本机输出模板名） |
| 11 | aerender 输出文件名多出 `00000` | aerender 对静帧自动加帧号 | 渲染后统一改名 |
| 12 | 无头 AE 跑完不退出、后续任务被阻塞 | 保存后弹退出确认框 | 轮询日志 `saved` → `SendKeys('{ESC}')` → 结束进程 |
| 13 | 整条顶栏/底栏一个图层，缩放时左右乱飞 | 组跨度 4900px，几何中心落在中间空白 | 按 x 空隙 >300px 拆簇，每簇独立裁边居中 |
| 14 | 文本包围盒取错，文字位置整体偏移 | 先设 Position 再取 `sourceRectAtTime` | 先 `setValue` 文本，再取包围盒中心设锚点，最后设 Position |
| 15 | 同一文字层换字体后宽度变化，居中失效 | 字宽随字体变化，锚点未重算 | 字体/字号定稿后再算锚点；或每次重建都重跑居中逻辑 |
| 16 | 半透明气泡单独出层后整体偏亮约 8–10 级 | 组内用了 `mix-blend-mode: hard-light`，隔离渲染时失去与背景的混合上下文 | 肉眼不可辨时保留；要求严格一致就与背景一起烘焙（该层不可单独动画） |

## 实现说明

本页的流水线来自一个工程实例：渲染、拆簇、裁边、AE 组装、像素验收各有一段一次性脚本（Python / JSX / PowerShell），脚本与工程路径绑定，未随仓提供。可复用的是方法与判据，不是代码；如果要复用，按上面的步骤重写，并把路径、画布尺寸、分组规则参数化。

## 参考来源

- Adobe 帮助中心「Import SVG files」（footage / 合成两种导入方式）：<https://helpx.adobe.com/after-effects/desktop/import-files/import-svg-files/import-svg-files.html>
- Adobe After Effects Scripting Guide（TextDocument / AVLayer / ImportOptions）：<https://ae-scripting.docsforadobe.dev/>
- Adobe 表达式语言参考（`sourceRectAtTime`）：<https://helpx.adobe.com/after-effects/using/expression-language-reference.html>
- Playwright `page.screenshot`（`omit_background` 透明截图）：<https://playwright.dev/python/docs/api/class-page#page-screenshot>
- MDN `mix-blend-mode`（`hard-light` 的混合语义）：<https://developer.mozilla.org/en-US/docs/Web/CSS/mix-blend-mode>
- 阿里巴巴普惠体官方字体站（字重与下载）：<https://www.alibabafonts.com/>
