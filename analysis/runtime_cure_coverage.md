# Cure 与原生复活接口的运行模块覆盖分析

状态：**静态覆盖已完成；用户测试所用启动版本的运行时命中已确认。**

## 输入

用户提供了同一套未修改 HotA 1.8.0 安装目录中的两个 EXE、`HotA.dll`、`HD_HOTA.dll`、`HW_HOTA.dll` 和 `patcher_x86.dll`。文件哈希见 `baselines/hota180_clean_SHA256.txt`，模块清单见 `runtime_modules.md` / `runtime_modules.json`。

## DLL/patcher 对 Cure 调用点的静态覆盖

四个运行模块中均未发现：

- 单体 Cure 原始调用字节 `E8 16 47 EA FF`；
- 群体 Cure 原始调用字节 `E8 67 46 EA FF`；
- 两处调用点或 CureCore 的 32 字节 EXE 上下文签名；
- `0x005A1B05`、`0x005A1BB4` 或 `0x00446220` 的绝对地址字面量。

因此，目前没有发现这些模块通过“保存原始 call 字节/绝对地址”的简单方式覆盖两处 Cure 调用。但 `HotA.dll` 与 `patcher_x86.dll` 都具备 patcher/Hook 设施，仍可能在运行时计算地址或模式扫描，静态未命中不能替代实机证明。

## `HotA.dll` 对原生复活接口的直接调用

`HotA.dll` 含有 5 个 EXE 绝对地址字面量，反汇编证明它们不是无关数据，而是 `mov eax, address; call eax` 形式的实际调用：

| HotA.dll 调用位置 | EXE 目标 | 文件偏移 | 关键调用形态 |
|---:|---:|---:|---|
| `0x1006D7B2` | `GetResurrectionTarget` `0x005A3FD0` | `0x0006CBB2` | `push context; push ...; push ...; call eax` |
| `0x1006DC70` | `GetResurrectionTarget` `0x005A3FD0` | `0x0006D070` | `push context; push ...; push ...; call eax` |
| `0x1006DD6D` | `GetResurrectionTarget` `0x005A3FD0` | `0x0006D16D` | `push context; push ...; push ...; call eax` |
| `0x10126752` | `ResurrectTarget` `0x005A7870` | `0x00125B52` | `push 0; push hitPoints; push target; call eax` |
| `0x101457F7` | `ResurrectTarget` `0x005A7870` | `0x00144BF7` | `push 0; push hitPoints; push target; call eax` |

后两处都把第三参数 `temporary` 设为 `0`。这从 HotA 1.8.0 自身的代码再次证明：调用原生 `ResurrectTarget(..., temporary=0)` 是正式运行模块已经采用的永久复活路径。

该证据只确认接口地址与调用方式可用，不授权在诊断版中执行复活；功能接入仍必须等实机日志证明 Cure 包装器命中。

## 诊断日志设施

两个 EXE 的导入表相同，并固定导入：

| API | IAT VA |
|---|---:|
| `CloseHandle` | `0x0063A0C8` |
| `CreateFileA` | `0x0063A108` |
| `WriteFile` | `0x0063A114` |

两个 EXE 均未启用 ASLR，`.text` 节区可读、可写、可执行。`Patch_v1.8` 的 `0x00639D80–0x00639FFC` 为零填充；诊断载荷使用 `0x00639D80–0x00639FDA`，不碰既有 `0x00639D00` 与 `0x00639D40` 两段 Hook，也不覆盖节区尾部非零字节。

## 证据结论

1. 纯净 EXE 与 `Patch_v1.8` 中两处 Cure 调用和 CureCore 完全一致。
2. DLL/patcher 静态扫描未发现对这两处调用的简单覆盖证据。
3. `HotA.dll` 已直接使用候选的原生资格验证与永久复活函数，接口地址可信度显著提高。
4. 用户回传日志已经证明测试所用启动版本真实命中；日志本身未记录 EXE 类型，因此另一个启动版本仍应在 Stage 2 测试中补测并注明。
