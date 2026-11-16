# Profile R6：固定 audit I/F 测试接线

本片完成固定 audit 的 I transcript/F envelope 测试接线，A/B 两台物理机各通过 122 条向量且结果流 SHA-256 一致，完整 `make test` 通过 578 项 Python 测试，119 条 Type A 由 R5 的 32/29/58 变为 **36 implemented / 33 partial / 50 not implemented**。日期：2026-11-08；基线 main `70f56a2f53318ec9ccd85c4122d6a9743f2aa70e`，叠加已完成但尚未提交的 R5 和本片；精确源码以机器摘要与公开源码包为准。

## 范围与结果

本片将固定 audit 的 scoped R5 检查接到 I transcript/F envelope：CreationContext、ReceiptIntent 和 PhaseIValidationRecord 使用 §17.4 正式 tag 与完整 ContentMap；运行期 ID 入摘要、digest 字段不自包含，Intent 输入数组保序并保留重复。CC-1 的两字段 helper 不冻结事件 frontier。I/F 身份/Intent/slot 绑定、记录重放与显式 DAG 中的严格祖先关系有独立 Python/Rust 实现。

**测试准入合约是本轮边界。** `test_contract` 在测试适配器外层，以调用者从外部提供的 SHA-256 pin 固定；schema lock 另有独立 pin。不能根据待验对象现算 pin 为其授信。测试合约绑定 Profile 三元身份、predicate、network、assurance 与一个被允许的 opaque ContractTuple；TEST replay 只按 ContractTuple 精确相等及显式 RegistrySnapshot 状态求值。失败原因用测试导入的 bstr，属于测试 contract，不是新冻结的规范 FailureReason wire。它既不读取记录声明的结果作为答案，也不读取外部时钟、网络或隐藏注册表。

支持的有限输入为单一直接指定的 audit Profile、隐式 index=0 PRIMARY slot、无 gate、无降级，只允许 INFORMATIONAL 假设。超出范围显式拒绝；不能用此入口检验 scope 或非 audit 方法。I 可以输出 SELECTED 或 REJECTED；F 必须引用 SELECTED，且重新执行同一测试函数。F 使用的 frontier 必须在其根的祖先闭包中包含本次 F 事件，此附加限制属于当前测试入口，不宣称为新增规范。

## 覆盖变化

119 Type A 从 R5 的 32/29/58 变为 **36 implemented / 33 partial / 50 not implemented**。完成 SV-97/103/104 三个摘要 owner 和 SV-101（CC-1 两字段）；新增 partial SV-96/98/102/110。18 个摘要中 9 implemented、2 partial、7 not implemented。

SV-102 继续 partial：通用 ReplayPhaseI、实际 admission predicate、ContractTuple 内部语义、scope/gate/降级与正式 FailureReason 导入均未完成。其余三个绑定规则仍在固定 audit/测试 imports 范围，不能冒充全量 I/F conformance。所有输出显式 `full_schema_valid=false`、`full_phase_i_replay=false`、`source_authentication=false`、`production_admission=false`、`receipt_created=false`。没有调用正式 CreateReceipt、没有新 ReceiptID、没有修改 Gate/ADR/OQ/主网资格。

## 验证证据

完整 `make test` 退出码为 0：默认 23 组 553 项（含本片新增 14 项）、执行器 25 项，共 **578 项 Python 测试**；另有 20 次 sanitizer 检测、既有 Claim/FM/RIR 对拍和 24 套公开快照的 249 条事件重放。R1–R5 的 66/74/104/145/382 条结果流哈希均与历史记录一致。

A/B 两台物理机各自构建 Rust 并通过 **122 条向量（14 正、108 负）**，源码 pin 一致，结果流 SHA-256 均为 `4671758536895ba099eb589db158815bf6cb99ffd75685b39363d538e263da13`。覆盖字段缺失、三个摘要、输入顺序/重复、外部 pin、重算摘要后的伪造记录、上下文/Intent/slot 漂移，以及事件缺失、错误 subject、相等/不连通事件和传递祖先关系。I SELECTED/REJECTED 与 F 的逐步 frontier 正例分别存在。

[机器摘要](PROFILE-CREATION-R6-20261108.summary.json)绑定源码、A/B 环境、计数和结果。包含逐文件 source pin 的[公开最小源码包](public-evidence/PROFILE-CREATION-R6-source.tar.gz)已解压到新目录，独立构建并重放 122 条，结果相同。最小包用于组件对拍；578 项全量回归使用完整仓库源码。此次没有新的 FM 任务/故障矩阵运行，没有创建正式 Receipt。

首次完整回归在测试监听端口处遭本地受限环境拒绝，保留原始日志后在支持端口与内存检测的本机环境重跑通过。开发阶段初次向量/CLI 检查的失败与修复后日志、A/B 部署记录、公开包复跑及最终全量日志均保留在操作者证据目录；没有把失败改写为通过。

## 兼容与下一步

R1–R5 的向量和结果保持原值，历史公开证据按原样保留。新增 Rust include/module 的源码随既有独立 FM/RIR 驱动一起传递与摘要绑定。旧 CLI 与 JSON bootstrap 保持；新增 I/F 两个入口必须提供 schema-lock 与测试合约两个外部 pin，生产模式持续 fail closed。

接下来应固定并接入 audit 实际使用的准入 predicate/ContractTuple、scope 与正式 imports，逐步替换此 TEST replay；再做正式 I/F 和 Receipt 创建验收。正式 I/F 与 Receipt 创建验收不以 Direct signature 或 non-audit 可达终态字段完成为前置条件。Phase B/D、来源忠实性、注册授权和 FM-A 验收仍独立推进。
