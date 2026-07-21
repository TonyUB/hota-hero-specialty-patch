# Patch_v2.5_STAGE3_TEST 启动故障取证

状态：**已撤回，禁止安装。**

## 用户现象

补丁覆盖到干净 HotA 1.8.0 后，游戏无法启动。

## 确定根因

启动代码在 `0x00639C00` 加载 `hota.dll`，随后把 `0x00639C20` 的 `MainProc\0` 传给 `GetProcAddress`，并在 `0x00639C17` 调用返回地址。

原 Stage 3 构建器把群体尸体扫描载荷放在 `0x00639C28`。该字节是 `MainProc` 的 NUL 终止符，而不是空闲代码洞。载荷覆盖终止符后，导出名延伸进机器码，`GetProcAddress` 无法解析 `MainProc`，启动流程随后调用空地址。

这是可重复的静态因果链，发生在玩法补丁入口执行之前。不会修改存档。

## 故障包标识

- ZIP SHA-256：`ccff614ce639415b8da4abc5aaff4a264f19a144e37a7851d520a7e89e29a4b0`
- `h3hota.exe` SHA-256：`8f729d9879af91020e3827df4522d5cef7bde9c3706acdd156e516269aa163ea`
- `h3hota HD.exe` SHA-256：`f6a0c003b661bc0dfeb38fc565acc62d10b97201637d4e5d300b0e7e64244a0a`

## 修复与防回归

- 修正版使用新名称 `Patch_v2.5_STAGE3_TEST2`，不会覆盖故障包。
- 第二载荷起点移到终止符之后的 `0x00639C29`。
- 构建器在写入前后都要求 `0x00639C20` 的 9 字节严格等于 `MainProc\0`。
- 故障包仅保存在本目录供取证，不得放回 `TEST/` 或 `Download/`。
