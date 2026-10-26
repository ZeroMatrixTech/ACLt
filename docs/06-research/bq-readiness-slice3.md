# B/Q 研究第三片：部署证据、减权与失效边界

日期：2026-10-26；工程标识 `BQ-W4-S3`。接续[反例边界](bq-boundaries-slice1.md)与[校准研究](bq-calibration-slice2.md)。
**本片完成证据清单、只读审阅模型、创建前降级条件和阶段化失效投影；未启用任何能力，也未建立实际部署 B/Q。**

## 1. 权威与完成边界

现行权威是 [ADR-0005](../05-decisions/ADR-0005-engineering-assumptions-and-mainnet-assurance.md)、[VerificationProfile 规范](../03-protocol/verification-profile-schema.md)的 D-04/06/07、MAP-1～8、LP、AR-1～5、AS-3、PB-9、§11.3/11.4 与[不变量](../01-requirements/invariants.md)。本片不新增 Principal、协议对象/终态、SemanticStatus、capability disposition 或自动降级触发条件。

研究实现 [readiness.py](../../tools/bq_boundaries/readiness.py)只消费显式输入，在三个研究标签之间给出**未来准入审阅候选上限**：

| 研究标签 | 含义 | 不代表 |
|---|---|---|
| BOUNDED_REVIEW_CANDIDATE | 在全部来源被假定有效的模型中，可提交 bounded 准入审阅 | ENABLED、完整 conformance 或可输出 TRUSTED |
| AUDIT_ONLY_REVIEW_CANDIDATE | 审计执行的共同前提被假定满足，但 bounded 前提不足；可另行审查 audit-only | 当前 Receipt 已降级、自动生成合法 audit Profile |
| NO_REEXEC_REVIEW_CANDIDATE | 当前材料连共同合约/日志/资源/assurance 前提也未建立 | 关闭已有实验进程、禁止本地模型研究、撤销用户已有实验授权 |

这些标签、research causes 和 evidence state 只是本地研究字段，不是正式 CauseSet、EffectiveVerdict 或 runtime capability。所有输出固定 `automatic_deployment_eligibility=false`、`writes_runtime_state=false`、`formal_phase_validator_implemented=false`。有正例的 inventory 明确为 synthetic-review，其“已有效”是人工 stipulation，未验证签名、注册、来源、设备或部署。

## 2. 14 项证据与来源要求

表中 A/B/C/D 是 ADR-0005 的主要证据层，用于本清单分工；不更改规范 Type A/Type B 分类。每个来源都须绑定内容/版本、原责任方、scope、有效期与撤销/不可达处置。研究文件中的 digest、来源标签和 tick 仅表达这些输入位置，不证明它们真实。

| requirement_id | 层 | 所需证据与主要 owner | 缺失后的审阅边界 |
|---|---|---|---|
| contract_schema_registry | A | 版本、完整 schema/编码、注册/引用与规则合约；protocol §3、Phase R/I/F | 无正式 reexec 候选 |
| runtime_conformance | C | 部署所用 RIR/RPR/validator 与审查版本实际相符，配套 conformance；MAP-5 | 同上 |
| lease_scope_binding | C | Receipt/active Lease 派生 capability 与真实执行 scope；ADR-0005 §2.7 | 同上 |
| log_and_status_sources | C | 批准日志、finalized/checkpoint/inclusion/consistency 与显式状态来源；EF-6/7、AS-3 | 同上；未知不能伪造 VALID |
| bounded_consumption_and_loss | D | 任务/Provider/簇/窗口/全局暴露、资金、尝试、期限与绝对损失边界；INV-09/10 | 同上；audit 也不允许无界消耗 |
| frozen_policy | A | 结果出现前冻结 Profile/选择/费用/限制；D-04、INV-01/12 | 同上 |
| support_capability_bound | C | A⁻ 集合、允许策略与 B 外生依据、误簇/共因与适用域；AR-2/3/5、SC-2 | 不形成 bounded 候选；不是票数自证 |
| correctness_bridge | C | 任务语义/验证器对错误候选支持能力的忠实关系；AR-2、MAP-5 | 同上 |
| population_binding | A | G、总体/簇映射、Snapshot/Receipt/随机性引用和因果绑定；PB-1～9 | 同上，来源忠实性仍另需 C 层日志 |
| randomness_slot_accounting | C | 排列来源、抗预知/偏置、固定 slot 与缺失处理、无过滤补抽；AR-2 | 同上 |
| q_truth_calibration | C | 独立真值、同任务域/Profile/资源/期限、任务单位与 δQ；LP-1/4/5 | 同上，不接受 synthetic 通过数作真实 Q |
| calibration_confidence_accounting | B | 第二片有限样本路线的 α、预登记家族/固定样本、选择误差及外推限制 | 该研究校准路线不足；不是新增协议字段或所有可能 Q 证明的通用规则 |
| assurance_components_revocation | D | 官方网络/版本/窗口、组件/reducer/capability contract、风险接受与撤销渠道；MAP-1/2/3/8 | 共同部署前提缺失，audit 也不能借用失效的全局 assurance |
| exact_dp_budget | B | 0≤B<Q≤G、Δmin、冻结 mixture、精确 DP、Nrequired≤Nmax；SV-10/11、LP-2/3 | 不形成 bounded 候选；不可事后重参数化 |

研究数值检查限定 G≤12、边界分量 π(Q)=1 和显式整数预算；不是完整 P0-1B Profile parser。scope 用摘要相等作人工夹具比较，不替代正式 ScopeContains。窗口采用规范半开语义，时间是调用方提供的逻辑 tick；没有读取或认证现实时间。

### 当前项目清单的解释

[project-gaps.json](../../tests/bq_readiness/fixtures/project-gaps.json)登记正式部署要求尚未建立；其中六个 requirement 关联五份旧实验/数学材料的实际摘要，索引见[证据路径](../../tests/bq_readiness/fixtures/project-evidence-index.json)。它们可证明有限工程进展，但没有被当成正式部署来源或注册审核。已保存的第一片、第二片、Work 1–3 证据不因本片而失效。

当前结果为 **NO_REEXEC_REVIEW_CANDIDATE**：正式合约、真实 runtime/日志/状态/能力绑定及部署 assurance 都还不足，尤其 B 没有现实全集依据、Q 仍只有人工研究样例。它不是对现有实验入口执行禁用；bounded 尚未获启用，而“已有诊断实验可继续”也不能改写为正式 REEXEC_AUDIT_ONLY 已合规。

## 3. 创建期选择：不是所有不足都能自动降级

D-06 的单一选择流程在 ReceiptID 计算前执行；降级 slot 必须有来源/目标版本与 digest、注册的 AUTO_DECIDABLE WeakeningEdge、Requester 授权、目标适用性/准入，且**源 slot 全部失败原因均在 enabling_triggers 内**。本片只投影 bounded→audit 这条边的约束，不实现完整 ordered slots、注册签名、Phase I/F transcript 或生成 ReceiptID。

§9.3 的自动触发集合仍只含：

1. SUPPORT_CAPABILITY_BOUND_UNAVAILABLE：所指 B 假设 scope/window 不适用（AR-3、SV-12I）。
2. POPULATION_TOO_SMALL：规范所述 G<Q 或 Nrequired>Nmax（LP-3）；注册期已应检查结构合法性。
3. CALIBRATION_OUT_OF_SCOPE：LP-4 的 scope 检查失败。

“B 根本没建立”“α 未控制”“assurance 渠道不可达”“合约版本错了”不是任意转译成这三个触发的许可。research causes 不自动等于正式 failure_reasons。B≥Q 的无效 Profile 不能伪装成一个通过注册的合法 source slot，再靠宽泛降级吞掉错误。

| 投影场景 | 结果 |
|---|---|
| 创建前，授权/显式边/摘要/完整原因覆盖/目标 gate 均满足（全为假定值） | AUDIT_SLOT_REVIEW_CANDIDATE；仍不执行创建 |
| 无授权、ATTESTED 边、摘要错、目标不适用/禁用 | NO_AUTOMATIC_FALLBACK |
| 允许的 B scope/window 触发同时伴随 CONTRACT_MISMATCH | 同上，不能只保留有利原因 |
| Receipt 已存在，即使 PRE_FREEZE、尚未首次 draw | 同上；同一 Receipt 不换 Profile |
| 首次 draw 后出现类似原因 | 失效处理，不能切到 audit-only 或改 B/Q/总体/预算 |

可在新 Intent 下另行准备 audit-only 候选，但不改写旧 Receipt，不把旧运行证据重用为新模型的采样。

## 4. 失效、撤销与期限

### PB-9 的四阶段边界

| 原阶段 | population binding 失败后的投影 |
|---|---|
| PRE_FREEZE | 拒绝当前 Phase B 操作，不产生新的 Snapshot；不凭此构造终态 |
| FROZEN_PRE_DRAW | 作废已冻结 Snapshot、阻止首次 draw；走 VERIFICATION_INVALIDATING→UNRESOLVED，且该 Receipt 禁止重新冻结 |
| RUNNING | VERIFICATION_INVALIDATING，P1 在 ACCEPT 前；按已接受规则导向 UNRESOLVED |
| TERMINAL | 不改终态，只走 §11.4 的资格更新审阅 |

“未 draw 可以重新挑总体”并不安全：冻结的总体构成本身已可观察。研究模型保留这一拒绝路径，不把无抽样记录当作重新冻结的许可。

### 安全假设、活性假设与未知来源不能混用

- **SAFETY_CRITICAL 撤销**：before_verification=BLOCK_ADMISSION，during_verification=VERIFICATION_INVALIDATING，after_terminal=QUALIFY_REVOKED（AR-1）。SOURCE 的 kernel 恰好达到接受阈值也不能绕过 P1。
- **CALIBRATION/LIVENESS 撤销**：使用该 Profile 冻结的 LIVENESS mapping；不能把所有 Q 问题强行按 SAFETY_CRITICAL 的默认覆盖。规范可表达 PROCEED，但这不证明原活性保证仍适用；应审查活性 claim，不能改 B/Q 或动态扩大预算。研究夹具明确传入 mapping，不设置隐藏默认。
- **渠道不可达/来源未知**：AS-3 的失败路径不产生假设 verdict，不猜 VALID，也不把未知直接当作证据已撤销；运行中 fail closed。终态后记录来源失败，不能仅凭不可达撤销旧 qualification。
- **窗口自然结束**：当前判断时已过有效期不能用于新的 bounded 判断；运行中失去必要安全前提按失效处理。若证据在原 Decision 发出时有效，随后普通到期本身不证明当时前提失效，不自动追溯撤销已终态 Decision。明确撤销某个证据版本与“现在过期”是不同事实。
- **终态已提交**：只允许追加、单调弱化的 qualification 更新，保留原终态/绑定证据版本；本片的 hint 不是已完成的 P0-5 传播、结算追回或新 EventRecord。

所有 lifecycle 输出都禁止授权重算 guest、改 Profile、重参数化或发出新的 TRUSTED。真正终态必须由完整 Phase D 和合法 finalized 事件提交；研究提示不能越过日志/资金/权限边界。

## 5. 证据失效与恢复交接清单

| 触发/信号 | 应保存 | 可以怎样继续 | 不能怎样继续 |
|---|---|---|---|
| B/Bridge 被撤销或适用域变化 | 原假设/evidence 版本、scope/window、原 Snapshot/原因集合、撤销源与事件 | 新请求在预声明选择合约下审查；进行中沿冻结失效映射 | 自选更宽 B、删掉共同原因、把旧结果变成新总体票 |
| Q 校准不匹配、漂移或 α/任务单位失真 | 数据/真值/预登记与误差预算、受影响声明、冻结 mapping | 撤下不再支持的活性保证并按冻结规则处置，重做未来校准 | 合成通过替代真值、事后增加样本直至过关 |
| 日志/状态/撤销源不可达或 checkpoint 不可信 | 错误、最后已认证锚点、原权利与 unknown 状态 | 恢复后验证来源一致性，再走原权威/规则 | 从本地缓存猜有效、自动退款/付款、开新 attempt |
| 时间窗到期或预算不足 | 绑定时间来源/窗口、DP 与原消费账 | 拒绝新准入/按原规则提交准确终态 | 在同一 Receipt 放宽窗口、忽略 Nmax |
| 发现新漏簇/共因 | 原映射、关联事实、B/Q/余量和受影响版本 | future 新 Profile/assurance 经 conformance/公告窗口审查 | 维护者改当次票权、个案终态或已绑定 disposition |

恢复后也不自动升权：MAP-3 的新版本/公告与 conformance 规则仍需满足；既有 Receipt 通过 required assumption 撤销减权，不增设可变“当前 disposition”第二权威。所有 operation、核验责任、时间来源与撤销源需落入后续正式实现，不由本研究工具代签。

## 6. 实际检查与复现

- 14 项清单、12 个 inventory 情形、8 个创建前选择情形、19 个生命周期投影；人工完整正例仅是 REVIEW 候选，当前项目清单无正式准入候选。
- 18 项新增回归覆盖共同前提/每个 bounded 缺项、合成 Q、scope/window/网络、数值/DP、多原因顺序不变、终态保留、创建期授权与运行中拒绝、LIVENESS mapping、来源 unknown 与报告保护。
- 四个实际 CLI 负向输入：伪造项目通过状态、重复 requirement、未知 ENABLED 状态、旧证据摘要漂移；均拒绝且不产生成功报告。JSON 重复键/浮点另有回归。
- 代码、前两片及旧数学模型原字节保留；没有网络、真实来源认证或双机故障实验。主机独立假设不因此升级为统计独立。

```sh
make check-bq-readiness
make test-bq-readiness BQ_READINESS_REPORT=/existing-parent/new-report.json
python3 -B scripts/check-bq-readiness.py \
  --inventory tests/bq_readiness/fixtures/project-gaps.json \
  --report /existing-parent/new-report.json
```

报告必须新建，含输入、11 个源码/夹具文件和五份项目实验材料的 pin；父目录须存在。已有报告拒绝覆盖。输出 PASS 表示检查流程重现，不表示 evidence 被认证或能力启用。[机器结果](../testing/bq-readiness-slice3-20261026.json)与[运行记录](../testing/BQ-READINESS-SLICE3-20261026.md)区分人工夹具、真实存在但限域的旧工件和未建立的部署事实。

## 7. 交付与后续

第三片完成的是研究证据→建议→失效边界的可复现映射，非完整生产 gate。B/Q 现实来源、正式对象/五相位实现、主网 assurance、正式终态/撤销日志及独立外审仍缺；OQ/Gate/SemanticStatus 不改变。

下一步可以统一收尾三片：固定相同源码与引用，汇总反例、条件校准、降级/禁用边界及剩余部署证据，明确本轮研究结论。它不阻塞不依赖 B/Q 的 RIR/运行时实现，也不把 ADR-0007 的正式对象迁移候选误算作本项研究。
