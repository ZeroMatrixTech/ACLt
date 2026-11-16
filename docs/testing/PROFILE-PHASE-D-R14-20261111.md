# R14 非主网注册与 Phase B/D 信封重放

R14 将已经认证的 FM-S3 历史证据接入版本化的非主网测试注册表与 Phase B/D 信封：
A/B 两端 17 条 Receipt 的注册与 B/D 信封验证通过、19 个负例均按预期拒绝，
完整 `make test` 通过 24 组 668 项 Python 测试和 20 次 sanitizer 检查。
基线为 main `6c34c4d`（R13）。验证者独立提供注册表摘要和 Receipt 列表。
注册项冻结配置、部署声明、七类测试来源、允许的 Profile、anchor 和 checkpoint。

Phase B 投影冻结 Receipt、CREATE、资金、Lease 和已提交的 ACTIVATE／CONSUME。
Phase D 提交 Phase B 摘要、R11 来源摘要及完整 R12 候选判决。两层信封都必须逐字节
匹配签名日志重放。即使重算篡改后的 B/D 链接，验证仍拒绝与原始授权事实不一致的
记录。Rust R13 入口独立重算并核对内层判决。 [信封与注册表格式](../../schemas/formal-migration/replay-envelope.md)

`make test-phase-d-envelope` 复核固定注册表、完整信封摘要和跨语言结果，也包含在
`make test` 中。负例覆盖错误的外部 pin、版本、部署、检查点、签名、来源和 Profile，
以及篡改资金、Lease、判决来源、内层判决与重算后的 B/D 链接。

FM-A08 增加固定部署下的注册和候选信封证据。正式验收覆盖正式 Profile 与来源审批、
新版 Intent/Receipt 冻结部署绑定，以及正式 Phase B/D 验证。可信时钟、日志终局性
与正式撤销机制属待定来源合约。正式 FM-A08 为 `PLANNED_NOT_RUN`。

## 双机结果

A/B 通过 SSH 在各自临时目录核对同一源码包的 81 项输入，独立认证 7 套签名
快照。17 条 Receipt 的注册与 B/D 信封验证通过，19 个负例均按预期拒绝。
R12 固定候选字节仍与历史摘要逐条匹配，两端各自用 Rust 重算候选判决。
完整结果摘要为
`8b4d8a0850a9cded136595420d2688484a6f409b140aa7d6f19581e393ca8ca9`。
验证使用历史签名快照，按只读接口运行。 [机器可读摘要](PROFILE-PHASE-D-R14-20261111.summary.json)

## 评审记录

R13 使用外部固定配置和已认证来源重算判决。R14 将该版本认可的测试来源、日志检查点
和 Profile 摘要显式写入版本化注册项，并验证 Phase D 对 Phase B 的引用。
可复现反例见 `source-contract-under-test-pin`、`checkpoint-replacement` 和
`changed-phase-b-with-matching-link`。相关边界为 INV-01、INV-03、INV-04、INV-07
和 INV-13，以及 TH-24、TH-27、TH-28、TH-37。注册者需维护固定部署的源材料与摘要。
退出该测试版本可停止处理新版回放信封，已签名的旧记录仍可按原接口验证。
来源审批及撤销继续由 OQ-04/OQ-05 追踪。 [ADR-0008](../05-decisions/ADR-0008-fm-s3-interface-decisions.md)

## 本地回归

`make test` 通过，含 24 组 668 项 Python 测试和 20 次 sanitizer 检查。
R1–R13 的结果摘要逐项匹配历史记录，R14 本地结果与双机一致；本片结论限于固定部署下的注册与候选信封证据。
