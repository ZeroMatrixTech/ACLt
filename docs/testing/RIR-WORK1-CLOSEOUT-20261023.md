# 第一项工作收尾：Rust → 候选 RIR → 执行 → 精确比较

日期：2026-10-23。工程跟踪标识：`RIR-WORK1`。
**结论：三个切片组成的第一项工程工作，在候选执行链与 stats-int-v1 的限定范围内完成。**
该完成不改变 SemanticStatus/VersionDisposition；ADR-0006 仍 PROPOSED，详细规则仍 CANDIDATE，G0/G2/P0-1B 保持开启。

## 验收范围

| 切片 | 已交付与本轮验收 | 状态 |
|---|---|---|
| 1：构建 | 官方 1.93.1 工具链锁、离线安装、safe 用户 crate/受信导出边界、空 run 的限定规范化和双机四组一致性 | 工程完成 |
| 2：显式 I/O | 五个 SDK 导入、16 字节原样输出、候选外壳与受限类型检查/Python 执行、gas/陷阱/输出丢弃 | 工程完成 |
| 3：统计 | safe Rust stats-int-v1、显式二进制适配、Python 与独立 Rust Wasm 解码/执行、C++/数学结果对拍 | 工程完成 |
| 组合收尾 | 同一工具链、相同入口、后两片相同 SDK；统一复现命令、当前源码与证据核对、交付与交接 | 工程完成 |

三个切片是逐步扩展的三个程序，不要求它们共享一个工件摘要。每片要求自己的两台机器、四个目录产生相同工件和记录。
完整 RIR/RPR conformance 不在本次工程完成的结论内：受限规范化/外壳是候选实现，Rust 执行器仍以 Python 预验证为前提，结果 CBOR/摘要仍共享 Python 后处理。
原 C++ worker 使用文本输入/输出，第三片用 `aclt.rir.stats-wire@1` 二进制适配，比较明确转换后的六字段统计行及候选输出字节，不声称原线格式逐字节相同。

## 本轮重新执行，而非沿用历史通过状态

安装前基线为 `f157cc15d34f999cd0b509395b1fd1caee87399c` 加第三片未提交变更；全部保留。本轮通过 SSH 将固定摘要的源码部署至 B 的新目录，A/B 分别使用已有固定工具链，调用新的统一入口，每片在两处独立编译。未安装新软件、启动 VM、复制 A 编译产物作为 B 输入或提交/推送。

- 本轮共 **12 次构建**（每片 4 次），各片 raw/normalized Wasm、候选工件及适用执行记录分别一致。
- 第二片 **220 条** Python 执行记录；第三片 **276 条** Python/Rust 差分记录，共 **496 条**。这些包含 Task outcome、创建期拒绝和 HostFault，不把全部记录叫作成功 Task。
- 第三片 **160 次 C++ 结果比较**；A 已有 Node 对本轮收集产物再做 **360+440=800 次语义对拍**，不核对 gas/调用深度/外壳绑定。两组各验证八份模块，共 16 份；这些不是不同的工作负载数量。
- 新检查器核对当前源码 pin、保留工件/记录、第三片 native Rust/C++ 二进制摘要，以及跨片工具链、入口、SDK 和原 C++ 快照的连续性。
- 三项实际负向控制均拒绝：修改 Wasm、缺失源码 pin、修改保留 Rust 二进制。五项收尾工具回归纳入默认检查；总计 **122 项 make check**，并检查交付清单、diff 和更新包。

A/B 独立物理主机是 DUALHOST-SSH-1 的有限实验接受假设。不同 hostname 只作辅助；同一操作者、软件与局域网仍有共因。SHA-256 一致性不构成来源认证或不可篡改证明。SSH 在这里负责部署/取证，不构成跨 LAN 任务协议验收。

[机器记录](rir-work1-closeout-20261023.json)保留本轮组合核对、源码摘要与原始报告摘要。本地 `<EVIDENCE_ROOT>/rir-work1-closeout-20261023/` 保存 A/B 全套新产物、source-lock、命令/日志、负向控制、Node 记录与交付包；实际连接地址及用户名只留在操作者本地。此前三片证据和失败记录均保留，不与本轮重复累加计数。

## 统一复现与证据核对

在 **A 和 B 各自**独立的新目录运行：

```sh
make test-rir-work1 RIR_TOOLCHAIN=/pinned/prefix RIR_WORK1_OUTPUT=/new/host-run
```

该命令顺序运行三片，保留 `slice1/`、`slice2/`、`slice3/`、各片日志与 `suite.json`。失败即停止，保留现场；拒绝覆盖既有目录。不自动 SSH、下载安装工具链或把单机两份目录当作双机证据。

回收 B 的结果后，在当前源码下核对：

```sh
python3 -B scripts/rir-work1.py verify \
  --slice1 /new/A/slice1 /retrieved/B/slice1 \
  --slice2 /new/A/slice2 /retrieved/B/slice2 \
  --slice3 /new/A/slice3 /retrieved/B/slice3 \
  --report /new/verification.json
```

核对器重新计算已保存证据的摘要，不执行编译器或远端任务；源文件与被测版本不同则拒绝。报告必须位于被核对目录之外且尚不存在。可选 Node 对拍继续使用第二/三片的 `oracle.cjs`。默认 `make check` 只做本地回归和清单检查，不产生新的双机通过记录。

各片具体范围与历史证据：[切片 1](RIR-BUILD-SLICE1-20261023.md)、[切片 2](RIR-IO-SLICE2-20261023.md)、[切片 3](RIR-STATS-SLICE3-20261023.md)。

## 交接：下一项工作

第一项不再继续扩展规范范围。下一项是 **冻结任务与重执行比较记录的绑定**，按以下顺序准备：

1. 先审阅并补齐正式 Receipt 候选编码、版本与哈希域，明确其绑定的工件、输入对象摘要和执行上限。尚缺正式编码时，不用临时 JSON 哈希充当 ReceiptID。
2. 验证同一工件只改变输入/上限时 rir_digest 保持不变、ReceiptID 变化；工件/输入/上限错绑明确拒绝，保留重放与失败证据。
3. 将双机 outcome 与精确比较记录绑定到同一冻结 Receipt，明确适用 Profile；相等不自动产生 TRUSTED，不新增 `REEXEC_EXACT` 方法。

完整 validator/独立 Rust 外壳、全指令/拒绝阶段 conformance、正式判决与结算仍分别跟踪，ADR 的接受证据要求不变。B/Q、无许可部署、市场/经济假设与生产资格的证据不因本轮通过而建立。下一项的完成条件是可复核的冻结绑定链；结算接入在此之后。
