# RIR 构建切片 1：最小空 run 探针

候选实验，跟踪 ADR-0006（PROPOSED）。只验证 Rust→Wasm→限定后处理→候选 CBOR 工件的构建可复现性；不实现通用 RIR validator、RPR、gas、stats-int-v1 或 Receipt。

用户库 `src/program.rs` 保持 no_std / forbid(unsafe_code)。`src/entry.rs` 是单独受信入口，只有该层使用 unsafe(no_mangle) 导出符号。它不是给用户源代码开放 unsafe。探针包含直接在受禁用户库中导出的预期编译失败。

## 工具链

固定 Linux x86_64 官方 Rust 1.93.1、wasm32v1-none 库及随编译器提供的 rust-lld。`toolchain-lock.json` 锁定官方组件 URL/SHA-256、编译器/链接器二进制和目标库摘要；构建入口会核对后两者。无需 Cargo、rustup、第三方 Python 库或 root 权限，不修改系统 Rust。

已有匹配工具链可直接指定 prefix。新安装时，先将 lock 中的三个官方压缩包下载到独立目录（也可由操作者离线提供），然后运行：

```bash
python3 experiments/aclt-rir-build-probe/install_toolchain.py \
  --downloads /absolute/path/to/downloads \
  --prefix /absolute/path/to/new-toolchain
```

安装器不联网，先核对全部压缩包再解包安装，保留相邻 `.unpacked` 目录和安装日志，拒绝覆盖已有 prefix 或解包目录。原始清单/URL 位于 lock；本地摘要不是独立可信签名。

## 构建与比较

从仓库根运行：

```bash
make check-rir-build-probe
make test-rir-build-probe \
  RIR_TOOLCHAIN=/absolute/path/to/toolchain \
  RIR_OUTPUT=/absolute/path/to/new-evidence
```

等价构建命令：

```bash
python3 -B experiments/aclt-rir-build-probe/build.py \
  --toolchain /absolute/path/to/toolchain \
  --output /absolute/path/to/new-evidence
```

每次在两个新位置独立编译，记录命令、源文件/工具链摘要、原始和后处理 Wasm、候选工件、移除清单及预期错误诊断。输出目录存在即拒绝；失败保留现场及 FAIL report，不自动删除重跑。

在两台物理主机分别执行同一源码与 lock，回收 B 的证据目录到 A，再运行：

```bash
python3 -B experiments/aclt-rir-build-probe/compare.py \
  /path/to/A-evidence /path/to/B-collected-evidence \
  --report /path/to/new-comparison.json
```

比较器重新散列四组保存产物，核对来源、工具链、候选域摘要和跨机一致性，拒绝覆盖比较结果。主机名不同只是观测条件，物理独立仍沿用 DUALHOST-SSH-1 的有限实验假设。SSH 地址、用户名、工具链路径均由操作者指定，不进入源码。

后处理只支持固定的空 run 模块形状，移除 name/producers/target_features 和已知辅助 global 导出；其他指令、导出或未知结构直接拒绝。候选外壳用文本字段键、SemVer 三元数组、input_arity=0，不是正式 wire contract。

`make check` 包含本目录 10 项纯 Python 回归；它不自动下载工具链或运行跨机构建。工具链、下载包和运行产物应放仓库外，或仓库的 artifacts/、.toolchain/ 等不交付目录。首次实测及收尾证据见 [报告](../../docs/testing/RIR-BUILD-SLICE1-20261023.md)。切片 1 的完成只限此范围，不关闭 ADR 接受或协议 Gate。
