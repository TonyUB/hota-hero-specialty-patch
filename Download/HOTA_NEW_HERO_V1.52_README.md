# HOTA_NEW_HERO_V1.52

正式发布日期：2026-08-24

适用版本：HotA 1.8.0 中文本地环境

SHA-256：`8f29a5d0b61ac8ce0fb1b4ec73b95686559aeb0ef54c4807be6c7f61c99cf2e3`

## 中文摘要

V1.52 以正式 V1.51 为唯一父输入，将奥蕾加寻宝术改为五档奖励：四等奖 / 三等奖 / 二等奖 / 一等奖 / 特等奖概率为 `59% / 25% / 10% / 5% / 1%`，金币为 `350 / 500 / 1000 / 2000 / 4000`。普通四档按 HotA 原生宝物类型动态筛选，特等奖使用 17 项固定池。

连续 12 次未获一等奖或特等奖时，第 13 次固定一等奖；连续 28 次未获特等奖时，第 29 次固定特等奖，大保底优先。奖励窗口显示 `保底：小XX/12，大XX/28`。真正挖出原版圣杯时完整保留原生圣杯流程，并跳过当天寻宝术的方尖塔、奖励和保底结算；实际获得特等奖宝物时播放原生圣杯音效。

安装时把 ZIP 内文件按原目录结构覆盖到独立的 HotA 1.8.0 测试副本。请勿将本包与其他修改同一可执行文件的补丁混装。

## English Summary

V1.52 uses formal V1.51 as its sole parent. Orega's Treasure Hunt now has five reward tiers at `59% / 25% / 10% / 5% / 1%`, paying `350 / 500 / 1000 / 2000 / 4000` gold. The four normal tiers are selected dynamically from native HotA artifact types, while the special tier uses a fixed 17-artifact pool.

After 12 digs without a first or special prize, dig 13 is forced to first prize. After 28 digs without special prize, dig 29 is forced to special prize, with large pity taking priority. The reward window reports both counters. A genuine native Grail dig keeps the native Grail flow and skips Treasure Hunt's Obelisk, reward, and pity settlement for that day; an actual special-prize artifact plays the native Grail sound.

Extract the ZIP into a separate HotA 1.8.0 test copy while preserving its directory layout. Do not combine it with another patch that edits the same executables.
