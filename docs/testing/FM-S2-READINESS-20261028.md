# FM-S2 前置收口：保留证据、ADR 分层评审与 audit 依赖

日期：2026-10-28；基线 `d669b02`。本轮只完成已授权的三项收口，不实现 FM-S2 或新增协议接受。

## 已交付

1. [三轮机器摘要与校验说明](MIGRATION-EVIDENCE-20261028.md)：补齐 FM-S1a、FM-S1b、RIR 核心的源码 revision/SHA、A/B 报告投影、工具环境、计数与实际存在的结果哈希。精确对照 #60/#61/#62 的 14/19/19 个源码输入，并从三个原始 revision 在本地临时目录重放；179/196/161 项计数与保留报告一致。RIR 完整 case records 的 SHA 重新核对为 `5a0e6d478892167a0ee80fdaaf1f68041f9d5edbb8c0ab700615778320c42034`。FM 原报告没有整轮结果 hash，不补造。
2. [ADR-0006 分层评审](../05-decisions/reviews/REVIEW-20261028-layered.md)：区分路线已接受、具体规则仍候选、局部实现与正式准入；逐项核对 §13 并列出六个规则包。尤其工件 pin 分歧不等于同一工件的 validator 语义分歧。未擅自将 §3–9 接受，也未改写原 §11/§13 条件。
3. [FM-S3 audit 依赖](../07-roadmap/fm-s3-audit-dependencies.md)：机器清单核对全部 119 Type A、6 Type B、原作废/延期项和额外 D-08-c。84 个 Type A 仍是公共/方法依赖，35 个由显式限定功能守卫拒绝；并非实现 84 个新规则或关闭 35 个通用规则。类型 B 忠实性保持集成审计义务。包、主责、前置与计划文件列明，验收均 PLANNED_NOT_RUN。

新增四个待审接口记录：⊥ 的 canonical wire、audit 无 EligibilitySnapshot 的 Phase B 路径、非主网 assurance、权威履约/预算/期限来源。它们阻止正式接口被静默简化，不阻止明确标注的候选限定测试。

## 验证和留存

新增 12 个有效反例/一致性回归，覆盖重新计算自校验值后的未知字段/路径越界/跨端不一致、捏造 FM result hash、真实源码 blob、RIR 全记录重放 hash 与依赖清单遗漏/计数/类型边界。本轮机器摘要是原双机证据的恢复，三个 replay 是新的本地执行；没有新 SSH/双机运行、安装软件、复制凭据或修改账本。原始材料和首次开发期比较错误保留于操作者 `<EVIDENCE_ROOT>/fm-s2-readiness-20261028/`。

默认校验器只做 metadata/依赖检查；显式 --repository 校验原始 Git 源码，--replay 才执行旧 driver。NOT_RUN 不可当成 PASS。完整 `make test` 退出为零：默认检查 359 项（原 347 + 新校验器 12），原 Claim/FM/RIR 对拍、state3/多节点/权威本地测试及 20 次 sanitizer 检查通过。源码包与摘要校验值另行核对。校验值不是认证签名、独立审计或物理/统计独立证明。

## 当前工作边界

下一主线为 FM-S2 固定 stats-int-v1/工件和显式 RPR 范围下的限定测试集成：唯一 Lease/epoch、原子资金+暴露预留、统一事件与双机故障矩阵。RIR 优先补该路径实际触及的拒绝/执行缺口，其余全量 conformance 保留后续门槛。

正式对象/非主网接口与运行准入仍未接受；P0-1B 3/19/97、ADR-0006 具体规则候选、所有 OQ/Gate/主网资格不升级。本轮也不替维护者决定 DIRECT_VERIFIED 的 V1 范围，不重写已有 squash 历史。状态页只更新当前入口，避免再追加大段历史记录。
