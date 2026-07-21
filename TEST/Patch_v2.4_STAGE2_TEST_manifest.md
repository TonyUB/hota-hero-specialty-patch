# Patch_v2.4_STAGE2_TEST 构建清单

状态：**Stage 2 实机测试版，仅处理仍有存活单位的兵队。**

该版本从唯一可信的 `Patch_v1.8` 构建：先完整执行原生 Cure；仅当治疗量溢出、目标确有阵亡且通过原生 Resurrection 资格验证时，调用原生永久复活函数。

- ZIP SHA-256：`bcb0a61265b68825ca151b82567fd261d57d49c20d7040ea09ab67b107e3f2bd`
- 包内文件数：12
- 包装器 VA：`0x00639D80`
- 载荷长度：635 字节
- 运行日志：`hota_cure_stage2.log`

## EXE 输出哈希

| 文件 | 输入 SHA-256 | 输出 SHA-256 | 精确差异区间数 |
|---|---|---|---:|
| `h3hota.exe` | `3a2de7000a79040c42633dcd512ee76e5568bad260622f5cac8a8c7f6512abf6` | `d712654471b06e6cf36e2cd5209e6f4ea744ab32af7d75ee08813b0334016bd2` | 51 |
| `h3hota HD.exe` | `7c3c6deca0c3afbb2e751512feefc65da5c5ea47536f337264e1a6cc6da826c2` | `4b03cae3868cbe161e8063883bfccb2967a7937f4c89e2c8b11584609d6ddbec` | 51 |

## 功能顺序

1. 非尤兰德/阿斯特拉、非英雄施法或无存活单位目标直接尾调用原生 Cure。
2. 目标英雄先执行原生 Cure，保留清除负面状态、治疗和原生特长缩放。
3. 只使用原生 Cure 返回的负值绝对值作为溢出量。
4. `numberAlive < numberAtStart` 时，按当前格子与施法方调用 `GetResurrectionTarget(..., context=0)`。
5. 验证返回指针与当前 Cure 目标完全一致。
6. 调用 `ResurrectTarget(target, overflow, temporary=0)`，不直接写兵队字段。

## 静态安全验证

- 两个 EXE 的单体/群体 Cure call 均反汇编为包装器目标。
- 机器码包含原生资格验证调用及 `push 0` 的永久复活调用序列。
- `EAX/ECX/EDX/EFLAGS`、非易失寄存器和原始 `ret 0x0C` 栈约定均恢复。
- 两个 EXE 大小不变，其他 10 个包内文件不变，完整回滚可重建输入。
- ZIP CRC 与 12 文件结构已验证。静态检查不能替代游戏内数量与战后永久性测试。
