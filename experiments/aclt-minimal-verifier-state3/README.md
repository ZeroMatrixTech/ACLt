# state3：严格单机局部回归

当前入口是 `bash scripts/run-ubuntu.sh`。它执行 68 个基础用例、strict、strict-adversarial 和 Rust/C++ 差分/资源检查；以运行日志为准。旧的 265 合计含当前不再调用的恢复/生命周期脚本，不是当前门禁计数。

当前策略见 [STRICT-POLICY.md](docs/STRICT-POLICY.md)：每项资格只消费一次，MAX_ATTEMPTS=1，MAX_RECOVERIES=0；`resume` 始终拒绝，不提供恢复计算入口。单机回归不替代物理双机部署证据，也不关闭任何协议 Gate。

```sh
bash scripts/run-ubuntu.sh
# 配置新的本地资格 registry，按 STRICT-POLICY.md 使用当前 CLI。
target/debug/coordinator init-registry REGISTRY
# 计算前需有合法、空闲且受支持的 registry。
target/debug/coordinator examples/input.txt 4 build/worker NEW_RUN normal 500 1 REGISTRY
```

部署编译产物 `build/coordinator-deployment` / `build/worker` 不包含测试环境钩子。`test-faults`（Rust）和 `ACLT_ENABLE_TEST_FAULTS`（C++）显式开启故障注入；独立的 `admission-test-registry` 只用于测试 registry root。runner 在隔离目录构建测试变体，部署产物不被覆盖。即使部署构建是 debug，也不会读取故障变量。

保留的 `scripts/check-{recovery,lifecycle,processes,batch,singlehost}.py` 是历史测试资产，依赖旧恢复语义，未接回当前门禁。原始 [恢复报告](docs/RECOVERY-REPORT.md)、[阶段报告](docs/STAGE-REVIEW.md)、[批次报告](docs/BATCH-REPORT.md)保留其时间范围；不能按旧命令重开已消费资格。历史源实现也只作归档，不是新的执行授权路径。

当前验证器完整重算结果；无速度/成本优势、身份独立性或敌对宿主隔离保证。校验和用于发现意外变化，不防拥有运行目录者的持续恶意改写。后续集成遵循 [双物理机 SSH 约定](../../docs/08-governance/dualhost-ssh-validation.md)。
