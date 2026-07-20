# 纯净 HotA 1.8.0 → Patch_v1.8 EXE 差异

标准版与 HD 版的补丁修改集合完全一致。

| 目标 | 纯净 SHA-256 | Patch SHA-256 | 不同字节 | 精确区间 | 逻辑分组 |
|---|---|---|---:|---:|---:|
| 标准版 | `b5f2f793af0986050fb41df7209c25d861ae0f837af52bb3bd6864ba4de84f41` | `3a2de7000a79040c42633dcd512ee76e5568bad260622f5cac8a8c7f6512abf6` | 80 | 17 | 6 |
| HD 版 | `5aaab925f06cccf23bb09814767590a95b84a557eb33d244800520be4f1f18de` | `7c3c6deca0c3afbb2e751512feefc65da5c5ea47536f337264e1a6cc6da826c2` | 80 | 17 | 6 |

## 精确差异区间（标准版；HD 版相同）

| 文件偏移 | VA | 节区 | 长度 | 纯净/回滚字节 | Patch_v1.8 字节 |
|---:|---:|---|---:|---|---|
| `0x000E5597` | `0x004E5597` | `.text` | 5 | `8b c6 5e 5b 5d` | `e9 a4 47 15 00` |
| `0x000E65DC` | `0x004E65DC` | `.text` | 11 | `8b 48 1a 81 f9 9b 00 00 00 75 03` | `e9 1f 37 15 00 90 90 90 90 90 90` |
| `0x00239D00` | `0x00639D00` | `.text` | 6 | `00 00 00 00 00 00` | `8b 48 1a 81 f9 9b` |
| `0x00239D09` | `0x00639D09` | `.text` | 9 | `00 00 00 00 00 00 00 00 00` | `0f 84 d8 c8 ea ff 81 f9 8d` |
| `0x00239D15` | `0x00639D15` | `.text` | 11 | `00 00 00 00 00 00 00 00 00 00 00` | `0f 84 cc c8 ea ff e9 ca c8 ea ff` |
| `0x00239D40` | `0x00639D40` | `.text` | 24 | `00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00` | `83 7b 1a 09 75 08 83 7d 08 29 75 02 31 f6 8b c6 5e 5b 5d e9 44 b8 ea ff` |
| `0x00279A28` | `0x00679A28` | `.data` | 1 | `03` | `04` |
| `0x00279A2C` | `0x00679A2C` | `.data` | 1 | `2f` | `76` |
| `0x00279A38` | `0x00679A38` | `.data` | 1 | `00` | `01` |
| `0x0027D07C` | `0x0067D07C` | `.data` | 1 | `00` | `01` |
| `0x0027D084` | `0x0067D084` | `.data` | 1 | `11` | `10` |
| `0x0027D088` | `0x0067D088` | `.data` | 1 | `07` | `13` |
| `0x0027D090` | `0x0067D090` | `.data` | 1 | `0f` | `16` |
| `0x0027D098` | `0x0067D098` | `.data` | 1 | `01` | `00` |
| `0x0027D09C` | `0x0067D09C` | `.data` | 4 | `2f 00 00 00` | `ff ff ff ff` |
| `0x0027D0A4` | `0x0067D0A4` | `.data` | 1 | `70` | `76` |
| `0x0027D0A8` | `0x0067D0A8` | `.data` | 1 | `73` | `76` |

## 逻辑分组

### 1. `0x000E5597` / `0x004E5597` (.text, 5 bytes)

纯净/回滚：`8b c6 5e 5b 5d`

Patch_v1.8：`e9 a4 47 15 00`

纯净：

```asm
004E5597  8b c6                        mov eax, esi
004E5599  5e                           pop esi
004E559A  5b                           pop ebx
004E559B  5d                           pop ebp
```

Patch_v1.8：

```asm
004E5597  e9 a4 47 15 00               jmp 0x639d40
```

### 2. `0x000E65DC` / `0x004E65DC` (.text, 11 bytes)

纯净/回滚：`8b 48 1a 81 f9 9b 00 00 00 75 03`

Patch_v1.8：`e9 1f 37 15 00 90 90 90 90 90 90`

纯净：

```asm
004E65DC  8b 48 1a                     mov ecx, dword ptr [eax + 0x1a]
004E65DF  81 f9 9b 00 00 00            cmp ecx, 0x9b
004E65E5  75 03                        jne 0x4e65ea
```

Patch_v1.8：

```asm
004E65DC  e9 1f 37 15 00               jmp 0x639d00
004E65E1  90                           nop
004E65E2  90                           nop
004E65E3  90                           nop
004E65E4  90                           nop
004E65E5  90                           nop
004E65E6  90                           nop
```

### 3. `0x00239D00` / `0x00639D00` (.text, 32 bytes)

纯净/回滚：`00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00`

Patch_v1.8：`8b 48 1a 81 f9 9b 00 00 00 0f 84 d8 c8 ea ff 81 f9 8d 00 00 00 0f 84 cc c8 ea ff e9 ca c8 ea ff`

纯净：

```asm
00639D00  00 00                        add byte ptr [eax], al
00639D02  00 00                        add byte ptr [eax], al
00639D04  00 00                        add byte ptr [eax], al
00639D06  00 00                        add byte ptr [eax], al
00639D08  00 00                        add byte ptr [eax], al
00639D0A  00 00                        add byte ptr [eax], al
00639D0C  00 00                        add byte ptr [eax], al
00639D0E  00 00                        add byte ptr [eax], al
00639D10  00 00                        add byte ptr [eax], al
00639D12  00 00                        add byte ptr [eax], al
00639D14  00 00                        add byte ptr [eax], al
00639D16  00 00                        add byte ptr [eax], al
00639D18  00 00                        add byte ptr [eax], al
00639D1A  00 00                        add byte ptr [eax], al
00639D1C  00 00                        add byte ptr [eax], al
00639D1E  00 00                        add byte ptr [eax], al
```

Patch_v1.8：

```asm
00639D00  8b 48 1a                     mov ecx, dword ptr [eax + 0x1a]
00639D03  81 f9 9b 00 00 00            cmp ecx, 0x9b
00639D09  0f 84 d8 c8 ea ff            je 0x4e65e7
00639D0F  81 f9 8d 00 00 00            cmp ecx, 0x8d
00639D15  0f 84 cc c8 ea ff            je 0x4e65e7
00639D1B  e9 ca c8 ea ff               jmp 0x4e65ea
```

### 4. `0x00239D40` / `0x00639D40` (.text, 24 bytes)

纯净/回滚：`00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00`

Patch_v1.8：`83 7b 1a 09 75 08 83 7d 08 29 75 02 31 f6 8b c6 5e 5b 5d e9 44 b8 ea ff`

纯净：

```asm
00639D40  00 00                        add byte ptr [eax], al
00639D42  00 00                        add byte ptr [eax], al
00639D44  00 00                        add byte ptr [eax], al
00639D46  00 00                        add byte ptr [eax], al
00639D48  00 00                        add byte ptr [eax], al
00639D4A  00 00                        add byte ptr [eax], al
00639D4C  00 00                        add byte ptr [eax], al
00639D4E  00 00                        add byte ptr [eax], al
00639D50  00 00                        add byte ptr [eax], al
00639D52  00 00                        add byte ptr [eax], al
00639D54  00 00                        add byte ptr [eax], al
00639D56  00 00                        add byte ptr [eax], al
```

Patch_v1.8：

```asm
00639D40  83 7b 1a 09                  cmp dword ptr [ebx + 0x1a], 9
00639D44  75 08                        jne 0x639d4e
00639D46  83 7d 08 29                  cmp dword ptr [ebp + 8], 0x29
00639D4A  75 02                        jne 0x639d4e
00639D4C  31 f6                        xor esi, esi
00639D4E  8b c6                        mov eax, esi
00639D50  5e                           pop esi
00639D51  5b                           pop ebx
00639D52  5d                           pop ebp
00639D53  e9 44 b8 ea ff               jmp 0x4e559c
```

### 5. `0x00279A28` / `0x00679A28` (.data, 17 bytes)

纯净/回滚：`03 00 00 00 2f 00 00 00 00 00 00 00 00 00 00 00 00`

Patch_v1.8：`04 00 00 00 76 00 00 00 00 00 00 00 00 00 00 00 01`

纯净：

```asm
00679A28  03 00                        add eax, dword ptr [eax]
00679A2A  00 00                        add byte ptr [eax], al
00679A2C  2f                           das
00679A2D  00 00                        add byte ptr [eax], al
00679A2F  00 00                        add byte ptr [eax], al
00679A31  00 00                        add byte ptr [eax], al
00679A33  00 00                        add byte ptr [eax], al
00679A35  00 00                        add byte ptr [eax], al
00679A37  00 00                        add byte ptr [eax], al
```

Patch_v1.8：

```asm
00679A28  04 00                        add al, 0
00679A2A  00 00                        add byte ptr [eax], al
00679A2C  76 00                        jbe 0x679a2e
00679A2E  00 00                        add byte ptr [eax], al
00679A30  00 00                        add byte ptr [eax], al
00679A32  00 00                        add byte ptr [eax], al
00679A34  00 00                        add byte ptr [eax], al
00679A36  00 00                        add byte ptr [eax], al
```

### 6. `0x0027D07C` / `0x0067D07C` (.data, 45 bytes)

纯净/回滚：`00 00 00 00 07 00 00 00 11 00 00 00 07 00 00 00 01 00 00 00 0f 00 00 00 01 00 00 00 01 00 00 00 2f 00 00 00 76 00 00 00 70 00 00 00 73`

Patch_v1.8：`01 00 00 00 07 00 00 00 10 00 00 00 13 00 00 00 01 00 00 00 16 00 00 00 01 00 00 00 00 00 00 00 ff ff ff ff 76 00 00 00 76 00 00 00 76`

纯净：

```asm
0067D07C  00 00                        add byte ptr [eax], al
0067D07E  00 00                        add byte ptr [eax], al
0067D080  07                           pop es
0067D081  00 00                        add byte ptr [eax], al
0067D083  00 11                        add byte ptr [ecx], dl
0067D085  00 00                        add byte ptr [eax], al
0067D087  00 07                        add byte ptr [edi], al
0067D089  00 00                        add byte ptr [eax], al
0067D08B  00 01                        add byte ptr [ecx], al
0067D08D  00 00                        add byte ptr [eax], al
0067D08F  00 0f                        add byte ptr [edi], cl
0067D091  00 00                        add byte ptr [eax], al
0067D093  00 01                        add byte ptr [ecx], al
0067D095  00 00                        add byte ptr [eax], al
0067D097  00 01                        add byte ptr [ecx], al
0067D099  00 00                        add byte ptr [eax], al
0067D09B  00 2f                        add byte ptr [edi], ch
0067D09D  00 00                        add byte ptr [eax], al
0067D09F  00 76 00                     add byte ptr [esi], dh
0067D0A2  00 00                        add byte ptr [eax], al
0067D0A4  70 00                        jo 0x67d0a6
0067D0A6  00 00                        add byte ptr [eax], al
```

Patch_v1.8：

```asm
0067D07C  01 00                        add dword ptr [eax], eax
0067D07E  00 00                        add byte ptr [eax], al
0067D080  07                           pop es
0067D081  00 00                        add byte ptr [eax], al
0067D083  00 10                        add byte ptr [eax], dl
0067D085  00 00                        add byte ptr [eax], al
0067D087  00 13                        add byte ptr [ebx], dl
0067D089  00 00                        add byte ptr [eax], al
0067D08B  00 01                        add byte ptr [ecx], al
0067D08D  00 00                        add byte ptr [eax], al
0067D08F  00 16                        add byte ptr [esi], dl
0067D091  00 00                        add byte ptr [eax], al
0067D093  00 01                        add byte ptr [ecx], al
0067D095  00 00                        add byte ptr [eax], al
0067D097  00 00                        add byte ptr [eax], al
0067D099  00 00                        add byte ptr [eax], al
0067D09B  00 ff                        add bh, bh
```

## 结论

- 纯净与 Patch_v1.8 的两个 EXE 均为相同尺寸；没有新增 PE 节区或文件增长。
- Patch_v1.8 对两个 EXE 应用了完全相同的 80 个差异字节。
- 代码修改集中在两处 Hook 和 `0x00639D00` / `0x00639D40` 两段原始零区代码。
- 其余数据修改集中在 `0x00679A28` 附近和 `0x0067D07C` 附近。
- CureCore 与两个 Cure call 点在纯净版和 Patch_v1.8 中均未变化。
