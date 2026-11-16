# R11 FM-S3 权威证据接入 Phase D

本报告基于基线 `698a0cb`，复用 FM-S3 公开签名快照，在已验证的日志前缀上导出 audit-only Phase D 的候选输入并复算终态，随后只读核对提交和结算。两台物理机独立复跑同一归档：7 份签名快照的 17 个 Receipt 条件、终态及结算绑定一致，另通过 10 项证据拒绝检查和 1 项闭合来源不可用的 R10 投影检查。

## 证据边界

调用方独立保存部署配置、一份已知 anchor 和预期最终 checkpoint。先以该部署的公钥验证快照签名及 genesis，逐事件重放请求、链和状态摘要，再核对 anchor 的前缀包含以及最终 checkpoint 的精确值。带外预期 checkpoint 固定本次取证的版本。验真失败拒绝证据包。

每个 Receipt 的输入取自首个且唯一的 `S3_FINALIZE` 之前的状态及事件。求值时间取该提交记录的权威时间。Phase D 结果绑定前缀序号、head、前置状态摘要和实际来源。其后，验证器核对同一 Receipt 唯一的 `S3_SETTLE`、终态事件引用、判决摘要与金额守恒。最终状态中保留的判决和结算须逐字节匹配重放结果。

## 适配口径

- FM-S3 的一次比较需要执行方和审计方两条已接纳结果。适配层按实际事件序列取首份结果，以 R10 的严格期限和预算规则复算接纳，两条结果对应一次比较。HostFault 槽位不计为有效结果。报告保留接纳事件序号和规范结果字节。
- 期限是按求值时间派生的 frontier 子事件。其父节点是决策前缀的 head。资金边界来自首次激活时已记录的资金不足事实。历史单链归档只能覆盖因果有序的情况。
- 观察方签名与闭合的 Receipt/Assignment/启动记录绑定由 FM-S3 重放验证。适配层保留原闭合记录和来源事件，用 R10 的测试闭合编码复算零提交条件。已认证前缀里的缺失启动触发 `UNRESOLVED`。仅缺少闭合记录时，仍按期限等其他有效条件求值。
- `phase_d_source_cbor_hex` 导出可复算的候选输入，另带 `ACLt/TEST/R11/PhaseDSource/1` 摘要。此适配采用 FM-S3 的非主网测试配置及证据类型。正式 Phase D 信封、执行器重跑和主网日志后端验收仍需单独证据。

## 复现

在仓库执行 `make test-fm-decision-replay` 会按仓库的独立 fixture 索引读取公开快照并核对所有候选终态。审查单个外部证据包时，独立提供 `--config`、`--anchor` 和 `--checkpoint`，再指定 `--snapshot` 及一个或多个 `--receipt HEX`。

```sh
python3 -B -m tools.formal_migration.s3_decision_replay \
  --config CONFIG.cbor --anchor ANCHOR.cbor --checkpoint EXPECTED.cbor \
  --snapshot SNAPSHOT.cbor --receipt RECEIPT_HEX
```

SV-119 新增 FM-S3 测试日志的签名、前缀包含及一致性证据，记为 partial。SV-115/121 已接到历史候选权威事实，仍需其他方法、正式 closure 合约和规范日志接口的验收。Type A 覆盖为 80/36/3。

## 实测结果

两台物理机独立校验并复跑同一归档。7 份签名快照共 17 个 Receipt 的条件、终态及结算绑定一致，分布为 8 个 `UNRESOLVED`、6 个 `EXPIRED`、2 个 `FAILED`、1 个 `FUNDING_EXHAUSTED`。其中 1 个 `UNRESOLVED` 来自历史签名日志中的启动状态不确定。双机还通过了 10 项证据拒绝检查和 1 项闭合来源不可用的 R10 投影检查。结果摘要为 `2f244334a7ddfb264d6c16f107cc5c06b1a3229ea6996023a83216cd48dc5c50`。

`make test` 通过 668 项 Python 测试和 20 次 sanitizer 检查，R1–R10 对拍结果摘要一致。新增本地回归构造同 genesis 的两份真实签名快照，验证旧快照仍可按旧 pin 复核，并拒绝用它满足更新 pin。双机部分使用已归档的测试日志，新增证据是两端独立复算。

源码包内含所需工具、公开证据和单独保留的索引。解包后校验 `SOURCE-PINS.json`，执行 `python3 -B scripts/check-fm-decision-replay.py --report R11.json` 可取得逐 Receipt 的前缀、判决和结算对照，以及候选 Phase D 输入。查看 [机器摘要](PROFILE-AUTHORITY-R11-20261109.summary.json) 和 [公开源码与证据包](public-evidence/PROFILE-AUTHORITY-R11-source.tar.gz)。
