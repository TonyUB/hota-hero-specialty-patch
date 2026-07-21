# Patch_v2.4_diag01 构建清单

状态：**仅诊断，不含任何复活调用。**

该版本从唯一可信的 `Patch_v1.8` 构建，保持两个 EXE 大小不变；仅重定向单体/群体 Cure 的两个调用点，并在既有 `.text` 零填充区写入诊断包装器。

- ZIP SHA-256：`210a542f140be64606f4b5af3b3768025f5badf3c3061ce0f5e07ff37d63cf40`
- 包内文件数：12
- 包装器 VA：`0x00639D80`
- 载荷长度：603 字节
- 日志文件：`hota_cure_diag01.log`

## EXE 输出哈希

| 文件 | 输入 SHA-256 | 输出 SHA-256 | 精确差异区间数 |
|---|---|---|---:|
| `h3hota.exe` | `3a2de7000a79040c42633dcd512ee76e5568bad260622f5cac8a8c7f6512abf6` | `df015751dd95371c867c67c963baec54ea70abf433d5f4d22a363bdf1b2f9e51` | 45 |
| `h3hota HD.exe` | `7c3c6deca0c3afbb2e751512feefc65da5c5ea47536f337264e1a6cc6da826c2` | `ffc40b2d071711d86919079c72e92b8b0dd0ac9776494ac98876c7c47c3cd6f7` | 45 |

## 逻辑修改区

两个 EXE 的逻辑修改位置相同；完整原始、修改及回滚字节见 JSON 清单。

| 位置 | 作用 | 长度 |
|---:|---|---:|
| `0x005A1B05` | single Cure call | 5 |
| `0x005A1BB4` | mass Cure call | 5 |
| `0x00639D80` | diagnostic-only wrapper, logger, and mutable ASCII template | 603 |

## 安全边界

- 包装器对非尤兰德/阿斯特拉、非英雄施法或无存活单位目标直接尾调用原生 Cure。
- 命中目标英雄后仍先完整调用原生 Cure，仅记录返回值；不调用 `GetResurrectionTarget` 或 `ResurrectTarget`。
- 静态检查已确认载荷不含 `0x005A3FD0`、`0x005A7870` 两个复活函数地址。
- PE 大小及其他 10 个包内文件保持不变。运行时是否真正命中仍须由用户实机日志确认。
