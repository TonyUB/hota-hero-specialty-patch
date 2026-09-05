# 特殊功能详解 / Special Mechanics

## 奥蕾加寻宝术 / Orega Treasure Hunt

### 中文规则

| 项目 | 当前正式规则 |
| --- | --- |
| 专属英雄 | 仅奥蕾加（英雄 ID 110）获得寻宝术；原生鹰眼术特长已停用。 |
| 挖掘资格 | 保留原生地块、圣杯、坑洞和其他限制，但奥蕾加移动后仍可挖掘；点击挖掘时至少需要 100 点当前行动力。 |
| 行动力结算 | 成功挖掘后仍由原生流程把剩余行动力清零，因此自然保持每天最多一次成功挖掘。 |
| 方尖塔信息 | 每次成功挖掘会在地图真实存在、且本队尚未访问的方尖塔中等概率选择一座，并调用原生访问流程同步藏宝图、队伍访问状态、提示和窗口。 |
| 方尖塔耗尽 | 没有未访问方尖塔时跳过该分支，但挖掘与奖励仍继续。 |
| 每日奖励 | 普通成功挖掘必得一档：59% 四等奖 + 350 金币；25% 三等奖 + 500 金币；10% 二等奖 + 1000 金币；5% 一等奖 + 2000 金币；1% 特等奖 + 4000 金币。 |
| 每日确定性 | 同一天、同一存档反复挖掘或更换合法地块，档位与具体宝物保持相同；进入下一天后生成新结果。 |
| 宝物池 | 四/三/二/一等奖分别按原生宝物类型 `0x02 / 0x04 / 0x08 / 0x10` 动态筛选；特等奖使用 17 项固定池。地图禁用、明确排除和无效 ID 均会跳过，巫师之井（138）与法师之戒（139）只进入一等奖。 |
| 双保底 | 连续 12 次成功挖掘未获一等奖或特等奖，第 13 次固定一等奖；连续 28 次未获特等奖，第 29 次固定特等奖。大保底优先。特等奖归零两者；一等奖仅归零小保底并继续累计大保底。 |
| 奖励窗口 | 通用奖励窗口显示金币与实际宝物，并在结算后显示 `保底：小XX/12，大XX/28`；关闭后立即刷新冒险地图资源栏。若目标档位无可用宝物，只发金币且保底不会被错误重置。 |
| 圣杯边界 | 奥蕾加真正挖出原版圣杯时完整保留原生圣杯流程，但跳过当天方尖塔、金币、宝物、提示和保底结算；双保底数值不变。实际获得特等奖宝物时播放原生 `UltimateArtifact.wav`。 |
| 初始配置 | 据点战斗法师；攻击 2、防御 1、力量 1、知识 1；20–30 大耳怪、5–7 恶狼骑士、5–6 半兽人；初级智慧术与初级侦察术；魔法书实际掌握观天（法术 ID 5）。 |
| 界面热修 | 使用最终确认的 V7 大小头像；两张头像均无可见调色板索引 0，宝箱图标保留实机水平镜像补偿。 |

完整图标列表见：[奖池详情](OLEGA_PRIZE_POOLS.md#prize-pool-gallery)。

### English Rules

| Item | Current release behavior |
| --- | --- |
| Specialty hero | Only Orega (hero ID 110) receives Treasure Hunt; the native Eagle Eye specialty type is disabled. |
| Dig eligibility | Native terrain, Grail, hole, and other restrictions remain. Orega may dig after moving, provided she has at least 100 current movement points when Dig is used. |
| Movement settlement | A successful dig still lets the native flow drain all remaining movement, naturally limiting successful digging to once per day. |
| Obelisk information | Every successful dig selects uniformly from Obelisks that exist on the map and have not been visited by the current team, then uses the native visit flow to synchronize the puzzle map, team visit state, message, and window. |
| Exhausted Obelisks | If none remain, the Obelisk branch is skipped while digging and the reward still resolves normally. |
| Daily reward | Every normal successful dig awards one result: 59% fourth prize + 350 gold; 25% third prize + 500 gold; 10% second prize + 1,000 gold; 5% first prize + 2,000 gold; 1% special prize + 4,000 gold. |
| Daily determinism | Reloading or moving to another legal tile on the same day keeps the same tier and artifact; the next day produces a new result. |
| Artifact pool | Fourth/third/second/first prizes dynamically use native artifact types `0x02 / 0x04 / 0x08 / 0x10`; special prize uses a fixed 17-ID pool. Map-disabled, explicitly excluded, and invalid IDs are skipped. Wizard's Well (138) and Ring of the Magi (139) are first-prize only. |
| Dual pity | After 12 successful digs without a first or special prize, dig 13 is forced to first prize. After 28 without special prize, dig 29 is forced to special prize. Large pity has priority. Special resets both; first resets only small pity while large pity continues. |
| Reward window | The general reward window shows gold and the actual artifact, followed by `保底：小XX/12，大XX/28` after settlement. If a tier has no eligible artifact, gold is still granted and pity is not incorrectly reset. |
| Grail boundary | A genuine native Grail dig preserves the full native Grail flow but skips Treasure Hunt's Obelisk, gold, artifact, message, and pity settlement for that day. Both counters remain unchanged. An actual special-prize artifact plays native `UltimateArtifact.wav`. |
| Starting profile | Stronghold Battle Mage; Attack 2, Defense 1, Power 1, Knowledge 1; 20–30 Goblins, 5–7 Wolf Riders, 5–6 Orcs; Basic Wisdom and Basic Scouting; View Air (spell ID 5) actually learned in the starting spell book. |
| Interface hotfix | Uses the final approved V7 large and small portraits; neither portrait contains visible reserved palette index 0, and the treasure-chest icon retains the in-game horizontal-mirror compensation. |

See the complete icon gallery: [奖池详情](OLEGA_PRIZE_POOLS.md#prize-pool-gallery).

---

## 阿萨泽尔战争机器 / Azazel War Machines

### 中文规则

| 项目 | 当前正式规则 |
| --- | --- |
| 专属英雄 | 仅阿萨泽尔（英雄 ID 63）获得本套战争机器规则。 |
| 初始配置 | 地狱战士职业“大魔鬼”，初始四维 `2/2/1/1`，初级弹道术、初级炮术，携带弩车与补给车，不携带急救帐篷；无魔法书和初始法术。 |
| 额外射击 | 弩车、加农炮和投石车每次原生行动额外射击 1 次；额外射击属于同一次原生行动的扩展，不伪造速度、士气或 done 状态。 |
| 战后修复 | 仅在胜利后修复战前已经拥有、战斗中被摧毁的战争机器。失败、撤退和投降不触发专属修复。 |
| 补给车增益 | 英雄至少掌握初级弹道术且己方补给车存活时，普通射手、弩车和加农炮攻击力 +4；补给车被摧毁后立即失效。 |
| 补给车伤害上限 | 每次物理命中最多使补给车损失当前最大生命值的 40%；战斗日志与最终伤害同步。 |
| 中级炮术 | 中级及以上炮术使弩车和加农炮攻击部队时，按向上取整后的 50% 原生有效防御结算。普通射手不获得该效果。 |
| 高级炮术 | 弩车和加农炮攻击部队时无视射程与城墙惩罚，光标和伤害预览同步为无惩罚结果；普通射手不受益。 |
| 城墙目标 | 加农炮攻击城墙时保留原生城防结算与额外射击，不进入对部队使用的 50% 防御或无视惩罚层。 |
| 双高级优先级 | 同时掌握高级弹道术和高级炮术时，每回合逻辑优先级为投石车 > 弩车/加农炮 > 箭塔 > 原生后续行动。 |
| 原生边界 | 不新增投石车城防结构伤害日志；原生普通射手、非目标英雄和其他战争机器规则保持不变。 |
| 说明同步 | 补给车静态说明及弩车、加农炮、投石车动态说明均显示当前规则。 |

### English Rules

| Item | Current release behavior |
| --- | --- |
| Specialty hero | Only Azazel (hero ID 63) receives this war-machine rule set. |
| Starting profile | Inferno might class Demoniac, `2/2/1/1` primary skills, Basic Ballistics and Basic Artillery, a Ballista and Ammo Cart, no First Aid Tent, and no spell book or starting spell. |
| Extra shots | The Ballista, Cannon, and Catapult fire one additional shot during each native action. This extends the same action and does not fake Speed, Morale, or done-state values. |
| Post-battle repair | Only victory repairs war machines that were owned before battle and destroyed during it. Defeat, retreat, and surrender do not trigger specialty repair. |
| Ammo Cart bonus | With at least Basic Ballistics and a living friendly Ammo Cart, ordinary shooters, the Ballista, and the Cannon gain +4 Attack. The bonus disappears immediately when the cart is destroyed. |
| Ammo Cart damage cap | Each physical hit can remove at most 40% of the Ammo Cart's current maximum HP; combat-log damage and settled damage remain synchronized. |
| Advanced Artillery | Advanced or Expert Artillery makes Ballista and Cannon attacks against creatures use 50% of native effective Defense, rounded upward. Ordinary shooters do not gain this effect. |
| Expert Artillery | Ballista and Cannon attacks against creatures ignore range and wall penalties, with cursor and damage preview synchronized. Ordinary shooters remain native. |
| Wall targets | Cannon attacks against walls retain native siege resolution and the extra shot; creature-defense and no-penalty layers do not apply to wall targets. |
| Dual-Expert priority | With both Expert Ballistics and Expert Artillery, the logical per-round priority is Catapult > Ballista/Cannon > towers > native continuation. |
| Native boundaries | No new Catapult structural-damage log is added. Ordinary shooters, non-target heroes, and unrelated war-machine behavior remain native. |
| Description sync | Static Ammo Cart text and dynamic Ballista, Cannon, and Catapult descriptions expose the active rules. |

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
