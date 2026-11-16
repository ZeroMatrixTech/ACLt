# Profile R9：运行期绑定与冻结状态集中实现

本轮按“最大进度覆盖”范围集中完成一个 Phase B 组件包，10 项 Type A 转为完成，367 条向量在 A/B 两台物理主机上通过且结果流 SHA-256 一致，完整 `make test` 退出码为 0（665 项 Python 测试）。日期：2026-11-08；基线 main `d67effc`（PR #79），开始时工作区干净；规范、ADR、OQ、Gate 与部署资格保持原状。

## 范围与计数

119 Type A 从 **69/35/15 → 79 implemented / 34 partial / 6 not implemented**。10 项转为完成：SV-68/77/82/92/93/94/99/105/106/107；SV-69/81 从未实现转为 partial。18 个摘要 owner 保持公式/显式输入投影已实现。逐项前后状态见[范围表](PROFILE-RUNTIME-R9-20261108.scope.json)，权威覆盖与函数/测试指针仍是 schema coverage/inventory。

“完成”指对应 Type A 的显式输入规则组件，不是整个 Phase B 的正式 conformance。EligibilitySnapshot、population_definition、随机性方案仍使用带外 pin 的 TEST import 适配器。SV-69 不能据此证明列出的单位与真实总体定义完整一致；SV-81 不把 opaque TEST 引用相等、有限允许参数集合检查冒充正式版本化随机性合约或承诺 opening 校验，两项继续 partial。

## 已实现的组件

- 七种 payload 的封闭字段和必填 transition；Snapshot freeze 必须带 freeze record。三个无 Snapshot 方法只允许 Lease pre-freeze 与无快照 round 路径，拒绝统计字段及伪造 FROZEN_PRE_DRAW。
- 六维 ActualBoundScope 和非空 fault/geography；每次 Lease/Snapshot 输入均比较全部 safety-critical/liveness 假设。INFO 不参与阻断。显式快照适配器中的每个抽样单位也单独比较 scope，不以总体均值或 declared scope 替代。
- Receipt/Profile/assurance 的完整绑定：外层、前后状态、Receipt 与实际 Profile 引用逐位相等；快照属于同一 Receipt；network 与 assurance identity 不可自选。
- 集群映射引用严格采用 `{id,digest}`，检查 ClusterMappingID，拒绝伪 Version 和跨 ID 域。只允许 CLUSTER_MAPPING_FIX 从无映射变为非空；固定后不能删除或替换。Snapshot 与前后状态及 freeze record 形成同一引用链。
- 冻结参数逐字段等于 Profile，含 G/B/Q/delta_min 和完整 mixture_weights。scope 过滤必须满足 `frozen = candidate − excluded`、excluded 是 candidate 子集，且 kept ID 集合与 Snapshot 完整相等、基数等于 G；重复 sampling ID 不得静默去重。
- 映射固定与冻结事件必须在显式 frontier 的因果祖先中，kind/subject 正确且严格先于关系成立。缺边、有环、错误主体或仅数组顺序先后均不能通过。
- 所有阶段组合均受单调性与 tag/阶段矩阵约束；无快照方法保留唯一启动/终态与严格因果约束。

## 失败后果与准入边界

纯 guard 返回四种后果：PRE_FREEZE 拒绝当前操作；FROZEN_PRE_DRAW 作废快照并禁止重冻；RUNNING 验证作废；TERMINAL 仅允许追加资格说明。它不进行状态写入、撤销、结算或资格追加；真实调用方必须另行原子执行这些后果。重复提供伪造 prior state 的来源忠实性与日志旁路，不由 Type A 向量证明。

[TEST import 合约](../../schemas/verification-profile/runtime-imports-candidate-r9.json)及独立类型表明确适配器边界。外部调用者必须带外提供 schema-lock 和 runtime-contract pin，不得从陌生待验输入现算哈希自授信。示例向量中的 pins 是已冻结测试夹具的复现输入。样本 assurance 仍为 DISABLED；guard 的 `accepted=true` 只表示组件规则成立，不能启用方法、生成 Lease/能力/Receipt/Decision。

CLI：

```sh
python3 -B -m tools.verification_profile.validator INPUT.cbor \
  --runtime-bindings-cbor --schema-lock-sha256 TRUSTED_SCHEMA_PIN \
  --runtime-contract-sha256 TRUSTED_TEST_CONTRACT_PIN
```

语义拒绝会返回非零；`--production` 始终拒绝。原 R1–R8 入口和正式 ReceiptIntent/1 不改。所有结果显式包含 `full_schema_valid=false`、`formal_phase_b_conformance=false`、`source_authentication=false`、`production_admission=false`、`protocol_decision_emitted=false` 和 `state_committed=false`。

## 验证与复现证据

完整 `make test` 退出码 0：默认 23 组 640 项、执行器 25 项，共 **665 项 Python 测试**；本片新增 30 项专项测试，20 次 sanitizer 检测及既有 Claim/FM/RIR 对拍通过。R1–R8 的历史结果流摘要保持原值，五份归档的 24 套公开快照、249 条事件继续用当前代码重放。

两台物理主机各自构建 Rust，并各通过 **367 条向量：33 正、334 负，其中 135 条结构拒绝、199 条语义拒绝**。全部六类 bounded tag 的 16 种阶段组合、三种无快照方法、两个外部 pin、跨 Receipt/身份/映射替换、六维 scope、参数漂移、过滤集合与因果反例均有覆盖。两端受测源码 pins 相同，结果流 SHA-256：

`e22945feb8626a34508b6e817b7038fde1b2fdca4d03f4dbfbe2c5fed58139ae`

[机器摘要](PROFILE-RUNTIME-R9-20261108.summary.json)记录 A/B 版本、源码 pins、计数和范围；含逐文件 SOURCE-PINS 的 [62 文件最小公开源码包](public-evidence/PROFILE-RUNTIME-R9-source.tar.gz)已在全新目录独立构建与重放全部 367 条，源码和结果摘要与 A/B 一致。完整 665 项回归使用完整仓库，公开最小包只承载本片复现，不冒充全仓回归环境。

开发中保留了初始导入类型/向量夹具错误、修正 runtime mapping 引用前的候选向量，以及全仓优化模式门禁失败：新模块初始化断言已改成显式检查。添加公开归档后清单曾过期，已重新生成并完整重跑。最终通过与原始失败日志、首轮及修复后 A/B 证据均留在操作者证据目录，不静默改写。

本轮是编码/纯函数对拍和本地回归，没有新任务协议、真实 Lease 启停或故障矩阵运行。两台物理机仅为有限工程假设；同操作者、LAN、相同软件和可能共享供电不构成统计或身份独立性。

## 后续主线

正式 Intent 版本/签名/Receipt 承诺、ENUM/sum wire 与真实 NormalizeDeclaredScope/FailureReason/predicate/gate 仍需收敛；完整 I/F/D、method evaluator、执行闭合与日志/来源认证继续独立验收。Phase B 运行准入的完成以本片 guard 接入真实服务并原子执行四类后果为前提，该前提尚未满足。P0-1B、G0/G2、FM-A 与 RIR conformance 的关闭由各自的验收决定。
