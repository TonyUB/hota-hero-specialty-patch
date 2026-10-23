# HOTA_NEW_HERO_V1.6

2026-10-20正式发布。SHA-256：`c99859c9f014f121b8982656de16a903277bc60fd482e76126c3a9251f5b0e7c`。

在V1.53正式基底上整合瓦伦与塔博克两名原创英雄，保留所有既有正式英雄。

- **瓦伦 人马统领**：基础半人马可从原升级按钮进入三选数量窗口；首领／射手／斥候每只20／30／20金币，仅基础半人马可升级。四种人马每级获得10%基础攻防（向上取整）及固定+1速；射手基础速度7、无距离/城墙惩罚，斥候基础速度12、飞行。金币和大小部队栏在窗口内实时更新。
- **塔博克 九头之主**：麾下大小九头钻地移动；小九头额外反击一次，大九头无限反击；配套独立钻地、出土与破土动画。驯兽师0411、防御+进攻、无书、初始1九头。
- 两名英雄的姓名、头像、传记、特长图标和说明均已整合，原鹰眼术专精停用；瓦伦替换马尔凯姆，克兰保持原样。
- 中英文首页及38页手册按最新英雄优先排序：瓦伦→塔博克→奥蕾加→阿萨泽尔→厄瑞玻斯→埃尔芙。

完整补丁共36个游戏文件、40个ZIP成员，不含游戏本体。标准版和HD版均实际进入主菜单；HD复核瓦伦说明及三种升级实时显示，标准版新开局核对塔博克配置和说明。动画与战斗机制沿用先前验收，整合轮未重跑全部战斗、攻城、联机及所有旧英雄矩阵。阿萨泽尔守城帐篷/补给车不恢复、守城弩车未确认的接受边界继续保留。

由两个独立测试包整合而成，不能通过相互覆盖旧测试包重现；具体实现、疑难复盘与校验记录已保存私有经验库。V1.53作为唯一上一正式版移入OLD；V1.52及旧手册可从发布前提交9070272bc5504dd127d29c39ee477e317b38a589恢复。

## English

V1.6 integrates Valen’s Centaur Command and Tabok’s Lord of Hydras into the V1.53 formal baseline. Valen offers native three-choice quantity upgrades at 20/30/20 gold, live resource/army updates, and level-based centaur bonuses. Tabok’s Hydras burrow and gain extra/unlimited retaliation. Portraits, biographies, specialty icons and ability text are included. The bilingual landing page and 38-page handbook list the newest heroes first.

Install the full patch into Chinese HotA 1.8.0; do not overlay earlier test packages. Standard and HD startup plus selected hero/UI checks passed. The complete battle, siege, multiplayer and legacy-hero matrix was not rerun in this integration. Existing V1.53 limitations remain documented.
