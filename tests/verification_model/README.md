# 验证轮数学模型对拍测试

本目录为单任务、单候选、二元集群证据的有限总体验证模型提供两套独立实现：

- `recursive_model.py`：逐步似然比状态机；
- `closed_form_oracle.py`：下降阶乘闭式、全枚举反例与精确 DP oracle；
- `test_verification_model.py`：递推/闭式、DP/全枚举和模型反例对拍；
- `conformance_vectors.json`：供其他语言实现使用的冻结有理数向量。
- `manifest.json`：算法 ID、算术类型和测试资产 SHA-256。

运行：

```powershell
python -m unittest discover -s tests/verification_model -p "test_*.py" -v
```

测试只使用 Python 标准库和精确 `Fraction` 算术。任何浮点输出只能用于展示，不得作为断言。

## 模型与实现测试的边界

运行时无法从本轮票数观察真实错误支持能力集合 `A⁻`。因此：

- `|A⁻| > B` 的枚举是一条模型反例，不是运行时必须自行检测的状态；
- `NULL_BOUND_EXACTLY_EXCEEDED` 只有在外生 `SupportCapabilityBound` 仍有效时才映射为接受；
- 单个 mixture 分量死亡只把该分量资本置零，不重分配权重，也不自动终止整个验证轮。

固定反例数值只约束 `finite-population-boundary-lr-v1`。未来算法变得更保守时，某个越界场景不再超过 `epsilon_f` 不构成安全回归；算法变更必须使用新 ID 和新向量。
