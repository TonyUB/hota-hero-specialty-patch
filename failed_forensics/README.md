# Failed forensics

v1.9、v2.0、v2.1、v2.2、v2.3 仅可在需要时作为失败取证输入，不能成为基线，也不能直接复用其治疗 Hook。

默认不在此仓库保存这些历史包，避免误用和仓库膨胀。

`Patch_v2.5_STAGE3_TEST_STARTUP_BROKEN.zip` 是一个例外：它是已经发给用户、并在干净 1.8.0 上确认无法启动的故障包，因而连同原始清单保留作精确取证。不要安装。根因和修复记录见 `Patch_v2.5_STAGE3_TEST_STARTUP_FAILURE.md`。

`Patch_v2.5_STAGE3_TEST2_SINGLE_TARGET_BLOCKED.zip` 可以启动，且群体尸体复活、永久性和负例均通过，但两名特长英雄的单体尸体会被运行时 Cure 活体效果检查显示为“抵抗魔法”。不要继续安装；结果见 `Patch_v2.5_STAGE3_TEST2_RUNTIME_RESULTS.md`。
