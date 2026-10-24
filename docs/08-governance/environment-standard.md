# ACLt Protocol 运行与协作环境规范

> 文档状态：Living engineering policy（本次建立的工程协作约定）  
> 当前语义基线：v0.5；ConformanceTarget：V1  
> 环境规范版本：ENV-1  
> 最后更新：2026-10-20
> 适用范围：当前 Linux 单机 state3 实验、模型、验证配置与自动进度流程

## 1. 范围与权威边界

本规范统一开发、测试和交接的环境记录，不定义协议执行语义，不改变 SemanticStatus、V1 VersionDisposition、ADR 或 Gate。协议与贡献要求沿用 [文档中心](../README.md)、[贡献指南](../../CONTRIBUTING.md)和[审计程序](audit-procedure.md)。

当前是单机局部实现。Rust 负责调度和验证，C++ 子进程负责计算，Python 负责模型、验证配置、测试与流程记录。当前入口没有第三方 Cargo 或 Python 库依赖，不需要数据库、Docker、Node.js、MATLAB、GPU、链节点、付款账户或常驻网络服务。Git 拉取与软件安装可能需要联网；运行和 Cargo 构建可以离线。

本文件是环境协作约定的唯一入口；其他说明链接本文件。新增依赖时必须同步本文件、依赖锁定文件、安装步骤与测试证据。

## 2. 目录与代码基线

本机当前布局：

```text
/home/tenneidp/Documents/ZeroMatrixTech/
├── .github/                 # 组织展示仓库，独立 Git 历史
└── ACLt/                    # 项目仓库；所有命令以此为根目录
    ├── docs/                # 规范、研究、治理与历史证据
    ├── schemas/、registries/ # Schema 与注册数据
    ├── tools/、tests/        # Python 工具及测试
    ├── scripts/             # 统一测试与进度入口
    └── experiments/aclt-minimal-verifier-state3/
```

其他成员可自行选择父目录，必须从 ACLt 仓库根执行本文命令。不得依赖维护者用户名或绝对路径。远端为 `https://github.com/ZeroMatrixTech/ACLt.git`。本次盘点分支为 `main`，完整提交为 `7d7f947c06c5bc398c16f05b816d98bcdce05cd3`，初始工作区干净。交接必须同时写提交 SHA 与工作区是否有未提交变更，不能只写“main 最新版”。

`experiments/aclt-minimal-verifier/` 与 `state2/` 为历史实现，当前统一入口指向 state3。旧任务记录不能迁入新版。运行目录记录计算程序绝对路径；仓库移动或重新编译后，旧任务恢复不保证可用。当前布局变更不追改历史报告中记录的原路径。

## 3. 工具链版本约定

下表的协作基线用于统一排障与复现；“本机观测”是 2026-10-07 的命令结果，不是全套测试通过证明。更换版本须记录完整版本并重新验收，不以“版本更高”自动视为兼容。

| 项目 | ENV-1 协作基线 | 已知要求与证据 |
|---|---|---|
| 操作系统 | Ubuntu 26.04.1 LTS，x86_64 Linux | state3 既有报告使用此环境；本机相同。其他 Linux 需另行验收 |
| Git | 2.53.x，优先 2.53.0 | 本机 2.53.0；这是协作选定版本，不是程序最低要求。其他维护中的版本可经 Git 操作与测试验收后使用 |
| Rust / Cargo | 优先 Ubuntu 官方 Rust 1.93.1 及配套 Cargo | state3 历史测试使用 Rust 1.93.1；Rust 至少 1.89；Cargo 精确版本须补录，不能推定与 rustc 一样 |
| C++ 编译器 | G++ 15.2.0，C++17 | 本机和历史报告均为 15.2.0；脚本使用 `-std=c++17 -O2 -Wall -Wextra -Werror` |
| Python | CPython 3.14.4 | 本机 3.14.4；标准库即可。此为协作基线，未证明最低兼容版本 |
| Shell | Bash 5.3.9 | 本机观测；脚本使用 Bash，不得改用 `sh` 调用 |
| 文件校验工具 | 能通过仓库清单验收的 `sha256sum` | 本机为 uutils coreutils 0.10.0；不限定必须是 GNU 实现 |
| 内存检测 | 编译器配套 ASan、UBSan、LeakSanitizer | 全量入口要求支持对应编译及运行；不得关闭泄漏检测后宣称完整通过 |

Rust 下限依据源码使用的标准库文件锁 API，官方 [`File` 文档](https://doc.rust-lang.org/std/fs/struct.File.html)标注该 API 从 1.89.0 稳定；项目 crate 使用 Rust edition 2021，Cargo.lock 格式为 4。edition、工具链版本、crate 版本、ProtocolVersion 和 ConformanceTarget 是不同字段。

**本机缺项：** 当前命令环境找不到 `rustc`、`cargo`、`cargo-1.93`，state3 的本地 `.toolchain/` 也不存在。因此当前机器尚未满足完整运行要求，历史成功记录不能替代本次验收。Rust 安装与全套重跑另行执行；本文编制未安装或升级软件。

## 4. 安装、版本记录与验收

首次获取代码：

```sh
git clone https://github.com/ZeroMatrixTech/ACLt.git
cd ACLt
```

Ubuntu 安装入口（需系统安装权限；先检查已有工具）：

```sh
sudo apt-get update
sudo apt-get install -y git g++ rustc cargo python3 bash coreutils
```

软件源可能提供不同补丁版本，安装命令不锁定版本。安装后必须核对第 3 节；记录实际版本及软件包版本，不为追求一致而盲目降级。需要严格复现时由团队保存经验证的软件源/包版本或镜像及摘要，目前仓库尚无固定容器镜像和全工具链锁定文件。

在仓库根记录环境，输出保存至本地产物目录：

```sh
mkdir -p artifacts
{
  date -u +%Y-%m-%dT%H:%M:%SZ
  git rev-parse HEAD
  git status --short
  uname -srmo
  cat /etc/os-release
  git --version
  python3 --version
  rustc --version --verbose
  cargo --version
  g++ --version
  bash --version
  sha256sum --version
  dpkg-query -W git g++ rustc cargo python3 bash coreutils
} > artifacts/environment.txt 2>&1
```

该清单用于记录，不代替验收；其中任一工具缺失或命令失败必须处理。运行前用 `command -v git python3 rustc cargo g++ bash sha256sum` 核对路径。普通协作者优先使用系统工具链；特殊本地工具链的路径、来源与版本必须显式登记。当前构建脚本若发现 `.toolchain/usr/lib/rust-1.93/bin` 会优先使用它；只有 `cargo-1.93` 的环境还须显式补记其版本，因为流程环境采集器默认探测 `cargo`。

全量验收与日常进度：

```sh
# 全量现有检查：失败即非零退出
bash scripts/run-singlehost.sh
# 日常检查、记录证据并生成 ACLT-PROGRESS.md
python3 scripts/aclt-flow.py run
# 环境变更、交接或需要重新取证时强制重跑
python3 scripts/aclt-flow.py run --force
# 仅查看已有状态；不产生新的测试通过证据
python3 scripts/aclt-flow.py status
```

初次验收须保留完整输出、退出码与环境记录。当前统一入口运行模型、验证配置、workflow 及 state3；以实际输出计数为准。2026-10-03 [集成报告](../testing/INTEGRATION-FIX.md)记录模型 13、配置 24、流程 22 以及实验 265 场景，这是历史证据，不是本文新增结果。

修改交付清单覆盖文件后运行 `python3 scripts/update-manifests.py`，检查其 diff，再执行 `sha256sum -c WORKFLOW-SHA256SUMS` 与 `sha256sum -c SINGLEHOST-SHA256SUMS`。不得仅刷新哈希来掩盖意外变化。

## 5. Linux 与文件系统要求

当前实现直接使用 Linux 进程、`fcntl` 文件锁、信号、子进程收养/父进程死亡保护及启动标识。完整验收采用普通用户、可写本地目录和支持文件锁、硬链接、原子重命名及文件同步的本地文件系统。不得把网络盘、云同步目录或共享运行目录直接当作已验证环境。

Windows 原生、macOS、WSL2、容器、ARM 主机均未在本次建立完整支持结论；可用于阅读或另行适配，报告必须注明具体环境和未通过项目。没有指定 CPU 核数、内存、磁盘最低额度，因为仓库尚无支撑这些下限的测量；运行前确认可用空间，记录宿主资源与负载，性能比较必须绑定输入、参数和硬件。

受 ptrace 或沙箱限制时 LeakSanitizer 可能失败，仓库保留了[原始失败日志](../testing/restricted-environment-run.log)。必须保存失败，转到支持检测的环境重跑；不得移除检测项后报告全量 PASS。运行期间不要移动任务目录或修改计算二进制。系统重启后当前实现拒绝自动恢复，不承诺断电恢复。

正常运行不得设置 `ACLT_TEST_PAUSE`、`ACLT_TEST_WORKER_GATE`、`ACLT_TEST_IO_FAIL`、`ACLT_TEST_IO_ERRNO`。测试驱动会在自己的临时目录注入故障。对 `RUSTC`、`RUSTFLAGS`、`CARGO_TARGET_DIR`、动态库路径、`PYTHONPATH`、locale 和时区等覆盖必须记录；进度流程仅保存部分环境摘要，不能视为完整系统或文件系统快照。

## 6. Git 与文件协作约定

每个成员使用独立 clone 或已授权创建的 worktree；一个工作目录同一时间只由一个写入流程操作。更新前先看 `git status --short`，不得覆盖他人的未提交修改。共同交接以 commit SHA 为准，Git 客户端补丁版本差异本身不等于代码基线差异。

ENV-1 采用小变更、主题分支、审查后合入主分支的约定：`docs/<topic>`、`fix/<topic>`、`feat/<topic>`。这是本次建立的协作流程，未声称远端已经启用分支保护或自动 CI。仅当仓库操作已获授权时执行：

```sh
git fetch origin
git switch main
git pull --ff-only
git switch -c docs/environment-standard
# 完成编辑与验收后，逐个添加本次文件；不使用盲目的 git add .
git diff --check
git diff --stat
```

提交说明使用 [CONTRIBUTING 的模板](../../CONTRIBUTING.md#6-提交说明模板)，写问题、变更、验证、剩余风险及同步文件。不得 force push 共享分支。审计准备阶段不自行提交、推送、合并或创建 PR；这些操作按获得授权的独立流程执行。

文本统一 UTF-8 与 LF，新文件末尾保留换行；不要批量改动历史文件行尾。建议在自己的 clone 设置 `git config --local core.autocrlf false`，不要覆盖用户全局设置。当前仓库尚未以 `.gitattributes` 或 `.editorconfig` 强制这些约定。

提交源代码、规范、测试、Cargo.lock 与经核查的正式证据；不提交 `.toolchain/`、`target/`、`build/`、本地缓存、凭据及临时产物。`ACLT-PROGRESS.md` 和当前 `.aclt-flow` 运行状态为生成物；已跟踪的历史示例与失败证据必须保留。检查 `git status` 和暂存 diff，不只依赖忽略规则。

## 7. 交接与环境升级

交接至少包含：完整 SHA、分支、未提交变更、ENV-1、系统/架构/内核、所有工具版本及路径、命令与退出码、输入和参数、日志/证据位置、通过与失败范围、剩余问题、负责人。公开记录不包含密钥、token 或无关个人数据。

环境升级遵循“记录旧环境 → 单独验证新环境 → 全量重跑 → 保留失败与差分 → 同步规范与证据 → 审查”的顺序。不得在任务恢复中途更换工具链或二进制；回退使用已验证工具链和新的任务目录，旧证据保留原版本标签。若新增 crate 或 Python 包，必须登记来源、版本、许可证和离线构建影响，并按 CONTRIBUTING 的第三方依赖边界审查。

仍待建立：Rust/Cargo 本机安装与精确包记录、跨平台验收、资源最低要求、固定工具链/镜像、自动 CI 与远端分支保护。本规范不把这些计划描述为已实现功能，也不宣称 P0-1B 关闭、G0/G2 退出或生产就绪。

## 9. 2026-10-20 外置权威账本实验环境补充

新增 `experiments/aclt-authority-admission/` 为独立实验 v2。Python/Cargo 无新增下载依赖；签名适配使用系统 OpenSSL CLI（本轮观测 OpenSSL 3.5.5，RSA-2048/SHA-256），测试需要本地回环网络权限。`make test-authority` 构建现有 C++ worker 并运行临时网络检查，纳入 `make test` 与流程证据。测试密钥仅在临时/证据目录生成，不放进源码更新包。

VM 复查另需 QEMU、cpio、ext4 工具、匹配的内核/驱动与 Python 最小运行时；必须显式提供资源路径并写入环境与摘要记录。无 KVM 时可以用 TCG，不能把 QEMU 来宾中断外推为宿主物理断电。外置账本与接纳端快照位于不同故障范围；本轮不证明账本自身回滚保护。详见[新实验说明](../../experiments/aclt-authority-admission/README.md)。

## 2026-10-23 候选编码切片环境复核

本轮实际可用 CPython 3.14.4、Unicode 数据库 16.0.0 与 rustc 1.93.1；上文“本机缺项”是此前快照，不再适用于本轮检查。新切片固定 Unicode 16.0.0，版本不同显式拒绝，避免跨实现规范化漂移。Rust 直接由 rustc 构建，无新增 Cargo/Python 下载依赖；SHA 对拍另用现有 OpenSSL。固定 Unicode 数据来源、生成器与许可证见 [Rust README](../../tools/verification_profile/rust/README.md)。本轮不重新认证完整 state3 环境或所有平台。

## 2026-10-23 后续验证环境切换（DUALHOST-SSH-1）

用户已撤销单机/同宿主 VM 替代真实双机验证的实验许可；后续集成、网络与故障验证采用两台物理机，通过 SSH 控制。新接受的独立主机假设仅限本轮实验，不扩张为统计/身份独立或主网保证。本地回归继续保留，历史记录不改写，P0-1B/G2 不关闭。连接事实、撤销条件、预检缺项及下一轮验收见 [双机 SSH 验证约定](dualhost-ssh-validation.md)。前文 VM 命令保留供历史审计，不作为后续默认执行许可。

## 2026-10-23 远端环境实际验收

B（aki2）已补齐 Ubuntu 官方 rustc/Cargo 1.93.1，独立 ext4 目录上全量 make test（含 sanitizer 和编码对拍）通过。已完成首轮真实 LAN 双机实验；实际版本、源码 pin、命令与证据见 [验收报告](../testing/DUALHOST-SSH-20261023.md)。上文缺项清单为历史快照，不能替代本轮记录，也不能将本轮通过外推到其他主机/代码版本。

## 2026-10-23 RIR 最小构建探针工具链

A/B 在各自实验目录内使用官方 Rust 1.93.1 独立 prefix（compiler、x86_64 库、wasm32v1-none 库及随包 rust-lld），不替换系统 Rust。四次空 run 构建与限定后处理产物一致；实际版本、摘要、编译参数、移除清单和证据范围见 [切片 1 报告](../testing/RIR-BUILD-SLICE1-20261023.md)。系统 sysroot 仍缺 wasm 目标库；后续命令必须显式选择实验工具链。未新增 Cargo/Python 依赖，现有 Node 引擎只用于本地复核，不成为项目运行依赖。

RIR 切片 1 的固定工具链 lock、离线安装与显式参数构建命令现已随 [维护入口](../../experiments/aclt-rir-build-probe/README.md)交付。工具链和产物继续存放仓库外或 artifacts/.toolchain 目录；未配置时默认 make check 只做纯 Python 回归，不会联网、安装软件或启动远端任务。

## 2026-10-23 RIR I/O 切片环境

切片 2 复用两端已锁定的 1.93.1 prefix，SDK/用户/入口均由各自 rustc 构建。受限 Python 参考执行只用标准库；可选现有 Node 引擎只在 A 上核对收集产物的语义，不是默认依赖。固定源码、输入、gas 账单和结果范围见 [报告](../testing/RIR-IO-SLICE2-20261023.md)。默认 make check 不连接远端、不自动下载工具链。

## 2026-10-23 RIR 切片 3 环境证据

[整数统计切片](../testing/RIR-STATS-SLICE3-20261023.md)复用前两切片固定官方 Rust 1.93.1 / wasm32v1-none 与 rust-lld，两台物理机各自编译 Wasm、无第三方 crate 的 native Rust 候选解释器和系统 G++ 15.2.0 C++ 基准；Python 3.14.4。没有新增软件安装、下载依赖、VM 或常驻服务。A 已有 Node v24.22.1 仅作可选语义 oracle。源码包包含维护入口和小型 golden，不包含工具链/运行二进制/大体积证据。

## 2026-10-23 RIR 第一项组合收尾

新增标准库脚本 `scripts/rir-work1.py` 和显式 `make test-rir-work1`，不增加依赖或改变工具链；两台物理机分别运行三片完整套件，再组合核对源码和产物连续性。本轮重跑与历史证据区分记录，见 [总报告](../testing/RIR-WORK1-CLOSEOUT-20261023.md)。默认检查仍不联网、不安装、不运行 VM。

## 2026-10-23 最小任务承诺切片环境

[任务承诺切片](../testing/TASK-COMMITMENT-SLICE1-20261023.md)仅使用现有 Python 标准库和第一项的已保存 Rust/Wasm fixture；没有新增依赖或编译器运行。双机新目录独立核对同一源码与 24 条/端记录，保留数据字节与源文件 pin。默认检查新增 19 项局部回归；不自动连接远端或将探针当成授权 worker。

## 2026-10-24 授权切片环境

[实验授权切片](../testing/TASK-AUTHORIZATION-SLICE2-20261024.md)复用现有 Python/SQLite、OpenSSL RSA-2048/SHA-256 和既有 Wasm fixture，无新增安装或下载。默认 make check 新增 24 项授权回归，因而新增对已有系统 OpenSSL CLI 的前置要求；局部检查不联网。双机矩阵显式使用 A LAN 临时端口和 B 专用目录，保持严格 SSH 主机密钥检查；测试密钥/凭据只放 private 运行目录，不入源码包。受控进程 SIGKILL 不代表断电，单一账本自身不回滚仍为接受假设。

## 第二项切片 3 环境补记（2026-10-24）

[因果日志/重放切片](../testing/TASK-REPLAY-SLICE3-20261024.md)复用现有 Python/SQLite/fsync/OpenSSL，不安装新软件，不改旧 Profile/gas 或授权实验源码。新增 26 项局部回归纳入默认检查；真实 LAN 仍显式 opt-in，A 临时可信服务、B 独立物理 worker，CHECK/CONSUME/SUBMIT 经 TCP，SSH 只部署/控制/取证。key/HMAC 运行材料不入源码包。完整包重传无 guest 调用；离线检查需要独立留存的 checkpoint/key pin，不能发现更新或解决权威回滚。进程 SIGKILL/重启不代表断电。

## 2026-10-24 第二项工作组合收尾

新增 `scripts/task-work2.py` 与显式 `make test-task-work2`，复用现有 SSH、Python/SQLite/OpenSSL 和已保存 Wasm fixture，无新依赖、安装或 Rust 重编译。A/B 独立新目录重跑三个切片，真实 LAN CHECK/CONSUME/SUBMIT 与受控进程故障继续遵守 DUALHOST-SSH-1；本地默认检查不联网。独立留存 checkpoint/key pin 后可只读复核原始证据；SHA 清单不是认证根或权威抗回滚。见 [总报告](../testing/TASK-WORK2-CLOSEOUT-20261024.md) 与 [维护入口](../testing/TASK-WORK2-MAINTENANCE.md)。

## 2026-10-24 测试资金预留环境

[资金预留切片](../testing/FUNDING-RESERVATION-SLICE1-20261024.md)复用已有 Python/SQLite/fsync/OpenSSL 和候选 CBOR/签名适配，无新增依赖、软件安装、Rust 重编译或 guest 计算。默认新增 22 项回归，真实 LAN 集成显式 opt-in；A 单一可信测试资金服务/账本，B 认证请求端，严格 SSH 只部署/控制/取证。仅预置整数测试资产，运行密钥/config/数据库不入源码包；进程重启不代表断电，权威不回滚仍为接受假设。

## 2026-10-24 双端固定测试结算环境

[固定结算切片](../testing/FIXED-SETTLEMENT-SLICE2-20261024.md)复用已有 Python/SQLite/OpenSSL 与保存的 Wasm fixture，无新依赖/安装/Rust 编译。A 服务/账本和 A reference worker 同故障域，B Requester/B worker 独立运行目录；实际 LAN 发送资金/START/结果/结算请求，严格 SSH 仅控制取证。两端执行同一 Python 实现，不称独立实现或统计独立。测试 HMAC 角色分开，A issuer/角色密钥留 A；实际运行 private 材料不入源码包。默认新增 26 项回归，双机仍显式 opt-in。

## 2026-10-24 结算故障恢复环境

[第三资金切片](../testing/SETTLEMENT-RECOVERY-SLICE3-20261024.md)复用未改动 v2 结算/审计及已有 Python/SQLite/OpenSSL，无新依赖/安装/编译/VM。显式双机在真实 COMMIT 前后及 worker fsync 点，仅 SIGKILL 本轮创建且匹配 ready/PID/start ticks 的实验进程；TCP reply loss 真实关闭测试连接，管理 SSH 不断开。A 服务/账本/A worker 同故障域，B 独立状态，key/config 不入公共取证/源码包。进程及 SQLite 热日志证据不冒充断电、failover 或账本抗回滚。默认新增 16 项回归、不联网。
