# ACLt 自动进度看板

更新：2026-10-03T10:50:42.293610+00:00

测试状态根据代码指纹、运行退出码和预期摘要自动更新。协议关闭仍需独立审阅。

| 工作 | 状态 | 证据 |
|---|---|---|
| 精确模型验证 | PASS | [运行日志](.aclt-flow/runs/20261003T104730Z-b646f16f-model/output.log) |
| 验证器规则与错误输入 | PASS | [运行日志](.aclt-flow/runs/20261003T104731Z-b7e84c46-profile/output.log) |
| 当前单机验证 | PASS | [运行日志](.aclt-flow/runs/20261003T104732Z-dbbbfffc-singlehost/output.log) |

## 自动采集的运行摘要

- 精确模型验证：Ran 13 tests in 0.325s
- 验证器规则与错误输入：Ran 24 tests in 0.534s
- 当前单机验证：PASS: 68 verification cases; worker input rejection and Python reference totals checked
- 当前单机验证：PASS: 12 multi-process scenarios; retries, late results, attempt limits, cleanup, and overwrite refusal checked
- 当前单机验证：PASS: 12 recovery scenarios; 13 actual coordinator SIGKILLs; maximum observed live workers=2
- 当前单机验证：PASS: 90 batch cases; 72 randomized SIGKILLs; groups={'atomic-write-interruption': 4, 'concurrent-recovery': 4, 'damaged-record': 29, 'injected-storage-error': 15, 'kernel-storage-error': 11, 'publication-regression': 3, 'random-interruption': 24}
- 当前单机验证：PASS: 22 lifecycle scenarios; permanent outcomes, authoritative snapshots, recovery limits and deadlines
- 当前单机验证：PASS: 55 single-host quota, task-binding and boundary scenarios
- 当前单机验证：PASS: 204 exact datasets, 408 mutated results, 20 sanitizer runs, 12 malformed inputs, 22 Rust/C++ reducer vectors

## 自动待办

- 需要决定：正式任务在哪一步永久结束？（负责人：待指定；依据：核对正式规范与本地发布规则）。
- 需要决定：正式流程采用哪份权威记录恢复？（负责人：待指定；依据：当前只有本地快照，尚非正式日志协议）。
- 需要决定：正式资源账本包含哪些消耗？（负责人：待指定；依据：现有比较单位和文件配额只有局部覆盖）。

规范 Type A：119 项；声明已实现 3，部分实现 5，未实现 111。

测试通过不会自动把任何规则改成完整实现，亦不会关闭 Gate。

## 决策登记

| 问题 | 状态 | 已选规则 |
|---|---|---|
| 正式任务在哪一步永久结束？ | OPEN | 待决定 |
| 正式流程采用哪份权威记录恢复？ | OPEN | 待决定 |
| 正式资源账本包含哪些消耗？ | OPEN | 待决定 |
