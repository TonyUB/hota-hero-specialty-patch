# Patch_v1.8 PE 静态清单

> 证据等级：静态候选。此报告不能证明 HotA 1.8.0 运行时执行这些地址。

## 输入

| 文件 | 大小 | SHA-256 | ImageBase | EntryPoint |
|---|---:|---|---:|---:|
| `h3hota.exe` | 2932736 | `3a2de7000a79040c42633dcd512ee76e5568bad260622f5cac8a8c7f6512abf6` | `0x00400000` | `0x00639C00` |
| `h3hota HD.exe` | 2932736 | `7c3c6deca0c3afbb2e751512feefc65da5c5ea47536f337264e1a6cc6da826c2` | `0x00400000` | `0x00639C00` |

## 标准版与 HD 版差异

两个文件大小相同；共有 **21** 个不同字节，分布在 **3** 个连续区间。

| 文件偏移 | 长度 | 节区 | VA | 标准版字节 | HD 版字节 |
|---:|---:|---|---:|---|---|
| `0x00095590` | 3 | `.text` | `0x00495590` | `55 8b ec` | `c2 04 00` |
| `0x000955B7` | 9 | `.text` | `0x004955B7` | `00 00 8d 04 c0 8d 04 c0 8d` | `cd 23 68 6f 74 61 31 35 00` |
| `0x0025C6DC` | 9 | `.rdata` | `0x0065C6DC` | `6e 75 6c 6c 6d 73 73 00 00` | `5f 68 64 33 5f 2e 64 6c 6c` |

## h3hota.exe

- PE 时间戳（UTC）：`1996-02-26T04:38:09+00:00`
- SizeOfImage：`0x002E7000`
- Header checksum：`0x002D7751`
- Calculated checksum：`0x002D1DF4`
- Overlay offset：`—`

### 节区

| 名称 | RVA | VirtualSize | RawOffset | RawSize | Entropy | SHA-256 |
|---|---:|---:|---:|---:|---:|---|
| `.text` | `0x00001000` | `0x00238BF2` | `0x00001000` | `0x00239000` | 6.685503 | `13e2f4e9f64f3e4f7a73ad79f79fd598f10e47e26981cb25b81636e93571a75e` |
| `.rdata` | `0x0023A000` | `0x00023969` | `0x0023A000` | `0x00024000` | 4.226522 | `8fb3020bb0c0713d832b7bf648882e4acc1d77e0718eeff766457d5d3d84b4b7` |
| `.data` | `0x0025E000` | `0x0004EEC0` | `0x0025E000` | `0x00034000` | 4.340692 | `7e849a7e960f33e33b915f734fdc79cde9fc89e0dc290337acf915226ea9e405` |
| `.rsrc` | `0x002AD000` | `0x0003925C` | `0x00292000` | `0x0003A000` | 4.791310 | `5a11133c5588039a19e2e9c60dc9f8e53313f314b38c9d6b8361caf5639d18ab` |

### 导入模块

`VERSION.dll`, `WINMM.dll`, `nullmss`, `smackw32.dll`, `DDRAW.dll`, `WSOCK32.dll`, `KeRNeL32.dll`, `USER32.dll`, `GDI32.dll`, `ADVAPI32.dll`, `SHELL32.dll`, `ole32.dll`, `binkw32.dll`, `IFC20.dll`

### 历史候选地址

#### H3CombatCreature::ApplySpell (historical) — `0x00444610`

节区 `.text`，RVA `0x00044610`，文件偏移 `0x00044610`。
静态直接引用：`0x005A139F` (call), `0x005A140D` (call), `0x005A1517` (call), `0x005A18AA` (call), `0x005A1E07` (call), `0x005A213D` (call), `0x005A6A77` (call)。

```asm
00444610  55                       push ebp
00444611  8b ec                    mov ebp, esp
00444613  83 ec 20                 sub esp, 0x20
00444616  53                       push ebx
00444617  8b 5d 08                 mov ebx, dword ptr [ebp + 8]
0044461A  56                       push esi
0044461B  8b f1                    mov esi, ecx
0044461D  8d 43 d1                 lea eax, [ebx - 0x2f]
00444620  83 f8 19                 cmp eax, 0x19
00444623  77 56                    ja 0x44467b
00444625  33 c9                    xor ecx, ecx
00444627  8a 88 d8 50 44 00        mov cl, byte ptr [eax + 0x4450d8]
```

#### Cure core (historical candidate) — `0x00446220`

节区 `.text`，RVA `0x00046220`，文件偏移 `0x00046220`。
静态直接引用：`0x005A1B05` (call), `0x005A1BB4` (call)。

```asm
00446220  55                       push ebp
00446221  8b ec                    mov ebp, esp
00446223  83 ec 08                 sub esp, 8
00446226  56                       push esi
00446227  8b f1                    mov esi, ecx
00446229  8b 86 c4 02 00 00        mov eax, dword ptr [esi + 0x2c4]
0044622F  c7 86 a4 04 00 00 00 00 80 3f mov dword ptr [esi + 0x4a4], 0x3f800000
00446239  db 46 6c                 fild dword ptr [esi + 0x6c]
0044623C  85 c0                    test eax, eax
0044623E  74 0e                    je 0x44624e
00446240  d9 5d fc                 fstp dword ptr [ebp - 4]
00446243  d9 45 fc                 fld dword ptr [ebp - 4]
```

#### Cure injection point (historical candidate) — `0x0044632D`

节区 `.text`，RVA `0x0004632D`，文件偏移 `0x0004632D`。
静态直接引用：`0x0044631D` (je)。

```asm
0044632D  8b 46 58                 mov eax, dword ptr [esi + 0x58]
00446330  2b c7                    sub eax, edi
00446332  5f                       pop edi
00446333  89 46 58                 mov dword ptr [esi + 0x58], eax
00446336  79 07                    jns 0x44633f
00446338  c7 46 58 00 00 00 00     mov dword ptr [esi + 0x58], 0
0044633F  5e                       pop esi
00446340  8b e5                    mov esp, ebp
00446342  5d                       pop ebp
00446343  c2 0c 00                 ret 0xc
00446346  90                       nop
00446347  90                       nop
```

#### H3Hero::CalculateSpellCost (historical) — `0x004E54B0`

节区 `.text`，RVA `0x000E54B0`，文件偏移 `0x000E54B0`。
静态直接引用：`0x0041C727` (call), `0x0041C771` (call), `0x0041C7D8` (call), `0x0041C822` (call), `0x0041C9A2` (call), `0x0041CF57` (call), `0x0041D1ED` (call), `0x0041D43F` (call), `0x0041DA1E` (call), `0x0041FC29` (call), `0x00425CC4` (call), `0x00430502` (call), `0x00430B1D` (call), `0x00439466` (call), `0x0043C5E6` (call), `0x005278EC` (call), `0x0056B361` (call), `0x0056B800` (call), `0x0056B955` (call), `0x0056B9B0` (call), `0x0059D0F2` (call), `0x0059D1C8` (call), `0x0059D215` (call), `0x0059D740` (call), `0x005A02EF` (call)。

```asm
004E54B0  55                       push ebp
004E54B1  8b ec                    mov ebp, esp
004E54B3  53                       push ebx
004E54B4  56                       push esi
004E54B5  8b 75 08                 mov esi, dword ptr [ebp + 8]
004E54B8  8b d9                    mov ebx, ecx
004E54BA  83 fe 39                 cmp esi, 0x39
004E54BD  75 08                    jne 0x4e54c7
004E54BF  5e                       pop esi
004E54C0  33 c0                    xor eax, eax
004E54C2  5b                       pop ebx
004E54C3  5d                       pop ebp
```

#### H3CombatManager::CastSpell (historical) — `0x005A0140`

节区 `.text`，RVA `0x001A0140`，文件偏移 `0x001A0140`。
静态直接引用：`0x0044113C` (call), `0x004411A7` (call), `0x00447CEA` (call), `0x00447F70` (call), `0x004483D8` (call), `0x00464FF2` (call), `0x00465033` (call), `0x00465060` (call), `0x0046508D` (call), `0x004650BA` (call), `0x00468CE2` (call), `0x00478986` (call)。

```asm
005A0140  55                       push ebp
005A0141  8b ec                    mov ebp, esp
005A0143  6a ff                    push -1
005A0145  68 81 42 63 00           push 0x634281
005A014A  64 a1 00 00 00 00        mov eax, dword ptr fs:[0]
005A0150  50                       push eax
005A0151  64 89 25 00 00 00 00     mov dword ptr fs:[0], esp
005A0158  81 ec 94 00 00 00        sub esp, 0x94
005A015E  53                       push ebx
005A015F  8b d9                    mov ebx, ecx
005A0161  8b 4d 10                 mov ecx, dword ptr [ebp + 0x10]
005A0164  56                       push esi
```

#### H3CombatManager::GetResurrectionTarget (historical) — `0x005A3FD0`

节区 `.text`，RVA `0x001A3FD0`，文件偏移 `0x001A3FD0`。
静态直接引用：`0x004212D4` (call), `0x004212FD` (call), `0x0043A985` (call), `0x0043A9C4` (call), `0x0043AEB7` (call), `0x0043AEF0` (call), `0x00447179` (call), `0x004474F0` (call), `0x00448296` (call), `0x00492A78` (call), `0x005A1C38` (call), `0x005A3CBF` (call), `0x005A89FC` (call), `0x005A8B28` (call)。

```asm
005A3FD0  55                       push ebp
005A3FD1  8b ec                    mov ebp, esp
005A3FD3  51                       push ecx
005A3FD4  8b 45 0c                 mov eax, dword ptr [ebp + 0xc]
005A3FD7  53                       push ebx
005A3FD8  8b d9                    mov ebx, ecx
005A3FDA  56                       push esi
005A3FDB  85 c0                    test eax, eax
005A3FDD  57                       push edi
005A3FDE  89 5d fc                 mov dword ptr [ebp - 4], ebx
005A3FE1  0f 8c 53 01 00 00        jl 0x5a413a
005A3FE7  3d bb 00 00 00           cmp eax, 0xbb
```

#### H3CombatManager::ResurrectTarget (historical) — `0x005A7870`

节区 `.text`，RVA `0x001A7870`，文件偏移 `0x001A7870`。
静态直接引用：`0x004482DE` (call), `0x0046918D` (call), `0x005A1CA2` (call), `0x005A1D59` (call)。

```asm
005A7870  55                       push ebp
005A7871  8b ec                    mov ebp, esp
005A7873  51                       push ecx
005A7874  53                       push ebx
005A7875  56                       push esi
005A7876  8b 75 08                 mov esi, dword ptr [ebp + 8]
005A7879  57                       push edi
005A787A  8b d9                    mov ebx, ecx
005A787C  8b 46 38                 mov eax, dword ptr [esi + 0x38]
005A787F  89 45 fc                 mov dword ptr [ebp - 4], eax
005A7882  8b 46 4c                 mov eax, dword ptr [esi + 0x4c]
005A7885  85 c0                    test eax, eax
```

#### Existing patch/code-cave risk area — `0x00639D00`

节区 `.text`，RVA `0x00239D00`，文件偏移 `0x00239D00`。
静态直接引用：`0x004E65DC` (jmp)。

```asm
00639D00  8b 48 1a                 mov ecx, dword ptr [eax + 0x1a]
00639D03  81 f9 9b 00 00 00        cmp ecx, 0x9b
00639D09  0f 84 d8 c8 ea ff        je 0x4e65e7
00639D0F  81 f9 8d 00 00 00        cmp ecx, 0x8d
00639D15  0f 84 cc c8 ea ff        je 0x4e65e7
00639D1B  e9 ca c8 ea ff           jmp 0x4e65ea
00639D20  00 00                    add byte ptr [eax], al
00639D22  00 00                    add byte ptr [eax], al
00639D24  00 00                    add byte ptr [eax], al
00639D26  00 00                    add byte ptr [eax], al
00639D28  00 00                    add byte ptr [eax], al
00639D2A  00 00                    add byte ptr [eax], al
```

#### Historical crash address — `0x0069124C`

节区 `.data`，RVA `0x0029124C`，文件偏移 `0x0029124C`。
静态直接引用：未发现；可能经跳转表或间接调用到达。

```asm
0069124C  00 00                    add byte ptr [eax], al
0069124E  00 00                    add byte ptr [eax], al
00691250  00 00                    add byte ptr [eax], al
00691252  00 00                    add byte ptr [eax], al
00691254  00 00                    add byte ptr [eax], al
00691256  00 00                    add byte ptr [eax], al
00691258  00 00                    add byte ptr [eax], al
0069125A  00 00                    add byte ptr [eax], al
0069125C  00 00                    add byte ptr [eax], al
0069125E  00 00                    add byte ptr [eax], al
00691260  00 00                    add byte ptr [eax], al
00691262  00 00                    add byte ptr [eax], al
```


## h3hota HD.exe

- PE 时间戳（UTC）：`1996-02-26T04:38:09+00:00`
- SizeOfImage：`0x002E7000`
- Header checksum：`0x002D7751`
- Calculated checksum：`0x002D7383`
- Overlay offset：`—`

### 节区

| 名称 | RVA | VirtualSize | RawOffset | RawSize | Entropy | SHA-256 |
|---|---:|---:|---:|---:|---:|---|
| `.text` | `0x00001000` | `0x00238BF2` | `0x00001000` | `0x00239000` | 6.685517 | `3b53c67c489d60f14ebe6126691ed5bc5ca398e9ab7d848abb662aac153ab8aa` |
| `.rdata` | `0x0023A000` | `0x00023969` | `0x0023A000` | `0x00024000` | 4.226601 | `8279a8dbbc17eeba9d6a0024e8d15c4d19fb0065475d0324af346894f192f6af` |
| `.data` | `0x0025E000` | `0x0004EEC0` | `0x0025E000` | `0x00034000` | 4.340692 | `7e849a7e960f33e33b915f734fdc79cde9fc89e0dc290337acf915226ea9e405` |
| `.rsrc` | `0x002AD000` | `0x0003925C` | `0x00292000` | `0x0003A000` | 4.791310 | `5a11133c5588039a19e2e9c60dc9f8e53313f314b38c9d6b8361caf5639d18ab` |

### 导入模块

`VERSION.dll`, `WINMM.dll`, `_hd3_.dll`, `smackw32.dll`, `DDRAW.dll`, `WSOCK32.dll`, `KeRNeL32.dll`, `USER32.dll`, `GDI32.dll`, `ADVAPI32.dll`, `SHELL32.dll`, `ole32.dll`, `binkw32.dll`, `IFC20.dll`

### 历史候选地址

#### H3CombatCreature::ApplySpell (historical) — `0x00444610`

节区 `.text`，RVA `0x00044610`，文件偏移 `0x00044610`。
静态直接引用：`0x005A139F` (call), `0x005A140D` (call), `0x005A1517` (call), `0x005A18AA` (call), `0x005A1E07` (call), `0x005A213D` (call), `0x005A6A77` (call)。

```asm
00444610  55                       push ebp
00444611  8b ec                    mov ebp, esp
00444613  83 ec 20                 sub esp, 0x20
00444616  53                       push ebx
00444617  8b 5d 08                 mov ebx, dword ptr [ebp + 8]
0044461A  56                       push esi
0044461B  8b f1                    mov esi, ecx
0044461D  8d 43 d1                 lea eax, [ebx - 0x2f]
00444620  83 f8 19                 cmp eax, 0x19
00444623  77 56                    ja 0x44467b
00444625  33 c9                    xor ecx, ecx
00444627  8a 88 d8 50 44 00        mov cl, byte ptr [eax + 0x4450d8]
```

#### Cure core (historical candidate) — `0x00446220`

节区 `.text`，RVA `0x00046220`，文件偏移 `0x00046220`。
静态直接引用：`0x005A1B05` (call), `0x005A1BB4` (call)。

```asm
00446220  55                       push ebp
00446221  8b ec                    mov ebp, esp
00446223  83 ec 08                 sub esp, 8
00446226  56                       push esi
00446227  8b f1                    mov esi, ecx
00446229  8b 86 c4 02 00 00        mov eax, dword ptr [esi + 0x2c4]
0044622F  c7 86 a4 04 00 00 00 00 80 3f mov dword ptr [esi + 0x4a4], 0x3f800000
00446239  db 46 6c                 fild dword ptr [esi + 0x6c]
0044623C  85 c0                    test eax, eax
0044623E  74 0e                    je 0x44624e
00446240  d9 5d fc                 fstp dword ptr [ebp - 4]
00446243  d9 45 fc                 fld dword ptr [ebp - 4]
```

#### Cure injection point (historical candidate) — `0x0044632D`

节区 `.text`，RVA `0x0004632D`，文件偏移 `0x0004632D`。
静态直接引用：`0x0044631D` (je)。

```asm
0044632D  8b 46 58                 mov eax, dword ptr [esi + 0x58]
00446330  2b c7                    sub eax, edi
00446332  5f                       pop edi
00446333  89 46 58                 mov dword ptr [esi + 0x58], eax
00446336  79 07                    jns 0x44633f
00446338  c7 46 58 00 00 00 00     mov dword ptr [esi + 0x58], 0
0044633F  5e                       pop esi
00446340  8b e5                    mov esp, ebp
00446342  5d                       pop ebp
00446343  c2 0c 00                 ret 0xc
00446346  90                       nop
00446347  90                       nop
```

#### H3Hero::CalculateSpellCost (historical) — `0x004E54B0`

节区 `.text`，RVA `0x000E54B0`，文件偏移 `0x000E54B0`。
静态直接引用：`0x0041C727` (call), `0x0041C771` (call), `0x0041C7D8` (call), `0x0041C822` (call), `0x0041C9A2` (call), `0x0041CF57` (call), `0x0041D1ED` (call), `0x0041D43F` (call), `0x0041DA1E` (call), `0x0041FC29` (call), `0x00425CC4` (call), `0x00430502` (call), `0x00430B1D` (call), `0x00439466` (call), `0x0043C5E6` (call), `0x005278EC` (call), `0x0056B361` (call), `0x0056B800` (call), `0x0056B955` (call), `0x0056B9B0` (call), `0x0059D0F2` (call), `0x0059D1C8` (call), `0x0059D215` (call), `0x0059D740` (call), `0x005A02EF` (call)。

```asm
004E54B0  55                       push ebp
004E54B1  8b ec                    mov ebp, esp
004E54B3  53                       push ebx
004E54B4  56                       push esi
004E54B5  8b 75 08                 mov esi, dword ptr [ebp + 8]
004E54B8  8b d9                    mov ebx, ecx
004E54BA  83 fe 39                 cmp esi, 0x39
004E54BD  75 08                    jne 0x4e54c7
004E54BF  5e                       pop esi
004E54C0  33 c0                    xor eax, eax
004E54C2  5b                       pop ebx
004E54C3  5d                       pop ebp
```

#### H3CombatManager::CastSpell (historical) — `0x005A0140`

节区 `.text`，RVA `0x001A0140`，文件偏移 `0x001A0140`。
静态直接引用：`0x0044113C` (call), `0x004411A7` (call), `0x00447CEA` (call), `0x00447F70` (call), `0x004483D8` (call), `0x00464FF2` (call), `0x00465033` (call), `0x00465060` (call), `0x0046508D` (call), `0x004650BA` (call), `0x00468CE2` (call), `0x00478986` (call)。

```asm
005A0140  55                       push ebp
005A0141  8b ec                    mov ebp, esp
005A0143  6a ff                    push -1
005A0145  68 81 42 63 00           push 0x634281
005A014A  64 a1 00 00 00 00        mov eax, dword ptr fs:[0]
005A0150  50                       push eax
005A0151  64 89 25 00 00 00 00     mov dword ptr fs:[0], esp
005A0158  81 ec 94 00 00 00        sub esp, 0x94
005A015E  53                       push ebx
005A015F  8b d9                    mov ebx, ecx
005A0161  8b 4d 10                 mov ecx, dword ptr [ebp + 0x10]
005A0164  56                       push esi
```

#### H3CombatManager::GetResurrectionTarget (historical) — `0x005A3FD0`

节区 `.text`，RVA `0x001A3FD0`，文件偏移 `0x001A3FD0`。
静态直接引用：`0x004212D4` (call), `0x004212FD` (call), `0x0043A985` (call), `0x0043A9C4` (call), `0x0043AEB7` (call), `0x0043AEF0` (call), `0x00447179` (call), `0x004474F0` (call), `0x00448296` (call), `0x00492A78` (call), `0x005A1C38` (call), `0x005A3CBF` (call), `0x005A89FC` (call), `0x005A8B28` (call)。

```asm
005A3FD0  55                       push ebp
005A3FD1  8b ec                    mov ebp, esp
005A3FD3  51                       push ecx
005A3FD4  8b 45 0c                 mov eax, dword ptr [ebp + 0xc]
005A3FD7  53                       push ebx
005A3FD8  8b d9                    mov ebx, ecx
005A3FDA  56                       push esi
005A3FDB  85 c0                    test eax, eax
005A3FDD  57                       push edi
005A3FDE  89 5d fc                 mov dword ptr [ebp - 4], ebx
005A3FE1  0f 8c 53 01 00 00        jl 0x5a413a
005A3FE7  3d bb 00 00 00           cmp eax, 0xbb
```

#### H3CombatManager::ResurrectTarget (historical) — `0x005A7870`

节区 `.text`，RVA `0x001A7870`，文件偏移 `0x001A7870`。
静态直接引用：`0x004482DE` (call), `0x0046918D` (call), `0x005A1CA2` (call), `0x005A1D59` (call)。

```asm
005A7870  55                       push ebp
005A7871  8b ec                    mov ebp, esp
005A7873  51                       push ecx
005A7874  53                       push ebx
005A7875  56                       push esi
005A7876  8b 75 08                 mov esi, dword ptr [ebp + 8]
005A7879  57                       push edi
005A787A  8b d9                    mov ebx, ecx
005A787C  8b 46 38                 mov eax, dword ptr [esi + 0x38]
005A787F  89 45 fc                 mov dword ptr [ebp - 4], eax
005A7882  8b 46 4c                 mov eax, dword ptr [esi + 0x4c]
005A7885  85 c0                    test eax, eax
```

#### Existing patch/code-cave risk area — `0x00639D00`

节区 `.text`，RVA `0x00239D00`，文件偏移 `0x00239D00`。
静态直接引用：`0x004E65DC` (jmp)。

```asm
00639D00  8b 48 1a                 mov ecx, dword ptr [eax + 0x1a]
00639D03  81 f9 9b 00 00 00        cmp ecx, 0x9b
00639D09  0f 84 d8 c8 ea ff        je 0x4e65e7
00639D0F  81 f9 8d 00 00 00        cmp ecx, 0x8d
00639D15  0f 84 cc c8 ea ff        je 0x4e65e7
00639D1B  e9 ca c8 ea ff           jmp 0x4e65ea
00639D20  00 00                    add byte ptr [eax], al
00639D22  00 00                    add byte ptr [eax], al
00639D24  00 00                    add byte ptr [eax], al
00639D26  00 00                    add byte ptr [eax], al
00639D28  00 00                    add byte ptr [eax], al
00639D2A  00 00                    add byte ptr [eax], al
```

#### Historical crash address — `0x0069124C`

节区 `.data`，RVA `0x0029124C`，文件偏移 `0x0029124C`。
静态直接引用：未发现；可能经跳转表或间接调用到达。

```asm
0069124C  00 00                    add byte ptr [eax], al
0069124E  00 00                    add byte ptr [eax], al
00691250  00 00                    add byte ptr [eax], al
00691252  00 00                    add byte ptr [eax], al
00691254  00 00                    add byte ptr [eax], al
00691256  00 00                    add byte ptr [eax], al
00691258  00 00                    add byte ptr [eax], al
0069125A  00 00                    add byte ptr [eax], al
0069125C  00 00                    add byte ptr [eax], al
0069125E  00 00                    add byte ptr [eax], al
00691260  00 00                    add byte ptr [eax], al
00691262  00 00                    add byte ptr [eax], al
```

## 当前结论边界

- 本报告只能说明磁盘文件在这些地址存在何种字节和静态指令。
- 没有纯净 HotA 1.8.0 EXE 时，不能判断这些字节属于官方版本还是 Patch_v1.8 修改。
- 没有 HotA/HD DLL、patcher 和动态命中证据时，不能判断游戏运行时是否执行、覆盖或绕开这些代码。
- 在诊断日志经实机确认前，不得基于本报告注入复活逻辑。
