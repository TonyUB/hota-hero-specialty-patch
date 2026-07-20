# Cure 真实运行路径

状态：**静态路径已定位，运行时尚未验证**

本文件记录 `Patch_v1.8` 两个 EXE 中的静态证据。地址在标准版与 HD 版中相同，但在取得 DLL/patcher 和实机诊断日志前，不能断言运行时一定执行这些磁盘字节。

## 输入

| 文件 | SHA-256 |
|---|---|
| `h3hota.exe` | `3a2de7000a79040c42633dcd512ee76e5568bad260622f5cac8a8c7f6512abf6` |
| `h3hota HD.exe` | `7c3c6deca0c3afbb2e751512feefc65da5c5ea47536f337264e1a6cc6da826c2` |

两个 EXE 的 Cure、CastSpell、GetResurrectionTarget 和 ResurrectTarget 候选区域字节相同。整个文件只有 21 个不同字节，分布在 3 个区间；主要差异是标准版导入 `nullmss`，HD 版导入 `_hd3_.dll`，未落在本报告的 Cure/Resurrection 路径内。

完整 PE 清单、候选地址字节与静态直接引用见 `pe_inventory.md` / `pe_inventory.json`。

## 已定位的静态调用路径

```text
H3CombatManager::CastSpell                    0x005A0140
├─ 单体 Cure 分支
│  └─ call Cure core                         0x005A1B05 → 0x00446220
└─ 群体 Cure 的存活兵队循环
   └─ call Cure core                         0x005A1BB4 → 0x00446220

Cure core                                    0x00446220
├─ 清除一组负面法术                         call 0x00444230
├─ 计算基础治疗量 + spell power
├─ 若有英雄施法者，加入原生法术特长增幅     call 0x004E6260, spell ID 0x25
└─ healthLost = max(0, oldHealthLost - H)    0x0044632D

原生 Resurrection 分支                      0x005A1C17
├─ GetResurrectionTarget                     call 0x005A3FD0
└─ ResurrectTarget                           call 0x005A7870
```

静态直接引用扫描在两个 EXE 中均只发现两处对 `0x00446220` 的直接调用：`0x005A1B05` 和 `0x005A1BB4`。这让“统一 call 包装器”成为比修改 Cure 函数内部更局部的候选方案。

## CastSpell 上下文

`0x005A0140` 是 `thiscall` 风格的战斗管理器函数，入口将 `ECX` 保存到 `EBX`，因此以下两个 Cure 调用点的 `EBX` 均为战斗管理器指针。

在英雄施法路径中：

- `[EBP-0x14]` 是施法英雄对象；非英雄施法路径将其置零。
- `[EBP+0x1C]` 在进入法术分支前被改写为最终 spell power。
- `ESI` 在 Cure 分支中为当前水系熟练度/效果档位。
- `EDI` 是当前目标战斗兵队指针。
- Cure 的法术 ID 是 `0x25`（十进制 37）。

两处调用均以相同签名进入 Cure：

```cpp
int __thiscall CureCore(
    CombatCreature* target, // ECX
    int mastery,            // stack arg 1
    int spellPower,         // stack arg 2
    Hero* casterHero        // stack arg 3; null for non-hero cast
);
```

该签名仍是静态推断，但有以下指令证据：

```asm
; 0x005A1AFA，单体 Cure
push [ebp-0x14]     ; hero
push [ebp+0x1C]     ; spell power
push esi            ; mastery
mov  ecx, edi       ; target
call 0x00446220

; 0x005A1BA9，群体 Cure 循环中的存活兵队
push [ebp-0x14]
push [ebp+0x1C]
push esi
mov  ecx, edi
call 0x00446220
```

## CureCore 的关键性质：返回值已编码溢出量

`0x00446220` 先执行原生治疗与负面状态清除。最终治疗量保存在 `EDI`，目标原 `healthLost` 位于 `[target+0x58]`。

```asm
0044632D  mov eax, [esi+0x58]  ; old healthLost
00446330  sub eax, edi         ; old healthLost - final healing H
00446333  mov [esi+0x58], eax
00446336  jns 0x0044633F
00446338  mov [esi+0x58], 0    ; clamp target state, but EAX remains negative
00446343  ret 0x0C
```

因此函数返回时：

```text
EAX >= 0  → 没有治疗溢出
EAX < 0   → overflow = -EAX
```

这比重新计算治疗量可靠：`EDI` 在进入上述代码前已经包含基础值、spell power，以及 `casterHero->0x004E6260(spell=37, targetLevel, amount)` 的原生特长增幅。包装器无需复制乌兰德/阿斯特拉的缩放公式。

## 英雄身份静态证据

英雄对象的 ID 字段候选偏移为 `+0x1A`：

- 当前 Adela 零祝福消耗 Hook 在 `0x00639D40` 使用 `cmp dword ptr [ebx+0x1A], 9`，与 Adela ID 9 一致。
- `CastSpell` 多处读取 `[hero+0x1A]` 作为英雄数据表索引。

当前数据给出的目标英雄 ID：

| 英雄 | ID | 证据 |
|---|---:|---|
| Uland / 尤兰德 | 25 (`0x19`) | `HotA_lng.lod/HOTRAITS.TXT` 的第 25 号顺序记录 |
| Astra / 阿斯特拉 | 170 (`0xAA`) | `HotA.dat` 偏移 `0x5016` 的 `hero170` 记录；同一记录在 `0x505E` 包含“治愈”、`0x50CE` 包含“阿斯特拉” |

诊断 Hook 仍应记录运行时读到的 ID，实机确认后再把这两个值作为功能门禁。

## 原生复活资格验证

原生复活分支在 `0x005A1C17` 取得目标格和当前施法方，并调用：

```cpp
CombatCreature* __thiscall GetResurrectionTarget(
    CombatManager* manager, // ECX
    int side,
    int hex,
    int context
); // 0x005A3FD0
```

`0x005A3FD0` 的静态代码同时处理存活兵队和尸体对象。对存活兵队，它至少检查：

- 兵队属于指定 side；
- 目标具备可复活状态标志；
- `numberAlive < numberAtStart`；
- 经 `0x005A83A0` 验证原生 Resurrection 效果可以作用于该目标。

这条路径应被复用，不能另建亡灵、元素、构装体等黑名单。Stage 2 只传入当前仍存活的 Cure 目标，不扫描尸体。

## 原生永久复活

`0x005A7870` 的静态签名为：

```cpp
void __thiscall ResurrectTarget(
    CombatManager* manager,  // ECX
    CombatCreature* target,  // stack arg 1
    int hitPoints,           // stack arg 2
    bool temporary           // stack arg 3
);
```

该函数原生更新：

- `[target+0x4C]` `numberAlive`；
- `[target+0x58]` `healthLost`；
- 上限 `[target+0x60]` `numberAtStart`；
- 相关战场对象、动画和日志状态。

当第三参数非零时，`0x005A78CD–0x005A78F1` 会增加/限制 `[target+0x54]` `numberForeverDead`，即把新增单位标记为战后不保留。传入 `temporary = 0` 会跳过该更新，是本项目要求的永久复活路径。

## 推荐实现：统一 Cure call 包装器

不要修改 `healthLost`、`numberAlive` 或 `numberForeverDead`。候选实现是把两处 5 字节 `call 0x00446220` 分别重定向到同一个包装器；包装器再调用原始 CureCore。

包装器的预期流程：

```text
1. 检查 casterHero 非空，记录/确认 [hero+0x1A]。
2. 非 Uland/Astra：尾调用原始 CureCore，保持原行为。
3. Uland/Astra：保存非易失寄存器、target、manager 与原始参数。
4. 调用原始 CureCore。
5. EAX >= 0：直接返回。
6. EAX < 0：overflow = -EAX。
7. 确认 target 的 numberAlive > 0 且 numberAlive < numberAtStart。
8. 通过 manager->GetResurrectionTarget(side, target->hex, 0) 复用原生资格验证。
9. 验证返回目标非空且与当前 target 一致。
10. manager->ResurrectTarget(validTarget, overflow, temporary=0)。
11. 恢复寄存器和栈，以 ret 0x0C 返回原调用者。
```

采用 call 包装器的理由：

- 单体和群体 Cure 的调用签名完全一致；
- 两个调用点都保留 `EBX = CombatManager*`；
- 原 CureCore 不改，原生治疗、清除负面状态和特长缩放完整保留；
- `EAX` 提供精确溢出量，无需静态复制公式；
- 原调用点之后的动画/日志代码不需要搬移或重放；
- 非目标英雄可直接尾调用原函数，影响面最小。

## 必须先做的诊断版

第一份构建只能重定向上述两个 call 到诊断包装器，不执行复活。满足以下条件时写一条最小日志：

```text
source=single|mass
spell=37
hero_id
target_pointer
number_alive
number_at_start
health_lost_before
cure_return_eax
computed_overflow
manager_pointer
```

诊断目标：证明标准版与 HD 版在真实游戏运行时都进入包装器，并确认 `EAX < 0` 与用户观察到的治疗溢出一致。

## 当前不能生成诊断构建的原因

1. 缺少纯净 HotA 1.8.0 两个 EXE，尚不能证明 call 点和代码洞是否已被 `Patch_v1.8` 修改。
2. 缺少 `HotA.dll`、`HD_HOTA.dll`、`HW_HOTA.dll` 和 `patcher_x86.dll`，无法检查启动后是否覆盖 call 点。
3. `0x00639D00–0x00639D1F` 与 `0x00639D40–0x00639D57` 已被现有功能占用；即使附近有零字节，也不能在完成纯净差异映射前分配。
4. 日志实现需要先确认可安全调用的文件 I/O/patcher 设施，不能把 CRT/Win32 调用约定当作已知事实。

## 需要补充的输入

```text
h3hota.exe                 纯净 HotA 1.8.0
h3hota HD.exe              纯净 HotA 1.8.0 + 对应 HD 启动文件
HotA.dll
HD_HOTA.dll
HW_HOTA.dll
patcher_x86.dll
patcher_x86.ini
HotA_Setup.ini
HotA_Settings.ini
```

取得这些文件后，下一步是：输入哈希 → 完整差异图 → DLL/patcher 覆盖扫描 → 诊断包装器 → 用户实机日志。此时仍不直接制作复活功能版。
