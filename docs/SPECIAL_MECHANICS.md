# 特殊功能详解 / Special Mechanics

## 矮人特长重制 / Dwarf Specialty Rework

| 项目 | 当前正式规则 |
| --- | --- |
| 专属英雄 | 尤佛瑞汀。 |
| 攻击与防御 | 总值为 `基础值 × 2 + floor(基础值 × floor(英雄等级 ÷ 2) ÷ 5)`；即1级约为基础值的200%，每2级再增加20%基础值，10级达到300%。 |
| 速度 | 矮人和战斗矮人均固定增加3点速度，最终分别为6与8；不随英雄等级继续增长。 |
| 不变属性 | 杀伤力与生命值保持兵种原生数值。 |
| 冒险地图移动力 | 以特长结算后的速度养步：仅矮人为1700，仅战斗矮人为1830；两者同时存在时按较慢的矮人取1700。 |
| 原生修正 | 后勤术、移动宝物、马厩、地形等修正继续按原生顺序结算。 |
| 初始技能 | 初级进攻术与初级幸运术。 |

| Item | Current release behavior |
| --- | --- |
| Specialty hero | Ufretin. |
| Attack and Defense | `base × 2 + floor(base × floor(hero level ÷ 2) ÷ 5)`. Level 1 is approximately 200% of base; every 2 levels add another 20% of base; level 10 reaches 300%. |
| Speed | Dwarves and Battle Dwarves each gain a fixed +3 Speed, ending at 6 and 8 respectively. Speed does not scale further with level. |
| Unchanged stats | Damage and Hit Points remain native. |
| Adventure movement | Uses specialty-adjusted Speed: Dwarf-only 1700, Battle-Dwarf-only 1830, and both together 1700 under the native slowest-stack rule. |
| Native modifiers | Logistics, movement artifacts, Stables, terrain, and other native modifiers retain their original settlement order. |
| Starting skills | Basic Offense and Basic Luck. |

---

## 破灭重塑 / Ruinous Reforging

![献祭按钮 / Sacrifice button](../assets/ui/erebus-sacrifice.png)

### 中文规则

| 项目 | 当前正式规则 |
| --- | --- |
| 使用位置 | 仅限冒险地图中厄瑞玻斯自己的英雄军队兵种信息窗；战斗、城镇驻军及另一名英雄的军队不能直接献祭。 |
| 可用来源 | 墓园 1—6 级基础及升级兵种。 |
| 禁止来源 | 骨龙、鬼龙及其他不在白名单中的生物。 |
| 生命值口径 | 使用兵种数据库基础生命值；不计生命戒指、生命之戒、活力之戒、血瓶、急救术或其他临时加成。 |
| 计算公式 | `骨龙数量 = floor(单支来源部队数量 × 该兵种基础生命值 ÷ (240 × 等级倍率))`。 |
| 等级倍率 | 来源兵种 1—6 级依次为 `2.0 / 1.8 / 1.6 / 1.4 / 1.2 / 1.0`，对应生命门槛为 `480 / 432 / 384 / 336 / 288 / 240`。基础与升级形态使用同一等级倍率。 |
| 余数处理 | 生命值余数不保留；玩家需要自行安排最合适的献祭数量。 |
| 兵槽处理 | 骨龙生成在来源兵槽，不要求额外空位；七个兵槽全满时仍可使用；不会与其他骨龙自动合并。 |
| 零结果/取消 | 计算结果为 0、来源不合格或取消确认时，部队不发生变化；不足 240 基础生命值时按钮显示为禁用态。 |
| 界面与结算 | 按钮、右键说明、确认弹窗和结算均正常。 |
| 普通升级 | 厄瑞玻斯的该按钮专用于献祭，不能同时承担城镇内普通升级；需要升级时请把部队交给其他英雄。 |
| 龙族范围 | 与“龙之血瓶”的加成范围一致：绿龙、金龙、骨龙、鬼龙、红龙、黑龙、圣龙、水晶龙、魔法龙、毒龙。 |
| 出战规则 | 军中存在至少一队龙族时，只有龙族部队进入战场；非龙部队仍可随身携带并作为献祭素材。 |
| 无龙回退 | 军中没有任何龙族时，不限制出战部队，全部兵力按原生规则进入战斗。 |
| 战后结算 | 胜利后未出战的非龙部队原位恢复；战败、逃跑或投降时不恢复，仍按原生规则失去军队。 |
| 陆地移动力 | 军中存在龙族时，仅以龙族中速度最慢的一队计算基础陆地移动力，忽略随身携带的非龙部队；无龙时回退原生全军养步。 |
| 原生修正 | 后勤术、移动类宝物、马厩和地形等原生修正继续在基础移动力之后正常结算。 |
| 已知显示边界 | 逃跑结算画面的“战场伤亡”可能对未部署部队显示“无”；这只是界面统计限制，不改变实际军队损失。 |
| 酒馆兵力生命周期 | 初次登场及隔周正常刷新时携带 1 骨龙；战败或逃跑后在当周酒馆返场时写入全局生物 ID 56，仅携带 1 骷髅兵；投降不触发重新生成，按原生规则保留全部兵力。ID 0 是枪兵，不得用于骷髅兵。 |

### English Rules

| Item | Current release behavior |
| --- | --- |
| Where it works | Only in Erebus's own hero-army creature window on the adventure map; it cannot be used in combat, a town garrison, or another hero's army. |
| Eligible sources | Necropolis tier 1–6 base and upgraded creatures. |
| Ineligible sources | Bone Dragons, Ghost Dragons, and all other non-whitelisted creatures. |
| HP source | Database base HP only; artifacts, First Aid, temporary bonuses, and similar effects are ignored. |
| Formula | `Bone Dragons = floor(source stack count × base HP / (240 × tier multiplier))`. |
| Tier multipliers | Source tiers 1–6 use `2.0 / 1.8 / 1.6 / 1.4 / 1.2 / 1.0`, producing HP thresholds of `480 / 432 / 384 / 336 / 288 / 240`. Base and upgraded forms share their tier multiplier. |
| Remainder | Fractional HP is discarded. |
| Slot behavior | The result replaces the source stack in the same slot, needs no empty slot, works with seven occupied slots, and never auto-merges. |
| Zero/cancel | An ineligible source, a zero result, or canceling leaves the army unchanged; a sub-240 stack shows the disabled state. |
| UI and settlement | The button, right-click help, confirmation dialog, and settlement all work normally. |
| Normal upgrades | Erebus's one native button is dedicated to sacrifice; transfer a stack to another hero for an ordinary town upgrade. |
| Dragon set | Matches the creatures affected by the Vial of Dragon Blood: Green, Gold, Bone, Ghost, Red, Black, Azure, Crystal, Faerie, and Rust Dragons. |
| Deployment | If the army contains at least one dragon stack, only dragon stacks enter combat; non-dragons may remain carried and may be used as sacrifice material. |
| No-dragon fallback | With no dragon stack in the army, deployment is unrestricted and the full army follows native combat rules. |
| Post-combat settlement | Carried non-dragons return to their original slots after victory. They are not restored after defeat, retreat, or surrender, which retain native army-loss behavior. |
| Land movement | When dragons are present, base land movement uses only the slowest dragon stack and ignores carried non-dragons. With no dragons, native full-army movement calculation is used. |
| Native modifiers | Logistics, movement artifacts, Stables, terrain, and other native modifiers continue to apply after the base movement calculation. |
| Known display boundary | The retreat casualty screen may show “None” for stacks that were never deployed. This is a reporting limitation only and does not preserve the army. |
| Tavern army lifecycle | Erebus starts and enters a normal weekly tavern refresh with 1 Bone Dragon. A midweek return after defeat or retreat carries only 1 Skeleton. Surrender does not regenerate the army and retains all troops under native rules. |

---

## 治愈复活 / Cure Resurrection

### 当前公式 / Current Formula

```text
B = 5P + 10 + 10 × max(0, clamp(w, 0, 3) - 1)
H = HotA 1.8.0 原生结算：每达到一个完整的 (8−n) 英雄等级区间，
    在 B 的基础上提高 10%
```

`H` 为最终治疗/复活生命值池，`B` 为 HotA 1.8.0 原生治愈基础值。`P` 为英雄当前有效力量，`n` 为目标生物等级，`w` 为水系魔法熟练度（无/初级/中级/高级 = 0/1/2/3）。等级增幅与最终整数取整直接交由 HotA 1.8.0 原生特长计算器处理。

`H` is the final healing/resurrection HP pool and `B` is the native HotA 1.8.0 Cure base value. `P` is current effective Spell Power, `n` target creature tier, and `w` Water Magic mastery (none/basic/advanced/expert = 0/1/2/3). Level scaling and final integer rounding are delegated directly to the native HotA 1.8.0 specialty calculator.

### 中文规则

| 项目 | 当前正式规则 |
| --- | --- |
| 专属英雄 | 仅尤兰德与阿斯特拉的治愈术获得永久复活能力；其他英雄保持原生治愈效果。 |
| 受疗对象 | 遵循原生治愈术的友方目标判定；可治疗存活部队，并可复活符合条件的己方阵亡非亡灵部队。 |
| 亡灵 | 可按原生路径回复当前生命，但不会通过此特长复活阵亡亡灵。 |
| 战争机器 | 存活战争机器继续按原生治愈资格接受治疗并使用恢复后的原生数值；被摧毁的战争机器仍由原生复活资格拒绝，不会被专属路径重新生成。 |
| 永久性 | 复活兵力在战斗结束后保留。 |
| 单体/群体 | 水系魔法只按原生规则决定单体或群体施法范围，并通过公式中的 `w` 项影响数值；不会改变专属英雄判定。 |
| 完整尸体 | 可复活已经整队阵亡并留有可选尸体的部队。尸体格被其他部队占据时不能复活。 |
| 重叠尸体 | 同一格有多个尸体时，一次只能复活当前可选中的一队。 |
| 动画/音效 | 保留原版治愈动画与音效，并补充复活起身动作；不播放转世重生的法术特效与音效。 |
| 战斗日志 | 先记录施放治愈；单体显示目标治疗量，群体逐队显示所有有效受疗单位的治疗量，再记录复活结果。 |
| 魔法书/悬停 | 魔法书显示当前对 1—7 级生物的治疗范围；存活目标悬停显示精确数值；尸体悬停保留原生“治愈”文字。 |
| 禁止范围 | 敌方部队、非原生合法目标、被占据而不可选择的尸体，以及其他英雄的治愈术，均不能获得本特长的尸体复活效果。 |

### English Rules

| Item | Current release behavior |
| --- | --- |
| Specialty heroes | Only Uland and Astra gain permanent resurrection from Cure; other heroes retain native Cure behavior. |
| Valid targets | Native friendly-target eligibility remains in force. Living stacks can be healed, and eligible fallen friendly non-undead stacks can be resurrected. |
| Undead | Existing HP may follow the native Cure path, but fallen undead are not resurrected by this specialty. |
| War machines | Living war machines remain healable under native Cure eligibility and use the new value; destroyed war machines remain rejected by native resurrection eligibility and are not recreated by the specialty. |
| Permanence | Resurrected troops remain after combat. |
| Single/mass | Water Magic keeps the native single-target/mass targeting rule and contributes through `w`; it does not change hero ownership of the specialty. |
| Full corpses | A fully destroyed stack can return if its corpse is selectable. A corpse occupied by another stack cannot be resurrected. |
| Overlapping corpses | If corpses overlap, one cast can restore only the currently selectable corpse. |
| Visual/audio | Native Cure visuals and sound remain, with the resurrection stand-up motion added. Resurrection spell visuals and sound are suppressed. |
| Combat log | Cure is logged first; single-target casts show that target's value, mass casts list every effectively healed stack, followed by resurrection results. |
| Spell book/hover | The spell book shows the tier 1–7 range; a living target shows its exact value; corpse hover intentionally keeps the native “Cure” label. |
| Exclusions | Enemies, native-illegal targets, occupied/unselectable corpses, and Cure cast by other heroes do not gain corpse resurrection. |
