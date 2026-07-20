# Analysis workspace

开始游戏逻辑补丁前必须完成以下交付物：

- [ ] `baseline_diff.md`：已完成两个修改版 EXE 的内部比较；纯净 1.8.0 差异与回滚字节待输入
- [ ] `existing_patch_map.json`：已登记两处现有 Hook 占用；完整归属与原始字节待纯净输入
- [ ] `cure_runtime_path.md`：静态调用图、Cure 溢出返回值和原生复活路径已定位；运行时证据待诊断
- [ ] `runtime_traces/`：能够证明真实路径执行的日志或调试证据
- [ ] `call_graphs/`：EXE、HotA DLL、HD DLL 与 patcher 之间的调用/覆盖关系

辅助产物：

- `pe_inventory.md` / `pe_inventory.json`：两个基线 EXE 的可复现 PE、反汇编和静态直接引用清单
- `../tools/analyze_pe.py`：生成上述清单
- `../tools/extract_lod.py`：安全列出/解包 H3 LOD，用于核验英雄数据来源

静态成果不能替代运行时日志，以上必需项仍未全部完成。
