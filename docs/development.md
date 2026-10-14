# 开发与维护入口

> 更新：2026-10-14。工程操作指南；不改变协议语义、Gate 或历史证据。

## 统一入口

从仓库根目录运行。Python 检查仅使用标准库；单机实验需要 Linux、GNU Make、Bash、C++17 编译器及匹配环境规范的 Rust/Cargo。工具版本和 sanitizer 要求见[ENV-1](08-governance/environment-standard.md)。

| 入口 | 工作 | 边界 |
|---|---|---|
| `make check` | 模型、配置、流程与交付回归测试，加清单检查 | 不编译或启动 VM |
| `make test` | 上述检查、当前 state3 单机实验及多节点本地检查 | 含 sanitizer；不包含 VM 故障注入 |
| `make test-singlehost` | 仅当前 Rust/C++ 实验 | 不含 Python 模型/流程组 |
| `make test-multinode` | admission 本地检查及消息顺序 | 报告默认在 `artifacts/multinode/`，不启动 VM |
| `make workflow` | 按输入指纹执行分组并留存证据 | 已通过且未变化的分组可复用 |
| `make status` | 更新进度看板 | 不运行测试 |
| `make manifests` | 显式更新当前交付校验清单 | 先审阅源码变更，再审阅清单差异 |
| `make check-manifests` | 只读校验文件内容和输入清单 | 新增交付输入也会使清单失效 |
| `make package PACKAGE=/new/path.zip` | 校验后生成增量更新包 | 不自动更新清单；拒绝覆盖同名文件 |

`bash scripts/run-singlehost.sh` 保留为原有单机全量入口（Python 分组、校验与 state3）。`python3 scripts/aclt-flow.py run --force` 可强制重跑证据流程。Make 默认只显示帮助，不使用 sudo。

源码修改后，先检查变更，再运行 `make manifests`，然后执行对应检查。刷新清单不能代替测试；交付脚本变化后运行 `make check` 和打包回归测试。

## 目录职责

| 位置 | 职责 |
|---|---|
| `docs/00-overview` 至 `docs/08-governance` | 当前规范、研究、状态和治理；权威映射见[文档中心](README.md) |
| `schemas/`、`registries/` | Schema、唯一覆盖登记和固定注册种子 |
| `tools/`、`tests/verification_profile/` | 验证配置实现及测试 |
| `tests/verification_model/` | 独立数学模型与精确对拍 |
| `scripts/`、`tests/workflow/`、`.aclt-flow/template.json` | 统一维护、交付与证据流程 |
| `experiments/aclt-minimal-verifier-state3/` | 当前单机参考实验 |
| `experiments/aclt-multinode-admission/` | 预登记身份的持久接纳原型 |
| `docs/testing/`、`docs/workflow/example/` | 历史证据和示例，不是本次 PASS |
| `docs/codocs/`、两个旧单机实验目录 | 历史版本，保留原路径与证据 |

旧单机版本不参与当前统一检查，不合并其代码或历史测试计数。多节点原型具有不同的模拟身份与持久接纳边界，保留独立模块；统一的是执行入口与证据登记。见[实验索引](../experiments/README.md)。

生产与测试 registry 的 Cargo 缓存分别位于 state3 的 `build/cargo-deployment` 与 `build/cargo-test-registry`。现有 `target/debug/` 程序入口保留；不覆写 Cargo 管理的缓存二进制。统一脚本显式选择构建目录，不使用外部 `CARGO_TARGET_DIR` 改写这两个目录。

## 清单与更新包

文件选择与过滤集中在 `scripts/repository_files.py`。`update-manifests.py` 负责更新/校验，`package-singlehost.py` 使用同一清单并验证归档内容。

四份清单分别覆盖 state3、多节点、工作流和更新包。刷新按依赖顺序进行。更新包保留原命名接口，包含两个当前实验、脚本、模型与配置测试、注册种子、使用文档及 LICENSE；不包含旧实验和 `docs/codocs/`。它是叠加到现有 checkout 的更新包，不能替代完整仓库或删除接收方旧文件。完整源码交付使用 Git checkout/归档。

默认输出 `dist/aclt-singlehost-update.zip` 和同名 `.sha256`。输出已存在、清单失效或交付输入为符号链接时拒绝打包；不会自动重签源码。中途失败的产物需要审查后另行处理。

本地产物放在 `artifacts/`、`build/`、`target/`、`dist/`、`.toolchain/` 和 `.aclt-flow/runs/`，不交付为源码。工作流历史示例中已保存的 `build/`、`artifacts/` 是证据例外。

## 变更与交付

按[贡献说明](../CONTRIBUTING.md)同步规范和不变量。结构维护不得改写协议语义或静默删除历史失败。报告记录基线、修改文件、真实检查结果及未覆盖项；提交、推送和发布按明确授权执行。局部检查通过不表示 Gate 退出或主网可用。
