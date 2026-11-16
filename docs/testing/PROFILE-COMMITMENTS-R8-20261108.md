# Profile R8：Claim、快照与承诺集中实现

本报告记录 2026-11-08 的 Profile R8 实施与验证，基线为 main `9415fe4`（PR #78），开始时工作区干净。本轮按“最大进度覆盖”合并实施共用承诺/绑定层：119 项 Type A 从 50/40/29 变为 69 implemented / 35 partial / 15 not implemented，完整 `make test` 退出码 0。规范、ADR、OQ、Gate 与部署资格均未改动，R7 的正式输入缺口保留。

## 范围与计数

本轮 19 项转为完成：SV-05/06/09/35/36/44/46/48/49/54b/70/71/78/86a/86b/86c/95/113/114。其中 13 项此前未实现，6 项此前 partial；SV-116 新增为 partial，SV-54a/57 和 R7 的 7 项适用性规则有新证据但继续 partial。

119 Type A 从 **50/40/29 → 69 implemented / 35 partial / 15 not implemented**。18 个摘要 owner 的现行公式、ContentMap 或完整显式输入投影均有实现（此前 12 implemented、2 partial、4 not implemented）；这不是 18 类对象全量类型/来源验收，也不是完整 L2、SchemaValid 或协议验收。逐项计数见[范围表](PROFILE-COMMITMENTS-R8-20261108.scope.json)，权威登记为 schema coverage/inventory。

## 已冻结的组件

- 注册组件复用方法矩阵、假设引用和排除注册表检查，补全方法专用排除、模板映射与状态、binding schema、STATIC 参数逐字节相等，以及 VersionRange 对应 slot 必须 RUNTIME。模板和 Profile 声明用规范 CBOR 比较，避免 Python 的 `True == 1` 混淆原生类型。
- Claim guard 检查完整字段、concrete slot 集合、STATIC 不可替换、双层快照摘要、实际 Receipt/snapshot identity、assurance 边界与方法附加字段。即使攻击者重算所有可见摘要，错误 Receipt、静态值或非 VALID 安全假设仍拒绝。它不执行 method evaluator，不生成或接纳协议 Decision。
- 快照组件按编码字节排序原因，保留所有事实并按默认 `REVOKED > OUT_OF_SCOPE > WINDOW_EXPIRED > VALID` 归约；证据版本和精确非 INFO 角色覆盖单独验证。INVALIDATING 可构造且不要求虚构快照/状态摘要。规范化 sum 的 tag/snapshot/failure wire 仍是适配器边界，SV-54a/57/116 保持 partial。
- 模板、RenderedClaim、AssumptionState、AssumptionStateSnapshot、MainnetAssuranceProfile、DecisionEvaluationInput 补齐剩余六个摘要 owner。模板 value_type/ENUM 数据原样入哈希，不借 L2 摘要通过宣称其 ENUM wire 或值类型语义已冻结。Decision input 绑定七个完整外层字段和内联载荷包装，不承担 SV-115 的方法重放/事实完整性认证。
- 八类版本化对象和四类治理运行期对象集中检查唯一 header 形状、重复身份、无伪 Version 及 runtime ID 投影；具体 runtime alias 不能互换。未知未来类型/版本或来源不在本片通过范围。

归约器执行用本片固定源码摘要的默认参考实现 `acl.reducer.r8-default`，不冒充官方已登记组件；真实 MAP 允许集合、发布/撤销与源日志继续按 SV-117/119 等验收。样本 MAP 仍为 DISABLED；绑定 guard 的成功不改变该处置，也不证明 TRUSTED 正当。

## 候选输入胶囊

[候选合约](../../schemas/verification-profile/admission-input-candidate-r8.json)和 `candidate-input` 操作将 base Intent v1、显式 task/environment/fault/geography、结构化候选 ContractTuple 与 N_max 放在一份独立 TEST 承诺中。scope、effects 和限额只从胶囊派生；其 ContractTuple 必须与 base Intent 的不透明字节逐位一致，不能额外覆盖派生字段。

该操作使用 **`ACLt/TEST/R8/AdmissionInput/1`**，不是新正式 Intent tag，也不解析旧 Intent 中未声明的子字段。旧 `ReceiptIntent/1` 摘要不覆盖胶囊新增字段；因此下一步必须明确正式版本、签名和 Receipt 承诺关系，不能把胶囊仅附在已签名旧 Intent 旁边就当作已授权。N_max 的预算来源、FailureReason/predicate/gate、程序/版本实际绑定也待闭合。R7 的七项仍为 partial，不因候选输入可运行而升格。

NATIVE_CBOR 只用于显式锁定的 R8 原生测试载荷 schema，不在旧入口启用。ENUM 和 sum union 的正式 wire 仍独立评审；Source/registry/log/reducer/authentication 都不由自报数据建立。所有输出为 `full_schema_valid=false`、`full_phase_i_replay=false`、`source_authentication=false`、`production_admission=false`、`protocol_decision_emitted=false`。

## 验证与证据

完整 `make test` 退出码为 0：默认 23 组 610 项（本片新增 33 项），执行器 25 项，共 **635 项 Python 测试**；20 次 sanitizer 检测及既有 Claim/FM/RIR 对拍通过。R1–R7 的 66/74/104/145/382/122/278 条结果流 SHA-256 与历史记录全部一致；五份归档的 24 套公开快照、249 条事件使用当前代码重放通过。

两台物理机各自构建 Rust 并通过 **287 条向量（62 正、225 负）**，源码 pin 与结果流一致，SHA-256 为 `bc7e439353cc6a0f377a81a159a3ef8840c65ef2e9dba2330f3df8eb6c2dedc6`。覆盖三种 Claim 方法/audit 排除、静态值/模板/快照替换、重算摘要后的安全反例、原因并发与编码序、无快照 invalidating、原生 bool/整数区别、四类 runtime alias/八类版本化 wire，以及候选胶囊取值、漂移和限额边界。

[机器摘要](PROFILE-COMMITMENTS-R8-20261108.summary.json)绑定 A/B 环境、源码、计数、范围表与候选合约。含 53 个文件及逐文件 pin 的[公开最小源码包](public-evidence/PROFILE-COMMITMENTS-R8-source.tar.gz)已在全新目录核对、独立构建并重放 287 条，结果一致；635 项全量回归使用完整仓库源码。

开发中测试发现了归约器引用在夹具间共享可变对象的问题，已改成每次构造独立引用并加入防污染回归；原生声明比较也加入 `True` 与整数 `1` 不得混同的反例。初次导入/向量/跨语言/单元失败日志、修复前向量及最终通过日志、A/B 与公开包复跑均保留在操作者证据目录。没有静默改写失败。

双物理机只支持有限工程验证；同操作者、LAN、软件和可能共享供电仍会相关。本轮没有新的任务协议/故障矩阵运行，不证明主网或身份/统计独立性。

最终在 Git 工作区进行交付覆盖检查时，发现基线已跟踪的 `CONTRIBUTORS.md` 未列入 `DELIVERY-SCOPE.json`；已补入顶层交付清单并重新生成清单。该修复只涉及文档交付，不改变上述受测组件与公开最小源码包。

## 后续主线

优先评审候选输入的正式版本/签名承诺与 ENUM/sum wire，再完成真实 NormalizeDeclaredScope、FailureReason/predicate/gate 和完整 I/F/Phase D 重放。完整边界/执行闭合/evaluator/日志认证及正式 FM-A、RIR conformance 按各自证据验收。本片未运行新的任务协议/故障矩阵，P0-1B 与 G0/G2 保持未关闭。
