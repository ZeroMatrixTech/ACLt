# ACLt 最简验证机

[立项与首轮规格](../../docs/07-roadmap/minimal-verifier-baseline.md)下的切片验证实验。判题规则 `aclt.exp.rir-stats-exact@1` 固定[候选 RIR stats-core](../aclt-rir-stats-probe/INDEPENDENT-CORE.md)的精确结果语义。

- `ask(artifact, data, limits)` 验证工件和上限，生成规范 CBOR 的 `Question`。题目绑定规则版本、RIR 工件摘要、输入摘要，以及 gas、输出、调用深度和内存页上限。题目和输入使用各自的实验摘要域；工件沿用既有 RIR 摘要域。
- `solve(question, artifact, data)` 用现有 Python 求值器产生 `Answer`，包含题目摘要与规范 `Outcome` 字节。
- `verify(question, artifact, data, answer, executor=...)` 核对题目和字节的绑定，调用验证者本地指定的 Rust 执行器，从原始工件和输入独立求值。逐字节比较规范结果，返回 `ACCEPT` 或带原因的 `REJECT`。执行器启动失败或无法产出结果时抛出 `ExecutionError`，提交仍待判定。

从仓库根目录复现，需要 ENV-1 的 Python 和 Rust：

```sh
make test-minimal-verifier
```

该命令也纳入 `make test`。测试在临时目录构建 Rust 执行器，以冻结的 `stats-int-v1` 向量检验正常输出、同题的正确与错误提交、不同 gas 上限下的跨题提交，以及已有除零 trap。另有工件与输入绑定、未知规则和执行器错误的用例。阶段 2 增加手算输出、相邻 gas 上限、结果字段负例及单侧计量偏差注入，详见[语义验收](SEMANTICS.md)。这些判决与证据仅适用于本地实验。

[双机作业切片](DISTRIBUTED.md)说明拆分、跨机交叉验证、归并、资源边界和验收命令。
