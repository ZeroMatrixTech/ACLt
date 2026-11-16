# Profile R7：注册、选择与绑定规则集中实现

本次按维护者接受的“13 项基础＋8 项条件扩展”范围实施，基础 13 项与扩展 SV-23 完成、其余 7 项保持 partial；278 条向量在 A/B 两台物理机上通过且结果流一致，完整 `make test` 退出码为 0（602 项 Python 测试）。日期：2026-11-08；基线 main `96ec459`（PR #77），开始时工作区干净；规范、ADR、OQ、Gate 与部署能力保持原状；源码内容以机器摘要、公开源码包和交付清单为准。

## 实际完成范围

- 基础 13 项完成：SV-12R、47、28、45；21、41、53a、53b、87、88；74、85、120。
- 扩展 SV-23 完成：考虑 DEGRADED slot 需要显式 bool 授权，不能强制转换其他类型。
- 扩展另外 7 项保持 partial：SV-12I、14、26、29I、43、55、58。它们已有独立 Python/Rust 组件和边界反例，缺少正式来源与调用接线，不能计为全规则完成。

119 Type A 从 **36/33/50** 变为 **50 implemented / 40 partial / 29 not implemented**。这是规则条目覆盖率，非项目、P0 或 Gate 完成度。新增 Policy、Manifest、WeakeningEdge 三个正式摘要 owner，18 个摘要现在为 **12 implemented / 2 partial / 4 not implemented**。逐项范围和缺口见[机器范围表](PROFILE-SELECTION-R7-20261108.scope.json)；覆盖权威仍是 schema coverage/inventory。

## 对象与规则

注册资产用唯一嵌套 header 与封闭字段；Policy/Edge/Manifest 使用 §17.4 正式 tag/ContentMap，不把身份、版本或自身摘要放进散列。Policy 同时绑定候选、展开结果和耗尽处置，不能由调用者选一个自洽摘要来代替复算。

Expand 按 D-06 候选顺序，以展开位置从 0 编号；每个来源 primary 后紧邻插入其声明的 degraded slot，degraded_from 指向来源位置。CandidateDecl 的 gate 只复制到该候选的 primary，DegradationDecl 没有 gate 字段，插入的 slot 不另行继承或发明 gate。同一 Profile 多次出现仍分别保留 gate，不按 ID 覆盖。gate 在本片仍是锁定 schema 的不透明原子值；本片不执行 GateOk。

每条自动边先解析实际 source/target 与完整快照引用，限定 bounded→audit；排除集只能增加、目标不能产生 claim，任务、constraints、equivalence 必须相同。只实现此冻结自动边，不启用 ATTESTED 或非 audit 执行。检查显式 Profile 对象/摘要/快照一致不等于完整 SchemaValid 或真实注册授权。

SV-28 是纯可考虑状态判断，DEPRECATED/REVOKED 产生不适用结果，不把 Profile 改为非法；SV-45 比较 slot、实际对象与快照中的完整三元身份。SV-12R/47 只验证假设引用和角色，不证明 B/Q 或假设为真。

Manifest 是测试资产，不进入语义 RegistrySnapshot。只检查声明的结构和摘要，不加载 file_digests 路径或认证 vector_sets 内容。相对 `../shared/vector.cbor` 可以作为相对清单数据，不授权文件读取；实际归档/读取工具仍使用各自的目录边界。事件组件覆盖全部十类 kind→subject 矩阵及字段、ID 类型，不代替 frontier 版本、checkpoint/inclusion/finality 或日志来源验证。

## 八项扩展的接口审查

当前冻结 ReceiptIntent 字段没有直接提供 NormalizeDeclaredScope 需要的全部 task/environment/fault_domains/geography，也没有确定 effects/N_max 的完整取值链；ContractTuple 等尚未冻结内部字段的 imports 按规范是不透明原子值，不得猜字段读取。

因此 `applicability-test` 只消费外层适配器显式给出的六维 DeclaredScope、evaluation_instant、N_max、effects、授权与来源失败标签。实现半开时间/版本区间、标量相等、集合方向、空维度拒绝、INFO 排除、两种不同的上限比较，以及混合非触发失败阻止降级。测试降级还要求非空失败事实；正式 FailureReason 到触发条件的投影及来源 slot 已落选证据仍缺。这些字段和原因字符串不是新增正式 wire。

输出 `bound_scope_window_ok` 只表示已编码 scope/window 条件满足，不证明现实 SupportCapabilityBound；`required_draws_within_limit` 只比较 N_required/N_max，不宣称建立活性或总体独立性。所有操作持续 `full_schema_valid=false`、`full_phase_i_replay=false`、`source_authentication=false`、`production_admission=false`；没有 CreateReceipt 或新 FM 任务运行。

## 验证与证据

完整 `make test` 退出码为 0：默认 23 组 577 项（本片新增 24 项）、执行器 25 项，共 **602 项 Python 测试**；20 次 sanitizer 检测、既有 Claim/FM/RIR 对拍通过。R1–R6 的 66/74/104/145/382/122 条结果流 SHA-256 均与历史记录一致；五份归档的 24 套公开快照、249 条事件使用当前实现完整重放通过。

两台物理机分别构建 Rust 并通过 **278 条向量（57 正、221 负）**，源码 pin 和结果流一致，SHA-256 为 `6b5b871d0ecf2ba48a256a216457cf8bd602ac5d810a9eab5b5d2bffdf5ea818`。测试覆盖全部目标规则的正例、缺字段/错类型/未知字段、完整身份替换、生命周期、重复候选各自 gate、slot/来源索引篡改、四项降级条件、三个正式摘要、十类事件 subject，以及半开区间、空维度、集合方向、混合失败、两种阈值和授权 bool。

[机器摘要](PROFILE-SELECTION-R7-20261108.summary.json)保留 A/B 环境、源码 pin、计数、结果和范围表摘要。含逐文件 pin 的[公开最小源码包](public-evidence/PROFILE-SELECTION-R7-source.tar.gz)已在新目录解压、核对并独立构建重放全部 278 条，结果一致。最小包只用于本片对拍，全量本地回归使用完整仓库。

开发初期导入/向量生成检查失败与修复后日志、A/B 原始报告和部署日志、公开包复跑及完整回归日志保留在操作者证据目录。两物理机属有限工程假设，同操作者/LAN/软件及可能共享供电的相关风险仍在；本轮没有新任务协议或故障矩阵运行，SSH 对拍的范围限于本片静态与组件对拍，端到端 FM 验收另行进行。

## 继续推进

下一轮先闭合正式 Intent/ContractTuple 的取值合约、scope normalization、effects/N_max 来源与 FailureReason/predicate/gate 接口，再把本片组件接入完整 ReplayPhaseI。R6 的四项 partial 维持 partial 等级，本片 helper 仅用于本片对拍。Phase B/D、来源忠实性和正式 FM-A 分别验收。新规范字段或语义选择须有明确版本和审查，计数提升不构成新增测试字段的依据。
