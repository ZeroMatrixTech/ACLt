# R10 Phase D 审计重放

R10 基于 `230dd4a`，为 `REEXEC_AUDIT_ONLY` 加入 Python/Rust 独立重放入口。冻结测试合约把 Receipt 绑定、期限和预算上限与外部 SHA-256 pin 对齐。schema lock 另行 pin。

- 审计求值器从内联规范结果字节、候选结果和接纳投影计算结果及聚合。采用严格期限和无溢出的预算比较，拒绝重复 attempt ID。等时记录的顺序来自测试投影。
- 事件 DAG 决定资金与期限条件的先后。两个合法但不可比较的事件选资金条件。缺失、不可见、错误主体或成环的事件触发验证作废。
- 执行闭合要求 Receipt、来源引用、闭合摘要和可见事件一致。仅零有效提交产生执行失败。来源缺失或闭合格式不合法产生验证作废。
- 重算完整条件向量、首个为真的条件和终态，逐字节对照提交记录。全假时省略 `selected_condition`，并使用 `UNRESOLVED`。

本轮采用 `ACLt/TEST/R10/ExecutionClosure/1`，输入为去掉 `closure_digest` 的闭合记录规范 CBOR。`ACLt/TEST/R10/DecisionReason/1` 绑定输入摘要、事件快照摘要、合约 pin、求值时刻、条件和值。两者属于 R10 测试编码。方法与闭合引用均为固定的 R10 测试组件标识。

范围为内联字节比较和候选来源投影。执行器实际重跑、日志及来源认证、完整 Phase D、其他三个方法、状态提交和正式准入各有独立验收。SV-112 完成结构投影，SV-115、SV-121 为部分实现。Type A 覆盖 80/35/4。

## 验证证据

- 完整 `make test` 通过 667 项 Python 测试和 20 次 sanitizer 检查。R1–R9 对拍结果摘要保持一致。
- 两台物理机分别从校验过的归档构建 Rust，并与本机 Python 对照 67 条向量。其中 15 条拒绝记录，其他向量包括验证作废后正确导出 `UNRESOLVED` 的情况。
- 两端结果 SHA-256 为 `66e218eb4e6cd0eca5827656922e46f7339913dd9c731f3c37fc14778f0c59a8`。归档包含 66 个源码及许可文件，另附逐文件 pin。
- [机器摘要](PROFILE-DECISION-R10-20261109.summary.json)和[公开源码包](public-evidence/PROFILE-DECISION-R10-source.tar.gz)。

在解包目录校验 `SOURCE-PINS.json` 所列 SHA-256，执行 `python3 -B scripts/check-decision-replay.py` 可复跑对拍。
