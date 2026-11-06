# MEMO-20261105：FM-S3 四项开放接口的决策备忘

> 性质：决策备忘，由助手起草，**未经接受**。它不是 ADR，也不修改规范、SemanticStatus、V1 处置、OQ 或 Gate。
>
> 基线：main `9598782`（PR #66）。
>
> 来源：[FM-S3 audit 依赖入口](../../07-roadmap/fm-s3-audit-dependencies.md)中“正式实现前必须明确的四个接口”。
>
> 规范依据：[VerificationProfile 规范](../../03-protocol/verification-profile-schema.md)（下称“规范”）、[ADR-0005](../ADR-0005-engineering-assumptions-and-mainnet-assurance.md)、[ADR-0007](../ADR-0007-formal-object-migration-foundation.md)。
>
> 后续决定见 [ADR-0008](../ADR-0008-fm-s3-interface-decisions.md)。首轮候选路线以首次重执行入口划定 RUNNING，并保留首份合法结果的计费资格。这两点分别对应下文 §2 的阶段边界与 §1 的 O-6b。

## 0. 总览

| 接口 | 一句话问题 | 推荐 | 阻塞 FM-S3 的哪一步 | 规范改动量 |
|---|---|---|---|---|
| AUTHORITATIVE-OBSERVATIONS | 哪些事实可以进入判决和计费，从哪里来 | **A：只取单一权威日志的投影** | S3b 的结果接纳与判决输入 | 小：主要是候选合约，不改规范正文 |
| AUDIT-PHASE-B-PATH | 不冻结 Snapshot 的方法没有合法的 Phase B 终态路径 | **A：为无 Snapshot 方法增加专用转换，统计参数改为条件存在** | S3b 的轮次状态与终态 | 中：§13.0.4、§13.1B.2A、SV-93/94/105 |
| NONMAINNET-ASSURANCE | 现行规范下非主网部署无法合法创建 Receipt | **A：新增非主网部署声明对象，部署边界改为联合类型** | 正式 CreateReceipt 与最终收尾 | 大：§9.2、RI-6、四类相位信封、DecisionEvaluationInput |
| AUDIT-WIRE-BOTTOM | `verified_claim_spec = ⊥` 没有合法的线上表示 | **A：省略键** | S3b 的候选 audit 合约字节 | 小：§3.1 类型、SV-30 |

建议的拍板顺序：1 → 2 → 4 → 3。前两项直接决定 FM-S3b 的写法；第 4 项改动最小，应在下一次双机运行前完成，避免候选字节迁移两次；第 3 项改动最大，但 S3b/S3c 可以先继续使用候选部署 pin。

---

## 1. AUTHORITATIVE-OBSERVATIONS：判决与计费的事实来源

### 问题

- FM-S1b 的 111 行费用表以每个角色（执行、审计、存储）的 COMPLETE/MISSING/HOST_FAULT 为输入，但这些目前只是假设值（`fm2-quote`）。
- Phase D 需要完整内联的 `DecisionEvaluationInput`：`method_evaluation`、`assumption_evaluation`、`boundary_observation`、`execution_observation`（规范 DE-1）。
- FM-S2 已有权威事件（Lease 激活、CONSUME、FENCE、权威逻辑时钟）；FM-S3a 的签名结果**没有**权威的接收时点。

需要决定：这些事实由谁产生、以什么形式进入判决，以及“结果在截止前到达”如何判定。

### 现行规范约束

- **DE-1**：Phase D 输入必须完整内联，不得只给引用或让 validator 从网络补取。
- **ResolveBoundary / SV-112**：资金与期限的先后只能由显式 `EventFrontierSnapshot` 的因果序判定，不得用墙钟或数组顺序；两者因果不可比时取 `BUDGET_EXHAUSTED`。
- **ExecutionObservation / SV-121**：只有合法 closure 且零有效提交才产生 `EXECUTION_FAILED`；来源不可用或格式错误时产生 invalidating。
- **费用表语义**（[policy.md](../../../schemas/formal-migration/policy.md)）：COMPLETE 指“规范的、已接受的、当前 epoch 的履约项（含格式正确的 Task trap）”，调用方自报的标签不算；MISSING 和 HOST_FAULT 时该角色费用为零。

### 选项

| 选项 | 内容 | 优点 | 缺点 |
|---|---|---|---|
| **A（推荐）** | 所有观测都是单一权威日志中的 EventRecord；Phase D 输入是已认证 `EventFrontierSnapshot` 的确定性投影 | 与 DE-1、SV-112 一致；时序只有一个来源；可离线重放 | 权威要新增几类事件；接收时点受权威可用性影响 |
| B | 权威日志加上 Provider 签名自报（自报时间、自报 HostFault）合并 | 权威侧改动少 | worker 时钟和自报可以伪造；同一事实有两个来源，违反“一个权威” |
| C | 引入第三方见证或观察者 | 削弱对单一权威的依赖 | 新增实体，违反 ADR-0001；首版不需要 |

### 推荐 A 的具体规则

- **O-1 来源唯一**：只有权威日志中的事件可以进入 Phase D 和费用求值。worker 本地 journal、文件和自报时间一律不进入。
- **O-2 接收时点**：结果的“接收时点”就是权威 `RESULT_ACCEPTED` 事件在因果 DAG 中的位置，不是任何墙钟。“截止前到达”用 ResolveBoundary 的因果序判定。
- **O-3 COMPLETE**：该角色在当前 Lease/epoch 下有一份签名完整、编码规范的 ResultSubmission，且在边界事件之前被权威接受（包括格式正确的 Task trap 结果）。
- **O-4 HOST_FAULT**：权威接受的、由该角色**自己签名**的 HostFault 报告，或权威记录的 C 类事件（如 RPR 复验分歧）。自报 HostFault 只会让自己的费用归零，没有作假的动机，因此可以接受；他人不能代报。
- **O-5 MISSING**：到边界或执行闭合时，以上两者都没有。
- **O-6 幂等与冲突**：每个 `(角色, Assignment, epoch)` 只接受第一份合法提交；字节相同的重传返回原回执；内容不同时记录 `RESULT_CONFLICT` 事件并保留第一份。
- **O-7 执行闭合**：恢复次数耗尽或期限到达后，由权威生成 `ExecutionClosureRecord`，引用 `EXECUTION_EXHAUSTED` 事件；来源不可用时按 SV-121 产生 invalidating。

### 需要你拍板的两个子问题

- **O-6b 同一角色提交两份不同内容（自我矛盾）**：推荐该角色按零费用处理并记录冲突事件，但**不做故障归因**（所有行仍为 `NO_ATTRIBUTION`），也不改变终态。备选是照常按第一份计费。
- **O-8 存储角色**：首版测试部署里，“存储履约”还没有可观测的定义。推荐首版政策冻结为存储恒为 MISSING、零费用，费用表中存储为 COMPLETE 的行登记为“不可达”并附依据（ADR-0007 D-2 允许）。备选是由权威在接收时保存输出对象，并在终态时记录一次保留检查事件。

### 对 FM-S3 的影响

FM-S3b 需要在权威端新增事件：`RESULT_ACCEPTED`、`RESULT_DUPLICATE`、`RESULT_CONFLICT`、`HOST_FAULT_REPORTED`、由权威逻辑时钟触发的 `DEADLINE_REACHED`，以及 `EXECUTION_EXHAUSTED`。还需要一个从事件快照到 Phase D 输入和费用格的纯投影函数。双机矩阵需要覆盖：结果回复丢失、重传、内容冲突、结果与截止竞争、权威不可达。

这项决定主要落在候选合约中，不需要修改规范正文；对应 P0-1B 的 A4 包（SV-112、SV-121）和 B0 包。

---

## 2. AUDIT-PHASE-B-PATH：无 Snapshot 方法的轮次路径

### 问题

规范 §13.0.4 的 Phase B payload 有六个封闭变体，RG-2 规定了每个变体允许的阶段转换。阶段单调推进：`PRE_FREEZE → FROZEN_PRE_DRAW → RUNNING → TERMINAL`。由此产生两个问题：

- **进入 TERMINAL 必须经过 `SNAPSHOT_FREEZE`**，而它要求 EligibilitySnapshot。`ROUND_TRANSITION_PRE_FREEZE` 只允许 `PRE_FREEZE → PRE_FREEZE`。
- **`RoundStateView.frozen_parameters` 是必填的 `FrozenStatParameters`**（G、B、Q、δmin、mixture 权重），对 audit-only 毫无意义。

所以按现行规范，`REEXEC_AUDIT_ONLY` 没有任何合法路径能走到 TERMINAL，而伪造 Snapshot 或统计参数是明确禁止的。将来的 `DIRECT_VERIFIED`、`PROOF_VERIFIED` 也会遇到同样的问题，因此修复应该对所有“无 Snapshot 方法”通用。

### 选项

| 选项 | 内容 | 优点 | 缺点 |
|---|---|---|---|
| **A（推荐）** | 新增 payload `ROUND_TRANSITION_NO_SNAPSHOT { transition }`，只允许无 Snapshot 方法使用；`frozen_parameters` 改为 `FrozenStatParameters?`，仅在 `REEXEC_BOUNDED` 时存在 | 保留显式、单调的 RoundStage；§8.4 的撤销阶段和 PB-9 失败后果照常适用 | 规范要改 payload 联合类型、RG-2 矩阵和相关 SV 行 |
| B | 无 Snapshot 方法不走轮次转换，由 Phase D 直接提交终态；RoundStage 只对 `REEXEC_BOUNDED` 定义 | 改动看似更少 | 失去“验证进行中”这一阶段，§8.4 撤销语义和 PB-9 要另写一套规则；终态后的 Lease 激活也需要单独的拒绝规则 |
| C | 用退化 Snapshot（G=0 等）走现有路径 | 不改 payload | 违反 PB-7（`|frozen_units| = G`），属于伪造对象，明确拒绝 |

### 推荐 A 的具体规则

- **RG-2 新增一行（仅限无 Snapshot 方法）**：`ROUND_TRANSITION_NO_SNAPSHOT` 允许 `PRE_FREEZE → RUNNING`、`RUNNING → RUNNING`、`RUNNING → TERMINAL`、`PRE_FREEZE → TERMINAL`（如验证开始前就 FAILED 或 EXPIRED）。这些方法永远不进入 `FROZEN_PRE_DRAW`。
- **方法互斥**：无 Snapshot 方法使用 `SNAPSHOT_FREEZE`、`*_POST_FREEZE` 或 `CLUSTER_MAPPING_FIX` 一律拒绝；`REEXEC_BOUNDED` 使用新 payload 也拒绝。
- **RUNNING 的起点**：取第一份被权威接受的 AUDITOR ResultSubmission（即接口 1 的 `RESULT_ACCEPTED`）。理由与 `REEXEC_BOUNDED` 以“首次 draw”为起点一致：一旦观察到验证证据，就不能再回到“验证前”。
- **Lease 激活**：无 Snapshot 方法只允许在 `PRE_FREEZE` 阶段激活 Lease（沿用 `LEASE_ACTIVATION_PRE_FREEZE`）。这与 ADR-0007 D-6“每个 Assignment 一次、不开放新 epoch”一致。

### 对 FM-S3 的影响

FM-S3b 要在 Lease 激活、首份审计结果接受和终态提交时发出 Phase B 转换记录。

规范改动范围：§13.0.4 `PhaseBPayload`（变为七个变体）、§13.1B.2A 的 `RoundStateView` 与 RG-2、§8.5 互斥矩阵，以及 SV-93、SV-94、SV-105、SV-66 的表述。对应 P0-1B 的 A3 包。需要 ADR 记录。

---

## 3. NONMAINNET-ASSURANCE：非主网部署的边界表达

### 问题

现行规范只为官方主网定义了部署边界，而且规则互相锁定：

- **RI-6**：`ReceiptIntent` 的 `network_id` 与 `assurance_profile_ref` 必须解析到**同一官方主网**工程边界。
- **MAP-2**：测试网、fork、私有部署不得复用主网 assurance；`outside_network_disposition` MUST 为 DISABLED。
- **Phase I/F/B 信封和 `DecisionEvaluationInput`** 都直接携带一个 `MainnetAssuranceProfile`。DE-2 还要求 evaluator 在 `MainnetAssuranceProfile.allowed_validator_refs` 中。
- **EF-7** 只定义了主网的状态生效点（finalized checkpoint）。

结论：**按现行规范，任何非主网部署都无法合法创建 Receipt**，而当前所有测试都运行在非主网部署上。FM 系列目前使用的“候选 network/deployment pin”不是 MAP，ADR-0007 D-3 也明确禁止把测试声明塞进 MAP 字段。

### 选项

| 选项 | 内容 | 优点 | 缺点 |
|---|---|---|---|
| **A（推荐）** | 新增对象 `NonMainnetDeploymentDeclaration`；信封与 Receipt 中的部署边界改为联合类型 `DeploymentBoundary ::= MAINNET(MainnetAssuranceProfile) \| NON_MAINNET(NonMainnetDeploymentDeclaration)` | 类型上不可能混淆；保持 MAP-2 原样；与 ADR-0005、ADR-0007 D-3 一致 | 规范改动最大，牵涉多个信封和摘要域 |
| B | 允许测试网发布与 MAP 同型的对象 | 代码改动最少 | 直接违反 MAP-2，正是该规则要防止的类型混淆 |
| C | 非主网时省略 assurance 字段，另加 `network_class` 标志 | 字段少 | DE-2 的 validator 允许集合等检查失去来源，仍要在别处补；“缺省即可运行”容易被误用 |

### 推荐 A 时声明对象应包含的内容

- `network_id`（不得等于官方主网）、部署 genesis 摘要、有效期；
- 运营方签署密钥引用（日志职责，**不是**新的 Principal）；
- 方法处置：V1 只允许 `REEXEC_AUDIT_ONLY`，所有能产生 TRUSTED 的方法为 DISABLED；
- 允许的 RPR、validator、execution capability contract、日志 contract 引用（替代 MAP 中的对应字段）；
- 时间来源声明（如权威逻辑时钟）；
- 状态生效点：单一权威 COMMIT 加签名 checkpoint，并**明确不是 finality**；
- 损失与预算上限引用，以及风险声明。

配套规则：

- RI-6 改为：部署边界必须解析为官方主网 MAP，**或**一份已登记的非主网声明，二者不得混用。
- CB-4、CLM-4：非主网下的判决必须显示“非主网、按声明的风险运行”，不得复用主网 claim 文本。
- EF-7 增加对应条款：非主网状态在声明的生效点生效，不继承主网 finality。

### 对 FM-S3 的影响

S3b、S3c 可以继续使用现有候选部署 pin 开发和做双机验证。但“候选端到端”收尾和任何正式 CreateReceipt 都需要这项决定先落地。

规范改动范围：§9.2 `ReceiptIntent` 及其 ContentMap、RI-6、§13.0.4 中 I/F/B/D 四类信封、`DecisionEvaluationInput`、新摘要 tag、EF-7。对应 P0-1B 的 G0 包。建议以新 ADR 记录，并在 ADR-0005 中补一行引用。

---

## 4. AUDIT-WIRE-BOTTOM：`verified_claim_spec = ⊥` 的线上表示

### 问题

- 规范 §3.1 把字段写成 `verified_claim_spec : VerifiedClaimSpec | ⊥`。SV-30 规定当且仅当方法为 `REEXEC_AUDIT_ONLY` 时取 ⊥，AO-1 重申了这一点。
- 全局编码禁止 null（SV-25、§17.2），但规范没有给 ⊥ 定义任何合法的线上形式。
- 早期 bootstrap JSON 用了 null；FM-S3a 的候选合约用的是 `{kind: NO_CLAIM}`，并明确声明这**不是**本接口的决定。

### 选项

| 选项 | 内容 | 优点 | 缺点 |
|---|---|---|---|
| **A（推荐）** | 省略键：类型改为 `VerifiedClaimSpec?`，SV-30 改为“当且仅当方法不是 `REEXEC_AUDIT_ONLY` 时存在” | 与规范现有惯例完全一致：可选字段一律省略键（§17.2、RI-3），safety/liveness 参数在不适用时 MUST 省略（§8.5）；不新增类型 | 失去“显式写出无 claim”的可读性，但方法字段已经唯一决定是否存在，不会有歧义 |
| B | 显式联合：`{kind: NO_CLAIM}` 或 `{kind: SPEC, spec: …}`（FM-S3a 现行候选形式） | 显式 | 其他所有方法的 VerifiedClaimSpec 都要多包一层；新增联合类型和负例；收益很小 |
| C | 空 map `{}` | 不改类型 | 与一个非法的空 spec 无法区分；规范明确“缺失与空集合是不同的值”，拒绝 |

### 推荐 A 的影响

- FM-S3a 的候选 audit 合约字节会变化：去掉 `verified_claim_spec`，向量重新生成，对应 Receipt 摘要也会变。建议**在 S3b 的第一次双机运行之前**完成，避免候选字节迁移两次。
- 规范改动：§3.1 字段类型、SV-30 措辞、§17.7 相关向量；删除 bootstrap JSON 中的 null 表示。对应 P0-1B 的 A1 包。

---

## 5. 决定之后的落地顺序

1. **你逐项拍板。** 可以直接回复，例如：“1A（O-6b 零费用，O-8 存储恒为 MISSING）、2A、3A、4A”。
2. **起草 ADR-0008**：记录四项决定和规范修订清单，状态按你的决定标注。
3. **一次性修订规范**：规范 §3.1、§8.5、§9.2、§13.0.4、§13.1B.2A 及 SV 表；按 CONTRIBUTING §7 同步检查相关文档。
4. **实施 FM-S3b**：
   - 按接口 1 新增权威事件与投影函数；
   - 按接口 2 发出 Phase B 转换；
   - 按接口 4 更新候选 audit 合约字节；
   - 接口 3 的正式对象在 S3c 或候选端到端收尾之前落地。
5. **P0-1B 覆盖随实现推进**：A1（SV-30）、A3（SV-93/94/105）、A4（SV-112/121）各自计入，不按测试数量抬高。

## 6. 不在本备忘范围

B/Q 与 `REEXEC_BOUNDED` 启用、官方主网 MAP 的具体内容、是否开 `DIRECT_VERIFIED` 线、ADR-0006 的规则接受，以及真实支付。这些各有自己的入口，不受本备忘影响。
