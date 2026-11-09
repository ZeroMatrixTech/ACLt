# R12 Phase D 候选编码与 FM-A08 预验收

基线为 main `b09705d`。本轮接口见
[Verification Profile §11.3.7](../03-protocol/verification-profile-schema.md#1137-phase-d-候选编码-1r12供接口评审)。
新域绑定部署配置、Receipt、Profile、日志前缀与状态、闭合来源及求值时间。
R11 来源先按旧版验证签名、checkpoint、原判决和结算，再投影到候选字节。
向量与拒绝用例可通过 `make check-phase-d-contract` 重放。

| FM-A08 项 | 候选证据 | 正式验收缺口 |
|---|---|---|
| 方法特定 Profile | 固定 REEXEC_AUDIT_ONLY，R11 只接受固定审计规则 | 正式注册 Profile 与冻结 evaluator 来源 |
| 证据与求值 | 重放同一前缀上的接纳顺序、成本、撤销、期限和授权闭合，再核对新旧终态 | 完整 Phase B/D 信封、正式认证来源、独立实现对拍 |
| 无 ACCEPT/TRUSTED | 冻结条件列表排除 ACCEPT，历史 17 条 Receipt 只有四种过程终态，篡改为 TRUSTED 被拒 | 正式信封及不同调用入口上的同一限制 |
| 无 EligibilitySnapshot 与 claim | 候选输入省略这两个对象，现有 Profile/接纳回归拒绝越界配置 | 正式部署准入证据 |

FM-A08 保持 `PARTIAL_CANDIDATE_EVIDENCE`，正式 `PLANNED_NOT_RUN`。
历史证据继承操作者时钟和测试 observer，资金耗尽证据限 ACTIVATE。工作区统计按
`coverage.json` 校验现行入口的计数，历史报告保留各自时点的计数。

## 复现

- `make check-phase-d-contract` 复核候选固定向量和历史 R11 结果。
- `python3 -B scripts/check-runtime-bindings.py --freeze-vectors /tmp/r9-vectors.json`
  导出原始 R9 JSON，须指定尚不存在的输出路径。生成结果使用历史 SHA-256 固定。
- `make test-runtime-bindings` 运行 R9 的 Python/Rust 对拍。R9/R10 历史归档保留原 JSON。

## 双机复核

A/B 通过 SSH 接收同一带摘要的源码包，在各自临时目录核验 96 项输入并独立运行。
两端得到同一 R12 结果摘要
`8457efabf3dffac0e27e37e2ad7a31af86bc53b982d7d45517e266e601855478`，
17 条 Receipt 的原终态分布为 8 UNRESOLVED、6 EXPIRED、2 FAILED、
1 FUNDING_EXHAUSTED，10 项候选记录篡改均被拒绝。R11 摘要保持
`2f244334a7ddfb264d6c16f107cc5c06b1a3229ea6996023a83216cd48dc5c50`。
双机本轮执行的是只读证据重放与组件对拍，未触发新任务或提交结算。

R9 两端均生成 18,425,353 字节，SHA-256 与原文件及两个历史包中的副本一致。
对拍结果摘要同 R9 归档，覆盖 367 条向量。现行源码以 156 字节 pin 替代原 JSON，
该文件对源码交付的净减量为 18,425,197 字节。独立导出耗时 A 约 5.7 秒、B 约
10.5 秒，含生成、摘要校验与写盘。数值仅为本轮观测。

[机器可读摘要](PROFILE-PHASE-D-R12-20261109.summary.json)提供输入清单和两端摘要。

## 接口评审记录

R10 的测试原因摘要和闭合摘要各自可复算，但缺少一套共同的候选来源绑定。
可复现反例见 `changed-cutoff`、`changed-closure-event` 和
`foreign-deployment`。R12 以相同已认证前缀为上下文，把原因和终态绑定到重放
输入。受影响边界为 INV-04、INV-07、INV-13，及 TH-24、TH-27、TH-28、TH-37。
版本只读并行，无状态迁移或新权限。弃用该版本时可停止消费候选投影，既有签名、
结算与旧版重放仍按原证据复核。候选端需维护部署与来源 pin。现有信任根不变，
时钟、日志和观察者权限仍按 ADR-0008 的有限测试约定，正式决定留在 OQ-04/OQ-05。

## 本地回归

`make test` 通过，含 24 组 668 项 Python 测试、20 次 sanitizer 检查。
R1 至 R11 的结果摘要逐项匹配各轮归档。把 README 的当前计数故意退回
80/35/4 后，库存门禁拒绝该副本。正式 FM-A 仍为 0/12。
