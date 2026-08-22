# VerificationProfile P0-1B 测试

状态：`STARTED / NOT CLOSED`。

本目录是 P0-1B 的首批可执行工件，只验证 [`../../schemas/verification-profile/coverage.json`](../../schemas/verification-profile/coverage.json) 明列的规则。它当前覆盖：

- 顶层必填/未知字段和方法参数块在场性；
- `REEXEC_AUDIT_ONLY` 无 claim；
- (0 \le B < Q \le G\)、`delta_min` 与 mixture weights 的精确有理数检查；
- AssumptionID 唯一；
- `CauseSet + reducer → EffectiveVerdict`、归约器绑定和 `TRUSTED` 安全假设闸门。

尚未实现 L2 CBOR、18 个摘要、五相位全量 Schema、全部注册对象、39+ 向量族和第二语言对拍。任何未覆盖规则都不得被描述为通过；参考 validator 的 `--production` 模式会主动 fail closed。

运行：

```powershell
python -m unittest discover -s tests/verification_profile -t . -v
```
