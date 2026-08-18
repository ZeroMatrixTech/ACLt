# ADR-0003：语义状态与版本处置二维分离

> 状态：`ACCEPTED`  
> 决定日期：2026-08-18  
> 适用范围：规范、ADR、路线图、Conformance Target、实现声明和审计  
> 关联：ADR-0002、OQ-02、TH-02、INV-02、INV-16、G0

## 1. 背景

ACLt 需要同时表达两个不同问题：一项语义是否已经成熟，以及该项能力是否进入某个工程一致性目标。此前文档使用 `DECIDED / OPEN`、`CANDIDATE/P0` 或单独的 `DEFERRED` 等紧凑写法，容易把语义成熟度、工作优先级和版本范围误读为同一状态。

尤其需要避免以下错误推断：

- 某项能力在 V1 延期，不等于项目永久拒绝该能力；
- 某项原则已经决定，不等于其算法、Schema、证明或测试已经完成；
- 某项能力被列入 V1 核心，不等于 G0 已经通过；
- v0.5 语义基线和 V1 一致性目标不是同一种版本号。

## 2. 决定

ACLt 对每个可追踪规范单元 `x` 和每个 Conformance Target `v` 分别存储：

\[
Status(x,v)=
\bigl(
SemanticStatus(x),
VersionDisposition(x,v)
\bigr)
\]

两个维度不得合并为一个枚举、一个斜杠字符串或一个隐含状态。

### 2.1 SemanticStatus

`SemanticStatus` 只回答“该语义结论在 ACLt 中成熟到什么程度”：

| 值 | 规范含义 |
|---|---|
| `OPEN` | 问题已识别，但尚无被接受的具体方案 |
| `CANDIDATE` | 已有可评审候选，但尚未被当前语义基线接受 |
| `DECIDED` | 已被当前语义基线接受；细节证据可以仍未完成 |
| `INVARIANT` | 所有声称兼容的实现和版本都必须保持的性质 |
| `SUPERSEDED` | 曾有效，但已被新决定显式替代 |
| `REJECTED` | 已评估并拒绝；重新开启需要新证据和变更记录 |

`DERIVED`、`ASSUMPTION` 和 `HYPOTHESIS` 保留为 ClaimQualifier，用于说明推导或证据性质，不再替代 `SemanticStatus`。`P0–P2` 是 Priority，`G0–G6` 是 Gate，问题队列的 `INVESTIGATING/BLOCKED/CLOSED` 是 IssueStatus；它们均不得占用版本处置字段。

### 2.2 VersionDisposition

`VersionDisposition` 只回答“该能力在指定 Conformance Target 中如何处理”：

| 值 | 规范含义 | V1 实现行为 |
|---|---|---|
| `CORE` | 该目标必须实现并通过一致性要求 | 缺失时不得声称 V1 conformance |
| `DEFERRED` | 当前目标不支持，但与未来扩展方向兼容 | 明确返回 `UNSUPPORTED`，不得静默降级 |
| `REJECTED` | 当前目标明确禁止，或与已冻结边界冲突 | 创建期拒绝或 fail closed |

VersionDisposition 必须按目标存储。同一能力可以在 V1 为 `DEFERRED`，在未来目标中通过新 ADR 和兼容性审查成为 `CORE`。

### 2.3 分离存储

- 各术语、决定、不变量、Claim 和 Open Question 的权威文件保存其 `SemanticStatus`。
- 每个 Conformance Target 使用独立 Profile 保存 `FeatureKey → VersionDisposition` 映射。
- V1 的唯一权威映射位于 [`../03-protocol/v1-profile.md`](../03-protocol/v1-profile.md)。
- Profile 通过 FeatureKey 和权威链接引用语义来源，不复制或覆盖来源的 SemanticStatus。
- Receipt 绑定实际使用的协议、RIR、runtime、frontend、验证和结算版本；它不绑定项目管理状态。

## 3. 版本命名

以下标识具有不同职责：

| 标识 | 含义 |
|---|---|
| `ProtocolVersion` | 对象、状态机、不变量和兼容规则的协议语义版本 |
| `ConformanceTarget` | 实现需要满足的工程能力集合；当前首个目标为 V1 |
| `RIRVersion` | RIR 指令、类型、错误和 canonical representation 版本 |
| `RuntimeProfileVersion` | RPR effects、资源、终止和可观察运行时语义版本 |
| `FrontendProfileVersion` | Rust Profile 或未来 frontend 的允许构造与 lowering 版本 |
| `VerificationProfileVersion` | 结果等价、抽样、聚合和停止规则版本 |
| `SettlementProfileVersion` | 资金终态、权利和结算规则版本 |

当前 `v0.5` 是协议语义基线；`V1` 是首个 Conformance Target。V1 不自动等于 `ProtocolVersion=v1.0`。

运行时承诺最终必须无歧义绑定：

\[
ContractTuple=(
ProtocolVersion,
RIRVersion,
RuntimeProfileVersion,
FrontendProfileVersion,
VerificationProfileVersion,
SettlementProfileVersion
)
\]

准确字段、编码和兼容矩阵仍属于 OQ-02 的 `OPEN/P0` 工作。

## 4. Gate 规则

一个 Conformance Target 的规格 Gate 只有在以下条件成立时才可退出：

\[
G0Close(v)
\Rightarrow
\forall x,
VersionDisposition(x,v)=CORE
\implies
SemanticStatus(x)\in\{DECIDED,INVARIANT\}
\]

此外，所有 CORE 项必须具有可实现规范、失败语义、追踪关系和相应验证计划。`OPEN + CORE` 或 `CANDIDATE + CORE` 是显式 Gate 阻断，不得通过把 VersionDisposition 改写为完成状态来掩盖。

`DEFERRED` 和 `REJECTED` 不要求 V1 实现相应能力，但必须具有确定的拒绝行为和禁止静默回退规则。

## 5. 后果

### 正面后果

- v0.5 与 V1 的关系不再依赖大小写或上下文猜测；
- 可以准确表达“方向已决定、实现证据仍开放”；
- V1 CORE 缺口能够被机械识别为 Gate 阻断；
- 未来版本可以重新分类能力，而不改写历史决定；
- 审计可以分别判断语义连续性和版本完整性。

### 成本与风险

- 现有紧凑状态字符串需要逐步迁移；
- FeatureKey 和版本 Profile 需要稳定维护；
- machine-readable registry 尚未建立，当前仍依赖 Markdown 表和审计；
- 仅分离状态不能替代 Schema、证明、测试或兼容性矩阵。

## 6. 被拒绝的替代方案

| 方案 | 处理 | 原因 |
|---|---|---|
| 用一个枚举同时表达成熟度与版本范围 | `REJECTED` | 状态组合爆炸，且无法表达跨版本变化 |
| 把 V1 等同于 ProtocolVersion v1.0 | `REJECTED` | 混淆语义基线与工程一致性目标 |
| `DEFERRED` 自动解释为未来必然支持 | `REJECTED` | 未来仍需证据、威胁更新和 ADR |
| CORE 自动解释为已经完成 | `REJECTED` | 会掩盖 G0 阻断和未完成证明 |

## 7. 连续性与验证

本决定不改变两类 Principal、permissionless functions、RIR/Rust Profile 方向、验证不确定性、资金边界或维护权限。它只规范这些结论如何被标记和按版本收录。

最低验证要求：

1. 文档索引只指向一个 V1 Profile；
2. VersionDisposition 不再承载 SemanticStatus；
3. 每个 V1 CORE FeatureKey 都能链接到权威语义和未决证据；
4. `OPEN/CANDIDATE + CORE` 在当前状态中被列为阻断项；
5. 历史文件不被重写，只通过当前权威入口隔离。
