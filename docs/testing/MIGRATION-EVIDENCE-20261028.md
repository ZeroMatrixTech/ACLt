# FM / RIR 保留证据摘要

本报告把原始双机报告恢复为仓库内机器摘要，覆盖 FM-S1a、FM-S1b 与 RIR 核心三组，保留对应合并源码、运行范围与校验值。恢复过程未执行新的 SSH 运行，也未产生新的双机结论。

| 摘要 | 对应的合并源码 | 原运行范围 |
|---|---|---|
| [FM-S1a](FM-S1A-20261028.summary.json) | #60 / 5780db3 | 两端各 179 项，89 固定向量 |
| [FM-S1b](FM-S1B-20261028.summary.json) | #61 / e69764a | 两端各 196 项，28 固定向量、111 费用格 |
| [RIR 核心](RIR-INDEPENDENT-CORE-20261028.summary.json) | #62 / d669b02 | 两端各 161 项，38 固定向量 |

摘要含完整源码 blob SHA、实际固定向量文件 SHA、每端计数/工具环境、原报告公开投影及校验值。三组源码清单分别有 14/19/19 个输入，已逐文件对照 Git 中上述 revision。原报告保留在操作者证据根，raw-report hash 是其留存锚点，不意味着仓库已包含原报告全部字节。

RIR 两端原始结果流的 SHA-256 均为：

`5a0e6d478892167a0ee80fdaaf1f68041f9d5edbb8c0ab700615778320c42034`

它由原 driver 对完整 `cases_detail` 列表作 canonical JSON 后计算，重放校验会重新计算该 hash。FM 两轮的原报告没有整轮结果流 hash，字段明确为 null；shared_checks_sha256 只覆盖计数/向量/源码等共同报告事实，不冒充完整结果流。每次临时新密钥签署也不应被误称为跨机器相同的签名流。

## 校验与本地重放

```sh
# 只核对公开摘要、跨端共同事实、审计依赖清单；不声称执行或源码验证
python3 -B scripts/check-migration-evidence.py

# 离线核对精确 Git revision 的全部源码 blob
python3 -B scripts/check-migration-evidence.py --repository .

# 从同一 Git 仓库的三个精确 revision 各自解包，在临时目录本地重放
python3 -B scripts/check-migration-evidence.py --repository . --replay \
  --output /new/local/replay-directory
```

全新重放目录保存每个 driver 的原输出和 JSON。重放不写 Git 工作区、下载依赖或改摘要。历史源码需在本地 Git 中存在，Rust/Python/OpenSSL 需已安装。无 Git 历史的源码压缩包默认只能做 metadata 检查，不能把 NOT_RUN 当成 source/replay PASS。

本轮已运行三个原 driver 的本地重放，source pins、计数与原报告一致；RIR 的完整记录摘要也重新核对。它是**新的单机重放证据**，不是新增 A/B 运行，更不是新的完整 RIR conformance。

Canonical JSON 精确定义为 Python `json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode('utf-8')`。summary_sha256 排除自身字段；report projection 和 shared checks 的范围由校验器显式定义。重复 JSON key、未知摘要字段、源路径越界、错 revision、计数/跨端事实不符及伪造 FM 整轮 hash 均拒绝。

这些 SHA 提供内容一致性和可复现锚点，不是数字签名或第三方独立审计，也不能证明物理主机/输入忠实性或统计独立。源码当前工作区后续变化不会悄悄改写历史摘要：核对的是记录的 Git revision。
