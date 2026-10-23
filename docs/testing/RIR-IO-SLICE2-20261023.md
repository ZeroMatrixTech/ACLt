# RIR 切片 2：安全 SDK 与可观察 I/O（2026-10-23）

结论：限定 I/O 切片完成。用户 Rust → 受信 SDK/入口 → 候选工件 → 限定结构/类型/canonical 检查 → Python 参考执行 → outcome/输出摘要，在 A/B 两台物理主机分别运行通过。该链仍为候选实验，不是完整 RIR/RPR 或生产执行证明。

基线 `677f244cb289a8b1432ec9ace4803d9deb331ea8`，叠加已有未提交切片 1 和本轮独立实验目录；不改写此前证据。源码入口 [aclt-rir-io-probe](../../experiments/aclt-rir-io-probe/README.md)。使用切片 1 已验收的官方 1.93.1 独立 prefix，未替换系统 Rust，无新增 Cargo/Python/Node 运行依赖。SSH 只控制和回收；本轮是两端独立构建/执行比较，不声称新增跨 LAN 任务接纳协议证据。

## 实际实现边界

- 用户库 no_std / forbid(unsafe_code)；安全 SDK 精确封装 5 个 aclt ABI。仅 SDK FFI 与入口导出层使用 unsafe 设施并绑定源码摘要。
- 负载要求一个 16 字节输入，输出相同 16 字节；不合要求的输入长度走 ABORT(2)。输入数量与候选 input_arity=1 不等先拒绝；两项明确标记的 unbound module probe 专测程序 input_count 分支 ABORT(1)，不是合法工件。
- 本地后处理识别并重新编码受限 Wasm grammar，包括有补长 LEB 的 call/global 索引、locals 和空 else；去掉已知自定义段及辅助 global 导出。原始产物 768 字节，后处理后 280 字节。导入签名/名称/模块精确检查，导出只留 run 与 memory。
- 限定类型检查覆盖支持指令的操作数、local/global、函数调用和 void 控制块；未知指令/结构拒绝。候选 CBOR reader 核对字段集合/值、规范表示、body 和输入数量；不是正式 Receipt/Lease。
- Python 解释器执行整数、受限访存、void 控制与直接调用；按候选表计量 gas。实例化 8192，正常路径额外 79，共 8271，逐指令账单见 [机器摘要](rir-io-slice2-20261023.json)。这仅对固定 fixture 核算，不是全语言计量证明。
- 同调用内先 gas、后参数地址、再输出限额；非 OK 不发布部分输出。范围加法使用数学整数。受控 Host 步数上限产生 HostFault，不能改写为 Task gas 耗尽；不宣称普通 Python 进程是生产敌对代码沙箱。

## 双机与独立语义核对

两台机器各两个新目录，从同一源码/lock 独立编译 SDK、用户库和入口，并独立执行每份工件的 55 个用例；四份 raw/normalized/候选工件和 execution.json 均逐字节一致。

每份用例：38 OK、7 ABORT（含两项 unbound module ABI probe）、4 创建期拒绝、2 gas trap、2 output-limit trap、1 call-depth trap、1 HostFault，共 55；四份共 220 条记录，不能把拒绝与宿主故障都算成合法 Task 执行。输入包括固定模式、32 个固定种子随机字节、错误长度、输入绑定，以及 gas/限额/深度边界。

A 上已有 Node 引擎对四份 raw 和四份 normalized 共 8 个模块，执行 360 次独立语义对拍：输出、ABORT、output-limit 一致。该 oracle **不覆盖 gas、call depth 或外壳/输入绑定**。A/B 受限执行都使用同一 Python 实现；尚无独立 Rust 解释器。不能把这些计数描述为完整双实现 RIR conformance。

17 项初始回归在 B 通过；补齐单工件执行 CLI 后，18 项 CLI 回归曾在新的 B 源目录重新通过。收尾时另补 Python 深递归栈耗尽必须归为 HostFault 的边界，再用新的 final-run 目录双机重建并重新执行全部用例和 oracle；最终 A/B 各 19 项回归通过，核心来源以 final-run/source-lock 及两端 report 的摘要为准，旧记录保留。与原有回归合并后 make check 为 103 项。目录、安装日志及失败/负例保留，未运行 VM。

| 工件 | SHA-256 / 候选域摘要 |
|---|---|
| raw Wasm | 4b0f5ff5a0e1db9cdf06efb9c78e821a7bf07f628524c87c7a39f582bacc02f0 |
| normalized Wasm | ed63eb8a3a5e5923d4009e40d456c23defe223a3c89d6cefe5c69732676e505e |
| candidate rir_digest | 7b1ffdc9f3c677f4ab7beff0dfaa406d4af5cfb1e430d3304c76570a5a9cb95b |

## 可复用交付与证据

make check 已接入纯 Python 回归；显式 `make test-rir-io-probe` 进行构建和固定用例；execute.py 运行指定工件，区分 REJECTED/TASK_OUTCOME/HOST_FAULT；compare.py 重新核对两端产物和执行记录；可选 oracle.cjs 使用已有引擎，无自动依赖安装。

源码交付清单包含本轮实验、工具链 lock、测试 fixture 与报告，不含编译器、下载包、私钥或运行目录。完整原始证据由操作者保存于 `<EVIDENCE_ROOT>/rir-io-slice2-20261023/`：早期 source-lock/final-source-lock、A/B 记录与 B-final-check，以及最终 final-run/ 下的 source-lock、A/B 构建与 execution.json、comparison、oracle-result 和原始日志。实际 SSH 地址和本地路径不入库。命令与范围见实验 README。

## 保持开放

ADR-0006 仍 PROPOSED；P0-1B、G0/G2 不关闭。外壳文本 wire-key、局部 cap 与 supported opcode 集是实验合约，不能反向定义协议。未完成完整 grammar/validator、独立 Rust RPR、全部 22 个 ADR 向量、memory.grow/call_indirect 等扩展、正式 Logical Object/Receipt/Lease、stats-int-v1 或结算。本轮只覆盖固定两页内存与 void 控制子集，保守拒绝完整 ADR 中其他合法程序。

下一步在保持这些边界下补独立 Rust 执行对拍，并扩展整数统计负载所需的受限指令/SDK 路径；不得把已有接纳或单机测试直接记为上述缺项通过。
