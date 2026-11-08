# 开发与维护入口

> 更新：2026-11-08。工程操作指南；不改变协议语义、Gate 或历史证据。

## 统一入口

从仓库根目录运行。Python 检查仅使用标准库；单机实验需要 Linux、GNU Make、Bash、C++17 编译器及匹配环境规范的 Rust/Cargo。工具版本和 sanitizer 要求见[ENV-1](08-governance/environment-standard.md)。

| 入口 | 工作 | 边界 |
|---|---|---|
| `make check` | 模型、配置、流程与交付回归测试，加清单检查 | 不编译或启动 VM |
| `make test` | 上述检查、当前 state3 单机实验及多节点本地检查 | 含 sanitizer；不包含 VM 故障注入 |
| `make test-singlehost` | 仅当前 Rust/C++ 实验 | 不含 Python 模型/流程组 |
| `make test-claim-codec` | 候选模板/claim 编码 Python/Rust 对拍 | 需要 Unicode 16.0.0、rustc、OpenSSL；不代表完整 P0-1B |
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

四份清单分别覆盖 state3、多节点、工作流和更新包。刷新按依赖顺序进行。更新包保留原命名接口；自 2026-11-05 起文件选择以 `DELIVERY-SCOPE.json` 为准，包含全部受管源码输入及历史 state1/state2、`docs/codocs/`（见下文“有界修复后的门禁与交付”），2026-10-14 版“不含旧实验和 codocs”的范围已被替代。解包到新目录可独立运行本地检查；叠加到已有 checkout 时不会删除接收方旧文件。Git 源码 pin 校验（`make verify-source`）仍需完整 Git checkout。

默认输出 `dist/aclt-singlehost-update.zip` 和同名 `.sha256`。输出已存在、清单失效或交付输入为符号链接时拒绝打包；不会自动重签源码。中途失败的产物需要审查后另行处理。

本地产物放在 `artifacts/`、`build/`、`target/`、`dist/`、`.toolchain/` 和 `.aclt-flow/runs/`，不交付为源码。工作流历史示例中已保存的 `build/`、`artifacts/` 是证据例外。

## 变更与交付

按[贡献说明](../CONTRIBUTING.md)同步规范和不变量。结构维护不得改写协议语义或静默删除历史失败。报告记录基线、修改文件、真实检查结果及未覆盖项；提交、推送和发布按明确授权执行。局部检查通过不表示 Gate 退出或主网可用。

## 外置权威账本实验（v2）

`make test-authority` 使用临时回环网络、OpenSSL 与现有 C++ worker 检查接纳端回滚和复制边界，报告在 `artifacts/authority/`。`make test` 与流程已接入；QEMU 验证单独运行，外部运行时与证据不随源代码包分发。详见[实验说明](../experiments/aclt-authority-admission/README.md)。

## 当前后续验证环境：双物理机 SSH

自 2026-10-23 起遵循 [DUALHOST-SSH-1](08-governance/dualhost-ssh-validation.md)。本地入口继续提供各自范围的回归，部署/网络/故障结论须来自真实双机运行；不再默认运行 VM 矩阵。下一轮优先为外置权威账本 v2 建立跨机驱动和证据核对，不将 SSH 连通当作分布式实验通过。

双机第 1 轮已完成，见 [环境与双机实测报告](testing/DUALHOST-SSH-20261023.md)。当前驱动为保存在工作区产物中的一次性适配器，尚未新增通用 make 双机目标；下一轮先做角色互换与 worker 中断，再整理参数化入口。

## RIR 构建切片 1 的维护入口

[最小构建探针](../experiments/aclt-rir-build-probe/README.md)已入库；`make check-rir-build-probe` 运行 10 项纯 Python 回归，纳入 `make check`。`make test-rir-build-probe RIR_TOOLCHAIN=/prefix RIR_OUTPUT=/new/path` 使用固定离线工具链生成新证据；`compare.py` 对账两台主机的四组构建。默认检查不自动安装工具链或连接远端；所有运行目录均拒绝覆盖。

## RIR 切片 2 的维护入口

[安全 SDK 与 I/O 探针](../experiments/aclt-rir-io-probe/README.md)：`make check-rir-io-probe` 运行 19 项纯 Python 回归；`make test-rir-io-probe RIR_TOOLCHAIN=/prefix RIR_IO_OUTPUT=/new/path` 独立编译两次并执行固定用例；`execute.py` 可单独运行一个保存的候选工件。所有命令显式选择新输出，错误分类保留。可选现有 Node oracle 只对拍语义，不对拍 gas。

## RIR 切片 3 的维护入口

[整数统计探针](../experiments/aclt-rir-stats-probe/README.md)：`make check-rir-stats-probe` 运行 14 项局部回归；`make test-rir-stats-probe RIR_TOOLCHAIN=/prefix RIR_STATS_OUTPUT=/new/path` 编译两次并比较 Python/Rust 执行和 C++ 基准。编译与原始证据留在显式新目录，前两切片保持独立。Rust 执行器直接解码 Wasm，但要求 Python 预验证，不能代替完整 conformance。双机通过范围见 [报告](testing/RIR-STATS-SLICE3-20261023.md)。

## 第一项工作（三切片）的统一入口

`make test-rir-work1 RIR_TOOLCHAIN=/prefix RIR_WORK1_OUTPUT=/new/host-run` 在一台主机依次重建三个切片；两台物理机分别运行后，用 `scripts/rir-work1.py verify --slice1 A1 B1 --slice2 A2 B2 --slice3 A3 B3 --report /new/report.json` 核对保留证据与当前源码。它不自动联网/安装、不覆盖旧产物；详细范围与下一项见 [总收尾报告](testing/RIR-WORK1-CLOSEOUT-20261023.md)。

## 第二项工作切片 1：候选最小任务承诺

[aclt-task-commitment](../experiments/aclt-task-commitment/README.md)提供显式候选 schema/CBOR、experimental_task_id 与绑定探针。`make check-task-commitment` 运行 19 项局部回归；`make test-task-commitment TASK_COMMITMENT_OUTPUT=/new/path` 保存每机证据，再用 `compare.py` 比较双机。CLI freeze 要求所有上限显式给定；execute-probe 不允许覆盖冻结上限且明确没有授权。见 [本轮报告](testing/TASK-COMMITMENT-SLICE1-20261023.md)。

## 第二项切片 2：实验授权与启动边界

[aclt-task-authorization](../experiments/aclt-task-authorization/README.md)接入签名 grant、调度/启动双检查、单一在线消费账本和持久启动意图。`make check-task-authorization` 及默认检查需要已有 OpenSSL，新增 24 项无网络回归。真实双机矩阵必须显式调用 `dualhost.py`，使用全新本地/远端目录与严格 SSH 主机密钥检查；它会启动并清理本轮测试服务/进程。范围与下一切片见 [报告](testing/TASK-AUTHORIZATION-SLICE2-20261024.md)。

## 第二项切片 3：因果记录与完整包重传

[aclt-task-replay](../experiments/aclt-task-replay/README.md)新增独立实验部署，保留旧实验源文件。`make check-task-replay` 新增 26 项本地回归，该片完成时默认合计 191 项，依赖已有 OpenSSL/Python/SQLite。显式双机入口使用全新目录，实际 LAN 走 CHECK/CONSUME/SUBMIT；正常 `replay` 仅重传封存包，`offline.py` 仅检查导出证据并要求调用者另存 key/checkpoint digest。不得把不完整状态自动续算，或把实验接纳解释成正确性/TRUSTED。字段、恢复规则、依赖与复现见 [报告](testing/TASK-REPLAY-SLICE3-20261024.md)。

## 第二项工作统一收尾入口

`make test-task-work2` 显式使用现有 SSH、LAN 和全新两端目录，重跑承诺、授权及因果重放三个切片；`scripts/task-work2.py verify` 只核对保存证据，需要独立留存的 key/checkpoint pin，不连接 B 或重新执行任务。五项收尾工具回归纳入默认检查（当时合计 196 项）；原三个实验源码保持不变。完整命令、证据布局、恢复边界与交接见 [维护入口](testing/TASK-WORK2-MAINTENANCE.md) 和 [总报告](testing/TASK-WORK2-CLOSEOUT-20261024.md)。

## 第三项切片 1：资金政策与预留

`make check-funding-reservation` 运行新增 22 项本地回归，该片完成时默认合计 218 项，使用既有 Python/SQLite/OpenSSL。真实 LAN 矩阵显式运行 [实验目录](../experiments/aclt-funding-reservation/README.md)的 `dualhost.py`，仅全新目录，A 为单一测试资金账本、B 为请求端。`audit.py` 按独立保存的 key/checkpoint pin 只读重建账目。没有真实资金、付款/退款或旧执行入口资金门禁；字段、恢复边界和证据见 [报告](testing/FUNDING-RESERVATION-SLICE1-20261024.md)。

## 第三项切片 2：固定结算实验入口

`make check-fixed-settlement` 新增 26 项局部回归，该片完成时默认合计 244 项，不联网。独立 [v2 实验](../experiments/aclt-fixed-settlement/README.md)提供 `executor.py execute|submit`、`client.py settle|status` 和只读 `audit.py`；真实双机矩阵显式使用全新目录、严格 SSH 和实际 LAN。比较/费用在执行前冻结，完整报告重传不续算；旧执行/账本入口不迁移。恢复与信任边界见 [报告](testing/FIXED-SETTLEMENT-SLICE2-20261024.md)。

## 第三项切片 3：结算恢复入口

`make check-settlement-recovery` 新增 16 项局部回归，该片完成时默认合计 260 项，不联网。独立 [恢复 wrapper](../experiments/aclt-settlement-recovery/README.md)保留原 v2 转移/审计，`client.py recover` 只发 STATUS；fault_driver/服务 test-control 仅显式测试使用。真实双机矩阵采用全新目录和严格 SSH，验证实际丢回复/自有进程 SIGKILL 与原权利恢复；9 份 checkpoint 可由原 auditor 只读复核。命令/范围见 [报告](testing/SETTLEMENT-RECOVERY-SLICE3-20261024.md)。

## 第三项工作统一收尾入口

`make test-funding-work3` 在全新两端根中显式重跑预留、固定结算和恢复三组真实 LAN 矩阵；`scripts/funding-work3.py verify` 只复核保存源码/证据及 11 个 checkpoint，不连接 B、不执行 guest。新增 5 项工具回归，默认合计 265 项，三个实验源码保持原字节。参数、独立账本边界及恢复规则见 [维护入口](testing/FUNDING-WORK3-MAINTENANCE.md) 和 [总报告](testing/FUNDING-WORK3-CLOSEOUT-20261024.md)。

## B/Q 边界模型（2026-10-26）

`make check-bq-boundaries` 运行 11 项本地确定性回归，已纳入 `make check`。`make test-bq-boundaries BQ_REPORT=/existing-parent/new-report.json` 重跑八个精确人工见证并保存源码 pin，现有报告拒绝覆盖。使用现有 Python 标准库，无下载、网络、guest 或数据库；不是部署 B/Q 校准。原数学内核保持不变，边界与后续研究见 [BQ-W4-S1](06-research/bq-boundaries-slice1.md)。

## B/Q 固定样本校准研究（2026-10-26）

`make check-bq-calibration` 新增 14 项确定性回归并纳入 `make check`；`make test-bq-calibration BQ_CALIBRATION_REPORT=/existing-parent/new-report.json` 运行合成输入的条件校准与敏感性并保存源码/input pin，不覆盖旧报告。标准库、离线，无新依赖、guest、SSH 或数据库。只接受显式 synthetic 研究数据，不估现实 B/Q，不支持边看边加样本；详见[研究边界](06-research/bq-calibration-slice2.md)。

## B/Q 证据审阅研究（2026-10-26）

`make check-bq-readiness` 纳入 18 项回归；`make test-bq-readiness BQ_READINESS_REPORT=/existing-parent/new-report.json` 重现研究清单和创建/生命周期投影。只读显式夹具与既有工件摘要，无网络、时钟读取或 capability 写入，不是正式 phase validator。新报告拒绝覆盖；边界见[第三片正文](06-research/bq-readiness-slice3.md)。

## B/Q 三片统一入口（2026-10-26）

`make test-bq-work4 BQ_WORK4_OUTPUT=/existing-parent/new-run` 重算三片并核对统一源码/原始报告/跨片边界；`python3 -B scripts/bq-work4.py verify --evidence /saved/run --report /new/report.json` 在临时目录重算核对，原证据只读。新增 5 项工具回归纳入默认 `make check`。全部离线，无新运行能力；范围与交接见[收尾报告](testing/BQ-WORK4-CLOSEOUT-20261026.md)。

## 正式迁移 FM-S1a 开工入口（2026-10-26）

[ADR-0007](05-decisions/ADR-0007-formal-object-migration-foundation.md) 已接受六项首轮路线，字段和实现分别验收；下一切片按 [FM-S1a](07-roadmap/formal-migration-plan.md) 开始共享编码与最小角色签名代码/向量，不另建总规划。先复用现有 P0-1B codec 并审查其候选 wire/import 限制，精确 suite/envelope 必须由向量固定；Python/Rust 独立、OpenSSL 依赖边界、拒绝行为与覆盖 owner 均需交付。当前无新代码/软件安装/双机运行，ADR-0006/Gate/现有对象 Schema 状态不变。

## FM-S1a 编码与签名维护

`make check-fm-s1a` 为默认回归的一部分；`make test-fm-s1a FM_S1A_REPORT=/new/report.json` 构建独立 Rust，核对固定字节/Schema View/摘要/签名及新密钥签署。完整本地入口 `make test` 包含该对拍。跨机运行按[候选合约](../schemas/formal-migration/README.md)中的显式 SSH 驱动，输出目录和远端目录必须新建；IP/用户名只保存在操作者产物。工具只输出测试身份有效性，不授权 Receipt/Lease/账务，不关闭 P0-1B 或 G2。

## FM-S1b 政策与 Receipt 维护

`make check-fm-s1b` 纳入默认检查，`make test-fm-s1b FM_S1B_REPORT=/new/report.json` 构建独立 Rust 并对拍全部费用格、旧引用/重绑定及签名。跨机驱动为 `scripts/fm-s1b-dualhost.py`，沿用严格 SSH/new-directory 规则；详见[候选合约](../schemas/formal-migration/policy.md)。报价只返回预算内候选金额，不触碰数据库或授予执行/结算权利。

## RIR 独立核心维护

`make check` 包含新增 12 个受限核心回归方法；`make test-rir-independent RIR_INDEPENDENT_REPORT=/new/report.json` 构建无 Python 预验证的 Rust 入口并核对原始结果字节/摘要。完整 `make test` 包含该入口。跨机命令见[独立核心说明](../experiments/aclt-rir-stats-probe/INDEPENDENT-CORE.md)，严格 SSH 和全新目录要求不变。原 executor/build/runtime/wasm/cases 及历史证据不覆盖；本入口不是正式 RPR 准入。

## FM/RIR 保留证据检查

`make check-migration-evidence` 检查三份摘要和 audit 依赖映射，不执行旧源码或声称新的双机运行。精确 Git blob 校验及临时目录重放使用[证据说明](testing/MIGRATION-EVIDENCE-20261028.md)中的显式 `--repository`/`--replay` 命令。校验源码 revision 与当前源码重跑是不同操作；不要为让历史摘要通过而刷新其源码 SHA。

## FM-S2 限定集成

`make check-fm-s2` 运行离线状态机、签名、竞争、固定向量与快照回归，不连接远端。显式 `make test-fm-s2 FM_S2_PEER=user@B FM_S2_A_HOST=A_LAN_IP FM_S2_REMOTE_ROOT=/new/B/path FM_S2_OUTPUT=/new/A/path` 创建全新双物理机测试部署。复核公共快照使用 `scripts/check-fm-s2-evidence.py`，必须提供带外保存的 genesis；详见[本轮报告](testing/FM-S2-20261031.md)与[候选合约](../schemas/formal-migration/execution.md)。所有正式准入/结算保持关闭。

## 2026-11-05 有界修复后的门禁与交付

`make check` 保持轻量本地检查，新增环境/文档/证据元数据与测试控制帧回归；以本次日志为准，前文各片总数均为当时快照。`make test` 才构建 Rust/C++、跑独立对拍、回环 HTTP 和 sanitizer；`make verify-source` 在含完整 Git 历史的 checkout 校验三份历史摘要的 52 项 pin 及 SOURCE-BASELINE 的 43 项 pin。元数据通过不能代替源码核对，源码核对不能代替重新执行。无 .git 的解包目录仍可校验清单并运行本地检查，Git 源码维度标为 NOT_RUN。

`DELIVERY-SCOPE.json` 明示完整源码交付范围，包含 AGENTS、历史 state1/state2、codocs 与 CI 配置；历史文件的入包不使其成为运行入口。已存在的受管文件不能藏在枚举之外。生成目录排除锚定在明确的实验构建路径；新增 tools/.../build/*.py 等源码仍会使旧清单失效。新文件和经审阅的删除可以先更新清单，未提交交付也可验收。

ZIP 使用固定 1980 时间、顺序、Unix 普通文件 0644 与 ZIP_STORED，避免墙钟、源文件 mtime/mode 和压缩库版本引入差异；源码体积稍大。ZIP 内 .sh 以 `bash` 调用，不靠可执行位。SHA 仅证明内容一致，发布来源签名/外部信任根仍未建立。

CI 配置只在 PR、main push 和手动触发时跑完整本地检查和打包重现，不含双机/VM。checkout 固定到 action revision、只读权限且不保留凭据；Ubuntu 镜像与 apt 来源版本仍非完整内容锁。入库不等于 GitHub 已执行，首次远端 CI 验收需在人工推送后观察。

预检固定已测 Python 3.14/Unicode 16.0.0、Rust/Cargo 1.93.1、G++ 15 与 OpenSSL 3.5；版本范围外明确拒绝，需单独重新验收。没有引入 rustup 或下载隐式依赖。state3 部署二进制与测试故障开关分离，旧恢复脚本未接回门禁。

## FM-S3a 签名结果局部切片

`make check-fm-s3-results` 运行固定候选审计合约、Receipt 重绑定、双角色签名结果与 S2 快照纯重放的本地回归；默认 `make check` 包含此入口。详见[报告](testing/FM-S3A-RESULTS-20261105.md)与[合约](../schemas/formal-migration/audit-results.md)。使用合成 outcome 字节，不产生新执行或双机证据；权威接纳、显式假设求值、终态和权利账务尚未接通。

## FM-S3b/S3c 候选权威、权利与 Task trap

上节“尚未接通”为 FM-S3a 当时状态。`make check-fm-s3-authority` 运行候选权威接纳、幂等与冲突、唯一终态、权利派生、COMMIT 中断恢复及 opt-in Task trap 的本地回归，默认 `make check` 包含此入口。显式双机运行 `python3 -B scripts/fm-s3-dualhost.py --peer <B_USER>@<B_IP> --a-host <A_IP> --remote-root /new/B/path --output /new/A/path`，加 `--task-trap` 使用固定除零工件；两端须为新目录，B 主机密钥严格校验；A/B 均用系统 rustc 构建同一执行器并比对摘要，脚本拒绝相同 hostname 的对端。A 同时承载权威与审计者，B 承载执行者。见[总体收尾](testing/FM-S3-CLOSEOUT-20261106.md)、[Task trap](testing/FM-S3-TASK-TRAP-20261106.md)与[接口规范切片](testing/FM-S3-INTERFACE-CLOSEOUT-20261106.md)。正式接口与准入仍未接通。

`make check-fm-s3-terminals` 运行可选合约字段的本地回归：已核验 RPR 入口与启动状态、观察方签名的执行闭合（FAILED）和激活时的资金边界（FUNDING_EXHAUSTED）。双机入口另有 `--execution-closure`（观察方闭合矩阵）与 `--terminals`（五个 Receipt 的组合矩阵）。字段与限制见[候选合约](../schemas/formal-migration/audit-terminals.md)，验收见[本切片报告](testing/FM-S3-TERMINALS-20261106.md)。

## FM 公开证据与组合双机矩阵

`make check-fm-public-evidence` 离线检查五份公开归档、固定源码与 24 套快照输入的索引；`make test-fm-public-evidence` 用当前实现完整重放 249 个历史事件，无需 Git 历史。genesis 与 checkpoint 的可信来源仍是留存报告或审查过的仓库版本，见[证据归档收尾](testing/FM-EVIDENCE-CLOSEOUT-20261107.md)。

`scripts/fm-s3-dualhost.py --terminals` 在两套独立账本上组合验收入口、执行闭合、资金边界与结算恢复；`--historical-gaps` 补跑 Work 2/3 迁移后的故障边界。两种模式的场景对照与复跑命令见[历史矩阵](testing/FM-S3-HISTORICAL-MATRIX-20261106.md)。

## Profile 规则 R1–R6

以下入口都在 `make test` 中，各自用独立的 Python 与 Rust 实现处理同一组固定向量，并比较结果流：

| 入口 | 切片 | 报告 |
|---|---|---|
| `make test-profile-digest` | R1 Profile 摘要与判决 | [R1](testing/PROFILE-DIGEST-R1-20261107.md) |
| `make test-profile-registration` | R2 嵌套类型、导入与 audit 注册 | [R2](testing/PROFILE-REGISTRATION-R2-20261107.md) |
| `make test-profile-references` | R3 排除引用与修正后的 wire 类型 | [R3](testing/PROFILE-REFERENCES-R3-20261108.md) |
| `make test-registration-rules` | R4 共同注册规则 | [R4](testing/PROFILE-RULES-R4-20261108.md) |
| `make test-method-matrices` | R5 四方法参数、失败与判决矩阵 | [R5](testing/PROFILE-MATRICES-R5-20261108.md) |
| `make test-creation-bindings` | R6 固定 audit I/F 测试接线 | [R6](testing/PROFILE-CREATION-R6-20261108.md) |

这些入口不是完整 ReplayPhaseI、CreateReceipt 或生产准入。每片的公开最小源码包在 `docs/testing/public-evidence/` 中，覆盖计数以 [coverage 登记](../schemas/verification-profile/coverage.json)为准。

## 开发者预览打包

预览源码包用 `make package PACKAGE=/new/path/aclt-preview-<DATE>-src.zip` 生成，命名与范围见[发行说明草案](releases/PREVIEW-20261106.md)。打包前须清单有效、工作区干净且位于待发布 commit；发布前检查清单以发行说明为准。预览名称不是 ProtocolVersion 或 ConformanceTarget。
