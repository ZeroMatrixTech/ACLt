# RIR 切片 3：stats-int-v1 候选执行与独立解释器

日期：2026-10-23。状态：**本切片限定范围完成**。安装前核对基线 `f157cc15d34f999cd0b509395b1fd1caee87399c`（前两切片已在基线中，主仓库工作区干净）；本轮不提交或推送。
环境沿用 ENV-1 与 DUALHOST-SSH-1；A/B 为用户接受的两台独立物理执行主机假设，不推导统计或身份独立。

## 本次交付

新增 [维护入口](../../experiments/aclt-rir-stats-probe/README.md)：safe Rust 的统计负载、受信 SDK/入口、固定 lowering、Python 参考执行器、独立 Rust Wasm 解码/执行器、原 C++ worker 快照、固定用例及证据比较工具。
链路为 Rust 源码 → 原始 Wasm → 候选规范化 Wasm/外壳 → Python/Rust 解释执行 → 精确结果比较。
没有使用原生统计捷径替代 RIR 执行；C++ 仅作外部结果基准。

输入候选编码 `aclt.rir.stats-wire@1`：LE u64 chunk、count，以及 count 个 LE i64；输出每行 48 字节，依次为 id/start/length/sum/min/max。
范围为 1..100000 个值、chunk 1..100000、值 ±10^9；检查完整长度和所有值后输出。具体错误码、字节顺序和适配器见实验 README。
该实验输入/输出与 C++ 文本格式不同：先用明确适配器转换，再比较六字段行；并单独比较候选二进制输出字节。这是同一统计工作负载的结果对拍，不是原 C++ 线格式的等价实现，也没有冻结正式 Logical Object。

Rust 执行器直接读取 Wasm 字节，独立建立指令树和机器状态，并独立实现整数、控制、ABI、gas、输出丢弃与陷阱。它的入口要求模块已通过候选 Python 验证器；不是第二套完整类型/规范编码/外壳验证器。结果 CBOR 与摘要由同一 Python 后处理产生，因此不声称摘要验证实现独立。

## 本轮执行结果

- A、B 各在两个全新目录构建并执行，共四组。B 通过 SSH 部署源码、核对源文件摘要并使用已有固定官方 Rust 1.93.1 前缀独立编译；不复制 A 的编译产物作为 B 输入。
- 四组 raw Wasm（1270 字节）、候选规范化 Wasm（735 字节）、候选工件与执行记录一致。
- 每组 69 个 Python/Rust 差分用例，共 276 条记录。每组 40 个合法统计输入同时与 Python 数学基准及独立编译 C++ worker 对拍，共 160 次 C++ 比较。
- 包含正负数、±10^9、32 组固定种子随机输入、末尾不足一块、chunk 大于 count、100000 个值、长度/数量/数值错误、gas 恰好与差 1、输出恰好/超限、调用深度与本地执行上限。
- 手写微模块额外核对空程序、乘法、除零、带符号除法溢出、内存越界、unreachable 与宿主 gas 优先级。样例 `[3,-1,5,8]`、chunk=2 的完整程序 gas=9126 是双实现一致值；只有微模块 gas 为直接手算 golden，不把完整程序值写成独立手算证明。
- 使用 A 已有 Node v24.22.1 验证八份 raw/normalized Wasm 并完成 440 次输出/abort/输出上限语义比较。它不核对 gas、调用深度或外壳绑定。
- 14 项新增纯 Python 回归纳入 `make check`；本轮暂存源码 `make check` 共 117 项实际通过；安装后在主仓库再次核对，命令和退出码保存在本地产物中。

每组结果：45 OK、12 ABORT、2 GAS_EXHAUSTED、2 OUTPUT_LIMIT、2 创建期拒绝、1 CALL_DEPTH、1 HOST_FAULT，以及除零、整数溢出、内存越界和 unreachable 各 1。
非 OK 结果均不包含部分输出；HOST_FAULT 不计为 Task 结果。执行上限只影响运行记录，不写入工件；工件摘要保持不变。没有用临时哈希冒充 ReceiptID。

候选 `rir_digest`：`7077c1ac21677dc89040c65a95a3008c43b0292c9e3763a67a4e44055c8a2879`。
完整摘要、工具版本、源文件锁、golden 与计数见 [机器记录](rir-stats-slice3-20261023.json)。实际 IP、用户名及主机目录仅保存在操作者本地，不入库。

## 证据和复现

主仓库内 `make test-rir-stats-probe RIR_TOOLCHAIN=/prefix RIR_STATS_OUTPUT=/new/path` 可重建每主机的两组证据；两机独立执行后，使用 `compare.py` 和可选 `oracle.cjs`。默认检查不自动联网、安装软件或启动 VM。
本轮本地 `<EVIDENCE_ROOT>/rir-stats-slice3-20261023/` 保存 `A/`、回收的 `B/`、源码锁与归档、比较记录、Node 记录及命令日志；B 使用新建私有实验目录。不同 observed hostname 只是辅助检查，不能证明物理独立。
开发过程中首次受限解码器拒绝新增整数比较指令的日志、编译诊断及早期试跑目录均保留；这些不计入四组最终证据。当前源码包不分发工具链、二进制或大体积运行证据。

## 剩余边界与下一项

本轮仅测试固定内存、整数、void 控制/函数和五个 ABI 导入的限定子集，未完成完整 RIR validator/RPR conformance、独立 Rust 外壳验证器、随机合法程序覆盖、内存增长、表/间接调用或全部拒绝阶段。
SSH 仅传输源码与证据；没有新增 LAN 任务协议、Receipt、正式验证判决或结算证据。ADR-0006 仍 PROPOSED/CANDIDATE，G0、G2、P0-1B 与 B/Q 假设状态不变；结果相等不自动成为 TRUSTED，也没有新增 VerificationMethod。

下一切片建议将候选工件、输入摘要、执行上限与输出/判决记录绑定到同一冻结任务，建立 Receipt 身份与重执行比较的最小路径，再接入结算。正式 Receipt 编码尚缺时应先补该编码，不能以临时任务哈希冒充协议 ReceiptID。
