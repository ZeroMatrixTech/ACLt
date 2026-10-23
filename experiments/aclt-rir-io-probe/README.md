# RIR 切片 2：安全 SDK 与 16 字节 I/O 候选执行链

候选实验，ADR-0006 仍为 PROPOSED。负载固定为一个 16 字节输入原样输出；不提供 stats-int-v1、正式 Receipt/Lease、结算、通用 RIR conformance 或生产 RPR。

`src/program.rs` 是 no_std / forbid(unsafe_code) 用户库。`src/sdk.rs` 只在受信 FFI 边界使用 unsafe，把输入复制到可写借用切片，从只读借用切片追加输出；5 个导入精确绑定 aclt.input_count/input_len/input_read/output_write/abort。`src/entry.rs` 单独负责受信导出属性与 panic handler。SDK 和入口都纳入构建来源摘要；本轮不冻结完整 Rust Profile 的依赖/unsafe 允许集合。

## 入口

使用切片 1 的同一官方 Rust 1.93.1 prefix 和 [离线安装器](../aclt-rir-build-probe/README.md)。本目录 lock 继续锁定相同组件及目标库。

```bash
make check-rir-io-probe
make test-rir-io-probe \
  RIR_TOOLCHAIN=/absolute/path/to/toolchain \
  RIR_IO_OUTPUT=/absolute/path/to/new-run
```

构建器在两个新位置分别编译 SDK、用户库与入口，核对/规范化 Wasm，封装候选 CBOR，执行每份工件的 55 个固定用例。`report.json`、每份 inspection.json / execution.json 和原始日志随新目录保留；已有目录一律拒绝覆盖。构建失败保留 FAIL report。

单独运行一个保存工件：

```bash
python3 -B experiments/aclt-rir-io-probe/execute.py \
  --artifact /path/to/new-run/first-location/candidate-artifact.cbor \
  --input /path/to/input-16-bytes.bin --report /path/to/new-result.json
```

TASK_OUTCOME 返回 0，记录 OK/ABORT/确定 trap；创建期 REJECTED 返回 2；HOST_FAULT 返回 3。非 OK 不发布部分输出。输入数量与工件固定 input_arity=1 不符，先拒绝，不能靠程序内部 abort 代替绑定。用例中标为 unbound-module-ABI-probe 的两项专门跳过外壳，只测试 input_count 的程序分支，不算合法绑定工件。

双机：A/B 从同一源码和 lock 分别构建、执行，再回收 B 目录到 A：

```bash
python3 -B experiments/aclt-rir-io-probe/compare.py \
  /path/to/A-run /path/to/B-collected-run --report /path/to/new-comparison.json
```

比较器重算 raw/normalized/候选工件/执行记录摘要，检查四组结果及来源一致。现有 Node 可作为可选的独立语义 oracle：

```bash
node experiments/aclt-rir-io-probe/oracle.cjs \
  /path/to/A-run /path/to/B-collected-run /path/to/new-oracle-report.json
```

oracle 只核对真实 Wasm 引擎中的输出、abort 和输出限额，不核对 gas、调用深度或外壳/输入绑定。Node 不是默认测试或执行器依赖；B 不需要安装 Node。

## 限定检查与执行能力

- 仅支持整数、void 控制块、直接调用、固定两页内存、少量已列出的 load/store/算术；解析后做该子集的操作数/局部变量/全局变量/调用类型检查。未知结构/指令拒绝，不能静默跳过。
- 原始 rustc 产物有补长调用/全局索引 LEB；后处理重新编码为最短形式，合并 locals、去掉已知自定义段和辅助导出。执行前再次核对外壳和 Wasm canonical 字节。
- 候选外壳文本键、SemVer=[0,1,0]、input_arity=1；它仍是本地实验合约。外壳最多 1 MiB、嵌套 16，控制嵌套 128、定义函数最多 32；这些保守限制小于完整 ADR 候选范围。
- Python 解释器按候选成本表计量；正常 fixture 的 gas=8271 有单独逐指令核算。实例化成本 8192；宿主先 gas、后地址、再输出额度。数学加法不回绕，失败无部分复制/追加。
- Host 本地步数上限只产生 HOST_RESOURCE_EXHAUSTED，不冒充 Task gas 耗尽。普通用户进程仍未构成恶意代码生产沙箱。

19 项纯 Python 回归纳入 make check；55 个执行用例包括固定/随机字节、绑定拒绝、ABORT、gas、限额、深度与宿主故障，不等于 55 条协议规则。两端使用相同 Python 实现；现有独立 Wasm 引擎的语义对拍不证明 Python gas 正确，更不替代后续 Rust 解释器/完整双实现 conformance。结果见 [实测报告](../../docs/testing/RIR-IO-SLICE2-20261023.md)。
