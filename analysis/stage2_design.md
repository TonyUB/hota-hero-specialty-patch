# Patch_v2.4_STAGE2_TEST 设计与静态验证

状态：**Stage 2 已通过实机门禁；正式 `Patch_v2.4` 已移除诊断日志。**

## 已通过的前置门禁

`Patch_v2.4_diag01` 实机日志共有 15 条有效记录，尤兰德 `0x19` 与阿斯特拉 `0xAA` 均命中单体和群体 Cure 包装器；所有 `overflow` 都等于 `max(0, -signed(EAX))`。详情见 `diag01_runtime_validation.md`。

## 功能范围

Stage 2 只处理：

- 施法英雄为尤兰德或阿斯特拉；
- Cure 目标仍有至少一个单位存活；
- Cure 后出现实际治疗溢出；
- `numberAlive < numberAtStart`，即兵队确有阵亡。

不处理全灭尸体，也不扩展高级水系群体 Cure 的尸体扫描。

## 包装器顺序

```text
原生 CureCore
  → 保存 EAX/ECX/EDX/EFLAGS
  → overflow = max(0, -signed(EAX))
  → 检查仍存活且确有阵亡
  → manager->GetResurrectionTarget(side, target->hex, context=0)
  → 要求返回指针 == 当前 Cure 目标
  → manager->ResurrectTarget(target, overflow, temporary=0)
  → 恢复原生 Cure 的返回寄存器、标志位与栈约定
```

调用参数来自 HotA 1.8.0 原生 Resurrection 分支：

- `target->hex`：`[target+0x38]`；
- 当前施法方：`[manager+0x132C0]`；
- `GetResurrectionTarget` 第三参数：`0`；
- `ResurrectTarget` 的 `temporary`：`0`。

包装器不直接写 `numberAlive`、`healthLost` 或 `numberForeverDead`。原生资格验证负责亡灵、元素、构装体及其他 Resurrection 限制，原生复活函数负责数量上限、剩余生命、动画和战后永久性数据。

## 载荷布局

| 区域 | VA | 长度 |
|---|---:|---:|
| Stage 2 代码 | `0x00639D80` | 441 字节 |
| 日志模板/文件名/十六进制表结束 | `0x00639FFB`（末地址不含） | 总载荷 635 字节 |

已知原始非零边界从 `0x00639FFD` 开始，载荷保留 `0x00639FFB–0x00639FFC` 两个零字节，不覆盖节区尾部数据。两个 Cure call 分别从 `0x005A1B05`、`0x005A1BB4` 重定向到包装器。

## 输出

```text
Patch_v2.4_STAGE2_TEST.zip
SHA-256 bcb0a61265b68825ca151b82567fd261d57d49c20d7040ea09ab67b107e3f2bd

h3hota.exe
SHA-256 d712654471b06e6cf36e2cd5209e6f4ea744ab32af7d75ee08813b0334016bd2

h3hota HD.exe
SHA-256 4b03cae3868cbe161e8063883bfccb2967a7937f4c89e2c8b11584609d6ddbec
```

静态验证包括输入哈希、机器码调用序列、PE 大小、其他 10 个文件不变、完整回滚重建、12 个 ZIP 成员和 CRC。用户回传的 HD 版日志与截图已证明两名英雄的单体/群体复活数量和原生动画正确；随后又确认新增单位战后保留，且亡灵只治疗、不复活。详情见 `stage2_runtime_validation.md`、`stage2_visual_validation.md`、`stage2_undead_runtime_validation.md` 与 `stage2_release_acceptance.md`。

正式版 `Patch_v2.4` 使用相同的资格校验和 `temporary=0` 原生复活机器码序列，删除测试日志模板、文件名和 Windows 文件 I/O，包装器缩减为 206 字节。
