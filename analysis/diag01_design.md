# Patch_v2.4_diag01 设计与静态验证

状态：**已构建；仅诊断，不复活；等待实机日志。**

## 设计

在 `Patch_v1.8` 两个 EXE 中分别将以下 5 字节调用重定向到同一包装器：

| 来源 | 调用点 | 原始目标 | 包装器 |
|---|---:|---:|---:|
| 单体 Cure | `0x005A1B05` | `0x00446220` | `0x00639D80` |
| 群体 Cure 存活兵队循环 | `0x005A1BB4` | `0x00446220` | `0x00639D80` |

包装器只对以下条件写日志：

- `casterHero != nullptr`；
- `[casterHero+0x1A]` 为尤兰德 `0x19` 或阿斯特拉 `0xAA`；
- `[target+0x4C] numberAlive > 0`。

不满足条件时直接尾调用原生 CureCore。满足条件时完整调用一次原生 CureCore，保存其 `EAX/ECX/EDX/EFLAGS`，写日志后逐项恢复，再以 `ret 0x0C` 返回；`EBX/ESI/EDI/EBP` 和栈平衡也保持原调用约定。

## 日志格式

日志写入游戏根目录的 `hota_cure_diag01.log`，每行固定 150 字节：

```text
HOTA_DIAG01 src=S spell=37 hero=00000019 target=00000000 alive=00000000 start=00000000 lost=00000000 eax=00000000 overflow=00000000 manager=00000000
```

除 `src` 与 `spell` 外，数值均为 8 位大写十六进制。`src=S` 表示单体，`src=M` 表示群体循环。`eax` 保留原生 Cure 的 32 位返回位型；当它为负数时，`overflow=-eax`，否则 `overflow=0`。

## 静态验证结果

- 构建输入严格逐项核验 `baselines/Patch_v1.8_SHA256.txt` 的 12 个哈希。
- 两个 EXE 的调用点均重新反汇编为 `call 0x00639D80`。
- 包装器代码 377 字节；代码、间隙、模板和字符串共占 603 字节，结束于 `0x00639FDB`（末地址不含）。
- 两个 EXE 文件大小不变；另外 10 个包内文件哈希不变。
- 载荷中不存在 `0x005A3FD0` 或 `0x005A7870` 字面量，因此不会调用资格验证或复活函数。
- 完整逻辑修改区的回滚字节可逐字节重建两个输入 EXE。
- ZIP 为原 12 文件结构，CRC 完整性测试通过。

## 构建输出

```text
Patch_v2.4_diag01.zip
SHA-256 210a542f140be64606f4b5af3b3768025f5badf3c3061ce0f5e07ff37d63cf40

h3hota.exe
SHA-256 df015751dd95371c867c67c963baec54ea70abf433d5f4d22a363bdf1b2f9e51

h3hota HD.exe
SHA-256 ffc40b2d071711d86919079c72e92b8b0dd0ac9776494ac98876c7c47c3cd6f7
```

完整输入/输出哈希、精确差异区间以及原始/修改/回滚字节由构建器写入 `output/Patch_v2.4_diag01_manifest.json`。静态验证不能证明游戏运行时实际执行该包装器。
