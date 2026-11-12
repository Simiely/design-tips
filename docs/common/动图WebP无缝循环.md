---
id: docs.common.webp-seamless-loop
title: 动图 WebP 无缝循环重制（设计资产逆向）
summary: 从"填满即重置"的动图 WebP 反推几何与配色，用程序重画成数学上无缝的循环：探针读参 → SDF 重绘 → 接缝量化验收。
type: how-to
kind: note
status: active
owner: "@simiely"
tier: normal
topics: [design, automation]
source_type: code
source: scripts/common/loop_webp.py
last_reviewed: 2026-11-12
related: []
---
# 动图 WebP 无缝循环重制（设计资产逆向）

> 适用环境：Windows 11 + Python 3 + Pillow 13.0.0（自带 libwebp）；2026-11-12 用两套真实资产（212×212，深/浅配色）跑通。
> 目标：交付的动图 WebP 是"播一次、填满即重置"，要改成**无限循环**，而**画布、时长、配色都不许变**；且不重做关键帧。

工具：`scripts/common/loop_webp.py`（`probe` / `make` / `check` 三个子命令）。

## 场景

- 动图 `loop=0` 但实际**不循环**：弧长涨到满圆后硬切回小弧，播放时看得见"抽一下"。
- 只有导出的 webp、没有源工程，却要按另一套配色或尺寸重出同一动效。
- 要把"看起来在转圈"的动效换成 Apple 风格的不确定进度指示（前缘匀速 + 后缘弹性跟随）。

**不适用**：位图插画、实拍、复杂形变 —— 回原工程或逐帧处理，别用代码重画。

## 做法

### 一、先量，别猜

```bash
python scripts/common/loop_webp.py probe in.webp
```

真实输出（212×212 深色资产）：

```text
canvas 212x212 / frames 72 / total_ms 9000 / cycle_frames 72
centre (106.0, 106.18) / radius 54.00 / stroke 9.64
fg (252,250,248) / track (239,239,239) / track_alpha 15
step_mean 86 / step_max 3075 / reset_at 62
NOTE frame 62 is a hard reset (step 3075 vs mean 86) -> not a loop
```

四个读数各自决定后面一步：

| 读数 | 决定了什么 |
|---|---|
| `radius` / `stroke` | 重画时的几何，必须与原图一致（`stroke` 用 alpha 0.5 交叉点算，不是目测） |
| `fg` / `track` / `track_alpha` | 两层颜色；轨道环通常只有 6% 不透明度 |
| `total_ms` / `cycle_ms` | 输出时长；`cycle_ms < total_ms` 说明是"同一段重复 N 次"，要取单周期 |
| `step_max / step_mean` | > 3 就是"填满即重置"，即待修的那处 |

几何与颜色都靠**亚像素**取，不靠肉眼：

- 取覆盖最满的一帧，按 1° 分箱在半径方向找 alpha 的 0.5 交叉 → 外沿/内沿；
- 弧不满整圆时质心会偏，所以每轮用 **Kasa 圆拟合**（过各角度描边中点）修正圆心，迭代 3–4 次收敛；
- 颜色分层：`alpha ≥ 200` 取主体色；`alpha 5–60` 且落在圆环中心线上的取样取轨道色与 alpha。

### 二、重画：解析式描边 + 无缝参数

```bash
python scripts/common/loop_webp.py make in.webp -o out.webp --ms 3000 --turns 3 --cycles 1
```

描边用**有符号距离场**渲染：圆头端点 = `min(|ρ − R|, 到两端帽圆心的距离)`，再减半个描边宽得到有符号距离，4× 超采样后盒下采样。边缘是可预期的亚像素精度，不是滤镜糊出来的。

运动模型（两个同余条件，缺一就有缝）：

```text
前缘  θ(t) = start + 360 · turns · t              匀速 → 读作稳转
弧长  L(t) = lmin + (lmax − lmin) · (0.5 − 0.5·cos(2π · cycles · t))
后缘      = θ(t) − L(t)                            弹性跟随
```

- **`turns` 与 `cycles` 必须是整数** → t=0 与 t=1 的状态完全重合，接缝从数学上消失；
- **`360·turns − (lmax−lmin)·π·cycles ≥ 0`** → 后缘角速度不为负，弧不会往回缩（工具会 `WARN` 并打印差值）；
- `lmax` 别给到 360°：留缺口才读作"进行中"，满圆会被读成"已完成"。

时长写进帧时长列表，用 `round(总时长·i/n)` 做差分：180 帧 @60fps → 16/17 ms 交替，合计精确 3000 ms；直接写 `duration=33` 会得到 2970。

编码参数：`save_all + lossless=True + exact=True + method=6 + minimize_size=True`。libwebp 会做帧间差分，几何图形 180 帧只有 77–83 KB（比有损源还小）。

### 三、验收：只看两个数

```bash
python scripts/common/loop_webp.py check out.webp --src in.webp
```

```text
frame step  mean 0.27  max 0.36 at frame 135
SEAM        0.28  (1.01x mean step)
VERDICT     LOOP OK: wrap is indistinguishable from a normal frame step
```

判据：

- **接缝 / 普通帧步长 ≈ 1.0** → 接缝与普通帧无差别，肉眼无法察觉；
- **`max` 不超过均值 3 倍** → 片中也没有别的硬切（只看接缝会漏掉片中重置，见坑⑥）；
- `--src` 顺带核对几何是否与原稿同尺寸：`R 54.00 vs 53.98 → geometry matches`。

实测（2026-11-12，同一 212×212 画布，两套配色）：

| 指标 | 源（非循环） | 重制·深色 | 重制·浅色 |
|---|---|---|---|
| 帧数 / 总时长 | 72 / 9000 ms | 180 / 3000 ms | 180 / 3000 ms |
| 帧步 mean / max | 0.26 / **8.38**（第 62 帧，33×） | 0.27 / 0.36 | 0.19 / 0.25 |
| 接缝 / 均值 | 0.41×（假 OK，真断点在片中） | **1.01×** | **1.01×** |
| 体积 | 121 KB | 77 KB | 83 KB |

## 坑

**① Pillow 读不到动图帧时长。**
症状：`im.info['duration']` 全是 `None`，按默认值重编码后总时长对不上。
根因：Pillow 的 WebP 解码器不暴露 ANMF 帧头。
规避：自己解析 RIFF——ANMF 块内偏移 12..14 是三字节帧时长，ANIM 块偏移 4..5 是 loop 次数。

**② 接缝指标被"透明像素的 RGB"污染。**
症状：某几帧的 diff 突然是其他帧的 10 倍，但画面看着完全一样。
根因：libwebp 在关键帧会还原（或清零）`alpha=0` 处的 RGB，逐像素比 RGBA 会把这当成画面变化。
规避：先按 alpha 合成到中灰再比（工具内 `on_background()`），比的是"渲染出来的样子"。

**③ 轨道环那一层漏乘自己的覆盖率。**
症状：整张画布蒙一层 6% 白纱，环反而失去对比，角落 alpha ≠ 0。
根因：写成 `alpha = 弧 + 6%·(1 − 弧)`，只用弧的覆盖率去调轨道。
规避：轨道单独算覆盖率再乘；验收时加一条断言——画布角落 alpha 必须为 0。

**④ 后缘倒退，看着像弧在往回缩。**
症状：转动中弧长忽长忽短还带反向。
根因：`360·turns < (lmax−lmin)·π·cycles`，旋转追不上弧长变化速度。
规避：提高 `turns` 或降低 `lmax`；工具在 `make` 时会 WARN 并给出差值。

**⑤ 从有损源读出的轨道色是噪声。**
症状：`probe` 报 `track (239,239,239)`，而设计 token 是 `#FCF9F7`（另一个配色同理）。
根因：6% 不透明度区域被有损编码量化，alpha 稳定但 RGB 抖动 ±3 级。
规避：合成到背景后差异 ≤1/255，肉眼不可见；要精确就 `--track R G B` 传设计值。

**⑥ 源是"同一段重复 N 次"的导出，或反之是"单次播放"。**
症状：源 9000 ms，视觉周期其实 3 s；直接继承总时长会得到慢 3 倍的循环。
根因：输出时长默认跟随源总时长，而源时长与设计上的单周期不一定相等。
规避：`probe` 报的 `cycle_frames` / `cycle_ms` 是**覆盖度曲线的最小重复块**——它 `< frames` 时直接用；本例源是"单次播放 + 重置"，覆盖度一直单调增长，所以它等于总长（72 / 9000 ms），单周期得按设计稿判断后用 `--ms` 指定。

## 边界

- 只收**纯几何**资产（圆环、线段、单色形）。有纹理、渐变、模糊、位图的一律回原工程。
- 换尺寸只改 `--canvas/--radius/--stroke`，别按"看起来差不多"的比例猜：本次两套源在同一 212 画布上环径分别是 54 与 67.5。
- 同一份几何 + 只换配色时，先出深色版再用 `--fg/--track` 换色，可保证两版 alpha 通道逐帧完全一致。

## 参考

- Pillow WebP 保存选项（`duration` 列表 / `loop` / `lossless` / `exact` / `minimize_size`）：<https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html#webp>
- libwebp `WebPAnimEncoder`（帧间差分与关键帧策略）：<https://developers.google.com/speed/webp/docs/api>
