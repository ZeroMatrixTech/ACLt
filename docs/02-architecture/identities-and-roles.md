# ACLt Protocol Principal、函数与权限

> 文档状态：`DECIDED` ontology；权限细节 `OPEN/P0`  
> 语义基线：v0.5  
> 最后更新：2026-08-18  
> 更新触发：新增身份、职能、签名责任、维护权限或控制关联语义

## 1. 分类规则

系统名词必须归入以下类别：

- **Principal**：持有密钥、签署承诺、承担义务并接收权利；
- **Permissionless function**：任何合规 Principal 均可尝试执行的职能；
- **Protocol object**：具有规范化语义和生命周期的数据；
- **Implementation**：运行协议的软件和基础设施；
- **Maintenance boundary**：规范和发布生命周期中的有限责任。

不得因为一个职能有名称，就为其创建固定身份或特殊权限。

## 2. 不可再约减的 Principal

| Principal | 必要性 | 可签署的核心承诺 | 责任 | 明确没有的权限 |
|---|---|---|---|---|
| `Requester` | 没有请求方就没有任务、验收或预算来源 | Receipt 提案、输入引用、政策选择、预算承诺 | 任务语义、输入权利、预算真实性、恶意任务风险 | 覆盖验证终态、追溯改政策、付费换取真理权 |
| `Provider` | 没有提供方就没有计算或其他函数的实际执行者 | 资源声明、Lease 接受、结果、Checkpoint、证据 | 接受后的履约、证据真实性、密钥和资源声明 | 因履约历史获得验证票权、治理权或最终审计权 |

Principal 是协议责任单位，不等于现实独立控制实体。一个控制者可以拥有多个 PrincipalID；一个 Principal 也可以运行多个 Node 或 Device。

## 3. Permissionless functions

| Function | 可执行者 | 输出 | 接受条件 | 权威边界 |
|---|---|---|---|---|
| `Plan` | 任意 Principal | WorkPlan / Assignment | 合法性、依赖、资源和版本检查 | 只能提案，不保证最优 |
| `Admit` | 任意 Principal/可复算实现 | CapabilityEstimate / ExposureDecision | 证据版本、不确定度、硬限额 | 不产生身份或真理权 |
| `Schedule` | 任意 Principal/实现 | Lease proposal | 暴露、并发、epoch、期限 | 不得绕过准入 |
| `Execute` | 接受 Lease 的 Provider | Result / Checkpoint / FailureEvidence | Lease、epoch、摘要、环境 | 输出不是自动可信 |
| `Sample` | 任意 Principal/实现 | draw order | Snapshot、随机性、去重 | 不得观察后改总体 |
| `Verify` | 任意 Principal | VerificationEvidence | 任务方法、来源、成本、版本 | 单次证据不是终局 |
| `Aggregate` | 任意可复算执行者 | ConfidenceState / Decision candidate | 预声明统计与停止规则 | 不得手工改权重 |
| `Settle` | 任意可验证执行者 | Settlement candidate | 终态、政策、资金、唯一权利 | 不得创造资金 |
| `UpdateEvidence` | 协议接受事件触发 | PerformanceEvidence | 归责、来源、追加性 | 不生成 Rank |

“任意”表示无固定任命，不表示未受限制。函数输出必须可以被其他实现复算或验证。

## 4. 签名责任矩阵

| 对象/动作 | 必需签署者 | 可提议者 | 协议接受条件 | 状态 |
|---|---|---|---|---|
| ComputeReceipt | Requester | Requester | canonical、版本、政策、预算合法 | `OPEN/P0` Schema |
| WorkPlan | 提案 Principal | 任意 Principal | 确定性合法性检查 | `OPEN/P0` |
| Resource declaration | Provider | Provider | 字段、时间和证据来源有效 | `OPEN/P0` |
| Lease acceptance | Provider | Schedule 输出 | epoch、暴露、期限有效 | `OPEN/P0` |
| ResultSubmission | 执行 Provider | Provider | Lease/epoch/摘要/幂等有效 | `OPEN/P0` |
| VerificationEvidence | 执行 Verify 的 Principal | 任意 Principal | 方法版本、输入绑定、来源有效 | `OPEN/P0` |
| VerificationDecision | 无特殊人类裁判；按 Aggregate 规则生成 | 任意复算者 | 唯一终态、策略快照、证据链有效 | `OPEN/P0` |
| Settlement | 无特殊裁判；按 Settle 规则生成 | 任意复算者 | 权利、资金、终态、唯一键有效 | `OPEN/P0` |
| ProtocolVersion release | Maintenance 发布流程 | 任何贡献者可提议 | 评审、测试、发布签名和版本策略 | `OPEN/P0` |

具体密钥结构、代理签名、轮换和撤销仍未冻结。

## 5. 现实控制关系

ACLt Protocol 必须把以下内容视为可能的相关性证据：

- 共同所有权或资金来源；
- 共享网络、自治系统、地址段或接入路径；
- 相同设备、硬件镜像、驱动、容器或软件栈；
- 高度同步的加入、退出、提交或投票行为；
- 相同结果模板、错误模式或异常时间特征；
- 可验证的现实组织或代理关系。

这些信号不必证明现实身份相同，但未知关联不能默认等于独立。相关性处理必须兼顾错误关联和隐私风险。

## 6. Provider 的多函数参与

Provider 可以执行计算、规划、验证、抽样或聚合，但：

- 每次输出都绑定其实际函数和输入；
- 执行能力证据不自动提高验证证据权重；
- 同一控制集群的多个函数输出仍需相关性处理；
- 自己执行任务不自动排除其验证输出，但冲突处理必须由预声明政策决定；
- 函数组合不得绕过暴露、抽样、资金或终态守卫。

## 7. 新 Provider

新 Provider 初始没有 PerformanceEvidence，但仍必须具有获取证据的路径。当前原则是：

- 无前置抵押；
- 低初始暴露和单任务价值；
- 有限并发、Lease 和尝试；
- 探索额度处于集群和全局硬损失上限内；
- 拒绝未接受任务不产生负面证据；
- 任务族之间默认不迁移能力。

探索公式和参数仍为 `CANDIDATE/P1`。

## 8. Maintenance boundary

维护者可以：

- 维护规范、Schema、状态机、测试和参考实现；
- 管理发布签名、版本、兼容性和撤销；
- 接收、修复和披露漏洞；
- 记录 ADR 和迁移说明。

维护者不得：

- 修改冻结 Receipt 或 Snapshot；
- 针对个案改变权重、停止规则或资金；
- 覆盖 VerificationDecision；
- 制造 Settlement 或退款；
- 把维护者分析作为更高权证据。

基金会、委员会或链上治理是可选组织方案，不是 Principal，也不是当前协议必需组件。

## 9. 非实体清单

| 名称 | 正确分类 |
|---|---|
| Protocol | 规则集合 |
| Control Plane | 实现 |
| Broker/Planner | Plan 的历史或上下文称呼 |
| Verifier | 执行 Verify 的 Principal/Node 的上下文称呼 |
| Scheduler/Sampler/Aggregator | 函数上下文 |
| Rank/Reputation | 已废弃的权威化抽象 |
| Node/Account/Device/Key | 执行或标识载体 |
| Foundation | 可选组织形式 |
| Blockchain | 可选基础设施 Adapter |
| Rust/C++ frontend、compiler、RIR runtime | 实现组件；不得成为 Principal、VerifierAuthority 或协议语义来源 |

## 10. 防止角色再膨胀的检查

新增名词时必须回答：

1. 它能否持有密钥并承担独立义务？
2. 如果不能，是否只是函数、对象或实现？
3. 若需要特殊权限，为什么公开验证不能替代？
4. 失陷后能否改变 Receipt、Decision 或 Settlement？
5. 是否增加行政成本和信任根？
6. 是否有退出、撤销和权限测试？
7. 它是否只是 source frontend/compiler/runtime，而其输出仍由 RIR 与 conformance 约束？

无法证明必要性的实体不得进入协议本体。

## 11. 当前未决问题

- PrincipalID 与密钥轮换/撤销；
- 代理、组织、设备和现实控制关系表达；
- 每个对象的签名责任与授权链；
- 冲突函数和自验证政策；
- 相关性信号、隐私、错误关联与申诉；
- 新 Provider 探索与集群暴露参数；
- Maintenance 发布和紧急撤销流程。
