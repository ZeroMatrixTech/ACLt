# FM 第四项证据归档收尾

2026-11-07，基线 `4138d9921362d2077c6cc8f5b4ebf1fe920f4359`。本轮补齐候选路径的留存材料和复核入口。原双机运行日期、原摘要和归档字节按各自记录保留，本轮新增双机运行数为 0。

## 公开归档与回放

| 留存证据 | 账本数 | 历史事件数 | 公开归档 |
|---|---:|---:|---|
| FM-S2 最终 17 场景 | 17 | 60 | [FM-S2](public-evidence/FM-S2-20261031-public-evidence.tar.gz) |
| FM-S3 候选总体收尾 | 1 | 39 | [S3 收尾](public-evidence/FM-S3-public-evidence.tar.gz) |
| 真实除零 Task trap | 1 | 39 | [Task trap](public-evidence/FM-S3-TASK-TRAP-public-evidence.tar.gz) |
| 观察方签名执行闭合 | 1 | 9 | [执行闭合](public-evidence/FM-S3-EXECUTION-CLOSURE-public-evidence.tar.gz) |
| 终态组合与历史矩阵 | 4 | 102 | [组合矩阵](public-evidence/FM-S3-HISTORICAL-MATRIX-public-evidence.tar.gz) |
| 合计 | 24 | 249 | 各账本独立，计数仅用于清点 |

S3 四份归档逐字节复制自已留存公开包，SHA-256 与原报告一致。S2 公开包从最终运行已导出的 17 份 config/snapshot/B-anchor 及固定源码构成。每份 S2 snapshot 与 config 的字节摘要均与 [原机器摘要](FM-S2-20261031.summary.json)一致。运行数据库、角色私钥与凭据留在原私有运行目录。

[归档索引](public-evidence/index.json)逐份固定归档摘要、源码清单摘要、genesis、checkpoint 和快照文件摘要。[公开检查器](../../scripts/check-fm-public-evidence.py)检查归档路径、重复文件、链接、私有运行材料和读取上限，并验证包内固定源码。回放使用当前实现，包内源码只作历史 pin 核验。

```sh
# 离线检查五份归档及二十四套固定输入
make check-fm-public-evidence
# 离线完整回放，使用已有系统 OpenSSL
make test-fm-public-evidence
# 对单套公开输入沿用原检查器，S3 使用 --s3b
python3 -B scripts/check-fm-s2-evidence.py --s3b \
  --config '<EXTRACTED>/config.cbor' --snapshot '<EXTRACTED>/snapshot.cbor' \
  --anchor '<EXTRACTED>/anchor.cbor' --expected-genesis '<PIN_FROM_RETAINED_REPORT>'
```

本轮二十四套快照在当前实现上全部重放通过，事件数、链头、状态摘要与固定索引一致，结果见 [机器摘要](FM-PUBLIC-EVIDENCE-20261107.summary.json)。`make check` 接入归档元数据检查，`make test` 接入完整公开回放。没有 Git 历史的源码包也能执行公开回放。

genesis 和 checkpoint 的可信来源由独立留存的报告或审查过的仓库版本提供。随包公钥、签名和 SHA 清单支持一致性复核，来源认证、新鲜性和权威抗回滚仍需各自的外部条件。

## 外部审计原文

[AUDIT-20261105-01 原文](../08-governance/audits/external/AUDIT-20261105-01.original.txt)于本轮按原字节接收归档。来源为操作者此前提供的仓库外文件 `ACLt-audit-20261105.md`，共 81,500 字节，SHA-256 为 `cb1be108c57df74091bc8dd9a56258c584a9f87630e1dba51ce7c24b847edebe`。使用 `.txt` 保留其中的历史路径、链接和代码原文，避免将历史审计片段作为当前文档入口解释。

原文标注审计者为 DeepSeek Harness 代理，日期 2026-11-05，原基线 `9cf9398`。此处记录文件来源和完整性；报告作者身份、执行陈述和全部发现没有额外独立认证。项目对发现的确认、反例和有界处置见 [原修复记录](AUDIT-FIXES-20261105.md)。原文中的操作建议按审计材料保留。

## GitHub CI 运行记录

本轮通过本机已认证 GitHub CLI 只读取得 API 记录。连接器读取该仓库返回访问错误，客户端读取成功。完整运行与步骤状态见 [CI 快照](ci/VALIDATE-20261107.runs.json)。时间均为 UTC。

| 运行 | 创建时间 | Head SHA | 结果 |
|---|---|---|---|
| [首次运行 42009685044](https://github.com/ZeroMatrixTech/ACLt/actions/runs/42009685044) | 2026-11-05 10:18:58 | `58ae7b09e85c7e44b2d6517216e2687448c40643` | failure，源码 pin 检查失败，后续实现/打包步骤跳过 |
| [修复后运行 42011671890](https://github.com/ZeroMatrixTech/ACLt/actions/runs/42011671890) | 2026-11-05 10:33:20 | `9ebbe3f7dce0366423e7e61917128c67602d1082` | success |
| [#71 主线运行 42223578937](https://github.com/ZeroMatrixTech/ACLt/actions/runs/42223578937) | 2026-11-06 13:12:07 | `b555231143b462c54fd320dc2924107a57fac4af` | success |
| [第三项分支运行 42289957609](https://github.com/ZeroMatrixTech/ACLt/actions/runs/42289957609) | 2026-11-06 20:37:44 | `4138d9921362d2077c6cc8f5b4ebf1fe920f4359` | success |

首次失败的原日志保留以下诊断，路径对应仓库内历史文件。

```text
FAIL: unavailable source 802cd74389d8b338b7fd5b03c985eab769b7c19b:tools/verification_profile/validator.py
Error: Process completed with exit code 1.
```

首次失败实际检出 PR 合并提交 `c119ccbf96f05d81edac0a2a0a1b69987eb3b0cf`。第三项成功运行实际检出 `963c9821496ee6a0b952443c977e0b97236d23a0`，将分支 `4138d99` 合到 `b555231`。两者从原 job 日志读取，CI 快照保留相关原始行和整份日志 SHA-256。PR 的 head SHA 与实际检出提交分别记录。其他两次仅据 API 保存 head SHA 和步骤结果。

成功记录中的源码检查、`make test` 以及两次源码包逐字节比较均成功。GitHub 执行的是 Ubuntu 容器内的本地实现验证。双物理机集成结论由前面的 LAN 归档支持。本轮第四项改动的 CI 需要后续分支提交触发。

## FM-A 候选证据列

[实施计划](../07-roadmap/formal-migration-plan.md#迁移验收编号)新增候选路径证据列。[机器追踪表](../07-roadmap/formal-migration-traceability.json)中 `candidate_path_evidence` 完整覆盖 FM-A01–A12，每项给出已覆盖性质、原报告、测试方法和正式验收缺口。原 `acceptance_requirements` 的十二项正式状态保留为 `PLANNED_NOT_RUN`，本轮新增正式验收决定为 0。

本轮归档覆盖有限候选路径。S1 双语言编码、S2 授权、S3 判决和结算各有对应证据。完整 RIR conformance、正式对象与信封、受认可来源、部署 assurance、真实断电、外部支付及权威抗回滚仍按各自门槛推进。


## 本轮验证

本地 `make check` 23 组共 468 项通过，包含 5 项新反例回归。反例覆盖归档被修改、更新归档哈希后包内源码或快照被修改、错误 genesis，以及路径穿越、链接、重复文件和私有运行材料。源码 pin 检查、交付清单与 Markdown 路径检查通过。

两次构建的源码包逐字节相同。解压后的无 Git 目录也成功回放 24 套快照、249 条历史事件。原始 CI 日志、本地检查日志及源码包复核结果另行留存在操作者证据目录，入库文件包含可直接运行的公开材料。
