# HotA 1.8.0 运行时模块静态清单

> 该报告只搜索导入、导出、字符串、地址字面量和 EXE 字节签名。未命中不等于运行时不会计算地址或动态覆盖代码。

| 模块 | 大小 | SHA-256 | ImageBase | EntryPoint | 导出 |
|---|---:|---|---:|---:|---:|
| `HotA.dll` | 2514432 | `0a48b6d8e2b1743bdc094f3c0dc5a0b4e995e06165993f07885252905b0be2d1` | `0x10000000` | `0x1020962E` | 2 |
| `HD_HOTA.dll` | 2905600 | `34c22f9ac460b57dd2ffcd205a80d0c118a42cf14005c9e4a042f4030e8e1bde` | `0x01000000` | `0x01264206` | 2 |
| `HW_HOTA.dll` | 205312 | `a806a256f546fedfd3935d17d91756847f98263f5f48b9a74d462f314e9d21be` | `0x10000000` | `0x100192D5` | 2 |
| `patcher_x86.dll` | 483328 | `8c10bae88bf42d30157b66611b045e5e904e14b2dda66988e90163bc0d3626bf` | `0x10000000` | `0x10012DE6` | 2 |

## HotA.dll

### 可能用于内存修改/诊断的导入

- `KERNEL32.dll!CreateFileA`，IAT `0x1022E040`
- `KERNEL32.dll!WriteFile`，IAT `0x1022E068`
- `KERNEL32.dll!CreateFileW`，IAT `0x1022E080`
- `KERNEL32.dll!OutputDebugStringW`，IAT `0x1022E090`
- `KERNEL32.dll!GetModuleHandleA`，IAT `0x1022E0A0`
- `KERNEL32.dll!LoadLibraryA`，IAT `0x1022E0A4`
- `KERNEL32.dll!VirtualAlloc`，IAT `0x1022E0A8`
- `KERNEL32.dll!GetProcAddress`，IAT `0x1022E0AC`
- `KERNEL32.dll!GetModuleHandleW`，IAT `0x1022E188`

### 候选 EXE 地址字面量

- GetResurrectionTarget `0x005A3FD0`：0x0006CBB3, 0x0006D071, 0x0006D16E
- ResurrectTarget `0x005A7870`：0x00125B53, 0x00144BF8

### 32 字节 EXE 签名

未发现。

### 相关字符串

- `0x0022CED8` (ascii): `SpellScr.def`
- `0x0022D10C` (ascii): `push __Hook_Ptr`
- `0x0022D49C` (ascii): `HotA.NewQuestLog`
- `0x0022D4CC` (ascii): `COMBAT_SPELL`
- `0x0022D4DC` (ascii): `ADV_SPELL`
- `0x0022D4F4` (ascii): `CREATURE_SPELL`
- `0x0022D568` (ascii): `MIND_SPELL`
- `0x0022D588` (ascii): `ARTIFACT_SPELL`
- `0x0022D648` (ascii): `patcher_x86.dll`
- `0x0022D658` (ascii): `_GetPatcherX86@0`
- `0x0022D874` (ascii): `HotA.CreatureWindowSetNextFrameCreatureID`
- `0x0022DC6C` (ascii): `[HotA CRASH INFO file]`
- `0x0022DCA4` (ascii): `HotA.dll version: %s`
- `0x0022DCBC` (ascii): `HotA.dll test version: %d`
- `0x0022DCDC` (ascii): `HotA_Setup.ini version: %s`
- `0x0022DCFC` (ascii): `HotA internal map format subversion: %d`
- `0x0022DD28` (ascii): `HotA internal savegame format subversion: %d`
- `0x0022DD58` (ascii): `HotA internal campaign format subversion: %d`
- `0x0022E470` (ascii): `PATCHER_DUMP_`
- `0x0022E480` (ascii): `PATCHER_LOG_`
- `0x0022FCC8` (ascii): `HotA.ComboArtDisabled`
- `0x0022FCE0` (ascii): `HotA.CanHaveBattles`
- `0x0022FCF4` (ascii): `HotA.MirrorMonsterSetup`
- `0x0022FD0C` (ascii): `HotA.MirrorResourceObjectSetup`
- `0x0022FD58` (ascii): `HotA.ShadowDrawNewSpeccolor24bitFunc_0`
- `0x0022FD80` (ascii): `HotA.ShadowDrawNewSpeccolor24bitFunc_1`
- `0x0022FDA8` (ascii): `HotA.ShadowDrawNewSpeccolorFunc`
- `0x0022FEA0` (ascii): `camphota.pcx`
- `0x0022FEE4` (ascii): `CSShota.def`
- `0x0022FFEC` (ascii): `[HotA] Air Supremacy.h3m`
- `0x00230074` (ascii): `HotA.DecorObjectsType`
- `0x0023008C` (ascii): `HotA.DecorObjects`
- `0x002300A0` (ascii): `HotA.DecorObjectsCount`
- `0x002300B8` (ascii): `HotA.PuzzleObjectsType`
- `0x002300D0` (ascii): `HotA.PuzzleObjects`
- `0x002300E4` (ascii): `HotA.PuzzleObjectsCount`
- `0x002300FC` (ascii): `HotA.NeedRedrawStacksBorders`
- `0x0023011C` (ascii): `HotA.FontColor`
- `0x00230200` (ascii): `HotA_Update.dll`
- `0x0023021C` (ascii): `HotA_Setup.ini`
- `0x0023022C` (ascii): `HotA_Settings.ini`
- `0x002303A4` (ascii): `spell`
- `0x00230408` (ascii): `Your HotA build contains game resources belonging to different version of HotA.The build is broken and cannot be run. Please reinstall the game.`
- `0x0023049C` (ascii): `HotA.Version`
- `0x002304AC` (ascii): `HotA.Build`
- `0x002304B8` (ascii): `HotA.TestBuild`
- `0x002304C8` (ascii): `HotA.IniVersion`
- `0x002304D8` (ascii): `HotA.Language`
- `0x002304E8` (ascii): `HotA.MapVerion`
- `0x002304F8` (ascii): `HotA.SaveVersion`
- `0x0023050C` (ascii): `HotA.DatLanguage`
- `0x00230520` (ascii): `HotA.IsReleaseBuild`
- `0x00230534` (ascii): `HotA.IsClosedTestingBuild`
- `0x00230568` (ascii): `Your HoMM 3 HD version is obsolete and not compatible with HotA.`
- `0x002305A9` (ascii): `You should update HD or play HotA without HD.`
- `0x002305D8` (ascii): `DATA\HotA_ext.lod`
- `0x002305EC` (ascii): `DATA\HotA_l_ext.lod`
- `0x00230698` (ascii): `HotA.ArtifactsCount`
- `0x0023079C` (ascii): `def.spells%02d`
- `0x002307BC` (ascii): `def.spells_n`
- `0x002307F8` (ascii): `def.spells00`
- `0x002308A4` (ascii): `def.spells01`
- `0x002308C4` (ascii): `SpellBE.p32`
- `0x00230910` (ascii): `HotA.SwapMgrCalledFromTown`
- `0x00230A20` (ascii): `HotA.CrDwellTable`
- `0x00230A34` (ascii): `hota.dat`
- `0x00230DEC` (ascii): `HotA.TavernHeroesEnabled`
- `0x00230E08` (ascii): `HotA.HeroesEnabledForSimTurnsPools`
- `0x00230E2C` (ascii): `HotA.ForbidHiringHeroes`
- `0x002310A8` (ascii): `HotA.HPL_tbl`
- `0x002310B8` (ascii): `HotA.HPS_tbl`
- `0x002310C8` (ascii): `HotA.PortraitsCount`
- `0x002310DC` (ascii): `HotA.HeroesDefaultPortraits`
- `0x00231117` (ascii): `@HotA.CloneModif`
- `0x00231128` (ascii): `HotA.SpellLength`
- `0x0023113C` (ascii): `HotA.SpellSkillLevel`
- `0x002313AC` (ascii): `HotA.MaxCombatLength`
- `0x002313C4` (ascii): `HotA.Stack_VisibleHitPointsLost`
- `0x00231410` (ascii): `Resurect.wav`
- `0x00231B08` (ascii): `casspells`
- `0x00231DD8` (ascii): `hota.lod`
- `0x00231DE4` (ascii): `hota_ext.lod`
- `0x00231DF4` (ascii): `hota_lng.lod`
- `0x00231E04` (ascii): `hota_l_ext.lod`
- `0x00231E14` (ascii): `data\hota.vid`
- `0x00231E34` (ascii): `data\hota.snd`
- `0x00231E44` (ascii): `data\HotA_lng.snd`
- `0x00232068` (ascii): `HotA_logs`
- `0x00232160` (ascii): `%s\HotA_Data`
- `0x00232180` (ascii): `Error! \HotA_Data\Mss32.dll not found!`
- `0x002328E4` (ascii): `HotA.PlayerStartTurn`
- `0x002328FC` (ascii): `HotA.TownGate_Name`
- `0x00232910` (ascii): `HotA.QuestGate_Name`
- `0x00232AA0` (ascii): `HotA.TwoWayMonolyths_Off`
- `0x00232ABC` (ascii): `HotA.TwoWayMonolyths_Count`
- `0x00232AD8` (ascii): `HotA.MonolythsOneWay_Off`
- `0x00232AF4` (ascii): `HotA.MonolythsOneWay_Count`
- `0x00232B88` (ascii): `HotA_RMGTemplates\%s`
- `0x00232BC8` (ascii): `HotA.Action_OnDirectoryEnterOnline`
- `0x00232E58` (ascii): `, HotA `
- 其余 14 条见 JSON。

## HD_HOTA.dll

版本：`0.4.0.20`

### 可能用于内存修改/诊断的导入

- `KERNEL32.dll!WriteFile`，IAT `0x01287060`
- `KERNEL32.dll!GetModuleHandleA`，IAT `0x0128707C`
- `KERNEL32.dll!GetProcAddress`，IAT `0x0128709C`
- `KERNEL32.dll!VirtualProtect`，IAT `0x012870C0`
- `KERNEL32.dll!VirtualAlloc`，IAT `0x012870D4`
- `KERNEL32.dll!LoadLibraryA`，IAT `0x0128710C`
- `KERNEL32.dll!CreateFileA`，IAT `0x01287124`
- `KERNEL32.dll!CreateFileW`，IAT `0x01287210`
- `KERNEL32.dll!GetModuleHandleW`，IAT `0x01287228`

### 候选 EXE 地址字面量

未发现。

### 32 字节 EXE 签名

未发现。

### 相关字符串

- `0x002938E0` (ascii): `HD.Func.LOG_WRITE`
- `0x002938F4` (ascii): `HD.Ini.Main`
- `0x00293900` (ascii): `HD.Ini.Main is NULL. Load again.`
- `0x00293934` (ascii): `HD.Ini.Main.Name`
- `0x00293A98` (ascii): `HotA.Stack_VisibleHitPointsLost`
- `0x00293B58` (ascii): `HD.Ini.Txt`
- `0x00293B64` (ascii): `HD.Ini.Txt.En`
- `0x00293BBC` (ascii): `HotA.SpellLength`
- `0x00293BD0` (ascii): `HotA.SpellSkillLevel`
- `0x00293E9C` (ascii): `HotA.HPS_tbl`
- `0x00294094` (ascii): `HotA.SaveVersion`
- `0x002942A0` (ascii): `HotA.QuestGate_Name`
- `0x002942DC` (ascii): `HotA.HPL_tbl`
- `0x002943D0` (ascii): `HotA.NewQuestLog`
- `0x00294418` (ascii): `HotA.CreatureWindowSetNextFrameCreatureID`
- `0x0029451C` (ascii): `SpellScr.def`
- `0x0029454C` (ascii): `HD.UI.Ext.SpellScroll`
- `0x00294564` (ascii): `HotA.ComboArtDisabled`
- `0x002945B8` (ascii): `HD.UI.Ext.SpellBook`
- `0x00294990` (ascii): `spells.def`
- `0x00294C68` (ascii): `HotA.DecorObjects`
- `0x00294C7C` (ascii): `HotA.DecorObjectsType`
- `0x00294C94` (ascii): `HotA.PuzzleObjects`
- `0x00294CA8` (ascii): `HotA.PuzzleObjectsType`
- `0x00294CC0` (ascii): `HotA.AdvMgr_LandDefShift`
- `0x00294D78` (ascii): `HotA.ReplayTurnInit`
- `0x00294D8C` (ascii): `HotA.ReplayTurnFinish`
- `0x00295280` (ascii): `HotA.SwapMgrCalledFromTown`
- `0x002953E0` (ascii): `HotA.TownGate_Name`
- `0x0029563C` (ascii): `hota.dll`
- `0x00295648` (ascii): `HotA.PlayerStartTurn`
- `0x00295688` (ascii): `HotA.60FpsHero`
- `0x00295698` (ascii): `HotA.60FpsFrameSkips`
- `0x002956D0` (ascii): `HD.HotA.GetShadowTerrain`
- `0x00295838` (ascii): `HD.HotA`
- `0x002958DC` (ascii): `HotA.Version`
- `0x002958EC` (ascii): `HotA.Build`
- `0x0029591C` (ascii): `%s\HotA.dll`
- `0x00295951` (ascii): ` hota.dll. `
- `0x00295998` (ascii): `The file hota.dll is not recognized. The game may not work properly. Reinstall the game.`
- `0x00295A18` (ascii): `HD.Option.CpuPatch`
- `0x00295C30` (ascii): `HD.Option.MusicPatch`
- `0x00297E2C` (ascii): `vk.com/h3hota`
- `0x00297E3C` (ascii): `h3hota.com`
- `0x00297E98` (ascii): `https://h3hota.com`
- `0x00297EAC` (ascii): `https://vk.com/h3hota`
- `0x00298754` (ascii): `https://sites.google.com/view/hota-lobby-ru/rules_conduct`
- `0x00298790` (ascii): `https://sites.google.com/view/hota-lobby-pl/rules_conduct`
- `0x002987CC` (ascii): `https://sites.google.com/view/hota-lobby-en/rules_conduct`
- `0x00298808` (ascii): `https://sites.google.com/view/hota-lobby-ru/rules_gaming`
- `0x00298844` (ascii): `https://sites.google.com/view/hota-lobby-pl/rules_gaming`
- `0x00298880` (ascii): `https://sites.google.com/view/hota-lobby-en/rules_gaming`
- `0x002988BC` (ascii): `https://sites.google.com/view/hota-lobby-ru/report`
- `0x002988F0` (ascii): `https://sites.google.com/view/hota-lobby-pl/report`
- `0x00298924` (ascii): `https://sites.google.com/view/hota-lobby-en/report`
- `0x00298A08` (utf16le): ` HotA `
- `0x00298A34` (utf16le): ` HotA `
- `0x00298B02` (utf16le): `RHotA VK`
- `0x00298B14` (utf16le): `HotA Discord`
- `0x00298B70` (ascii): `HotA.HeroesDefaultPortraits`
- `0x00299208` (ascii): `The host has HotA version {%s}.`
- `0x00299228` (ascii): `You have HotA version {%s}.`
- `0x00299930` (ascii): `HotA.ForbidHiringHeroes`
- `0x00299970` (ascii): `HD.HotaVer`
- `0x00299AD8` (ascii): `HD.Hota180Fixed`
- `0x00299AE8` (ascii): `HD_HOTA.DLL`
- `0x00299B4E` (ascii): ` HotA {`
- `0x00299BF8` (ascii): ` HotA.`
- `0x00299C00` (ascii): `HotA - `
- `0x00299CAA` (ascii): ` HotA.`
- `0x00299CF6` (ascii): `HotA Crew {has} {nothing} {to} {do} with the development and support of online lobby. In case of issues when accessing the lobby, please abstain from posting complaints on the Discord channel and on other project's pages.`
- `0x00299DD5` (ascii): `HotA is a non-profit project, and the HotA Crew has never once accepted donations over 16 years of development. By supporting the lobby you support the creator of HoMM3 HD+, not the HotA project.`
- `0x00299EDF` (ascii): ` HotA {`
- `0x00299F86` (ascii): ` HotA.`
- `0x00299F8E` (ascii): `HotA `
- `0x0029A031` (ascii): ` HotA.`
- `0x0029A04A` (utf16le): ` HotA 1.8.0`
- `0x0029A064` (utf16le): `Download HotA 1.8.0`
- `0x0029A0D4` (ascii): `HD.IsGogHota`
- `0x0029A130` (ascii): `https://h3hota.com/ru/download`
- `0x0029A150` (ascii): `https://h3hota.com/en/download`
- `0x0029AD4C` (ascii): `HotA Developer`
- `0x0029B9B4` (ascii): `HotA.FontColor`
- `0x0029BE9C` (ascii): `Update.ini`
- `0x0029C3D8` (ascii): `patcher_x86.dll`
- `0x0029C3E8` (ascii): `_GetPatcherX86@0`
- `0x0029C3FC` (ascii): `_GetPatcherX86Version@0`
- `0x0029C7A8` (ascii): `%s\HotA_RMGTemplates`
- `0x0029CC38` (ascii): `HotA.HeroesEnabledForSimTurnsPools`
- `0x0029CE6C` (ascii): `HotA.CanHaveBattles`
- `0x0029DAC4` (ascii): `%s\hota.dll`
- `0x0029DB14` (ascii): `HotA.NeedRedrawStacksBorders`
- `0x0029DBAA` (ascii): `Are you sure you want to cast the spell?`
- `0x0029DBD4` (ascii): `SpellConfirm`
- `0x0029DED0` (ascii): `%s\HotA_Data`
- `0x0029DEE0` (ascii): `HotA_Data`
- `0x0029DF20` (ascii): `HotA_Data\draw_template.dll`
- `0x0029DF58` (ascii): `HotA_Data\hota_te.dll`
- `0x0029DFF4` (ascii): `SpellBook`
- `0x0029E008` (ascii): `SpellInt.def`
- 其余 10 条见 JSON。

## HW_HOTA.dll

### 可能用于内存修改/诊断的导入

- `KERNEL32.dll!GetProcAddress`，IAT `0x1002A000`
- `KERNEL32.dll!LoadLibraryA`，IAT `0x1002A004`
- `KERNEL32.dll!GetModuleHandleA`，IAT `0x1002A008`
- `KERNEL32.dll!CreateFileA`，IAT `0x1002A020`
- `KERNEL32.dll!GetModuleHandleW`，IAT `0x1002A048`
- `KERNEL32.dll!WriteFile`，IAT `0x1002A10C`
- `KERNEL32.dll!CreateFileW`，IAT `0x1002A128`

### 候选 EXE 地址字面量

未发现。

### 32 字节 EXE 签名

未发现。

### 相关字符串

- `0x000287A0` (ascii): `patcher_x86.dll`
- `0x000287B0` (ascii): `_GetPatcherX86@0`
- `0x000287C4` (ascii): `HotA.SaveVersion`
- `0x0002887C` (ascii): `#ru.ini`
- `0x00028884` (ascii): `#en.ini`
- `0x00028898` (ascii): `HW.patch.start_res_gold`
- `0x000288B0` (ascii): `HW.patch.start_res_ore`
- `0x000288C8` (ascii): `HW.patch.start_res_wood`
- `0x000288E0` (ascii): `HW.patch.start_res_mercury`
- `0x000288FC` (ascii): `HW.patch.start_res_sulfur`
- `0x00028918` (ascii): `HW.patch.start_res_crystal`
- `0x00028934` (ascii): `HW.patch.start_res_gems`
- `0x00028C0C` (ascii): `HotA.MonolythsOneWay_Count`
- `0x00028C28` (ascii): `HotA.TwoWayMonolyths_Count`
- `0x00028C44` (ascii): `HotA.MirrorMonsterSetup`
- `0x00028C5C` (ascii): `HotA.MirrorResourceObjectSetup`
- `0x00028C9D` (ascii): ` HotA.MirrorMonsterSetup not found.`
- `0x00028CC4` (ascii): `HotA.Zone_AddRoadPoint`
- `0x00028CEC` (ascii): `HotA.HeroesEnabledForSimTurnsPools`
- `0x0002E76C` (ascii): `C:\Ultra\Projects\HD3x\Sources\Release\HD_HW_HOTA.pdb`
- `0x0002F14C` (ascii): `HW_HOTA.dll`

## patcher_x86.dll

版本：`4.18.2.0`

### 可能用于内存修改/诊断的导入

- `KERNEL32.dll!VirtualAlloc`，IAT `0x1005F014`
- `KERNEL32.dll!GetProcAddress`，IAT `0x1005F018`
- `KERNEL32.dll!VirtualProtect`，IAT `0x1005F024`
- `KERNEL32.dll!GetModuleHandleA`，IAT `0x1005F044`
- `KERNEL32.dll!GetModuleHandleW`，IAT `0x1005F074`
- `KERNEL32.dll!WriteFile`，IAT `0x1005F15C`
- `KERNEL32.dll!CreateFileW`，IAT `0x1005F168`
- `KERNEL32.dll!OutputDebugStringA`，IAT `0x1005F184`
- `KERNEL32.dll!OutputDebugStringW`，IAT `0x1005F188`

### 候选 EXE 地址字面量

未发现。

### 32 字节 EXE 签名

未发现。

### 相关字符串

- `0x0005DE75` (ascii): `Patcher_x86: Assembler: %d: "%s"`
- `0x0005DEB5` (ascii): `Patcher_x86: Assembler: Duplicate label "%s" found!`
- `0x0005DEFD` (ascii): `Patcher_x86: Assembler: %d: "%s"`
- `0x000625BC` (ascii): `Patch `
- `0x000625C4` (ascii): `LoHook`
- `0x000625CC` (ascii): `HiHook`
- `0x00062604` (ascii): `patcher_x86.dll`
- `0x0006261C` (ascii): `patcher_x86.ini`
- `0x00062688` (ascii): `  patches count: %u`
- `0x00062744` (ascii): `N_LAST_RECURSIVE_HOOK_ADDRESS = 0x%X`
- `0x0006297A` (ascii): `ERROR!   %.8X: can not apply CALL_ HiHook! (owner: %s) Wrong opcode: %.2X %.2X ...!`
- `0x000629DA` (ascii): `ERROR!   Can not create %s at %.8X (%s): Wrong Patcher Instance!`
- `0x00062AD9` (ascii): `Patcher_x86: FATAL ERROR! Cann't create Jmp/Hook at 0x%.8X! Unknown opcode.`
- `0x00062B39` (ascii): `Patcher_x86: CreateAsmHook: too many _ExecDefault commands!`
- `0x00062B88` (ascii): `__Hook_Ptr`
- `0x00062BC8` (ascii): `_lohook_in_xp: TlsGetValue failed.`
- `0x00062BEC` (ascii): `_lohook_in_xp: TlsSetValue failed.`
- `0x00062C38` (ascii): `push __Hook_Ptr`
- `0x0006EDDC` (ascii): `C:\Ultra\Projects\HD3x\Sources\Release\patcher_x86.pdb`
- `0x0007031C` (ascii): `patcher_x86.dll`
- `0x0007032C` (ascii): `_GetPatcherX86@0`
- `0x0007033D` (ascii): `_GetPatcherX86Version@0`
- `0x000705BA` (ascii): `VirtualProtect`
- `0x00070C30` (ascii): `OutputDebugStringA`
- `0x00070C46` (ascii): `OutputDebugStringW`
- `0x0007183C` (ascii): `.?AVPatch@@`
- `0x00071850` (ascii): `.?AVPatcherInstance@@`
- `0x00071870` (ascii): `.?AVLoHook@@`
- `0x00071888` (ascii): `.?AVHiHook@@`
- `0x000718A0` (ascii): `.?AVNewHiHook@@`
- `0x000718B8` (ascii): `.?AVPatcher@@`
- `0x00071D60` (utf16le): `patcher_x86 Dynamic Link Library`
- `0x00071DF8` (utf16le): `patcher_x86`
- `0x00071F04` (utf16le): `patcher_x86.dll`
- `0x00071F44` (utf16le): `patcher x86`

## 证据边界

- DLL 可以通过基址加 RVA、模式扫描、加密/压缩表或 patcher 脚本间接定位 EXE，因此没有地址字面量或完整签名并不能排除覆盖。
- 最终判断仍需要启动后的内存字节、断点命中或诊断包装器日志。
