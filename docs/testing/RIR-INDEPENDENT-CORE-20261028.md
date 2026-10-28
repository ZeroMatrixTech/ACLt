# RIR 独立 stats-core：原始工件到结果字节

日期：2026-10-28；起点 `e69764a`（FM-S1b 已由 PR #61 合并）。维护者选择先推进 RIR 独立线；本轮完成已安排的核心切片，不接受 ADR-0006、不启用正式执行入口。

## 实现与证据范围

新增 [Rust 独立入口](../../experiments/aclt-rir-stats-probe/src/independent_executor.rs)、[验证/编码核心](../../experiments/aclt-rir-stats-probe/src/core.rs)、[有限支持 contract](../../experiments/aclt-rir-stats-probe/independent-contract.json)与[说明](../../experiments/aclt-rir-stats-probe/INDEPENDENT-CORE.md)。Rust 直接接收原始 RIRArtifact CBOR，自行检查外壳、受限 Wasm 规范重编码、类型/索引/导入/资源/输入绑定、调用方保留的工件 pin，执行后自行编码 Outcome CBOR 和计算 artifact/outcome SHA。结果不经 Python 补摘要。Rust 复用既有独立 primitive/NFC/SHA 核心；Python 使用原 normalizer/validator/interpreter，未引入第三方依赖。

旧 executor.rs、build.py、wasm.py、runtime.py、cases.py、编译用源和 fixture 均保持原字节，历史 source pin 不改写。新解释器以旧 Rust 解释器为代码起点，但只通过新独立验证入口进入执行；独立性指与 Python 的实现/进程数据依赖分开，不是声称第三份全新解释器。crate-internal codec 可见性调整只服务共享原语，不改变旧 FM/Claim 字节合约。

固定 [38 向量](../../experiments/aclt-rir-stats-probe/tests/independent-vectors.json)，新增 12 个默认 Python 回归方法。两物理主机各 161 项检查：固定 vectors、39 个 stats 数据集、80 个 seeded integer 程序、无 Python/源码/OpenSSL 的独立 binary、工件 pin 分歧、真实输入文件丢失及大于 1 MiB 的输出。随机程序将运算值写入内存并输出，不能靠丢弃计算值掩盖数值分歧。每个 Task 结果同时核对 result、gas、原始 CBOR、outcome_digest，A/B 最终 results_sha256 相同。

A 类四个拒绝码在已声明核心范围有负例；B 类确定 Task trap 仍有 gas/结果；C 类宿主/复验分歧不输出 Task result/CBOR/digest。输入过大在执行前拒绝；线性内存和输出增长使用 fallible reservation。内存注入只是受控路径验证，不冒充真实物理 OOM 或所有分配点已证明容错。

源码 SHA、新独立目录、编译器/环境、原始命令/输出、A/B 报告保存于操作者 `<EVIDENCE_ROOT>/rir-independent-core-20261028/dualhost-run1/`，实际 IP/用户名/路径不入库。两物理主机的分离是沿用 DUALHOST-SSH-1 的接受假设；SSH 传输和执行不等于任务 TCP、Lease/账务或网络故障验收。

## 对 FM-S2 与未关闭项的影响

该局部路径已摆脱 Python 预验证/结果后处理，但不能把 stats-core 当完整 RIR-0 validator：table/element/data 等模块 grammar、全允许指令/typed block、全静态数量范围、超出核心或触发资源 guard 的组合错误优先级、memory.grow/call_indirect 边界和全宿主故障仍待补齐。Python wrapper 对原受限 parser 的错误作分类，也不提供全七阶段规范证明。

正式 ReceiptID 的身份变化测试、ADR-0006 §11 规范同步与人工接受仍缺；只改变执行上限不改变 rir_digest 的检查不冒充已完成正式 ReceiptID 测试。MG-01/MG-02、P0-1B、G2、OQ/主网资格均不关闭，ADR-0006 保持 PROPOSED。

FM-S2 授权/原子预留/事件结构可以针对候选接口开发；正式执行准入仍等待全 RIR/RPR、字段/官方对象、非主网接口与部署证据汇合。下一步继续完整 validator/指令/边界 conformance 与 ADR 接受准备，不把本核心 PASS 写成正式路径已经可执行。

## 回归与同步核对

完整本地 `make test` 退出为零：默认回归 347 个方法（原 335 + 本轮 12）；原 Claim 29,766 项、FM-S1a 179 项、FM-S1b 196 项、本核心 161 项对拍及旧 state3/20 次 sanitizer/多节点/权威本地检查通过。清单/差异/交付包另行核对，实际日志保留于同一证据根。没有重写历史通过记录或把旧证据当新运行。

按 CONTRIBUTING 同步矩阵核对 protocol-spec、task-lifecycle、invariants、threat-model、术语、架构与 v1-profile：本轮提供候选实现，未改变 RIR/RPR 权威语义、结果等价、Principal 集合或 VersionDisposition；对应 INV-01/02/09/16 与 TH-02/27/29/33—35 的完整证明仍不由局部证据替代。ADR 补记、MG 清单、计划/追踪、当前状态、OQ、论断证据及开发/索引已同步。
