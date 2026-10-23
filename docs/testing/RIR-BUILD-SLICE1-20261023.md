# RIR 构建切片 1：Rust → Wasm 双机可复现性（2026-10-23）

结论：最小 no_std 空 run 程序在两台物理主机、每台两个新目录内共四次独立构建成功，原始 Wasm、限定后处理的 Wasm 与候选工件均逐字节相同。这里只验证候选 lowering 构建可行性，不是 RIR validator/RPR、通用 Rust lowering 或 stats-int-v1 的实现验收。

基线 `677f244cb289a8b1432ec9ace4803d9deb331ea8`；使用当前 ADR-0006 PROPOSED 候选作为可行性实验输入，不将它作为已接受规范或 conformance 权威。源程序、候选工具及原始证据在操作者本地 `<EVIDENCE_ROOT>/rir-build-slice1-20261023/`，不改写此前审阅/测试记录。没有运行 VM。

## 工具链与环境

两端原有 Ubuntu rustc/Cargo 保持不变。系统 sysroot 仍缺少 wasm32v1-none；本轮在各自实验目录内安装官方 Rust 1.93.1（2026-02-12 发布）独立 prefix：rustc、x86_64 标准库与 wasm32v1-none 库。rust-lld 随官方 rustc 组件提供，显式选择其路径，避免混用系统版本。未安装 rustup、未改 PATH/系统包、未执行 sudo。

官方来源：[wasm32v1-none 目标说明](https://doc.rust-lang.org/rustc/platform-support/wasm32v1-none.html)、[1.93.1 发布清单](https://static.rust-lang.org/dist/channel-rust-1.93.1.toml)。三个下载包均匹配该清单中的 SHA-256；清单摘要及组件版本/URL/摘要保存在 toolchain-lock.json。HTTPS 获取和本地摘要核对不是独立第三方签名审计。

两端都从源码运行自己的编译器/链接器，不拷贝 A 的已编译结果到 B 作为构建输入。编译器与 linker 文件摘要、工具链 lock、源码摘要和 rustc verbose 在 A/B 匹配。两端使用同一供应商/版本工具链，不构成独立编译器实现验证。

## 源程序与编译约定

- 用户库：`#![no_std]`、`#![forbid(unsafe_code)]`，只提供安全 `entry()`，无依赖、无堆分配、无输入输出。
- 单独受信入口层：导出 `run: [] → []`，调用用户入口并提供 panic handler。导出属性 `#[unsafe(no_mangle)]` 位于该层；这不是向用户库开放 unsafe。
- 目标 wasm32v1-none；edition 2021、opt-level=s、panic=abort、debuginfo=0、单 codegen unit；链接阶段 fat LTO、无 start entry、显式 run 导出、栈 65,536 字节、内存 min=max=2 页。
- 编译命令、源码路径 remap 与每一步 stdout/stderr 均保存。使用 rustc 直接构建两个 crate，不使用 Cargo，因此没有 Cargo.lock；无第三方 crate。

实际发现：用户 crate 同时使用 forbid(unsafe_code) 和导出 no_mangle 属性会编译失败。两端均保存该预期失败诊断，不能把链接符号导出当成受禁属性以外的隐式例外。后续完整 SDK/Profile 仍需明确受信入口、允许属性和依赖闭包；本轮不冻结这些规则。

## 后处理与候选工件

原始模块 260 字节。编译器额外导出 __data_end、__heap_base，并附加 name、producers、target_features 自定义段。

本轮版本化限定后处理 `aclt.rir.empty-run-lowering@1`：

1. 仅识别实际最小模块结构；严格要求一个空 run、无 import、整数常量 global、两页有 max 内存；遇到其他函数体或未知结构直接拒绝，不伪装为通用 validator。
2. 移除上述三个已知自定义段和两个已知辅助 global 导出，记录移除清单；保留内部 globals、内存及 run 语义。未知导出/未知自定义段不静默删除。
3. 对该限定结构核对最短 LEB 和重编码，得到 72 字节 Wasm，仅有 run 和 memory 导出，无导入、自定义段或 start。
4. 候选外壳采用 ADR 字段名作 text wire keys，SemVer=[0,1,0]、input_arity=0，按候选 CBOR 键编码字节顺序编码为 171 字节；以 ACLt/RIR-0/Artifact/1 域计算候选 rir_digest。该 wire-key 选择仍是实验合约，不是正式 Schema/完整编码实现。

| 产物 | SHA-256 / 候选域摘要 |
|---|---|
| 原始 Wasm（四次相同） | 211c4d8dd586f47d665c65ae0e46cfceb2f89627d6c9df50a5fdb95981847ccf |
| 后处理 Wasm（四次相同） | 028500823203e069891ca3b3b80bced8d54f7333217d2e9af369b3f348d5e3f5 |
| 候选 rir_digest（四次相同） | 430a1314d303e8c35fc9291b6ab49335df22d187a424fb9c36f2c10ebf465aff |

## 检查与证据

- 四次独立构建和跨机逐字节比较通过；A/B 各一个预期用户导出编译失败探针。
- 现有 Node WebAssembly 引擎对回收的四份 raw 和四份 normalized 文件共 8 份模块分别验证、实例化和调用 run，均正常返回，内存为 131,072 字节。引擎只作为本地现有结构/执行 oracle，没有新增项目依赖，也不等于 RPR 或 gas 一致性验收。
- 限定适配器 78 项检查通过，覆盖 72 个截断前缀、有效但非空函数体、未知 section/custom/export 与幂等性/固定产物一致性；不是协议规则数或 RIR conformance 数。
- 原始模块、后处理模块、候选 CBOR、全部命令/退出诊断、下载摘要、源码摘要、移除清单和远端产物已保留；远端 prefix 与目录也保留供后续实验。
- 下载清单最初在受限沙箱内 DNS 失败；授权联网后下载成功，未绕过摘要验证。

本地证据文件：toolchain-lock.json、deployment-source-lock.json、build-report.json、normalization-report.json、remote-results/、comparison.json、wasm-engine-check.json、scope-check.json。脚本 get_toolchain.py、install_toolchain.py、run_probe.py、normalize_probe.py、deploy_remote.py 为本轮一次性可复查适配器，不是通用仓库构建入口；首次运行要求新目录，不能覆盖原证据。

## 保持开放与下一步

ADR-0006 保持 PROPOSED，P0-1B、G0/G2 不关闭。没有执行完整 RIR 22 向量、没有 gas、没有 Receipt/结算绑定，也没有 stats-int-v1 支持；no-op 成功不证明复杂 Rust 子集能落入候选范围。

下一切片先加入最小安全 SDK 与显式 input_read/output_write 路径，用一个可观察的输入→输出程序检验 imports、内存访问及候选指令集合；同时落实正式候选编码/validator 与解释器的最小接口，再推进整数统计负载。两台主机重新独立构建和运行，不继承本轮源码摘要作为新切片证据。

## 同日收尾：仓库维护入口与范围验收完成

前文的一次性探针记录原样保留；现已将本切片整理为 [仓库实验入口](../../experiments/aclt-rir-build-probe/README.md)，含固定工具链 lock、离线安装器、用户库与受信入口、显式参数构建器、限定后处理、证据比较器和 10 项纯 Python 回归。新增目录已纳入源码交付清单，make check 自动执行其回归；构建仍须显式提供工具链和新输出目录。

维护入口在两台机器重新各构建两次，独立离线安装器也分别执行通过；四组 raw、normalized 与候选工件均相同，候选 rir_digest 与首次探针相同。保存证据的重新运行被拒绝，原 PASS report 内容不变。收尾源文件摘要和结果见 [机器摘要](rir-build-slice1-closeout-20261023.json)，完整原始证据由操作者保留在 `<EVIDENCE_ROOT>/rir-build-slice1-closeout-20261023/`。已有的 74 项回归加本轮 10 项回归共 84 项；交付清单与覆盖盘点通过。

第一个切片在“最小构建可行性＋可复用入口＋真实双机复现＋保留失败/拒绝覆盖”的范围内完成。ADR 仍 PROPOSED，未把切片完成升级为 G0/G2 或 RIR conformance。下一切片继续为显式输入输出 SDK/执行路径。
