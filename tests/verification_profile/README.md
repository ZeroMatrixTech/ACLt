# VerificationProfile P0-1B 测试

状态：`STARTED / NOT CLOSED`。

本目录是 P0-1B 的首批可执行工件，只验证 [`../../schemas/verification-profile/coverage.json`](../../schemas/verification-profile/coverage.json) 明列的规则。它当前覆盖：

- 顶层必填/未知字段和方法参数块在场性；
- `REEXEC_AUDIT_ONLY` 无 claim；
- (0 \le B < Q \le G\)、`delta_min` 与 mixture weights 的精确有理数检查；
- AssumptionID 唯一；
- `CauseSet + reducer → EffectiveVerdict`、归约器绑定和 `TRUSTED` 安全假设闸门。

已有候选模板/claim 切片的 L2 CBOR、2 个摘要局部实现与 Python/Rust 对拍；仍未完成全量 18 摘要、五相位 Schema、全部注册对象及规范要求的全量向量族。任何未覆盖规则都不得被描述为通过；参考 validator 的 `--production` 模式会主动 fail closed。

运行：

```powershell
python -m unittest discover -s tests/verification_profile -t . -v
```

2026-10-23：全量盘点为 119 项 Type A（3 implemented、8 partial、108 not implemented），18 个规范摘要均未实现。详见 [逐项盘点](../../docs/testing/P0-1B-INVENTORY-20261023.md)。此次只修正覆盖登记，不新增验证能力；历史数量保留为当时快照。

后续编码切片更新：本页 3/8/108 与 18 摘要全未实现的统计保留为盘点时基线；当前登记已变为 3/19/97，2 个摘要部分实现、16 个未实现。Python/Rust 限域对拍及 SV-42 说明勘误见 [编码切片记录](../../docs/testing/CLAIM-CODEC-20261023.md)；以 coverage.json / inventory.json 当前记录为准。
