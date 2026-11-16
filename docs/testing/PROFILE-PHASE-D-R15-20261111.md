# R15 创建时冻结非主网部署绑定

R15 实现从 Phase I Intent、Phase I transcript 到 Phase F Receipt 的候选创建接口：
本机与 `aki2` 各自创建签名账本并提交 14 个事件，两条 Receipt 的创建、判决、结算
及回放均通过，13 个负例均按预期拒绝，完整 `make test` 通过 24 组 668 项 Python
测试和 20 次 sanitizer 检查。基线为 main `df94423`（R14）；权威在提交时核对配置、
来源、Profile、时间、请求者及签名，生成新版 ReceiptID，并在 ReplayEnvelope/2 中
核对这份冻结证据；旧配置按原版本解释。 [创建合约](../../schemas/formal-migration/bound-creation.md)

原 genesis 承诺了 Receipt 白名单。R15 使用白名单批准底层任务与政策承诺，再把该
承诺及部署绑定一起写入新版 Receipt。Lease、判决与结算权利沿用新版 ReceiptID。
结算另用底层承诺核对政策报价。首次局部运行暴露了旧报价校验直接比较两种 ID 的
问题，修复后保留对两个承诺的独立校验。

`make test-bound-creation` 新建签名账本，验证一致结果和到期两条路径，包含创建重试、
授权、结果、结算与 B/D 回放。负例覆盖部署、来源、签名、时点、版本、预算和信封替换。
两条路径使用测试结果与权威时钟。内层判决由 Rust 独立重放。

正式 FM-A08 验收的前置项包括 Profile 和来源审批、正式撤销机制与正式部署证据。
本轮证据适用于 ADR-0008 的候选非主网审计路径。相关不变量为 INV-01、INV-03、
INV-04、INV-07 和 INV-13，威胁边界为 TH-24、TH-27、TH-28、TH-37。
[ADR-0008](../05-decisions/ADR-0008-fm-s3-interface-decisions.md)

## 本地签名证据

新账本提交 14 个事件。两条 Receipt 分别达到 `UNRESOLVED`（一致结果）和
`EXPIRED`，13 个负例均按预期拒绝。新版 Receipt 创建重试返回原结果。
导出的公开证据使用独立记录的注册表摘要再次离线复核，两条 Receipt 均通过。
两次新建账本的结果摘要一致，生成的部署密钥和日志标识各自独立。

## 双机验证

本机与 `aki2` 从同一份源码归档分别编译并创建签名账本，生成了不同的 genesis。每台机器均提交 14 个事件，通过两条 Receipt 的创建、判决、结算及回放，13 个负例均按预期拒绝。两端的语义结果摘要一致，两份签名证据各自通过独立的离线复核。测试在各自主机的临时目录运行。

## 本地回归

`make test` 通过，含 24 组 668 项 Python 测试和 20 次 sanitizer 检查。
R1–R14 的结果摘要逐项匹配历史记录，两次 R15 本地运行的语义结果摘要一致；本片结论限于 ADR-0008 的候选非主网审计路径。
[机器可读证据](PROFILE-PHASE-D-R15-20261111.summary.json)
