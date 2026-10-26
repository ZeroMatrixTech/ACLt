# B/Q 反例与模型边界回归

`test_boundaries.py` 为原定第四项第一片（BQ-W4-S1）的 11 项确定性检查。

- 新组合枚举使用既有逐步状态机；对拍旧闭式能力概率和有限总体 DP，旧源码与 manifest 不变。
- G≤12 的 toy 模型全部用 Fraction；response filtering/support-first 是故意失效的采样器，不是建议实现。
- 正确候选活性和错误候选接受率分开；latent capability/共同故障/域漂移均为人工构造，不是校准数据。
- `make check-bq-boundaries` 只运行本地模型；`make test-bq-boundaries BQ_REPORT=/existing-parent/new.json` 写新报告，禁止覆盖旧报告。
- source pin 覆盖模型、入口、回归和旧递推/闭式依赖；不是生产统计 gate、独立身份识别或两语言 conformance。

研究边界见 [正文](../../docs/06-research/bq-boundaries-slice1.md)。
