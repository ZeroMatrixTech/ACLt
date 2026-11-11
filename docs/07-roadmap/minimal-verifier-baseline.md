# ACLt 最简验证机

> 文档状态：工程立项与首轮实验规格草案<br>
> 决定来源：维护者于 2026-11-11 确认将工作重心转向「问—答—验」基线<br>
> 语义边界：v0.5；实验接口为候选设计，V1 处置见 [V1 Profile](../03-protocol/v1-profile.md)

## 目标与范围

在参与者诚实、基础设施正常、单一记录方且无资金结算的环境中，让独立验证者依据冻结的判题规则，判定一份提交是否答对了指定问题。首轮只覆盖 `stats-int-v1` 实际使用的 RIR 子集及用于验收的同子集小程序。模块独立于正式迁移（FM）的 Lease、权威来源与结算路径。

## 对象与流程

| 对象 | 首轮内容 |
|---|---|
| `Question` | 判题规则及其语义版本、RIR 工件摘要、输入摘要、会影响结果的资源上限。以现有规范编码与分域摘要机制派生 `question_id`。 |
| `Answer` | `question_id` 与提交的 `Outcome`。首轮结果包含输出或确定性 trap，以及 `gas_used`。 |
| `Verdict` | 对一次提交给出 `ACCEPT` 或 `REJECT`，拒绝附原因。裁决若独立记录，绑定 `question_id` 与答案内容摘要。 |

- **Ask** 接收规则、工件、输入与上限。超出支持范围时拒绝，合法时返回冻结的 `Question`。首轮规则是按固定的候选 RIR 语义执行并精确比较 `Outcome`。
- **Solve** 接收冻结的问题及相应字节，提交 `Answer`。首轮用现有 Python 求值器生成结果，提交者可自行选择求解方式。
- **Verify** 接收冻结的问题、工件和输入字节及一份答案。先核对问题绑定与字节摘要，再由独立 Rust 入口从题目数据求出规范结果，精确比较 `Outcome` 的规范编码。每份提交独立判定。正确的确定性 trap 也可得到 `ACCEPT`。

闭环入口见[最简验证机实验](../../experiments/aclt-minimal-verifier-baseline/README.md)。阶段 2 的[语义与向量](../../experiments/aclt-minimal-verifier-baseline/SEMANTICS.md)固定了计量边界与单侧偏差测试，本地复查使用 `make test-minimal-verifier`。

## 首轮验收

1. **闭环与对拍。** `stats-int-v1` 和小程序走完 `Ask → Solve → Verify`。Python 与 Rust 对同一组向量产出的规范结果字节一致。
2. **语义边界。** 手算向量覆盖正常输出、除零指令 gas 恰好够时的除零 trap、差 1 gas 时的 gas 耗尽 trap。正确提交均得到 `ACCEPT`。超出支持范围的题目在 Ask 阶段拒绝。
3. **拒绝路径。** 分别改动输出、trap 原因或 `gas_used`，以及将原提交交给另一道题，均得到 `REJECT`。替换传给 Verify 的工件或输入字节时，摘要检查拒绝。
4. **差异检测。** 人为改动一侧的计量规则，固定向量须检出预期分歧，保留对应向量与结果字节。

## 开工顺序与证据边界

1. 从实现所用的仓库版本锁定候选规则、指令、输入输出约定、计量和上限，先写出手算向量。参照 [ADR-0006 草案](../05-decisions/ADR-0006-rir-deterministic-wasm-core-subset.md)和[已有独立 RIR 核心](../../experiments/aclt-rir-stats-probe/INDEPENDENT-CORE.md)。
2. 复用规范编码、内容寻址及现有执行入口，完成独立闭环与本地验收。历史对拍记录只作为定位入口和选择向量的依据。
3. 闭环成立后，按具体场景评估轨迹证书对逐步复核、分歧定位和验证成本的影响。[ADR-0009 草案](../05-decisions/ADR-0009-proof-verified-computation-statements.md)可供参考。未来的判题规则可允许同题多解，沿用三个流程对象。

首轮结果仅支持此实验范围。关联的 OQ-02、OQ-05 与 OQ-06 见[未决问题](open-questions.md)。协议语义、ADR 状态、V1 处置及 Gate 结论由各自的权威入口决定。
