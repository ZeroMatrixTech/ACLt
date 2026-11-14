# ACLt Protocol v0.5 当前状态

> 文档性质：持续更新的项目快照（living document）  
> 基线版本：v0.5  
> 快照日期：2026-11-13
> 当前阶段：G0 — 语义与问题空间冻结  
> 权威范围：记录“现在已经知道什么、还没有证明什么、下一步需要什么证据”；不替代协议规范、ADR 或测试结果。

## 当前实施入口（2026-11-13）

最简验证机的乌托邦基线覆盖可信环境中的多机分工、派发、验证和归并。[通用分布式作业契约](distributed-job-contract.md)的首个整数向量切片已在本地三来宾上联合验收身份绑定、跨子树依赖、尝试账和交接发布，见[联合验收报告](../testing/MULTIVM-GENERAL-JOB-20261113.md)。[可信双机条件](minimal-verifier-baseline.md#可信双机验收)适用于物理双机证据。

| 工作 | 当前事实 | 下一动作 |
|---|---|---|
| 当前开发重心 | [ACLt 最简验证机](minimal-verifier-baseline.md)已立项，首轮规格为实验草案。本地闭环与[阶段 2 语义验收](../../experiments/aclt-minimal-verifier-baseline/SEMANTICS.md)已通过 | 按[乌托邦基线闭合条件](minimal-verifier-baseline.md#乌托邦基线闭合条件)推进：补容量排序回归（M1）、物理双机基线验收（M3）、排序任务族接入通用契约（M2）、补齐契约 §6 的证据复用与双写者停止（M9） |
| 本地双来宾验证 | [第 1 轮报告](../testing/MULTIVM-20261112.md)：同一作业在单宿主两个 QEMU 来宾上跑平坦两片、显式预算两片与树归并三片，两端角色切分、逐片交叉验证和归并输出均通过校验 | 只算来宾级证据；[DUALHOST-SSH-1](../08-governance/dualhost-ssh-validation.md) 的物理双机条件与 G2/G3、P0-1B 仍未关闭 |
| 本地可配置多来宾验证 | [n VM 验收](../testing/MULTIVM-N-20261112.md)：三来宾三片、四来宾六片均通过角色轮换、原始帧重放与成功输出等价验收 | 已验证[来宾工作进程退出与 TCP 断连](../testing/MULTIVM-N-FAULTS-20261113.md)时停止归并与留证，并验证[显式预算内的单次求解补算](../testing/MULTIVM-N-RETRY-20261113.md)；固定统计工件的[整题资源准入](../testing/MULTIVM-ROOT-LIMITS-20261113.md)已验收；并行调度、一般恢复、经济性与原 Gate 各自待验收；完整单机 trap 等价用于明确声明该要求的任务 |
| 可信宿主下的协调器交接 | [两阶段来宾验收](../testing/MULTIVM-HANDOFF-20261113.md)：第 0 片接纳后重启来宾，接手实例复用回执，完成同一作业与预算 | 接手由可信宿主串行化；在途恢复、自动选主与抗回滚待验收 |
| 单节点交付容量对照 | [物理双机固定容量排序](../testing/DUALHOST-CAPACITY-SORT-20261114.md)已通过：单个 6 MiB 镜像无法完整交付 8 MiB，双机各用同规格镜像完成并可重放 | 将排序任务族接到通用契约的统一尝试账、接纳与交接入口 |
| B/Q 三片研究 | [PR #58](https://github.com/ZeroMatrixTech/ACLt/pull/58) 已合并到 main `f5f415f`；现实 B/Q 未建立 | 不阻塞独立的 RIR/运行时实现 |
| 正式迁移路线 | [ADR-0007](../05-decisions/ADR-0007-formal-object-migration-foundation.md) 的 D-1～D-6 已由维护者接受，仅限首轮测试路线 | 测试签名及最小费用/Receipt 候选合约已固定；官方对象与运行准入仍待验收 |
| 已有 FM-S3 与 P0-1B 路线 | 候选 FM-S3 audit-only 链路覆盖 UNRESOLVED、EXPIRED、FAILED、FUNDING_EXHAUSTED 四个过程终态：[8 场景收尾](../testing/FM-S3-CLOSEOUT-20261106.md)、[Task trap](../testing/FM-S3-TASK-TRAP-20261106.md)与[终态和历史矩阵](../testing/FM-S3-HISTORICAL-MATRIX-20261106.md)；P0-1B 按 Profile R1–R11 切片推进 | 正式接口保持 OPEN。正式启动来源、Phase B/D、信封和准入证据列为后续工作；[终态报告](../testing/FM-S3-TERMINALS-20261106.md#留给规范修订的事项)中的 4 项与非主网部署联合类型评审待规范修订 |
| 有界审计修复 | [本轮记录](../testing/AUDIT-FIXES-20261105.md)：证据映射、测试控制面、部署故障隔离与源码交付门禁 | PR #65 已合并；首次失败与修复后通过已留存 [CI 记录](../testing/FM-EVIDENCE-CLOSEOUT-20261107.md#github-ci-运行记录)，正式准入仍关闭 |
| FM-S3 规范对齐 | [第一项四片收尾](../testing/FM-S3-INTERFACE-CLOSEOUT-20261106.md)覆盖无 claim 编码、Phase B、接纳边界和非主网部署草案 | 正式信封和准入另行评审 |
| FM-S3 终态与历史回归 | [组合双机结果](../testing/FM-S3-HISTORICAL-MATRIX-20261106.md)通过入口、执行闭合、资金边界与结算恢复，并逐项对照 Work 2/3 的 38 个历史场景 | 候选证据与正式 FM-A 验收分开记录 |
| FM 证据归档 | [第四项收尾](../testing/FM-EVIDENCE-CLOSEOUT-20261107.md)归档五份公开包并重放 24 套快照，补齐原始审计、CI 记录和 12 项 FM-A 候选证据 | 正式 FM-A 仍逐项验收；本轮改动的 CI 随提交触发 |
| P0-1B Profile 注册 | [R1 正式摘要与判决](../testing/PROFILE-DIGEST-R1-20261107.md)及 [R2 嵌套类型/导入与注册上下文](../testing/PROFILE-REGISTRATION-R2-20261107.md)：新增 RegistrySnapshot/事件快照摘要与六类注册条目检查，audit Phase R 显式接两个快照；[R3](../testing/PROFILE-REFERENCES-R3-20261108.md)补排除集/注册对象引用与两个摘要，并修正 TimeRange/ExternalTypedObject wire | [R4](../testing/PROFILE-RULES-R4-20261108.md)落实共同假设/撤销/scope/方法必需类与静态集合摘要；[R5](../testing/PROFILE-MATRICES-R5-20261108.md)补四方法参数/失败/条件矩阵；[R6](../testing/PROFILE-CREATION-R6-20261108.md)补固定 audit I/F 测试接线、三个摘要与 CC-1；[R7](../testing/PROFILE-SELECTION-R7-20261108.md)集中完成注册/选择/绑定 14 项，扩展 7 项仍 partial；[R8](../testing/PROFILE-COMMITMENTS-R8-20261108.md)集中完成 19 项 Claim/快照/承诺规则，18 个摘要公式/投影已有双语言实现；[R9](../testing/PROFILE-RUNTIME-R9-20261108.md)补七种 Phase B 的运行期绑定/冻结/阶段守卫，snapshot/population/randomness 仍限 TEST imports，SV-69/81 partial。[R10](../testing/PROFILE-DECISION-R10-20261109.md)加入 audit-only Phase D 测试重放，SV-115/121 partial。[R11](../testing/PROFILE-AUTHORITY-R11-20261109.md)接入 FM-S3 候选权威来源与结算对照，SV-119 partial；下一步评审候选输入胶囊的正式版本承诺、ENUM/sum wire，闭合 FailureReason、predicate/gate 和完整重放。其他方法 wire 缺口独立追踪，完整 Phase R 尚未验收 |
| Phase I/F/B/D 候选接口 | [R14](../testing/PROFILE-PHASE-D-R14-20261111.md)验证历史 B/D 信封，[R15](../testing/PROFILE-PHASE-D-R15-20261111.md)实现创建时部署绑定并串联授权、判决与结算 | [R16](../testing/PROFILE-PHASE-D-R16-20261111.md)验证候选部署撤销；正式 FM-A08 仍依赖 Profile/来源审批、撤销传播和部署证据 |
| 开发者预览 | [发行说明草案](../releases/PREVIEW-20261106.md)与[维护记录](../08-governance/audits/audit-20261106-01-repository-maintenance.md)：源码包可重现、包内本地检查可运行 | 发布前在待打标签 commit 上重跑双机并确认 CI；预览不是 ProtocolVersion、ConformanceTarget 或部署启用 |
| 证明验证路线 | [ADR-0009](../05-decisions/ADR-0009-proof-verified-computation-statements.md) `PROPOSED` 草案：以推导证书验证计算陈述，分陈述绑定、推导检查与语义充分性三层；`verification.proof-assisted` 仍为 V1 `DEFERRED` | 评审接口；首个实例依赖 RIR-0 形式语义（PO-11），在此之前只走非主网测试路线 |
| 验收边界 | P0-1B 为 80/36/3，ADR-0006 仍 PROPOSED，Gate/OQ/主网资格不变 | 不将路线接受当成 conformance 或部署启用 |

当前依据：[ADR-0006 分层评审](../05-decisions/reviews/REVIEW-20261028-layered.md)、[三份机器摘要与校验](../testing/MIGRATION-EVIDENCE-20261028.md)、[FM-S3 audit 依赖](fm-s3-audit-dependencies.md)。以下带日期记录为历史，不覆盖本表优先级。

## 1. 二维状态

本文件按 ADR-0003 分别记录：

- `SemanticStatus`：`OPEN`、`CANDIDATE`、`DECIDED`、`INVARIANT`、`SUPERSEDED`、`REJECTED`；
- V1 `VersionDisposition`：`CORE`、`DEFERRED`、`REJECTED`。

`DERIVED`、`ASSUMPTION` 和 `HYPOTHESIS` 只作为 ClaimQualifier；`P0–P2` 只作为 Priority。不得用一个斜杠状态同时表示语义成熟度、版本范围和优先级。

V1 映射的唯一权威入口是 [`../03-protocol/v1-profile.md`](../03-protocol/v1-profile.md)。本文件只展示连接结果和阻断，不复制完整 Profile。

## 2. 一句话状态

ACLt Protocol v0.5 已完成最小语义基线和文档骨架：两类不可约 Principal、无中心裁决者的函数化流程、二维状态模型、ACLt Abstract Machine 边界、Logical Object Memory、Compile 三阶段、Provider Dispatch 握手、RIR/Rust Profile/RPR 执行边界，以及证据到暴露的风险链条已经明确。有限总体验证的条件数学内核已闭合；对象 Schema、RIR/RPR 形式语义、完整状态机、主网 assurance、日志/恢复 contract、结算矩阵与参考实现仍未达到可实现冻结状态。

因此，v0.5 当前是“可审查的研究与规范基线”，不是生产就绪协议，也不是已证明安全的系统。

工程进展：三切片候选 RIR 执行链的[第一项工作已限域收尾](../testing/RIR-WORK1-CLOSEOUT-20261023.md)；完整协议与 conformance 状态仍如下表。

版本连续性：**v0.5 是协议语义基线；V1 是建立在其上的首个执行与 conformance 目标。** 采用 V1 名称不会使 v0.5 自动升级为 v1.0，也不表示 G0 已通过。

## 3. 当前事实表

| 领域 | SemanticStatus | V1 | 已确定内容 | 尚缺内容 |
|---|---|---|---|---|
| 名称与定位 | `DECIDED`；外部权利 `OPEN` | — | 名称为 ACLt Protocol；它是协议而非区块链 | 名称法律检索、域名、商标和兼容性标识政策 |
| 代码许可 | `DECIDED` | — | 代码与参考实现采用 Apache-2.0；根目录 `LICENSE` 已存在 | 未来源码 SPDX、按需 NOTICE 和第三方许可清单 |
| 其他工件许可 | `DECIDED` | — | 2026-11-14 决定规范、文档、仓库内研究文稿与测试证据沿用 Apache-2.0；第三方材料保留原许可；名称与商标不在许可范围内，见「名称与定位」 | 按需 NOTICE；文稿投稿时出版方另有条款的单独处理 |
| 状态与版本 | `DECIDED` | `CORE` | SemanticStatus 与 VersionDisposition 分离；v0.5 是语义基线，V1 是 ConformanceTarget | machine-readable registry、版本兼容矩阵 |
| 最小本体 | `DECIDED` | `CORE` | 只有 Requester 与 Provider 是不可约 Principal | Principal Schema、轮换与控制关系 |
| Abstract Machine | 边界 `DECIDED`；形式模型 `OPEN` | `CORE` | 以对象和合法事件驱动状态转换；无共享机器地址空间 | machine-readable 状态、完整转换和恢复模型 |
| Logical Object Memory | 不可变接口 `DECIDED`；细节 `OPEN` | `CORE` | 内容寻址、显式引用、输出新对象 | Schema、可用性、保留、隐私和 GC |
| 协议函数 | `DECIDED` | `CORE` | Compile/Plan/Admit/Schedule/Execute/Verify/Settle 等是 permissionless functions | 完整输入、输出、错误和确定性要求 |
| Compile | 三阶段边界 `DECIDED`；算法 `OPEN` | `CORE` | `Lowering + Decomposition + Packing`，不得扩大 Receipt | TaskGraph、合法性谓词、等价证明和 vectors |
| Provider Dispatch | 握手与单一权威边界 `DECIDED`；算法 `OPEN` | `CORE` | proposal 不产生义务；Provider accept 后 Lease 生效；Dispatch/RPR 消费 Lease capability | capability Schema、候选选择、API、时钟、旁路和竞态测试 |
| Task 与 Receipt | `INVARIANT` 接口；Schema `OPEN` | `CORE` | 任务语义在结果揭示前冻结 | canonical encoding、哈希域、版本兼容 |
| 执行表示与前端 | 方向 `DECIDED`；Wasm 子集路线 `DECIDED`（2026-10-23 项目决定）；子集/编码/计量/结果/ABI `CANDIDATE`（ADR-0006 草案）；形式语义 `OPEN` | `CORE` | RIR 规范表示；Rust Profile reference frontend；RIR 主体基于 Wasm Core 1.0 子集 | ADR-0006 审查与接受、RIR validator/解释器双实现与向量、Rust lowering 和 conformance |
| RPR 与 Host OS | 边界 `DECIDED`；contract `OPEN` | `CORE` | 默认隐藏宿主状态；不支持时 fail closed | capability ABI、effects、计量、错误、checkpoint |
| 结果验证 | Profile/条件数学内核 `DECIDED`；部署前提 `CANDIDATE` | `CORE` | DIRECT/PROOF/REEXEC_BOUNDED/AUDIT_ONLY；有限总体 e-process；Bayesian 仅作效率层 | VerifiedClaim、部署 \(B/Q\)、独立性证据、固定算术和跨实现 conformance |
| Sybil 与相关性 | 原则 `DECIDED`；算法 `OPEN` | `CORE` | 不假设身份独立；保守折减并叠加硬暴露上限 | 信号、隐私、分组算法和最坏损失校准 |
| 权威隔离 | `INVARIANT` | `CORE` | 历史能力、付款和 FoundationReport 不进入真理权重 | 可执行权限与负例测试 |
| 资金 | 类型与解耦 `DECIDED`；账务 `OPEN` | `CORE` | FundingPolicy 不证明 correctness；发行非默认 | 锁定、耗尽、退款和破产处理 |
| 结算 | `INVARIANT` 接口；矩阵 `OPEN` | `CORE` | 每项权利最多一次 | 故障归因、退款、尾数与部分履约 |
| 维护边界 | `DECIDED`；流程 `OPEN` | `CORE` | Maintenance 不是运行时裁决者 | 发布、撤销、响应、密钥和最小组织流程 |
| 主网工程 assurance | 原则 `DECIDED`；对象 `CANDIDATE` | `CORE` | 限 `network_id`、版本化、只减权、不进入个案权重 | Schema、组件注册、日志 contract、损失预算和撤销演练 |
| 多原因假设状态 | 判决/诊断分层 `DECIDED` | `CORE` | 完整 CauseSet 派生唯一 EffectiveVerdict | reducer Schema、组合向量与迁移 |
| 实现与适配器 | `OPEN` | `CORE` | 当前 state3 单机实验、预登记多节点原型、外置权威账本实验与自动进度流程已落地；Control Plane 是实现；基础设施可替换 | 完整参考实现、RIR/RPR、正式对象接口和互操作测试 |
| 运营成熟度 | `OPEN` | — | 威胁与不变量登记已建立 | SLO、事件响应、灾难恢复和试点数据 |

## 4. 已完成的最小文档基线

截至本快照，最小仓库中的 Markdown 文档已经全部建立：

- `00-overview`：项目定义、设计原则、术语和系统上下文。
- `01-requirements`：威胁模型和系统不变量。
- `02-architecture`：Abstract Machine、Logical Object、Compile、Dispatch、分层架构、身份与任务生命周期。
- `03-protocol`：协议规范骨架、V1 Profile、结果验证、能力证据与暴露模型。
- `04-analysis`：稳健性论证和管理成本边界。
- `05-decisions`：最小实体、RIR/Rust Profile、二维状态、验证 Profile/e-process 与工程 assurance 决策记录。
- `06-research`：主张与来源、验证数学模型及最后两个问题的思路树。
- `07-roadmap`：当前状态与待决问题。
- `08-governance`：已接受的审计程序、报告模板和按编号归档的审计记录。

“文档已建立”不等于相应设计已证明。文档中的状态标签和关闭证据决定其成熟度。

## 5. v0.5 不变量状态

`docs/01-requirements/invariants.md` 当前记录 16 条规范性不变量。它们是实现接受条件的来源，但尚未全部形式化或转化为可执行测试。

| 工作项 | 状态 | 下一证据 |
|---|---|---|
| 不变量编号与自然语言定义 | 已完成 | 跨文档一致性评审 |
| 不变量到威胁的映射 | 部分完成 | 完整双向追踪矩阵 |
| 不变量到协议函数的映射 | 部分完成 | 每个转移的前置/后置条件 |
| 不变量到测试的映射 | 未开始 | conformance test ID 与测试向量 |
| 不变量的形式化表达 | 未开始 | 状态机、时序性质或可检查断言 |

## 6. 验证门（Gates）

版本推进不按文档数量或主观完成百分比判断，而按可复核证据通过以下验证门：

| Gate | 目标 | 退出证据 | 当前状态 |
|---|---|---|---|
| G0 | 规格化：术语、本体、二维状态、Abstract Machine、对象、RIR/RPR、Compile、Dispatch、状态机、不变量、统计与资金政策 | 每项 V1 CORE/P0 可由机器或测试表达；连续性审计无未登记冲突 | 进行中 |
| G1 | 仿真与模型验证 | 能力、调度、验证、相关性、攻击、资金、行政成本和 RIR/RPR 模型的敏感性与反例 | 未开始 |
| G2 | 单机参考实现 | Registry、RIR toolchain/RPR、Compile、Lease、Result、Verify、Settle、Event 通过并发/重放/崩溃性质测试 | 已有局部单机实验；完整 Gate 未通过 |
| G3 | 局域网多 Provider MVP | 断连、退出、恢复、沙箱和初始 SLO 故障注入 | 未开始 |
| G4 | 持久化与灾难恢复 | 数据库/日志/对象存储适配器、备份恢复、RPO/RTO 与 conformance | 未开始 |
| G5 | 对抗验证 | Sybil、串谋、证据刷取、预算耗尽、compiler/runtime 与维护滥权的损失界或检测率 | 未开始 |
| G6 | 异构扩展与外部试点 | 新硬件、任务类型和可选账本保持不变量且证据不错误迁移 | 未开始 |

任何 Gate 都不得用“已有实现”反向定义协议语义。结构和算法闭合仍需要唯一 Schema、确定规则和可复算证据；来源忠实性和部署事实则允许由日志、权限审计、故障注入、试点与版本化 assurance 建立。工程证据不必被伪装成形式证明，但其适用网络、组件、有效期、撤销和损失边界必须公开。

### 6.1 2026-08-18 G0 连续性审计

**结论：语义连续性通过，G0 退出未通过。** 本轮已消除 v0.5 与 V1、源语言与规范执行表示、项目 V1 与旧验证类型 `V1` 占位编号之间的冲突，并将 RIR/Rust Profile 决定映射到 ADR、威胁、不变量、协议、验证与路线图。

仍阻断 G0 退出的证据包括：RIR/对象 canonical schemas、完整状态机、RIR validator 与 runtime/effects/resource 语义、Rust Profile lowering、验证定理、相关性与最大损失模型、资金/退款/结算矩阵、控制面一致性/恢复和发布撤销流程。

当前允许开展的是 G0 内的工程化规格工作，例如 schema、validator、golden vectors、可执行模型、差分测试脚手架和仿真准备；这些产物不得被表述为 G1 已完成、G2 参考实现已合格或系统鲁棒性已证明。

### 6.2 2026-08-18 语义结构修订审计

本轮本地准备变更接受 ADR-0003，将 SemanticStatus 与 V1 VersionDisposition 分离，并保守闭合 Abstract Machine、Logical Object Memory、Compile 三阶段、RPR/Host OS 和 Provider Dispatch 的概念边界。对应审计报告位于 [`../08-governance/audits/audit-20260818-01-semantic-structure.md`](../08-governance/audits/audit-20260818-01-semantic-structure.md)。

结论保持：**语义连续性通过，G0 退出未通过。** “边界已决定”不等于 Schema、状态机、算法、证明或 conformance 已完成；全部 `OPEN/CANDIDATE + CORE` 项继续作为阻断。

## 7. 当前最高优先级

### P0 — 阻断 G1

1. 建立 SemanticStatus registry 与 V1 Profile 的 machine-readable join，并验证全部 CORE 阻断可枚举。
2. 固定 Abstract Machine、Logical Object 和所有规范对象的最小字段、版本、规范编码与哈希域。
3. 固定 Task、Assignment、Lease proposal/accept、Receipt、Execution、VerificationSession、Settlement 的状态机。
4. 冻结 RIR grammar/schema、canonical encoding、validator、Rust Profile lowering、RPR capability 与 runtime effects/resource/error 语义。
5. 固定 Lowering/Decomposition/Packing 的 Schema、TaskGraph/WorkPlan 合法性谓词与语义保持条件。
6. 建立威胁—不变量—函数—证明义务—测试追踪表。
7. 固定 VerificationProfile、VerifiedClaim/ExcludedClaims、MainnetAssuranceProfile、CauseSet/reducer、exact result equivalence、样本帧、有限总体 e-process、精确算术与随机性承诺；P0-1B 可用固定测试参数实现接口，不等待通用部署 \(B/Q\) 证明。
8. 固定 Lease 派生 ExecutionCapability、Dispatch/RPR 检查接口和日志 finality/inclusion/consistency contract。
9. 写出资金锁定、终态、退款、处罚和 at-most-once 结算矩阵。

**P0-1 当前状态（2026-10-23 复核）**：P0-1A 经 AUD-20260821-10 判定 `PASS / CLOSED`；P0-1B 已创建首批 L1a/L1b、注册表种子和单元测试工件，状态 `STARTED / NOT CLOSED`。L2、全量 119 项 Type A、完整五相位对象、18 摘要和第二语言对拍仍未完成；6 项 Type B 与 SV-40 不计入 P0-1B 关闭。 全量盘点：119 项 Type A 中 3 项局部 implemented、19 项 partial、97 项未实现；模板/claim 两个摘要部分实现，其余 16 项未实现；候选 ClaimTemplate/结构化 claim 编码链已完成 Python/Rust 限域对拍；下一步是候选 wire/import 合约审查及完整模板类型接入，见[编码记录](../testing/CLAIM-CODEC-20261023.md)。

### P0 — 阻断公开发布

1. 完成 **ACLt Protocol** 名称冲突检索。
2. 保持根目录 Apache License 2.0 `LICENSE` 不被改写，并给未来适用源码加入 `SPDX-License-Identifier: Apache-2.0`。
3. 决定名称、商标和兼容性声明的使用政策。规范、文档与研究文稿已于 2026-11-14 决定沿用 Apache-2.0。
4. 决定贡献者许可机制（仅项目许可证、DCO 或 CLA）及第三方代码接受规则。

### P1 — 阻断 G1/G2 的可信推进

1. 为 `REEXEC_BOUNDED` 建立可部署的能力集合上界 \(B\)、活性下界 \(Q\)、随机排列独立性和跨任务错误预算；保持递推/闭式/全枚举持续对拍。
2. 校准相关性分组、证据折扣和硬暴露上限。
3. 固定 CapabilityEstimate 的不确定性表达、冷启动和衰减模型。
4. 建立最小可执行模型、仿真场景和失败注入基线。
5. 建立 frontend lowering、RIR validator、RPR/Host OS capability 与资源计量的差分 conformance 基线。
6. 为官方主网选择首批 assurance 组件集合、风险预算和撤销/降级演练；结论不外推到主网外。

### P2 — 可在核心稳定后并行

1. 扩展非确定性任务、隐私任务、数据本地性与硬件证明支持。
2. 评估 unsafe/full-std、原生执行、GPU/专用加速器和 C++23 conforming frontend 的独立 Profile；不得绕过 RIR。
3. 评估账本、支付、身份、对象存储等可选适配器。
4. 评估 TEE、零知识证明或其他密码学增强，但不得预设其必要性。

## 8. 进度更新规则

每次会改变 v0.5 认知状态的提交，都应更新本文件：

- `CANDIDATE` 被证明、证伪或替换；
- 新增、删除或重写不变量；
- 某个 Gate 的退出证据发生变化；
- 协议对象、状态机、验证假设、资金或结算规则发生变化；
- 试验、仿真、审计或试点产生了影响结论的新证据；
- 风险由“已知但未量化”变为“已量化”，或反向退化；
- 版本、许可证、维护边界或发布策略发生变化。

更新时必须同时：

1. 修改“当前事实表”中相应行；
2. 更新 `open-questions.md` 的问题状态和证据链接；
3. 更新受影响的规范、分析或 ADR；
4. 在下方日志增加一条记录。

## 9. 状态变更日志

| 日期 | 基线 | 变化 | 证据/文档 | 影响的 Gate |
|---|---|---|---|---|
| 2026-11-14 | v0.5 | M3 完成固定统计用例的物理双机验收。两种 LAN 返回顺序的归并结果均与单机参照逐字节一致，漏片和错绑提交均由实跑证据重放并被拒绝 | [M3 验收报告](../testing/DUALHOST-BASELINE-20261114.md)、OQ-04、OQ-06 | 不变 |
| 2026-11-14 | v0.5 | 维护者决定规范、文档、研究文稿与测试证据沿用 Apache-2.0，仓库全部工件采用同一许可；第三方材料保留原许可；名称、商标与贡献机制仍 `OPEN` | `README.md`、`CONTRIBUTING.md`、OQ-01 | 公开发布 |
| 2026-10-23 | v0.5 / V1 target | 项目决定 RIR 主体采用确定性 Wasm 核心子集；起草 ADR-0006（`PROPOSED`），未改规范对象与 V1 处置 | [ADR-0006 草案](../05-decisions/ADR-0006-rir-deterministic-wasm-core-subset.md) | G0 未通过退出 |
| 2026-10-23 | v0.5 / V1 target | 候选模板/claim 编码、2 摘要与 Python/Rust 对拍；规则仍为局部覆盖 | [编码记录](../testing/CLAIM-CODEC-20261023.md) | G0/G2 未通过退出 |
| 2026-10-23 | v0.5 / V1 target | 完成 119 项规则与 18 摘要覆盖盘点；修正登记，运行时能力未改变 | [盘点报告](../testing/P0-1B-INVENTORY-20261023.md) | G0/G2 未通过退出 |
| 2026-10-07 | v0.5 / V1 target | 同步已合入的 state3 与流程入口及 2026-10-03 限域证据；P0-1B 未关闭 | `../testing/INTEGRATION-FIX.md`；本轮 Markdown 维护报告 | G0/G2 均未通过退出 |
| 2026-08-17 | v0.5 | 建立最小 Markdown 文档基线；明确当前处于 G0 | `docs/` 全集 | G0 |
| 2026-08-17 | v0.5 | 决定代码与参考实现采用 Apache License 2.0；其他工件维持独立许可边界 | `README.md`、`CONTRIBUTING.md`、OQ-01 | 公开发布/G6 |
| 2026-08-17 20:51:52 CEST | v0.5 | 根目录 `LICENSE` 已切换并落地为 Apache License 2.0 英文全文 | `LICENSE`；提交 `e5d5bc149c2773332c944b000fa23f5f3a5bc97a` | 公开发布 |
| 2026-08-18 | v0.5 / V1 target | 接受 RIR 作为规范执行表示、Rust Profile 作为 V1 参考前端；未来 frontend 必须降级到同一 RIR | ADR-0002 及同步文档 | G0/G1/G2 |
| 2026-08-18 | v0.5 / V1 target | 接受 SemanticStatus 与 VersionDisposition 二维分离；建立 V1 Profile 唯一映射 | ADR-0003、`03-protocol/v1-profile.md` | G0/G1/G2 |
| 2026-08-18 | v0.5 / V1 target | 保守闭合 Abstract Machine、Logical Object、Compile、RPR/Host OS 与 Provider Dispatch 的概念边界；形式语义和证据继续开放 | 架构、协议、生命周期和 AUDIT-20260818-01 | G0/G1/G2 |
| 2026-08-19 | v0.5 / V1 target | 接受 VerificationProfile 与有限总体 e-process；条件数学内核经精确递推、闭式、全枚举和 DP 对拍闭合；通用 permissionless 的 \(B/Q\) 与独立性仍阻断部署 | ADR-0004、验证模型说明、`tests/verification_model/` | G0/G1 |
| 2026-08-21 | v0.5 / V1 target | 接受工程事实分层闭合和官方主网 assurance；不再以自然人身份唯一性或现实日志的形式完美证明阻塞接口实现；多原因采用事实集合+单一派生 verdict，Dispatch 采用单一 Lease 权威+多检查点 | ADR-0005、最后两个问题思路树 | G0/G1/G2 |

日志只记录影响项目认知或成熟度的变化；排版、错字和无语义重构不必记录。

## 10. v0.6 就绪条件

只有在以下条件同时满足时，才应讨论将 v0.5 基线提升为 v0.6：

- G0 完成，核心术语、问题登记和文档之间不存在已知语义冲突；
- G0 的二维状态 registry、Abstract Machine、Logical Object、对象编码、状态机与错误语义达到可实现冻结状态；
- RIR、Rust Profile、RPR/Host OS capability、runtime/effects/resource model 与 conformance 规则达到可实现冻结状态；
- Lowering、Decomposition、Packing 和 Provider Dispatch 的合法性与竞态规则达到可实现冻结状态；
- 验证核心至少有一套明确、可复核且标注适用边界的证明或反例结论；
- 资金、暴露、终态和结算可以对所有已声明失败路径给出确定结果；
- 不变量至少映射到可执行模型或测试计划；
- 所有仍未解决的高风险问题都具有明确风险接受者、上限和下一关闭证据；
- 名称政策、代码许可证落地、其他公开工件的许可边界与贡献规则不再阻断公开发布。

v0.6 不代表生产就绪；它代表 v0.5 的核心开放问题已经被收敛为一套可实现、可验证的新基线。


## 2026-10-03 本地单机测试补记

以主仓库 ab9f233 与未提交的 state2 实验目录为基线，完成当前实验功能的 259 个场景，并运行现有模型、扩展验证配置、差分与内存检查。实验新增本地额度和任务绑定，运行记录升级为 v3；未冻结新的协议语义。验证器修复未知版本、错误输入与部分精确参数检查，生产模式继续拒绝。SV-57 的完整 Phase D 接入仍缺失，覆盖登记修正为部分实现。

本地证据与未实现清单见 [单机验收记录](../testing/SINGLEHOST-REPORT.md) 与 [逐条规则账本](../testing/SINGLEHOST-COVERAGE.json)。P0-1B、G0/G2 和其余 Gate 的关闭结论不变。

## 2026-10-03 主仓库集成与恢复顺序修复

统一入口改为 state3；修复 workflow 的安装目录与缺失模板。恢复必须先通过启动标识、期限和恢复次数检查，再预留验证额度。新增 6 个已有接受分块的回归场景，单机场景合计 265；主仓库模型 13、验证器 24、流程与集成 22 项通过。旧报告的 state2 名称与 259 数量保留为历史基线，不代表当前目录或当前测试数。详见 [修复报告](../testing/INTEGRATION-FIX.md)。

## 2026-10-07 文档维护复核

当前目录基线为 `5e8263ae48aee30b7219275ddbf3686ff802374e`（main）。state3 为当前统一入口；265 场景等数字引用 2026-10-03 已存证据。本轮仅重跑 22 项流程/集成测试，不把历史记录转为新的全量 PASS。完整 P0-1B、G0/G2 退出和其余 Gate 的关闭结论不变；详见 [维护报告](../08-governance/audits/audit-20261007-01-markdown-maintenance.md)。

## 2026-10-20 接纳端回滚与复制限域证据

外置单一可信账本实验已完成本地验证、接纳端快照/复制与断网矩阵、四个确定事务断电点及 40 次随机整机硬终止，并独立核对签名、结果与账本。详见[本轮工程记录](../testing/AUTHORITY-ADMISSION-20261020.md)。证据仅在权威账本自身不回滚的信任边界内成立，不关闭 P0-1B、G0/G2 或更高 Gate。

## 2026-10-23 ADR-0006 审阅修订（候选）

已修订空 else 的唯一编码、validator 首失败归属、宿主多 trap 优先级、输入数量位宽、工件/Receipt 身份分离与重执行术语，并保存候选边界向量；见 [修订记录](../testing/RIR-ADR-REVISION-20261023.md)。ADR 仍为 PROPOSED，规则仍为 CANDIDATE；向量未在 RIR validator/解释器中执行，G0/P0-1B/G2 不关闭。

## 2026-10-23 RIR 构建切片 1（候选可行性证据）

[双机最小构建报告](../testing/RIR-BUILD-SLICE1-20261023.md)：固定官方工具链下，A/B 各两次最小 no_std 空 run 编译，raw Wasm、限定后处理 Wasm 与候选工件均一致；导出属性与 forbid(unsafe_code) 的边界由受信入口层显式承接。证据不覆盖完整 SDK、RIR validator/runtime、gas 或 stats-int-v1。ADR-0006 仍 PROPOSED，G0/P0-1B/G2 不关闭；下一切片为显式输入输出 SDK 和执行路径。

### RIR 切片 1 收尾

[可复用构建入口](../../experiments/aclt-rir-build-probe/README.md)及离线安装、跨机证据比较和 10 项回归已入库；两端按维护入口重跑共四次构建通过。第一个切片在最小空 run 构建范围内完成，见 [收尾记录](../testing/RIR-BUILD-SLICE1-20261023.md)。该完成状态不改变 ADR-0006 PROPOSED、OQ-05 OPEN 或协议 Gate。

## 2026-10-23 RIR 切片 2：安全 SDK / I/O 候选闭环

[切片 2 报告](../testing/RIR-IO-SLICE2-20261023.md)：两端四次独立构建与受限 Python 执行，220 条用例记录一致；现有独立 Wasm 引擎 360 次语义对拍一致，不覆盖 gas/深度/绑定。安全 SDK、候选外壳 reader、限定类型检查/解释执行及显式 CLI 已入库；19 项回归纳入 make check。仍缺独立 Rust RPR 和完整 conformance，不关闭 ADR 接受或 G0/G2。

## 2026-10-23 RIR 切片 3：整数统计与独立候选执行

[切片 3 报告](../testing/RIR-STATS-SLICE3-20261023.md)：stats-int-v1 经显式二进制适配器接入候选 RIR；双机四组构建一致，276 条 Python/Rust 执行差分记录、160 次 C++ 行比较和 440 次现有 Wasm 引擎语义对拍通过。新增独立 Rust Wasm 解码/执行器，其入口仍依赖 Python 预验证，外壳/摘要实现独立性未完成；14 项局部回归纳入 make check。下一项是冻结输入/上限与正式 Receipt 的绑定；ADR-0006、G0/G2/P0-1B 状态不变。

## 2026-10-23 第一项工作收尾：三切片候选执行链

**工程范围完成**：[总收尾与交接](../testing/RIR-WORK1-CLOSEOUT-20261023.md)。统一入口在双机重新完成 12 次构建、496 条记录、160 次 C++ 比较及 800 次现有引擎语义对拍；122 项本地回归通过。受限子集与预验证依赖保留，不等于正式 RIR/RPR conformance 或 G0/G2/P0-1B 退出。下一项为正式 Receipt 候选编码及工件/输入/执行上限冻结绑定，然后接入重执行比较记录。

## 2026-10-23 第二项切片 1：最小任务承诺候选

[任务承诺报告](../testing/TASK-COMMITMENT-SLICE1-20261023.md)：ExperimentalTaskCommitment 与专用实验身份绑定 RIR、输入、Profile 和显式执行上限；双机 48 条探针记录一致，19 项新增回归纳入默认检查。调用方保存的 expected ID 用于拒绝替换和错绑，执行入口仍是无授权的诊断探针。正式 ComputeReceipt/签名/Lease/ExecutionCapability/EventRecord 不因此实现，Gate 状态不变。下一切片为实验授权与启动前持久化。

## 2026-10-24 第二项切片 2：实验授权与启动意图

[授权切片报告](../testing/TASK-AUTHORIZATION-SLICE2-20261024.md)：A 单一可信实验账本、B 实验 Python RIR 入口，经真实 LAN 完成 16 个场景，签名 grant 在调度/启动处检查，fsynced intent 和唯一 CONSUME 在 guest 前完成；24 项新增回归，默认合计 165 项。任意恶意宿主、权威回滚、正式 Lease/capability 与完整事件重放仍未覆盖，Gate 状态不变。下一切片为完整提交/接纳与可重放因果日志。

## 2026-10-24 第二项切片 3：提交接纳与可重放因果链

[重放切片报告](../testing/TASK-REPLAY-SLICE3-20261024.md)：新增独立实验流，串起注册/授权/持久启动/outcome/不可变提交/接纳/ACK。双机 12 个场景和 7 个篡改反例通过；两端各 26 项新增回归，默认合计 191 项。独立离线 reducer 重建 34 条 A 事件、55 条 B 事件、4 接纳/5 消费，重传与重放不再次执行任务。丢回执与已 ACK 分离，不完整状态禁止续算。正式对象、正确性判决、结算、恶意宿主/权威抗回滚未覆盖，Gate 不变。下一步为第二项三切片统一收尾。

## 2026-10-24 第二项工作收尾：冻结承诺、授权与可重放提交

**限定工程范围完成**：[统一收尾报告](../testing/TASK-WORK2-CLOSEOUT-20261024.md)。统一入口新跑两端承诺 48 条记录、授权 16 场景、提交/重放 12 场景及 7 个篡改反例；三片两端各 69 项回归，默认合计 196 项。跨片核对实际 RIR/输入字节、Profile、上限与等价规则，另进程重建中间 pending ACK 和最终 34/55 条因果流。正式对象、正确性判决、结算与 Gate 状态不变；下一项建议为同一冻结任务的双端 outcome/精确比较证据绑定。命令与交接边界见 [维护入口](../testing/TASK-WORK2-MAINTENANCE.md)。

## 2026-10-24 第三项切片 1：冻结资金政策与原子预留

[资金预留报告](../testing/FUNDING-RESERVATION-SLICE1-20261024.md)：新增预置整数测试资产与冻结实验资金政策，按原 cap 原子预留、幂等保留原回执。双机 12 场景、5 个篡改反例通过，两端各 22 项新增回归，默认 218 项。独立离线重建 18 条事件、初始 300=可用 50+预留 250，2 个唯一预留。未实现支付/退款、比较决定/结算权利或旧入口资金门禁；正式对象、OQ-10 和 Gate 状态不变。下一切片是绑定比较/结算依据后实现固定支付与退款。

## 2026-10-24 第三项切片 2：结果绑定与固定测试结算

[固定结算报告](../testing/FIXED-SETTLEMENT-SLICE2-20261024.md)：独立 v2 测试部署冻结比较规则，资金先于新入口 START，双端完整 outcome 派生唯一分配；OK 相等按固定费用支付退余款，预声明完整 no-pay 全退，缺失/未知保留预留。双机 12 场景/6 个篡改反例、两端各 26 项回归通过，默认 244 项。矩阵 5 份 outcome、2 份结算；paid=30/refunded=170/active reserved=100，资产总量保持 1000。旧入口/旧库不迁移，正式对象、OQ-10/判决/Gate 不变。下一片扩展实际丢回复/中断和账务恢复矩阵。

## 2026-10-24 第三项切片 3：真实结算故障与恢复

[恢复报告](../testing/SETTLEMENT-RECOVERY-SLICE3-20261024.md)：独立 wrapper 复用原 v2 转移，以真实 TCP reply loss、COMMIT 前后服务 SIGKILL、B 持久边界终止与首次 barrier 竞争验证原权利恢复。双机 14 场景/6 个篡改反例、两端各 16 回归通过，默认 260 项；9 份 checkpoint 另进程重放一致。矩阵 61 条事件、6 份唯一结算，paid=150/refunded=450/active reserved=100，总量保持 1000。recover 仅 STATUS，未知不自动退付/重算。正式对象、OQ-10/Gate 不变；下一步第三项三片统一收尾。

## 2026-10-24 第三项工作统一收尾：测试资金与固定结算恢复

**限定工程范围完成**：[收尾报告](../testing/FUNDING-WORK3-CLOSEOUT-20261024.md)。统一入口重新运行三组双机矩阵（预留 12、固定结算 12、恢复 14 场景），分别通过 5/6/6 个篡改反例；两端各 64 项局部回归，新增 5 项收尾工具回归，默认合计 265 项。11 个 checkpoint 另进程重放及冻结任务/工件/输入/Profile/上限/正常 outcome 连续性通过；明确 v1→v2 政策版本变化和各自独立资产供给。正式对象/完整终态故障矩阵/真实支付及 OQ-10/Gate 不变。下一轮建议先整理正式对象与接口迁移缺口，不继续扩大定价/支付范围；维护入口见 [交接](../testing/FUNDING-WORK3-MAINTENANCE.md)。

## 2026-10-24 正式对象迁移缺口清单（规划草案）

按第三项收尾建议，[迁移缺口清单](formal-object-migration.md)把 Work 1–3 的 19 类实验替身逐项对应到正式对象，写出缺口、拒绝条件与验收条件，并列出 8 个跨对象结构性缺口（如两条启动授权路径、多套事件流、三种 CBOR 规则、政策未进入 Receipt、付款不以终态为前提）和 6 个待决问题。它是非规范的工程规划，未实现任何对象，SemanticStatus、OQ 与 Gate 状态不变。

## 2026-10-26 原定第四项第一片：B/Q 反例与模型边界

本节记录原定第四项 B/Q 研究。[BQ-W4-S1](../06-research/bq-boundaries-slice1.md)现已实现八个精确小总体见证：能力/实际票数、Sybil 观测等价、共同错误、响应过滤、能力依赖排序、Q 均值/尾部、域漂移及 Q 失真下预算失败。新增 11 项局部回归；默认合计 276 项。对照含 55 组有效 null 枚举、6 行能力反例闭式对拍与 11 条活性 DP 曲线，旧数学内核不变。本片是本地模型证据，不建立实际 B/Q、不运行双机矩阵、不关闭 G1/G2/OQ 或启用 bounded；下一片研究适用域、真值标签、覆盖率校准和敏感性，不阻塞 RIR/运行时。

## 2026-10-26 原定第四项第二片：校准与敏感性

[BQ-W4-S2](../06-research/bq-calibration-slice2.md)交付固定样本、独立真值/同适用域的任务级 Q 精确阈值检验，区分 α/δQ/δL，并对固定候选家族作保守多重控制。新增 14 项回归、默认合计 290 项；四项 CLI 非法输入正确拒绝。合成零失败样例中，α=δQ=1/20 时单 Q 最小 59 个样本、三 Q Bonferroni 方案最小 80 个；五组敏感性覆盖漏计能力、支持损失、共同尾部、外生 TV 界和 20 点未来参数/预算网格。声明/哈希不建立 iid 或真值，全部样例为人工模型，不是实际 B/Q 校准或双机部署证据，不启用 bounded，不变更 OQ/Gate。下一片整理部署证据与降级/禁用条件。

## 2026-10-26 原定第四项第三片：部署证据与失效边界

[BQ-W4-S3](../06-research/bq-readiness-slice3.md)完成 14 项 A/B/C/D 证据清单和非权威审阅模型，12 个 inventory、8 个创建前选择、19 个 lifecycle 投影；新增 18 项回归、默认合计 308 项。四个 CLI 负向输入拒绝且不生成报告。明确降级只在创建前按显式边/Requester 授权/完整失败原因覆盖选择；同 Receipt 不换 Profile，终态不改判；PB 冻结后未 draw 也不许重冻，安全撤销、LIVENESS mapping、普通到期与来源 unknown 分开。研究正例仅为假定来源下的 REVIEW 候选；当前项目正式部署证据不足，不启用 bounded，也不把旧实验当成正式 audit-only conformance。相关 OQ/Gate/资格保持原状，下一步为三片研究统一收尾。

## 2026-10-26 原定第四项三片统一收尾

[BQ-WORK4 收尾](../testing/BQ-WORK4-CLOSEOUT-20261026.md)完成限定研究与可复现交接：统一入口新算三片、锁定 25 个源码/报告/旧工件并核对跨片分数、Q 样本门槛与未获准入边界；另进程 verify 在临时目录重算，四项 CLI 篡改控制正确拒绝。新增 5 项收尾回归，默认 313 项。现实 B/Q、正式来源/五相位、部署 assurance、OQ/Gate/资格未改变。下一步可继续不依赖 B/Q 的 RIR/运行时，或为固定任务部署取得独立真值/校准/能力全集依据；命令见[维护入口](../testing/BQ-WORK4-MAINTENANCE.md)。

## 2026-10-26 FM-F0 路线收口

在 B/Q 合并后的 main 上完成 FM 命名整理、维护者接受 D-1～D-6、audit-only/EligibilitySnapshot 与结算前提修正。旧迁移草案 stash 原样保留；[FM-F0 交接记录](../testing/FORMAL-MIGRATION-F0-20261026.md)区分路线、字段、实现和部署四层。下一次直接实施 FM-S1a；不新增研究阶段，不改变旧实验或规范已有终态优先序。

## 2026-10-28 FM-S1a：共享编码与最小角色签名

[本轮报告](../testing/FM-S1A-20261028.md)记录 Python/Rust 独立规范字节、Schema View、摘要、最小测试身份及 RSA 精确签名输入；89 固定向量（16 正例、73 负例），两物理主机各 179 项对拍与临时新密钥签署通过。增加 10 项默认回归；这是候选测试合约的局部实现，官方 PrincipalRecord/PrincipalRef、完整 ENUM slot/import、密钥生命周期、持久重放消费及后续对象仍未完成。P0-1B 3/19/97、ADR-0006 PROPOSED、各 Gate 与主网资格不变；下一片 FM-S1b。

## 2026-10-28 FM-S1b：政策、费用矩阵与 Receipt 候选合约

[本轮报告](../testing/FM-S1B-20261028.md)记录政策先于 Receipt 的无环绑定、111 费用格、Logical 输入/执行引用和 Requester 签名。两语言/两主机各 196 项对拍，增加 12 项默认回归；完整本地回归含 S1a/原 Claim 编码与 sanitizer。报价无副作用，不是终态或结算权利；组件字节只做来源/摘要绑定。官方对象/注册、非主网接口、RIR/runtime conformance、真实授权/资金/暴露/事件仍待后续实现；P0-1B 3/19/97、ADR-0006 PROPOSED、OQ/Gate/主网资格不变。下一片 FM-S2。

## 2026-10-28 RIR 独立 stats-core

[本轮报告](../testing/RIR-INDEPENDENT-CORE-20261028.md)记录新 Rust 原始外壳入口、受限 Wasm canonical/type 检查、RPR 支持声明与独立结果 CBOR/SHA。38 固定向量、两端各 161 项复核，包括无 Python/源码运行、四类拒绝码、重验证分歧、宿主故障、超 1 MiB 输出。旧 executor/编译探针取证源码保持原字节。完整七阶段/指令集/资源故障、正式 ReceiptID 与 ADR-0006 接受仍未完成；MG-01/02、P0-1B/G2 和生产准入不关闭。下一步优先补全量 conformance，FM-S2 的结构开发不因此等于正式执行已准入。

## 2026-10-31 FM-S2 限定集成（补齐历史索引）

[原报告](../testing/FM-S2-20261031.md)记录 17 场景与 60 事件的原双机证据；这是原轮次的索引补记，不是本次新增执行。2026-11-05 的回归与修复单列[本轮记录](../testing/AUDIT-FIXES-20261105.md)。
