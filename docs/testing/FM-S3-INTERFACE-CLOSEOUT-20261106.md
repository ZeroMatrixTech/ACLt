# FM-S3 接口规范切片收尾

2026-11-06。本报告记录 FM-S3 接口规范切片的四项交付：无 claim 编码、无 Snapshot Phase B、结果接纳时点与预算、非主网部署边界均完成草案与局部验证；P0-1B 119 条 Type A 当前为 3 implemented / 24 partial / 92 not implemented。基线 `3275a63` 加本轮规范草案与局部实现；范围是推进列表第一项的规范、向量和局部校验，正式部署和 P0-1B 全量验收分别记录。[ADR-0008](../05-decisions/ADR-0008-fm-s3-interface-decisions.md)

| 切片 | 草案与局部验证 | 后续验收 |
|---|---|---|
| 无 claim 编码 | Profile schema v2 的 audit 方法省略 claim 键。独立摘要域，11 个字段投影字节向量与 v2 Schema View 骨架。既有 v1 绑定按原版本复核。[向量](../../tests/verification_profile/codec/profile-v2-claim-presence.json) | 完整 VerifiedClaimSpec、ContentMap 摘要与注册接线。 |
| 无 Snapshot Phase B | 四条转换，按 Receipt 绑定启动事实和已提交判决。运行中到终态检查启动的严格因果先行。[向量](../../tests/verification_profile/test_phase_b.py) | 正式事件来源、完整 Phase B 信封与日志忠实性。 |
| 结果接纳时点与预算 | 权威验证完成时点、严格期限、增量预算、重传与原子提交。S3 候选权威复用预算检查。边界按事件 DAG 因果序归因。[向量](../../tests/verification_profile/test_admission.py) | 可耗尽预算的权威事件、正式时钟和完整 Phase D。 |
| 非主网部署边界 | 独立的带 tag 声明、带外 pin、来源及资金额度。§9.2.2 描述 Intent/Receipt 和 I/F/B/D 接线。局部守卫覆盖跨部署替换、时窗、撤销与非主网终态约束。[向量](../../tests/verification_profile/test_deployment.py) | 独立评审新版信封、正式 wire、来源认证、撤销证明及准入。 |

P0-1B 119 条 Type A 当前为 **3 implemented / 24 partial / 92 not implemented**。局部证据登记在 SV-30、SV-93/94/105、SV-112、SV-117。覆盖表按规则记录，正式 Phase B/D、SV-100 的接口行为与非主网准入各有独立验收门槛。[覆盖登记](../../schemas/verification-profile/coverage.json)

局部 guard 接收已解码、已绑定或由权威显式提供的事实。它们的成功结果不能代替来源认证和完整相位验证。首轮 S3 候选双机证据仍以原运行摘要为准。[双机候选收尾](FM-S3-CLOSEOUT-20261106.md)
