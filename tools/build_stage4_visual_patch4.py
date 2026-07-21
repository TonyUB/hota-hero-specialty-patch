#!/usr/bin/env python3
"""Build the fourth Cure-resurrection visual test on Patch_v1.8.

TEST3 safely suppressed the Resurrection circle and sound while preserving the
creature animation loop, but limited the loop to exactly the death animation's
frame count. The native loop needs one additional iteration to execute its own
transition from animation group 5 back to standing group 2. TEST4 adds only
that completion iteration and otherwise reuses the verified TEST3 design.
"""

from __future__ import annotations

from typing import Any

import build_stage4_visual_patch3 as base


BUILD_NAME = "Patch_v2.6_VISUAL_TEST4"

base.BUILD_NAME = BUILD_NAME
base.BUILD_SCOPE = "stage4_native_standup_completion_frame_test"
base.SUPERSEDES_TEST_BUILD = "Patch_v2.6_VISUAL_TEST3"
base.SUPERSEDED_RESULT_FIELD = "test3_runtime_result"
base.SUPERSEDED_RUNTIME_RESULT = (
    "No crash and correct sound/effect isolation, but revived stacks stopped "
    "on death-animation frame zero (the hit pose)"
)
base.EXTRA_STANDUP_COMPLETION_FRAME = True

# TEST3 used the last byte of the low cave for its flag. The one-byte INC that
# adds the native completion iteration fills that byte, so TEST4 relocates the
# same scoped flag to the last validated byte of the high cave.
base.SILENT_FLAG_VA = 0x00639D7F


def instructions(report: dict[str, Any]) -> str:
    return f"""# {BUILD_NAME} 测试说明

状态：**第四轮动画测试版，不替换 `Download/Patch_v2.5.zip`。**

TEST3 已确认：游戏不再崩溃，治愈术音效、复活音效隔离和圆圈隐藏都正确，单体与群体复活也能生效。但原生死亡动画共有 `N` 帧，TEST3 只刷新了 `N` 次，最终停在第 0 帧（视觉上是受击姿势）；原版需要第 `N+1` 次刷新才会自行切回站立状态。

本版只增加这一个原生收尾帧：

- 继续保留原版治愈术演出/音效；
- 继续隐藏复活圆圈并跳过复活音效；
- 完整倒放兵种死亡帧后，由原版分支切回站立状态；
- 普通转世重生的圆圈、音效和起身动作不变。

## 安装

1. 覆盖到干净 HotA 1.8.0，不要叠加 TEST1、TEST2、TEST3 或 v2.5。
2. 解压 `{BUILD_NAME}.zip` 到游戏根目录并覆盖。
3. 先启动 `h3hota HD.exe` 到主菜单，再进行战斗测试。

## 必测

1. 单体治愈复活全灭尸体：兵种完成起身后回到正常站立姿势，不停在受击帧。
2. 高级水系群体治愈同时复活至少两队尸体：每队都回到站立姿势，不依赖鼠标刷新。
3. 确认仍无灰棕复活圆圈、无复活音效，原版治愈术演出/音效仍存在。
4. 普通转世重生的圆圈、复活音效和起身动作全部保持原版。
5. 战斗结束后复活数量永久保留；亡灵、重叠尸体和被占格尸体规则不变。

## 校验

```text
{BUILD_NAME}.zip
SHA-256 {report['zip_sha256']}
```
"""


def research_markdown(report: dict[str, Any]) -> str:
    return f"""# Stage 4 TEST4：补足原生起身状态切换帧

状态：**静态构建完成，等待实机门禁。**

## TEST3 实机反馈

- 不再崩溃；
- 治愈术动画/音效正确；
- 复活圆圈和复活音效已正确移除；
- 单体与群体复活均生效；
- 复活单位最终停在受击姿势。

## 根因

原生 `0x005A7B22–0x005A7B6B` 循环把动画组 5 的死亡帧从 `N-1` 倒放到 `0`。只有下一次循环在 `EDI >= N` 时，`0x005A7B3D` 才会把动画组切换为站立组 2，并把帧号清零。

TEST3 为去掉不可见圆圈带来的额外等待，将总刷新次数设为恰好 `N`，因此原生状态切换分支没有执行，单位停在死亡动画第 0 帧；该帧视觉上就是受击姿势。

## TEST4 修正

- 治愈专用路径把总循环次数从 `N` 改为 `N+1`。
- 不直接写动画组或帧号；新增的一次迭代让原版 `0x005A7B3D–0x005A7B44` 自行切换到站立组 2、帧 0。
- TEST3 已通过的合法特效对象、越界圆圈帧、复活音效绕过和公共标记清理逻辑不变。
- 为容纳单字节 `INC EAX`，作用域标记从低代码洞末字节 `0x00639D3F` 移到已验证高代码洞末字节 `0x00639D7F`；两处均为同一静态字节标记，语义不变。

ZIP SHA-256：`{report['zip_sha256']}`
"""


base.instructions = instructions
base.research_markdown = research_markdown


if __name__ == "__main__":
    raise SystemExit(base.main())
