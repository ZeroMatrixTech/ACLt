# P0-1B Profile 摘要与判决结构第一片

本片交付 Profile 的正式内容投影、摘要重算与选定注册期字段检查，66 条固定向量在 A/B 两台物理机上全部通过且结果流 SHA-256 一致，完整 `make test` 退出码为 0；全局 119 条 Type A 由 `3 implemented / 24 partial / 92 not implemented` 变为 `7 / 28 / 84`。基线 main `41f0ee9`，日期 2026-11-07；实现依据为 VerificationProfile 规范 §3.1、§3.3.3、§11.3、§17.4。

## 规则交付

| SV | 范围与证据 | 登记 |
|---|---|---|
| SV-02 | 按正式 ContentMap 投影并重算摘要，覆盖四种方法。v2 使用 `ACLt/P0-1/Profile/2`，v1 保留 `…/1` 只读核对。身份与 advisory 不入摘要，supersedes 和在场可选字段入摘要。 | IMPLEMENTED |
| SV-17 | audit 的 DecisionCondition 数组禁止 ACCEPT，因此冻结 CanonicalTerminal 下不产生 TRUSTED。 | IMPLEMENTED |
| SV-39 | 四种方法共用冻结条件顺序的严格子序列，拒绝乱序、重复和错误 default。方法适用集合完整性另归 SV-20。 | IMPLEMENTED |
| SV-63 | 四种方法的 DecisionMapping 使用字符串条件数组，拒绝带 terminal 的对象或覆盖字段。 | IMPLEMENTED |
| SV-18/19/20/64 | audit 的 13 事件 key/value 行、映射值域、五条件集合及四终态集合得到校验。其余方法分支待实现。 | PARTIAL |

全局 119 条 Type A 从 `3 implemented / 24 partial / 92 not implemented` 变为 `7 / 28 / 84`。18 个摘要中 Profile 摘要 implemented，模板/claim 两项 partial，其他 15 项未实现。登记的实现符号与测试方法可由 `make check-profile-inventory` 复核。

## 入口与数据边界

Python 实现在 [profile.py](../../tools/verification_profile/profile.py)，Rust 在 [profile.rs](../../tools/verification_profile/rust/profile.rs)，复用各自既有的独立 CBOR/NFC/SHA 核心。Rust 的新模式为 `profile-digest`、`profile-decision`、`audit-profile`，输入为 `kind<TAB>CBOR-hex`。两端返回原始 CBOR、ContentMap CBOR 与摘要。

```sh
python3 -B -m tools.verification_profile.validator profile.cbor --profile-cbor
make test-profile-digest
```

既有 JSON bootstrap 调用方式保留。新增 raw-CBOR 入口运行摘要、判决结构与 audit 分支检查；`--production` 继续依剩余覆盖缺口拒绝。该入口的零退出码只表示所列规则通过。

SV-02 的输入是已确定原生类型的规范 CBOR。投影保留嵌套字段的原生值及字节，不从字段名推断类型，不解析外部引用。嵌套 L1a/L1b、不可变 schema import、ExcludedClaims/RegistrySnapshot 解析与其他摘要有各自的规则 owner。当前向量在这些位置使用固定测试输入；整个对象通过 SchemaValid 或注册授权属于对应规则 owner 的验收范围。新 audit 字段检查要求 v2，v1 只用于摘要复核。

FailureMapping.entries 使用规范 §3.2.1 声明的排序 `{key, value}` 行。key 是 ObservableEvent，value 包含 outcome 与 attribution。候选 FM-S3 的 Profile schema/摘要与历史快照保留各自字节，正式对象接入该运行链需后续切片。

## 验证

[固定向量](../../tests/verification_profile/codec/profile-digest-vectors.json)共 66 条，15 条正例、51 条反例。覆盖四种方法的摘要和通用判决检查、v1 只读、身份/advisory 不变性、冻结字段篡改、claim/参数块在场性、事件/条件缺失与重复、顺序、终态覆盖及非规范 CBOR。

12 项默认回归覆盖正式 hash preimage 的独立 hashlib/OpenSSL 核对、正常 CLI、生产边界、输入不变与旧双机源码清单。新 Rust 模块加入后，同步 S1a/S1b/RIR 活跃构建清单与源码 pin 采集；历史已归档源码与摘要保持原样。


两台物理机各自构建后各 66 项通过，结果流 SHA-256 均为 `e7c80d5b7d424dd2b60b0c7654c306ac6c3b12e71d607fc69d93c7553de24b1b`，部署源码 pin 一致。原始报告与源码清单见 [机器摘要](PROFILE-DIGEST-R1-20261107.summary.json)。本轮双机范围为构建与编码/摘要核对，新增任务协议运行数为 0。

开发期首个测试将非 audit 方法中的合法 ACCEPT 条件误列为反例，已按方法适用矩阵改为未知条件反例。首次完整回归在现有网络控制测试处遇到受限执行环境的 socket 权限错误，失败日志已保留，后续在允许回环网络的环境重跑。

完整 `make test` 退出码为 0。默认 23 组 480 项（原 468 + 本片 12）以及执行器另 25 项通过，20 次 sanitizer、原 Claim/FM/RIR 对拍通过；24 套历史快照的 249 条事件用当前实现重放通过。原始构建、失败与全量日志保留在操作者本地证据目录。
