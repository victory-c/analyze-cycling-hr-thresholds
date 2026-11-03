# Connect IQ Store listing

Paste these into the Connect IQ developer dashboard when uploading
`bin/HrThresholds.iq`. Icon: `store/store_icon.png` (500×500).

## App name

- English: HR Thresholds
- 简体中文: 心率阈值

## Category

Data field · Cycling

## Short description (English)

Live heart-rate zones from your own VT1 and cycling LTHR, time below VT1, and
your best 20/30/40/60-minute HR — the evidence you need to check your threshold.

## Description (English)

HR Thresholds turns two numbers you already trust — your aerobic threshold
(VT1) and your cycling lactate-threshold heart rate (LTHR) — into a data field
that tells you where you are and what the ride actually did.

**On screen**
- Current HR with a colour-coded zone badge (Z1–Z5).
- A three-segment bar of time below VT1, between VT1 and LTHR, and at or above
  LTHR. Riding a base block? Watch the blue segment.
- Best continuous 20, 30, 40 and 60-minute average HR so far, with the gap to
  your LTHR (for example `181 (-7)`).

**Saved to your activity**
Best 20/30/40/60-minute HR and the three time-in-domain percentages are written
to the FIT file and appear in the Garmin Connect activity summary.

**Zone model**
Zones use a transparent dual-threshold split instead of percentages of max HR:

- Z1 up to floor(0.90 × VT1)
- Z2 up to VT1 − 1
- Z3 VT1 up to floor(0.90 × LTHR)
- Z4 up to LTHR − 1
- Z5 LTHR and above

Only VT1 and LTHR are physiological anchors; the 90 % splits are operational.

**Setup**
In Garmin Connect (or Connect IQ) open the field's settings and enter VT1 and
LTHR in bpm. Until both are set, the field colours HR by your Garmin cycling
zones and does not guess thresholds for you.

**How best windows are measured**
Short HR dropouts (up to 12 s by default, configurable) are linearly
interpolated. Longer gaps or pauses end the window, so a coffee stop never
counts as part of a "best 60 minutes". Best windows are candidate evidence, not
a threshold diagnosis — check terrain, heat, drift and repeatability across
rides before changing LTHR.

Open source, with the full analysis method:
https://github.com/victory-c/analyze-cycling-hr-thresholds

## 简体中文描述

心率阈值数据字段：用你自己的 VT1（有氧阈）和骑行乳酸阈心率 LTHR，实时显示心率区间，
统计 VT1 以下 / VT1–LTHR / LTHR 以上三个生理区的时间占比，并记录本次骑行最佳连续
20/30/40/60 分钟平均心率及其与 LTHR 的差值。结果同时写入 FIT 文件，在 Garmin Connect
活动摘要中可见。

在 Garmin Connect 的数据字段设置中填写 VT1 和 LTHR 即可使用；未设置时按 Garmin
骑行心率区间着色，不会替你猜测阈值。最佳窗口只是候选证据，改 LTHR 之前请结合地形、
温度、心率漂移和多次骑行的一致性来判断。

## What's new (1.0.0)

First release.

## Permissions shown to users

- Fit Contributor — write best-window HR and time-in-domain to the activity.
- User Profile — read Garmin cycling HR zones as a fallback before setup.
