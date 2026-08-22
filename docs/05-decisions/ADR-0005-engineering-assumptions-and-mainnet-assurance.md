# ADR-0005：工程假设、主网保证与单一权威边界

> 状态：`ACCEPTED`
> 决定日期：2026-08-21
> 适用范围：协议规范、VerificationProfile、主网部署、参考实现、审计和后续工程 Gate
> 关联：ADR-0001、ADR-0003、ADR-0004；OQ-03、OQ-05、OQ-08、OQ-11—OQ-13；INV-10—INV-16

## 1. 背景

ACLt 此前容易把三类不同问题放进同一个“必须证明”门槛：

1. 给定完整输入，协议算法是否有唯一结果；
2. 输入是否忠实反映现实系统；
3. 某个公开网络是否愿意在这些工程条件下承担风险。

第一类必须由规范、确定算法和 conformance vectors 闭合。第二类通常依赖日志、状态机、部署权限、故障恢复和审计，不能由 JSON Schema 或数学定理单独证明。第三类是带有效期、组件版本、损失预算和撤销机制的工程风险接受。

如果要求第二、三类都先获得开放世界中的形式证明，P0-1B、参考实现和主网试验会被不可证明的“现实世界完全诚实”命题永久阻塞。反过来，如果把工程报告直接当成统计证据，又会让维护组织获得个案真理权。

## 2. 决定

### 2.1 四层闭合模型

每项要求必须归入且只归入以下主要证据层：

| 层 | 核心问题 | 主要证据 | 是否阻塞接口实现 |
|---|---|---|---:|
| A. 结构闭合 | 对象、类型、编码和状态是什么 | Schema、canonical encoding、静态向量 | 是 |
| B. 算法闭合 | 给定完整输入是否产生唯一结果 | 纯函数、定理、模型检查、差分对拍 | 是 |
| C. 来源忠实性 | 输入是否来自真实且未旁路的系统 | append-only 日志、权限边界、集成测试、故障注入、实现审计 | 否；但来源未建立时对应能力必须关闭或 fail closed |
| D. 部署风险接受 | 官方主网是否愿意在这些有限条件下启用能力 | 版本化 assurance、有效期、组件允许集合、损失预算、撤销 | 否；但不得把未接受部署描述为已获保证 |

形式证明不是所有工程事实的唯一合格证据。来源忠实性和部署事实 MAY 使用可复现工程证据；规范算法、资金守恒、终态唯一性和统计定理的数学前提不得因此被放宽。

### 2.2 不证明自然人身份唯一性

ACLt 不要求、也不声称证明每个 Provider ID 背后是不同自然人或法人。身份数量不得直接等于独立证据数量。官方主网可以使用可观察的所有权、资金、网络、设备、软件栈和行为信号形成相关性簇，并把残余漏合并风险纳入：

- 预先冻结的支持能力上界或降级规则；
- Provider、相关簇、Receipt、时间窗和系统级暴露上限；
- `ExcludedClaims`；
- 绝对资金和损失预算。

无法建立 `REEXEC_BOUNDED` 所需条件时，该 Profile 必须为 `AUDIT_ONLY` 或 `DISABLED`，但这不阻止 Schema、validator、日志和仿真工件继续实现。

### 2.3 官方主网 assurance

维护组织 MAY 发布版本化 `MainnetAssuranceProfile`，只对其明确声明的官方 `network_id`、有效期和组件集合负责。它至少绑定：

- 允许启用的 VerificationProfile 和能力处置；
- RPR、validator、日志后端与执行 contract 版本；
- 相关性策略、假设证据、conformance 清单；
- 单 Receipt 与系统级损失预算；
- 撤销、降级和重新启用流程。

维护组织不是运行时 Principal。它不得修改个案 Evidence、Aggregate、终态、Provider 权重或停止规则；不得在观察结果后改变 \(G,B,Q,\varepsilon_F\)；不得让 `FoundationReport`、历史履约或资金进入真理权重。assurance 是部署准入和能力上限，不是一张验证票。

主网外部署、fork、私有网络或替换组件不继承官方 assurance。它们可以复用协议和代码，但必须发布自己的风险声明。

### 2.4 日志忠实性使用工程 contract

协议只冻结日志消费 contract：事件的规范编码、因果引用、checkpoint、inclusion/consistency/finality 验证和失败语义。官方主网可以用区块链、Merkle transparency log 或等价 append-only 模块实现。

Schema 不能证明写入方没有旁路。参考实现必须通过权限隔离、状态机强制写入、崩溃恢复、重放和独立对账证明其没有已知旁路。缺失、无法验证或未 finalized 的事件不得驱动安全终态。

### 2.5 `TRUSTED` 是条件性结论

`TRUSTED` 只表示：在 Decision 绑定的任务语义、RIR/RPR、VerificationProfile、假设快照、主网 assurance、统计模型、日志与损失边界内，规范停止条件已满足。它不表示：

- 身份绝对独立；
- 实现没有未知缺陷；
- Source→RIR 与 Requester 未编码意图正确；
- 主网外环境获得同等保证；
- 外部业务损失已经有界。

### 2.6 多原因与单一判决分层

多重假设失效不再被建模为“单值 verdict 或 flag set”二选一：

- **诊断事实层**保存规范排序、去重的 `CauseSet`，允许多个原因和各自证据引用；
- **判决层**由冻结归约函数从 `CauseSet` 派生唯一 `EffectiveVerdict`；
- `EffectiveVerdict` 用于状态机和跨实现一致性，`CauseSet` 用于审计、修复和统计；
- 原始原因不得在观察后删减，归约优先序必须版本化。

V1 可以继续使用单值 `EffectiveVerdict`，但不得因此丢弃已观测的并发原因。

### 2.7 单一 scope 权威，多工程检查点

是否需要“第三个 Dispatch scope”不再按绑定点数量裁定：

- Receipt/Intent 声明允许范围；
- active Lease 是本次执行元组的唯一授权来源；
- EligibilitySnapshot 是本次验证总体的冻结来源；
- Dispatch 和 RPR 在启动时验证 Lease 派生的 capability/digest，但不得创建或改写第三份 scope；
- 执行元组发生变化时，旧 Lease 失效，必须产生新 Lease 并重新检查。

因此采用“一个权威值，多处验证”的工程结构。Dispatch/RPR 检查属于来源忠实性和集成测试，不是第三套协议真相。

## 3. 工程实现要求

后续实现 MUST：

1. 为每项规则标记 A/B/C/D 证据层，禁止用 Schema 测试冒充来源忠实性；
2. 对外部组件使用版本化引用和允许集合，未知版本 fail closed；
3. 把日志、Lease、Dispatch、RPR 和 Decision 的关键绑定放入可重放记录；
4. 提供能力开关 `DISABLED | AUDIT_ONLY | ENABLED`，未满足主网 assurance 时不得产生条件性 `TRUSTED`；
5. 对 Type A/B 分别建立文件向量与集成/权限/恢复测试；
6. 保留绝对资金和暴露上限，不能用更高统计置信度替代损失边界；
7. 在用户可见 Claim 中显示适用网络、assurance 版本和 `ExcludedClaims`。

## 4. 不变边界

本决定不允许：

- 以“工程可行”为由省略确定性算法或让两个实现产生不同终态；
- 用维护者意见替代协议证据；
- 在结果出现后修改规则或扩大能力；
- 将官方主网的条件性结论宣传为开放世界的绝对保证；
- 因日志使用区块链就宣称底层共识、密钥和实现永不失效。

## 5. 状态影响

- 工程闭合原则和主网/主网外边界：`DECIDED`；
- `MainnetAssuranceProfile` 的精确 Schema：`P0-1A CLOSED`；
- P0-1B Schema、validator 和向量：`STARTED / NOT CLOSED`；
- 具体主网组件、参数与风险预算：部署级 `CANDIDATE`；
- 通用 permissionless 身份独立性证明：不再作为 V1 关闭目标。

本 ADR 不单独关闭 P0-1。P0-1 仍需要 VerificationProfile Schema 的独立入口审计、P0-1B 工件和跨文档 conformance。

## 6. P0-1A 采纳矩阵

本节是 ADR-0005 对 [`../03-protocol/verification-profile-schema.md`](../03-protocol/verification-profile-schema.md) 的明确采纳，不再保留“待 ADR 裁定”的中间状态。

| 决定 | 裁定 |
|---|---|
| D-01 | 接受：Profile 三元组进入 `CanonicalSemantics` |
| D-02 | 接受方案 (a)：`REJECTED_AT_CREATE` / `UNSUPPORTED` 是 `CreateReceiptResult`，不是 Receipt 终态 |
| D-03 | 接受：`DRAFT → REGISTERED` 冻结，不追溯 |
| D-04 | 接受：同一 Receipt 不切换 Profile |
| D-05 | 接受：一个 Profile 恰好一个 VerificationMethod |
| D-06 | 接受：选择与降级合并为单一创建期算法 |
| D-07 | 接受：V1 自动弱化边仅限规范登记的单向边 |
| D-08 | 接受：`ClaimBinding` 是 `TRUSTED` 的必需组成；实现旁路仍为 Type B |
| D-09 | 接受：`ExcludedClaims` 同时供程序与 Requester 查看 |
| D-10 | 接受：官方主网使用版本化、限域、可撤销的工程 assurance，不获得个案真理权 |

同时接受 `acl.enc.p0-1@1` 为 `TRANSITIONAL` 迁移源：产出侧单写最终统一编码，解析侧在旧绑定全部终态前双读；OQ-02 负责最终编码对账。P0-1A 的 `CauseSet + versioned reducer → EffectiveVerdict` 与 `ExecutionCapability` 引用边界是本 ADR §2.6—§2.7 的规范落点。
