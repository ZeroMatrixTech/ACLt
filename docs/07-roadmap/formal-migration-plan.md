# 正式对象迁移实施入口（FM）

日期：2026-10-26；基线 `f5f415f7c65952adba01f7b0c9f21d554b14c264`（B/Q PR #58 已合并）。

路线决定的唯一来源是 [ADR-0007](../05-decisions/ADR-0007-formal-object-migration-foundation.md) §2：D-1～D-6 已接受；本页只列实施顺序和验收，不复制六项选择。对象差距见[迁移清单](formal-object-migration.md)，机器关系见[追踪表](formal-migration-traceability.json)。FM 不是 BQ-WORK4，也不是新的 ProtocolVersion。

## 当前交接

2026-10-31 [FM-S2 限定测试集成](../testing/FM-S2-20261031.md)完成，接通单权威 Lease/epoch、资金与五维暴露原子预留、持久 intent/唯一 Attempt、统一事件/签名 checkpoint 与公开重放；17 个真实双机场景通过。限定候选命名域内运行，官方 schema/非主网 assurance/完整 RPR 尚未准入。到期 FENCE 释放暴露但保持测试资金，不能提前模拟 FM-S3 的终态/退款。

前置的 [FM-S3a 结果接入的局部切片](../testing/FM-S3A-RESULTS-20261105.md)：新候选 Audit 合约进入新 Receipt，签名结果对照 S2 消费日志纯重放。后续接纳、判决和账务的证据见下列双机收尾。

首轮候选 FM-S3 已完成 [双机验收与总体收尾](../testing/FM-S3-CLOSEOUT-20261106.md)。正式接口和准入按收尾记录中的门槛独立验收。

实施范围 **FM-S3 限定 audit-only 结果/显式求值/判决/权利与恢复**，依赖按 [audit 清单](fm-s3-audit-dependencies.md)处理。[ADR-0008](../05-decisions/ADR-0008-fm-s3-interface-decisions.md) 已接受首轮候选接口路线，精确合约与正式接口验收仍按切片推进；固定 raw-artifact Rust 只优先补实际路径缺口，完整 conformance 保留独立门槛。此前 FM-S1a/S1b 与[前置收口](../testing/FM-S2-READINESS-20261028.md)保留原报告。P0-1B 81/35/3（2026-11-18）、ADR-0006 PROPOSED、OQ/Gate/主网资格不升级。

## 实施顺序

| 切片 | 内容与退出证据 |
|---|---|
| FM-S1a | 复用现有 P0-1B Python/Rust codec 起点，补齐所需类型、wire/import 边界、规范性拒绝与资源上限；最小 Principal 公钥/角色绑定及测试签名 envelope。以代码、精确字节/签名正负向量和独立两语言对拍收尾 |
| FM-S1b | 最小可达终态/费用矩阵、Funding/Settlement policy、LogicalObject/执行引用与 Receipt schema/摘要单向绑定。政策先冻结，再由 Receipt 引用，不形成哈希环 |
| FM-S2 | 新部署中 Receipt→合法 Assignment→资金/暴露原子预留→Provider 接受 Lease→capability/Attempt→统一事件；替换两条旧启动权威，跑对应真实双机集成/故障矩阵 |
| FM-S3 | 签名 ResultSubmission→audit-only 证据/显式求值→唯一准确终态→分项权利/退款→恢复。无 B/Q/EligibilitySnapshot 依赖，不以比较相同直接付款；不改判或重复分配 |
| RIR 独立线 | MG-01/02 按 ADR-0006 §13 补独立外壳/validator/摘要与完整 conformance；不由 FM 的局部成功顺带关闭 |

## FM-S1a 的具体开工条件与交付

开工依据：六项路线已接受；已有 [Python codec](../../tools/verification_profile/codec.py)、[Rust codec/独立 SHA/NFC](../../tools/verification_profile/rust/README.md)、[106 条固定向量和差分入口](../testing/CLAIM-CODEC-20261023.md)。这些是有限候选实现，不能直接改名成通用正式对象实现。

本片范围限于以下各项，Receipt/资金转移/Lease/真实密钥生命周期不提前进入：

1. 在现有规范 owner 下核对 primitive、整数、容器、Rational/SemVer、ENUM、Schema View 和必要导入的封闭合约；明确哪些规则得到完整支持、哪些仍 partial，不按通过测试数量抬高覆盖率。
2. 精确定义最小 Principal 公钥绑定和 Requester/Provider 签署责任。日志实现密钥独立引用，不新增协议 Principal。私钥不入库，未知 key/role/network/version 必须拒绝。
3. 冻结测试签名 suite 的确切 padding/参数、hash、key/signature 编码、尺寸限制、签名输入、协议/对象/网络/角色上下文与摘要域。不能仅写 RSA/SHA256；RSA 路线接受不预先决定这些字节。
4. Python/Rust 独立编解码和摘要实现逐字节一致，不调用 Python 替 Rust 预验证；明确签名适配共享的 OpenSSL 依赖不算第二份独立密码学实现。
5. 正例包含合法重绑定/重新签署后的成功；负例覆盖非最短/重复/未知/溢出/非 NFC、未知 import、错 key/role/network/context、篡改 payload 和重放，不能靠全部拒绝通过。
6. 交付新向量、规范/实现/规则编号映射与局部回归、现有完整检查；必要的双机编码/构建复核明确为该范围，不冒充端到端任务/账务验收。不安装无来源依赖，不迁移旧实验库。

FM-S1a 已形成可审查的[测试合约与精确 suite](../../schemas/formal-migration/README.md)，字节/tag/envelope 仅在该候选测试命名域中固定，不等于官方注册授权。FM-S1a implementation_started=true，limited_slice_complete=true；官方 PrincipalRecord、完整 ENUM slot/import 与下表整条迁移验收仍未完成。

## 各片交付与回归要求

沿用原 store 计划的交付义务：每个实现切片附规范/schema/registry 同步清单、golden/negative vectors、独立实现差分与拒绝前后业务状态不变检查；需要集成的阶段附真实双机驱动和新报告，保留失败证据。纯文档或局部编码阶段的证据范围限于该阶段，双机集成的完成状态由对应阶段的真实运行单独证明。

FM-S3 应以新对象重跑原授权提交/重放 12 场景、结算 12 场景及恢复 14 场景所对应的矩阵，再补 deadline、旧 epoch、终态竞争与拒绝状态不变；历史场景数是回归基线，不是本轮已通过记录。通用 R-G1～6、A-G1～6 仍由迁移清单约束。

## 迁移验收编号

| ID | 迁移完成时要证明的性质 | 候选路径证据 |
|---|---|---|
| FM-A01 | 正式入口拒绝旧实验 schema/ID，业务状态不变 | 候选 S2 拒绝旧操作、未知字段和错网络/Receipt，拒绝前后业务状态核对。 [FM-S2-20261031](../testing/FM-S2-20261031.md) |
| FM-A02 | 两语言规范编码/未知字段/数值/资源拒绝及独立字节对拍 | Python/Rust 字节和签名对拍，资源拒绝，独立受限 RIR 核心。 [FM-S1A-20261028](../testing/FM-S1A-20261028.md)、[FM-S1B-20261028](../testing/FM-S1B-20261028.md)、[RIR-INDEPENDENT-CORE-20261028](../testing/RIR-INDEPENDENT-CORE-20261028.md) |
| FM-A03 | 版本、政策、输入、资源或语义变化不沿用旧承诺/授权 | 政策与执行组件绑定 Receipt，变化后原承诺与签名不可复用。 [FM-S1B-20261028](../testing/FM-S1B-20261028.md)、[FM-S2-20261031](../testing/FM-S2-20261031.md) |
| FM-A04 | 政策→Receipt 与其他因果/摘要依赖无环 | 候选政策先冻结，Receipt 单向引用，拒绝反向摘要依赖。 [FM-S1B-20261028](../testing/FM-S1B-20261028.md) |
| FM-A05 | 角色/密钥/网络/签名责任正确，issuer 不代签 Provider | Requester、Provider 与 issuer 分钥，结果角色/签名错位被拒绝。 [FM-S1A-20261028](../testing/FM-S1A-20261028.md)、[FM-S2-20261031](../testing/FM-S2-20261031.md)、[FM-S3-CLOSEOUT-20261106](../testing/FM-S3-CLOSEOUT-20261106.md) |
| FM-A06 | 唯一 Lease、两类原子预留、并发/超额与重复启动拒绝 | 单 Lease，资金与五维暴露原子预留，并发 CONSUME 单一成功，中断后不补算。 [FM-S2-20261031](../testing/FM-S2-20261031.md)、[FM-S3-HISTORICAL-MATRIX-20261106](../testing/FM-S3-HISTORICAL-MATRIX-20261106.md) |
| FM-A07 | 旧 epoch/冲突幂等键不覆盖当前事实或产生新权利 | 旧 epoch 与冲突 nonce 拒绝，原签名请求重放、结果冲突和首次结算竞争保留原事实。 [FM-S2-20261031](../testing/FM-S2-20261031.md)、[FM-S3-CLOSEOUT-20261106](../testing/FM-S3-CLOSEOUT-20261106.md)、[FM-S3-HISTORICAL-MATRIX-20261106](../testing/FM-S3-HISTORICAL-MATRIX-20261106.md) |
| FM-A08 | 方法特定 Profile/证据/求值；audit-only 无 ACCEPT/TRUSTED，无 EligibilitySnapshot | audit-only 配对产生 CONCORDANT/UNRESOLVED，无 claim 与 EligibilitySnapshot 依赖。 [FM-S3-CLOSEOUT-20261106](../testing/FM-S3-CLOSEOUT-20261106.md)、[FM-S3-TERMINALS-20261106](../testing/FM-S3-TERMINALS-20261106.md)、[R12 预验收](../testing/PROFILE-PHASE-D-R12-20261109.md)、[R13 对拍](../testing/PROFILE-PHASE-D-R13-20261110.md)、[R14 注册与信封](../testing/PROFILE-PHASE-D-R14-20261111.md)、[R15 创建绑定](../testing/PROFILE-PHASE-D-R15-20261111.md) |
| FM-A09 | INV-07 五项前提齐全，金额由政策派生，重复请求取原权利 | 已提交终态和冻结政策派生过程费/退款，调用者指定金额/政策/终态被拒，重复取原权利。 [FM-S3-CLOSEOUT-20261106](../testing/FM-S3-CLOSEOUT-20261106.md)、[FM-S3-TERMINALS-20261106](../testing/FM-S3-TERMINALS-20261106.md)、[FM-S3-HISTORICAL-MATRIX-20261106](../testing/FM-S3-HISTORICAL-MATRIX-20261106.md) |
| FM-A10 | 有界 deadline/恢复/unknown，按冻结规则唯一终态，无自动 guest 重试 | 入口未知触发失效，闭合 FAILED、激活时资金边界、期限与持久状态恢复得到双机覆盖。 [FM-S3-TERMINALS-20261106](../testing/FM-S3-TERMINALS-20261106.md)、[FM-S3-HISTORICAL-MATRIX-20261106](../testing/FM-S3-HISTORICAL-MATRIX-20261106.md) |
| FM-A11 | 丢回复/COMMIT 边界/竞争下至多一次与守恒 | 双机丢回复、COMMIT 前后退出、B 屏障首次结算及退款恢复，签名 checkpoint 与守恒核对。 [FM-S3-CLOSEOUT-20261106](../testing/FM-S3-CLOSEOUT-20261106.md)、[FM-S3-TERMINALS-20261106](../testing/FM-S3-TERMINALS-20261106.md)、[FM-S3-HISTORICAL-MATRIX-20261106](../testing/FM-S3-HISTORICAL-MATRIX-20261106.md) |
| FM-A12 | 来源未知/错锚点不驱动新安全终态，合法旧签名不等于新鲜性 | 错锚点/截断快照拒绝，未知启动与自述不驱动 FAILED；公开回放绑定外部 genesis/checkpoint。 [FM-S2-20261031](../testing/FM-S2-20261031.md)、[FM-S3-CLOSEOUT-20261106](../testing/FM-S3-CLOSEOUT-20261106.md)、[FM-S3-TERMINALS-20261106](../testing/FM-S3-TERMINALS-20261106.md) |

候选列对应追踪表中的 `candidate_path_evidence`。正式验收状态仍逐项记录为 `PLANNED_NOT_RUN`。本轮证据归档和回放见 [第四项收尾](../testing/FM-EVIDENCE-CLOSEOUT-20261107.md)。

这些是整条迁移的要求；FM-S1a 一片的验收范围限于该片，全部 FM-A 仍需逐项完成。局部编码对拍不构成完整 RIR/RPR、身份控制独立、B/Q、真实支付、主网资格或 Gate 的替代证据。

## 2026-10-28 FM-S1b 交接

[候选政策/Receipt 合约](../../schemas/formal-migration/policy.md)与代码固定了 111 费用格、单向内容 DAG、Logical 输入与执行组件引用、Requester 签名及正负向量。scope/预算/资源/未知字段/旧引用拒绝，合法重绑定改 Receipt 摘要。费用求值是无副作用的假设计算，不生成终态、权利或资金。FM-S1b limited_slice_complete=true；MG 与 FM-A 整条验收保持未完成。FM-S2 需要审查后落实官方 schema/非主网接口、单一 Lease/epoch、两类原子预留与统一事件，不可仅凭本片 PASS 启用正式准入。

## 2026-10-28 RIR 独立线优先交接

按维护者安排先推进 RIR 独立性。[核心切片报告](../testing/RIR-INDEPENDENT-CORE-20261028.md)已补受限 Rust raw-artifact 入口、独立类型检查和结果编码/摘要。它解除该有限入口的 Python 预验证/后处理依赖，不代表 MG-01/02 全部完成。下一步补完整 validator/指令与边界 conformance、正式 Receipt 身份测试和 ADR-0006 审阅；FM-S2 可开发授权/预留/事件结构，正式执行准入仍等待上述证据和原有字段/部署门槛。
