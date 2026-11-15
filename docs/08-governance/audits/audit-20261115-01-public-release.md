# 首次公开发布准备审计

> 编号：AUD-20261115-001
> 状态：`ACCEPTED_FOR_RECORD`（发现项均 `OPEN`）。报告由调度会话核实后入库，并由 Codex 审计入库 PR
> 日期：2026-11-15，10:44–11:05（CET，UTC+01:00）
> 基线：`origin/main` `5235424c83d0028d57695219aef86e7df62d8f77`（#127）。审计在该提交的分离 worktree 中进行，开始和结束时工作区都干净。
> 类别：发布准备审计（重点 A7），附带文档变更审计与历史档案审计。
> 范围来源：Issue #129 计划卡（维护者 2026-11-15 批准），阶段跟踪 #128。
> 审计者：Claude Code（Opus 5.5），只读子代理。程序：[审计程序](../audit-procedure.md)。
> 偏离：见“A0 偏离记录”。

本报告不构成法律意见。涉及许可、版权、商标和个人信息的判断，只核对了仓库内的事实以及仓库自己的陈述和规则。是否需要法律意见，由维护者决定（OQ-01 的关闭证据中列有“必要的法律意见”）。

## A0 — 授权与边界冻结

**目标。** 判断仓库能否从私有转为公开，以及以现有 `PREVIEW-20261106` 改写的首次公开发行说明需要满足哪些条件。按分级发现项交给 P1… 条目修复。

**允许的操作。** 读取仓库与 Git 历史；通过 `gh` 只读查询 GitHub 设置、Issue、PR 和评论；把远端全部引用镜像克隆到 scratchpad 做历史扫描；在分离 worktree 中运行 `make check`、`make test`、`make verify-source`、证据检查和两次打包。构建产物只写入被 `.gitignore` 忽略的路径和 scratchpad。

**禁止的操作。** 修改已跟踪文件，提交、推送、建标签，创建或修改 Issue 和评论，修改仓库设置，SSH 或 VM 运行，以及携带项目名称、人名、邮箱或代码访问外部服务（包括名称和商标检索）。

**维护者已作出的决定（前提，不列为待决）。** 来源为 #128，维护者 2026-11-15 原话：

1. 确认乌托邦基线闭合，记录工作由条目 C1 完成；
2. 本阶段可以占用物理 A、B 机；
3. 本阶段的蒙特卡洛只覆盖安全层；
4. 保留提交历史，接受其中的主机名、本地路径和作者邮箱随仓库公开；贡献机制采用 DCO；首次公开的发行说明改写现有的 `docs/releases/PREVIEW-20261106.md`；
5. 仓库全部工件采用 Apache-2.0（README“开源与许可”、CONTRIBUTING §11、OQ-01）；第三方 Unicode 数据适用 `Unicode-3.0`（`tools/verification_profile/rust/UNICODE-LICENSE.txt`）。

**排除范围。** 协议语义的正确性、Gate 退出、理论缺口建模，以及外部名称和商标检索（只列出待检索项）。

### A0 偏离记录

| 偏离 | 原因 | 风险 | 补偿 | 批准者 |
|---|---|---|---|---|
| A3 语义差异矩阵与 A5 追踪覆盖率未重新计算 | 本轮没有语义变更集；#129 的重点是 A7 和发布准备 | 协议层追踪缺口不会在本轮暴露 | `check-repository-evidence.py` 文档检查 PASS；以前次审计结论为准；语义连续性一维只判定限域结论 | #129 计划卡定义的范围 |
| A10 不准备修订，不生成更新包 | #129 计划卡的非目标：本条目不修复 | 发现项都处于 `OPEN` | 修复由 P1… 条目承担，合入后增量回验 | #129 |
| A7 未用外部一手来源核实 | 隐私约束：不得把项目信息发往外部服务 | Unicode License V3 正文未与官方原文比对 | Apache-2.0 正文与本机 Debian `/usr/share/common-licenses/Apache-2.0` 逐行比对；GitHub 设置以 API 为一手来源 | 调度会话指令 |
| 首次历史扫描中止 | 正则在大型 JSON 上出现二次方回溯，CPU 约 10 分钟仍未完成，我手动终止，退出码 144 | 无 | 改用有界正则重跑，33 秒完成；失败记录保留在附录 | — |
| 无人工签署 | 子代理审计 | — | 由调度会话核实，再由 Codex 审计 | — |

## A1 — 仓库与文档盘点

- **已跟踪文件。** 共 769 个。按顶层目录：`experiments` 279，`docs` 263（其中 4 个为非 ASCII 文件名），`tests` 70，`tools` 67，`scripts` 48，`schemas` 20，`.github` 4，`registries` 3，`.claude` 3，`.aclt-flow` 2，根目录 10。
- **按扩展名。** `.py` 267，`.md` 208，`.json` 153，`.rs` 37，`.gz` 26，`.txt` 20，`.log` 17，`.sh` 7，`.cpp` 5，`.toml`/`.lock`/`.tsv` 各 3，`.cjs` 2，`.yml`/`.html`/`.cbor`/`.docx` 各 1。
- **远端引用。** 包括 `main`、26 个附注标签 `evidence/*`、110 个 PR 头引用（`refs/pull/N/head`）。转为公开后，这些引用都可以被抓取。全部引用可达 313 个提交，其中 `main` 132 个；共 1772 个 blob，未压缩 100.8 MiB，pack 19.47 MiB。
- **本地专有引用。** 本地另有 `refs/agents/*` 检查点和若干本地分支，它们不在远端，不在公开范围内（见 AUD-20261115-024）。
- **社区文件现状。** 已有 `LICENSE`、`README.md`、`CONTRIBUTING.md`、`CONTRIBUTORS.md`、PR 模板和 2 个 Issue 模板。没有 `SECURITY.md`、`NOTICE`、`CODE_OF_CONDUCT.md` 和 `CODEOWNERS`。
- **内部代理工作文件。** `AGENTS.md` 与 `.claude/skills/{aclt-audit,aclt-plan,aclt-sync}/SKILL.md` 已入库，并列入 `DELIVERY-SCOPE.json`，因此也进入源码包。

## A2 — 时间戳与来源核查

| 文件 | 头部日期 | 最后提交 | 差异 |
|---|---|---|---|
| `README.md` | 最后更新 2026-11-11 | 2026-11-14 `747ab15`（许可范围改动） | 头部未更新 |
| `CONTRIBUTING.md` | 最后更新 2026-10-14 | 2026-11-14 `747ab15`（§11 改动） | 头部未更新 |
| `docs/07-roadmap/current-status.md` | 快照日期 2026-11-13 | 2026-11-14 `5235424` | 头部未更新；“当前实施入口”内容已过期（AUD-20261115-015） |
| `docs/releases/PREVIEW-20261106.md` | 起草 11-06，同步 11-08，11-14 只改第 7 节 | 2026-11-14 | 自述“其余内容未重新同步” |
| `docs/README.md` | 最后更新 2026-11-11 | 2026-11-14 | 头部未更新 |
| `CONTRIBUTORS.md` | 2026-11-08 | 2026-11-08 | 一致 |

#128 的五项决定（2026-11-15）尚未写入仓库内任何权威文档（AUD-20261115-010）。GitHub 上 `5235424` 的 push CI 运行于 2026-11-14T19:58:29Z，结论为 `success`。

## A3 — 语义差异

本轮没有变更集，不建语义差异矩阵（见偏离记录）。需要落入文档的决定变化只有 #128 的五项，见 AUD-20261115-010。

## A4 — 跨文档连续性

| 检查链 | 结果 | 发现项 |
|---|---|---|
| 许可陈述：README、CONTRIBUTING §11、OQ-01、current-status、PREVIEW §7 | 许可范围一致，均为全部工件 Apache-2.0、第三方 Unicode-3.0。OQ-01 仍写“未经修改的 Apache License 2.0 英文全文”，与 README 如实描述的附录版权行不符 | 012 |
| 贡献机制 | README 第 198 行、CONTRIBUTING 第 184 行、OQ-01、current-status 第 163 行都写“待决定”，与 #128 的 DCO 决定不符 | 003、010 |
| 物理双机状态 | 4 处仍写“2026-11-12 起暂停新增物理双机运行”，与 2026-11-14 的物理双机运行（M3、容量排序）及 #128 的阶段授权不符 | 011 |
| Gate 表：README 与 current-status | 一致，G0 进行中，G1、G3–G6 未开始，G2 只有局部单机实验 | — |
| 乌托邦基线闭合：minimal-verifier-baseline 闭合表与 current-status | 闭合表 5 项均为“已满足”；current-status 的“下一动作”仍把已合入的 M1、M2、M9 列为待做 | 015（与 C1 重叠） |
| P0-1B 计数 | README、current-status 为 80/36/3；PREVIEW §6 仍为 36/33/50 | 005 |
| 编号空间 | theory-gap Issue 使用 G1–G7（#114、#120–#124），与工程 Gate G0–G6 同名，例如 #123“G6”与 Gate G6 | 017 |

## A5 — 安全与可实现性追踪

不在本轮范围，见偏离记录。只核对了与发布有关的安全面：

- **安全披露渠道：** 缺失（AUD-20261115-002）。
- **CI 的信任面：** 只有 `pull_request` 与 `push` 触发，没有 `pull_request_target`。工作流不引用 secrets。`permissions: contents: read`，checkout 已固定 SHA 且 `persist-credentials: false`。仓库没有 Actions secrets、variables、environments、deploy keys 或 webhooks（API 计数均为 0）。

## A6 — 历史档案与权威性

`docs/codocs/README.md` 已声明目录内文件不构成当前规范，并列出当前入口。逐文件检查文件开头：

- v0.3 中文版、`ACLt_v0.5_Unresolved_Issues.md` 有 `SUPERSEDED` 横幅；
- v0.5 英文版开头有历史名称说明；
- v0.3 英文版、v0.4 中英文版、v0.5 中文版开头没有历史横幅。

转为公开后，读者可能经搜索直接进入这些文件（AUD-20261115-016）。`docs/codocs/README.md` 第 31 行写“现行 ADR-0001…0007”，但现行已到 ADR-0009。

本轮没有发现旧的 Rank、51%、Foundation 语义回流到当前入口。CONTRIBUTING §2 把它们列为禁止语义。

历史证据（日志、摘要、证据包）按维护者决定 4 保留原样，不改写。

## A7 — 许可证、发布与外部事实

### A7.1 密钥与凭据（覆盖全部历史）

扫描对象：远端全部引用可达的 1772 个 blob，并递归展开 33 个 `.tar.gz` blob（HEAD 26 个加历史版本）和 1 个 `.docx`。另扫描 26 个标签对象、313 条提交说明、131 个 Issue/PR 正文、59 条评论和 1 个 Discussion。

| 类别 | 命中 | 判定 |
|---|---|---|
| PEM 私钥块（`-----BEGIN … PRIVATE KEY-----`） | 0 | — |
| GitHub、AWS、Google、Slack、OpenAI/Anthropic 令牌格式、JWT | 0 | — |
| 带凭据的 URL（`scheme://user:pass@`） | 0 | — |
| SSH `IdentityFile`；`.env`、`.pem`、`.key`、`id_*`、`known_hosts`、`authorized_keys`、`.netrc`、`.pypirc` 等文件名 | 0（867 个历史路径，以及 1193 个证据包成员名） | — |
| 通用赋值（`password`、`secret`、`token`、`api_key` 等后接 `=` 或 `:`） | 20 个 blob 路径，14 个不同取值 | 都是代码中的变量。取值来自运行时生成（`secrets.token_bytes`/`token_hex`）、函数参数或字典查找，没有字面密钥。文件位于 `experiments/aclt-{authority-admission,multinode-admission,settlement-recovery,task-authorization,task-replay}/`、`scripts/check-test-controls.py`、`tests/workflow/test_delivery.py`、`tools/repository_checks.py`、`tools/test_control.py` |
| 高熵类 base64 串（≥32 字符，熵 ≥4.5） | 202 个不同取值 | 全部是路径片段、标识符，或 CBOR 证据中的二进制片段。没有私钥 DER 前缀（`MIIE…`、`MC4C…`、`openssh-key`） |
| GitHub 正文与评论 | 0 个密钥形态 | 只出现回环地址和来宾虚拟网段地址 |

测试签名密钥由驱动临时生成（如 `scripts/check-fm-s1a.py` 中的 `openssl genpkey`），只有公钥和签名入库。结论：本轮未发现凭据（AUD-20261115-022）。

### A7.2 个人信息清单（维护者已接受，仅登记范围）

| 类别 | 数量 | 位置 |
|---|---|---|
| 作者/提交者邮箱身份 | 全部远端引用中共 8 个不同邮箱：维护者 4 个（4 个不同域）；外部贡献者（#35）3 个，其中 1 个为 GitHub noreply；另有 1 个 GitHub web-flow 提交者 | 提交元数据，`main` 与 `refs/pull/*` |
| `Co-authored-by` 尾注 | 3 个身份：2 个 AI 服务的 noreply 地址，以及外部贡献者的 1 个邮箱 | 提交说明 |
| 标签签署者 | 26 个附注标签，共用维护者的 1 个邮箱 | `refs/tags/evidence/*` |
| `/home/<用户>` 路径 | 2 个不同用户目录。HEAD 11 个文件，历史中另有 `docs/08-governance/environment-standard.md` 的旧版本 | `docs/08-governance/audits/external/AUDIT-20261105-01.original.txt`、`docs/08-governance/audits/audit-20261007-01-markdown-maintenance.md`、`docs/08-governance/audits/audit-20261007-02-environment-standard.md`、`docs/testing/{experiment-baseline,experiment-regression,restricted-environment-run}.log`、`docs/workflow/example/.aclt-flow/runs/*/record.json`（3 个）、`experiments/aclt-minimal-verifier-state{2,3}/docs/lifecycle-validation-output.txt` |
| 主机名 | 2 个，出现在 33 个路径（全部在 HEAD 中） | `docs/08-governance/dualhost-ssh-validation.md`、`docs/08-governance/environment-standard.md`、`docs/testing/DUALHOST-SSH-20261023.md`、`docs/testing/PROFILE-*.summary.json`（17 个）、`docs/testing/PROFILE-PHASE-D-R15/R16-*.md`、`docs/testing/FM-S2-20261031.summary.json`、上述 3 个 `.log` 和 3 个 `record.json`、2 个 `lifecycle-validation-output.txt`、外部审计原文；证据包 `FM-S2-20261031-public-evidence`、`PROFILE-REGISTRATION-R2-source`、`PROFILE-RULES-R4-source` 各 1 个成员 |
| 用户名（作为单词） | 15 个路径（全部在 HEAD 中） | 上述含 home 路径的文件，以及 `audits/audit-20260818-01`、`audit-20260819-02`、`audit-20260819-03` |
| 证据包 tar 头中的属主用户名 | 4 个包 | `docs/testing/public-evidence/FM-S3{,-TASK-TRAP,-EXECUTION-CLOSURE,-HISTORICAL-MATRIX}-public-evidence.tar.gz` |
| 局域网或公网 IP | 0 | 全部历史和证据包中只有 RFC 1918 的 10/8 来宾虚拟网段地址（5 个，集中在 MULTIVM 证据与 VM 实验代码）、回环地址和全零地址 |
| 第三方邮箱 | 2 个 Linux 内核维护者列表或开发者地址，出现在来宾串口启动日志中；另有 1 个 `example.invalid` 测试地址 | `MULTIVM-*` 证据包中的 `*-serial.log`；`tests/repository_hardening/test_git_sources.py` |
| 文档元数据 | `.docx` 的 `dc:creator`、`Company` 字段非空 | `docs/codocs/v0.2/` 下的 DOCX |
| GitHub Issue、PR 与评论 | 0 个 home 路径，0 个邮箱 | 只有回环地址和来宾虚拟网段地址（#119 的评论） |

### A7.3 许可证

**LICENSE 正文。** 与 `/usr/share/common-licenses/Apache-2.0`（SHA-256 `cfc7749b…3d30`）逐行比对，只有两处差异：本机副本开头多一个空行，附录示例的版权行已填写公司中文全称。第 1–176 行条款正文逐字一致，`END OF TERMS AND CONDITIONS` 完整。README 第 200 行如实写明附录版权行已填写。

**SPDX 覆盖。** 共 238 个文件声明 `Apache-2.0`，2 个声明 `Unicode-3.0`（`unicode_data.rs` 与生成器中的字符串）。

| 语言 | 总数 | 有 SPDX | 缺 SPDX |
|---|---:|---:|---:|
| Python `.py` | 267 | 216 | 51 |
| Rust `.rs` | 37 | 20 | 17 |
| Shell `.sh` | 7 | 0 | 7 |
| C++ `.cpp` | 5 | 1 | 4 |
| JavaScript `.cjs` | 2 | 2 | 0 |
| `Makefile`、`.toml`、`.yml`、`.html` | 1+3+1+1 | 0 | 6 |
| Markdown、JSON 等文档与数据 | — | — | README 第 200 行声明由 README 与 `LICENSE` 覆盖 |

缺 SPDX 的 79 个源码文件（`.py`、`.rs`、`.sh`、`.cpp`）分布：

- `experiments/aclt-minimal-verifier{,-state2,-state3}`：40 个；
- `experiments/aclt-multinode-admission`：7 个；
- `experiments/aclt-rir-{build,io,stats}-probe`：8 个；
- `scripts/`：6 个（`aclt-flow.py`、`check-profile-inventory.py`、`package-singlehost.py`、`repository_files.py`、`update-manifests.py`、`run-singlehost.sh`）；
- `tests/verification_model`：3 个，`tests/verification_profile`：6 个，`tests/workflow`：3 个；
- `tools/verification_profile/{__init__,admission,deployment,event_frontier,phase_b,validator}.py`：6 个。

**至少 26 个缺 SPDX 的文件已被留存证据钉住字节。** 涉及 `docs/testing/SOURCE-BASELINE.json`、`AUDIT-FIXES-20261105.summary.json`、`FM-S1A/S1B/S2` 摘要、`PROFILE-PHASE-D-R12…R16` 摘要、`bq-*` 报告等，还受 `experiments/*/SHA256SUMS` 约束。CI 中也没有 SPDX 检查。

**NOTICE。** Apache-2.0 第 4(d) 条只在被再分发的作品“包含 NOTICE 文件”时产生义务。本轮未发现任何随附 NOTICE 的第三方 Apache 组件，也没有 vendored 代码。Unicode License V3 要求在数据副本中附带版权和许可声明，`UNICODE-LICENSE.txt` 与数据在同一目录，并已进入源码包（已核对包内清单）。按仓库陈述，目前没有 NOTICE 义务（AUD-20261115-013）。这是对许可文本的事实核对，不是法律意见。

**第三方材料。**

| 材料 | 位置 | 许可 | 处理 |
|---|---|---|---|
| Unicode 16.0.0 规范分解数据（生成） | `tools/verification_profile/rust/unicode_data.rs` | `Unicode-3.0`，文件头 SPDX 与同目录全文齐备 | 已标注 |
| Google Fonts（Press Start 2P、ZCOOL KuaiLe、Noto Sans SC） | `docs/00-overview/aclt-theater.html` 运行时从 `fonts.googleapis.com` 加载 | 字体未入库，不再分发 | NOTE：打开页面会向第三方发请求 |
| Linux 内核启动输出 | MULTIVM 证据包中的来宾串口日志 | 运行日志 | NOTE |
| 外部审计原文（DeepSeek 输出） | `docs/08-governance/audits/external/AUDIT-20261105-01.original.txt` | 按 README，全部工件为 Apache-2.0 | NOTE：AI 产出的权利状态不在本轮判断范围 |
| 文献引用 | `docs/06-research/`、`docs/codocs/` | 引用加链接 | 抽查未见大段引文；未逐篇核对 |

**依赖许可。**

- 3 个 `Cargo.lock` 只含本 crate，没有外部 crate；3 个 `Cargo.toml` 都没有 `license` 字段。
- Python 的 109 个 import 名中，不在 `sys.stdlib_module_names` 内的都是仓库本地模块（如 `wasm`、`cases`、`build`），没有第三方 Python 包。
- `.cjs` 只用 Node 内置模块。
- 外部工具链（rustc/cargo、g++、OpenSSL CLI、Python、e2fsprogs、QEMU、Node）都不随仓库再分发。
- CI action 只有 `actions/checkout`，已固定 SHA（v4.2.2）。容器镜像使用可变标签 `ubuntu:26.04`，apt 包未固定版本。

**README 与 CONTRIBUTING 的许可陈述。** 两者对许可范围的陈述一致。两者都把贡献机制写作待决，与 DCO 决定不符（003）。

### A7.4 贡献机制：DCO 需要同步的文件（只列清单，不起草文本）

1. `CONTRIBUTING.md` §11（第 182–184 行）：贡献机制、第三方代码接受规则和 NOTICE 维护规则；§5 推荐工作流；§6 提交说明模板（Signed-off-by 行）；头部“最后更新”。
2. `README.md`“开源与许可”第 198 行：“贡献许可机制……仍待决定”；“参与项目”一节。
3. `docs/07-roadmap/open-questions.md`：OQ-01 第 72 行备选路径 6、第 75 行当前建议、第 77 行关闭证据，以及第 46 行索引状态。
4. `docs/07-roadmap/current-status.md`：第 158–163 行“P0 — 阻断公开发布”第 4 项；第 207 行之后的决定日志新增一行；§3 事实表的相应行。
5. `.github/pull_request_template.md`：合并检查加入 sign-off 项。
6. `.github/workflows/validate.yml` 或新增工作流：DCO 检查（现有 313 个提交中 Signed-off-by 为 0，需要写明起算点）。仓库设置 `web_commit_signoff_required` 现为 `false`（维护者操作）。
7. `docs/08-governance/environment-standard.md` §6 的提交步骤。
8. `docs/08-governance/parallel-workflow.md` 与 `AGENTS.md`：代理产生的提交由谁签署 DCO，以及它和现有 `Co-Authored-By` 尾注的关系。这是需要维护者决定的政策点。
9. `.claude/skills/aclt-sync/SKILL.md` 第 52 行的 `git commit` 步骤，以及其他会提交的技能步骤。
10. `CONTRIBUTORS.md`“署名原则”。
11. 改写后的发行说明（原 `PREVIEW-20261106.md` §7）。

### A7.5 安全政策

- 仓库内没有 `SECURITY.md` 或 `.github/SECURITY.md`。
- CONTRIBUTING §10（第 178 行）写明正式安全披露流程为 `OPEN/P0`，要求联系当前维护者，但没有给出渠道。
- PREVIEW §9 写“安全问题请私下报告给维护者”，渠道是占位符。
- `GET /repos/.../private-vulnerability-reporting` 返回 404，私有仓库不可用。该功能需要维护者在转为公开后启用。
- `security_and_analysis` 为 `null`：secret scanning 和 push protection 未启用，转为公开后可以免费启用（维护者操作）。

### A7.6 README 与对外陈述

**做得好的地方：**

- 有“非目标与禁止主张”；
- 写明“尚未证明整体鲁棒性”；
- Gate 表与 current-status 一致；
- 没有发现“生产就绪”、“主网可用”或“已证明安全”之类的正面主张（在仓库全部 `.md` 中检索，命中都是否定语境）。

**欠缺：**

- 没有 OQ-01 要求的“v0.5 公开时标为 draft/research baseline”统一成熟度标签；
- 没有“当前没有可部署软件”的入口级陈述（这句话只在 PREVIEW §1 中）；
- 首段“面向……无许可分布式计算的开放协议”是设计目标，但当前证据基于固定协调器和可信宿主（#101 第 1、4 项）；
- 没有英文摘要；
- 环境前提只通过 `docs/development.md` 间接给出。

快速开始中的 `make check`、`make test`、`make workflow` 都存在于 Makefile 中，`make help` 可用。README 的本地链接全部存在（895 个本地链接检查 PASS），外部链接只有 apache.org 两处。

### A7.7 发行说明：改写 PREVIEW 需要改的内容（只列项）

1. **标题、版本名和状态头（第 1–13 行）。** `preview-20261106`、`DRAFT`、起草基线 `b05d567`、同步 `6ffb578` 都需要换成首次公开发布的名称与基线。第 13 行“受邀内部开发者与评审者。不得再分发”与 Apache-2.0 的再分发许可冲突。
2. **§2 发行物。**
   - “635 个、约 30.5 MB”已过期：本轮实测 769 个文件，63,740,412 字节（ZIP_STORED，不压缩）。
   - “五份 FM 公开归档与 R1–R6 源码包”已过期：现有 26 个证据包，包括 R7–R11、MULTIVM、DUALHOST-BASELINE。
   - `<COMMIT_SHA>`、`<ZIP_SHA256>`、`<CI_RUN_URL>` 仍是占位符。
   - 标签名需要改。
3. **§3 环境。** 与 ENV-1 复核一致性（本机实测 Ubuntu 26.04.1、Python 3.14.4、rustc 1.93.1、G++ 15.2.0、OpenSSL 3.5.5）。
4. **§4 计数。** “23 组 553 项”和“24 组 578 项”已过期：本轮 `make check` 为 23 组 643 项，`make test` 为 25 组 755 项。
5. **§5 双机复现。** 目前只有 FM-S3；缺最简验证机、物理双机基线（M3）和容量排序入口。需要与 #128 的 R2、R4（双机 nVM 安全层蒙特卡洛）的关系一并写明。
6. **§6 内容表。** P0-1B 的“36/33/50、9 个摘要 owner 已实现”已过期（现为 80/36/3）。“ADR-0001～0008”漏了 ADR-0009（`PROPOSED`）。缺乌托邦基线闭合（C1）、通用作业契约和多来宾证据。
7. **§7 已知限制。**
   - “历史证据”一条要按决定 4 改写为“已决定保留并随仓库公开”；
   - 许可一条补充 DCO；
   - 补上 #101 的限制（固定协调器和角色、同宿主 VM 证据口径、统计独立性未建立）；
   - 补上安全层蒙特卡洛只报告“N 次运行、0 次违反”，不报告概率（#128 的统计口径约束）。
8. **§9 反馈渠道。** `<反馈渠道>` 要改为公开 Issue 或 Discussions；安全问题指向 `SECURITY.md` 或私密漏洞报告。
9. **§10 检查清单。**
   - 第 1 项“本维护分支已合入 main”；
   - 第 4 项“A/B 重跑 FM-S3”，对应 AUD-20261106-012；
   - 第 7 项标签名；
   - 第 8 项“接收者名单”和“接收者确认分发范围”，公开发布不适用。

   需要补上公开前置项：名称检索、可见性切换、分支保护、私密漏洞报告、DCO 检查，并写明清单各项与“仓库转为公开”和“打发布标签”这两个动作分别是什么关系。
10. **§11 撤回。** “停止分发”和“通知接收者”对公开 Git 仓库无法实现，需要改写为公开撤回声明的语义。
11. **引用处同步。** `docs/README.md` 第 226 行（`releases` 草案、未发布）与第 292 行，`docs/development.md` 第 206 行，`current-status.md` 的“开发者预览”行，以及 `README.md` 第 135 行。

### A7.8 名称与商标：待维护者对外检索的项目（本轮未检索）

1. “ACLt”和“ACLt Protocol”在目标法域商标库中的检索（例如 CNIPA、USPTO、EUIPO、WIPO Global Brand Database），重点是软件与计算服务相关类别；
2. 同名或近似的软件与项目：GitHub、GitLab，以及 crates.io、PyPI、npm、Docker Hub 等包名；
3. 域名可用性；
4. 与通用术语 “ACL”（Access Control List）的混淆风险；
5. 公开历史中出现的旧名称（DistributedCompute、RUDCP、DCP、BigMind）。v0.5 历史文档已记录 “DCP” 有第三方同名使用，需要确认公开历史不会造成关联误认；
6. `LICENSE` 附录版权行中的公司中文全称，与 `CONTRIBUTORS.md` 第 10 行的维护主体 “ZeroMatrixTech”（也是 GitHub 组织名）是否为同一法律主体及其对应关系；
7. `CONTRIBUTORS.md` 对第三方产品名（Codex、Claude、DeepSeek）的指称性使用。

### A7.9 #101 中与公开陈述有关的条目

#101 仍为 OPEN。与公开陈述有关的有三条：

- 第 1 项：固定协调器、固定角色、固定对端地址；
- 第 3 项：实验记账的推广边界；
- 第 4 项：证据口径。同宿主多 VM 只覆盖来宾级；物理故障域分离、无许可协调和统计独立性需要各自取得证据。

这些都需要写进公开发行说明，README 的入口陈述也不能被读成已经实现（AUD-20261115-021）。

### A7.10 外部事实来源表

| 事实 | 来源 | 核实方式 |
|---|---|---|
| Apache-2.0 正文 | 本机 Debian `common-licenses` 副本 | 逐行 diff |
| Unicode License V3 | 仓库内副本 | 未与一手来源比对（偏离记录） |
| 仓库可见性、合并策略、Actions 权限 | GitHub REST API | `gh api`，只读 |
| 分支保护与 rulesets | GitHub REST API | 返回 403（私有仓库需 Pro），转为公开后才可设置 |
| 私密漏洞报告 | GitHub REST API | 返回 404 |
| CI 运行结果 | GitHub Actions API | `5235424` 为 success |

## A8 — 结构与机械一致性

| 检查 | 结果 |
|---|---|
| `check-repository-evidence.py` 与 `make verify-source` | PASS：基线 43 个 pin；留存摘要 FM-S1a 14、FM-S1b 19、RIR 19；文档部分 27 个 claim、9 个决定 ID、895 个本地链接 |
| Markdown 结构（208 份） | H1、代码块配对、相对链接与末尾换行：0 个实际问题。3 个 GitHub 模板没有 H1，这是模板格式要求 |
| 换行符 | 739 个文本文件为 LF，没有 CRLF 或混合换行 |
| 行尾空格 | 187 处，基本是 Markdown 硬换行，不处理 |
| 末尾无换行 | 3 个非 Markdown 文件：`experiments/aclt-multinode-admission/ordering_checks.py`、`schemas/formal-migration/value.schema.txt`、`schemas/verification-profile/claim-test-bytes.schema.txt` |
| 清单校验 | `make check` 内的 `check-manifests` 通过 |
| 最大 blob | 17.57 MiB（`tests/verification_profile/codec/runtime-bindings-vectors.json`，生成的测试向量）；前 10 名都低于 GitHub 50 MiB 警告线。pack 19.47 MiB |
| 已提交的生成文件 | 校验清单、测试向量、`unicode_data.rs`（附生成器）、证据日志。都是有意入库，不处理 |
| `.gitignore` | 已覆盖 `artifacts/`、`build/`、`dist/`、`__pycache__/`、`.claude/worktrees/`、`.claude/settings.local.json`。未覆盖 `.agents/`（主检出中有未跟踪副本）、`.env*` 和编辑器目录 |
| 构建 | 运行 `make test` 后 worktree 的 `git status --porcelain` 为空 |

## A9 — 结论

### 发现项

| 编号 | 级别 | 发现 | 证据位置 | 影响 | 修复要求 | 后续分组 | 状态 |
|---|---|---|---|---|---|---|---|
| AUD-20261115-002 | BLOCKER（发布） | 没有安全漏洞报告渠道 | 缺 `SECURITY.md`；CONTRIBUTING 第 178 行；PREVIEW 第 139 行；私密漏洞报告 API 返回 404 | 公开后，漏洞报告者只能走公开 Issue | 建立 `SECURITY.md`，写明渠道、范围和响应预期；同步 CONTRIBUTING §10、README、发行说明；转为公开后启用私密漏洞报告 | P1-b；维护者启用设置 | OPEN |
| AUD-20261115-003 | BLOCKER（发布） | DCO 已决定，但仓库仍写“待决定”；没有 sign-off 说明和检查；现有提交中 Signed-off-by 为 0 | A7.4 所列 11 处；`web_commit_signoff_required=false` | 外部贡献无法按既定机制接收；文档与决定冲突 | 按 A7.4 清单同步；增加 DCO 检查并写明起算点；明确代理提交由谁签署 | P1-b；维护者设置 | OPEN |
| AUD-20261115-004 | BLOCKER（发布） | 79 个源码文件缺 SPDX；至少 26 个被留存证据钉住字节；CI 没有 SPDX 检查 | A7.3 表；`docs/testing/SOURCE-BASELINE.json` 等；current-status 第 161 行把它列为“阻断公开发布” | 违反项目自定的公开条件（CONTRIBUTING §11） | 补齐 SPDX，或经维护者决定用目录级或文件外声明覆盖被钉住和历史冻结的文件；修改字节时按证据规则处理清单和 pin，不改写历史证据；加 SPDX 检查 | P1-a | OPEN |
| AUD-20261115-005 | BLOCKER（发布） | PREVIEW 不适合作为公开发行说明：分发范围写“受邀内部、不得再分发”，与 Apache-2.0 冲突；计数过期；有占位符；检查清单面向内部 | A7.7 的 11 项 | 公开时会误导，并与许可冲突 | 按决定 4 改写，逐项处理 A7.7 | P1-c | OPEN |
| AUD-20261115-006 | BLOCKER（发布） | README 没有 OQ-01 要求的“draft/research baseline”统一成熟度标签，也没有“当前没有可部署软件”的入口级陈述 | README 第 3–7、9、13–15 行；OQ-01 第 75、77 行 | 公开读者可能高估成熟度 | 在 README 加统一成熟度声明，与 overview §10、current-status §2 保持一致 | P1-c | OPEN |
| AUD-20261115-007 | BLOCKER（发布） | 名称与商标检索未做；名称、商标和兼容性声明政策未定 | current-status 第 158–162 行第 1、3 项；OQ-01；A7.8 | 项目自定的公开阻断项 | 维护者按 A7.8 检索并记录结论和政策 | 维护者（P-末） | OPEN |
| AUD-20261115-008 | BLOCKER（发布，承接 AUD-20261106-012） | 发布 commit 还没有双机证据和 CI 记录；PREVIEW 清单第 4 项仍要求 FM-S3 双机重跑 | PREVIEW 第 145–153 行；前次审计“后续状态” | 发布标签缺少清单要求的证据 | 改写后的清单要写明公开发布要求哪类双机证据（FM-S3 重跑和/或 #128 R4），以及它与“转为公开”的关系；在发布 commit 上执行并记录 | P1-c；维护者、R4 | OPEN |
| AUD-20261115-009 | MAJOR（发布） | 公开后需要的仓库设置尚未规划落地：分支和规则集保护（私有仓库返回 403）；Actions 允许全部 action，未强制 SHA 固定；fork PR 审批策略；secret scanning 与 push protection；私密漏洞报告 | `gh api` 结果见 A7.10；`allowed_actions=all`、`sha_pinning_required=false` | 公开后 `main` 无保护，外部 PR 可以运行任意代码 | 转为公开后：`main` 要求 PR、要求 `local-validation` 和 DCO 检查、要求分支最新、禁止强推和删除；Actions 限定已选 action 并要求 SHA 固定；外部贡献者 PR 需审批；启用 secret scanning、push protection 和私密漏洞报告。保留现有的仅 squash、合并后删分支、`default_workflow_permissions=read` | 维护者；P1-e 写入发布清单 | OPEN |
| AUD-20261115-010 | MAJOR | #128 的决定没有写入权威文档：DCO、保留并公开历史个人信息、本阶段物理机授权、蒙特卡洛只做安全层（审计程序 §4 要求写入） | `git grep '2026-11-15'` 在 `*.md` 中无相关命中；current-status 第 207 行仍写“贡献机制仍 OPEN”；PREVIEW 第 118 行 | 权威文档与决定不一致；AUD-20261106-017、018 无法关闭 | 在 current-status 决定日志、OQ-01、ENV-1 和 DUALHOST-SSH-1 中记录，并注明来源 #128 和日期；随后关闭 AUD-20261106-017（许可部分）和 -018 | P1-d（决定 1 由 C1 处理） | OPEN |
| AUD-20261115-011 | MINOR | 4 处仍写“2026-11-12 起暂停物理双机”，与 11-14 的实际运行和 #128 的授权不符 | `minimal-verifier-baseline.md` 第 38 行；`environment-standard.md` 第 19 行；`dualhost-ssh-validation.md` 第 6 行；`AGENTS.md` 第 6 行 | 公开读者和代理读到的是错误的当前约束 | 改为带日期的历史叙述，并补写当前授权 | P1-d | OPEN |
| AUD-20261115-012 | MINOR | 许可陈述过期：OQ-01 写“未经修改的 Apache License 2.0”；README、CONTRIBUTING 头部日期未更新 | OQ-01 第 75 行；README 第 7 行；CONTRIBUTING 第 5 行 | 陈述不一致 | 与 README 第 200 行统一；更新头部日期 | P1-a | OPEN |
| AUD-20261115-013 | MINOR | OQ-01 关闭证据要求的“第三方许可清单”没有独立文档；Cargo.toml 没有 `license` 字段；NOTICE 目前没有义务，但未记录这一判断 | OQ-01 第 77 行；3 个 `Cargo.toml` | 关闭证据不完整 | 建立第三方清单（A7.3 表），记录无 NOTICE 义务的依据；补 `license = "Apache-2.0"` | P1-a | OPEN |
| AUD-20261115-014 | MINOR | CONTRIBUTORS 与事实不符：漏列 Copilot（`main` 上 #95 有 Copilot co-author，PR 引用中共 12 条尾注）；“只为 Claude 保留 co-author”的说法不准确；维护主体名与 LICENSE 版权行的关系未说明 | CONTRIBUTORS 第 10、21–25、30 行 | 公开署名不准确 | 修正表格与署名原则；维护者确认法律主体名称 | P1-b；维护者 | OPEN |
| AUD-20261115-015 | MINOR | current-status 的“当前实施入口”把已合入的 M1、M2、M9 列为下一动作；快照日期 11-13 | current-status 第 4、13 行 | 状态页过期 | 随 C1 更新 | C1 / P1-d | OPEN |
| AUD-20261115-016 | MINOR | 4 份 codocs 文件开头没有历史横幅；codocs README 写“ADR-0001…0007” | A6 | 公开读者可能误读为当前规范 | 只在文件开头加横幅，不改正文；更新 ADR 范围 | P1-d | OPEN |
| AUD-20261115-017 | MINOR | theory-gap 的 G1–G7 编号与 Gate G0–G6 同名 | #114、#120–#124 的标题；#128 | 公开读者会把 “G6” 理解为 Gate | 维护者决定换前缀或加限定；文档引用处同步 | 维护者 / P1-d | OPEN |
| AUD-20261115-018 | MINOR | CI 容器使用可变标签 `ubuntu:26.04`，apt 包未固定版本，而 `check-environment.py --full` 会拒绝范围外的版本；CI 没有 DCO 和 SPDX 检查 | `validate.yml` 第 15、21 行 | CI 结果可能随上游漂移，可复现性下降 | 固定镜像摘要，或在清单中写明漂移处理；增加检查（同 003、004） | P1-e | OPEN |
| AUD-20261115-019 | MINOR | `.gitignore` 未覆盖 `.agents/`、`.env*` 和编辑器目录 | `.gitignore`；主检出中未跟踪的 `.agents/` | 容易误提交本地状态 | 补齐忽略规则 | P1-e | OPEN |
| AUD-20261115-020 | MINOR | GitHub 仓库描述 “An Distributed Computing Solution” 有语法错误，且与 README“不是计算平台……或单一软件产品”的定位不符；没有 topics | `gh api` 的 `description` 字段 | 公开首页的定位误导 | 维护者改写描述 | 维护者 | OPEN |
| AUD-20261115-021 | MINOR | #101 中的限制（固定协调器、同宿主 VM 证据口径、独立性）没有出现在 README 和发行说明的公开陈述中 | #101；README 第 9、128 行 | “无许可”等设计目标可能被读成已经实现 | 写入发行说明的已知限制，并在 README 入口加限定 | P1-c | OPEN |
| AUD-20261115-022 | NOTE | 全部历史、证据包和 GitHub 正文中都没有发现凭据 | A7.1 | — | 公开前在发布 commit 上重扫一次 | — | OPEN |
| AUD-20261115-023 | NOTE | 个人信息范围已登记（A7.2）。维护者的决定覆盖维护者本人的信息；外部贡献者（#35）的 3 个邮箱也会随历史公开 | A7.2 | 第三方个人信息公开 | 维护者决定是否告知该贡献者；本报告不作法律判断 | 维护者 | OPEN |
| AUD-20261115-024 | NOTE | `AGENTS.md`、`.claude/skills/*` 是内部代理工作流程，会随仓库和源码包公开；本地 `refs/agents/*` 和本地分支不在远端 | `DELIVERY-SCOPE.json`；本地引用 | 披露内部流程；误推送本地引用会扩大公开面 | 维护者确认公开这些文件；推送时不要使用 `--all` 或 `--mirror` | 维护者 | OPEN |
| AUD-20261115-025 | NOTE（承接 AUD-20261106-016） | 发布来源没有签名根；26 个证据标签都未签名 | `git for-each-ref refs/tags` | SHA 只证明内容一致 | 发行说明披露；建议签名发布标签 | P1-c；维护者 | OPEN |
| AUD-20261115-026 | NOTE | theater 页面运行时加载 Google Fonts；外部审计原文和 AI 产出的权利状态 | A7.3 第三方材料表 | 浏览者会向第三方发请求；权利状态未作判断 | 维护者决定是否本地化字体，以及是否取得法律意见 | 维护者 | OPEN |
| AUD-20261115-027 | NOTE | README 只有中文；没有 CODE_OF_CONDUCT（行为要求写在 CONTRIBUTING §10）；Issue 模板只有两类 | 根目录 | 公开协作的入口门槛较高 | 维护者决定 | 维护者 | OPEN |

### 前次审计遗留项

| 编号 | 本轮状态 |
|---|---|
| AUD-20261106-012 | OPEN，由本轮 008 承接 |
| AUD-20261106-016 | OPEN，由本轮 025 承接 |
| AUD-20261106-017 | 许可部分已由 2026-11-14 决定解决；名称与商标部分由本轮 007 承接。关闭要等 010 把决定写入文档 |
| AUD-20261106-018 | 维护者已于 2026-11-15 决定接受（#128 决定 4）；等 010 记录后可关闭 |

### 分维度结论

> 语义连续性：PASS（限域：本轮没有协议语义变更集；只核对入口、状态与治理陈述。发现的不一致是状态与治理陈述，不涉及协议对象、不变量或 ADR，见 010–012、015）；目标 Gate：NOT_ASSESSED；结构完整性：PASS；历史隔离：PASS（附 MINOR 016）；发布准备：FAIL（7 个 BLOCKER 未关闭：002–008）。
> 允许开展：P1-a～P1-e 修复条目；维护者的名称检索与设置规划；按 #128 继续 C1、R1–R4；修复合入后做增量发布准备回验。
> 禁止宣称：仓库已满足公开条件；许可已合规或已经过法律审查；名称可用；DCO 已生效；预览版或公开版已发布；任何 Gate 退出、conformance 或正式接口准入；生产或主网可用；身份或统计独立；本报告构成法律意见。

## A10 — 修订与交付

本轮不准备修订（#129 的非目标），不生成更新包。所有发现项均为 `OPEN`。交付物只有本报告，由调度会话核实后入库，同时更新 `docs/README.md` 审计索引和 `SINGLEHOST-SHA256SUMS`（按 #129 文件集）。本轮没有执行任何仓库写操作。

## 附录：命令与退出码

| # | 命令（类别） | 退出码 | 结果 |
|---|---|---:|---|
| 1 | `git fetch origin` | 0 | `origin/main` = `5235424` |
| 2 | `git worktree add --detach .claude/worktrees/audit-p0 origin/main` | 0 | 结束时 `git worktree remove` 退出 0 |
| 3 | `git clone --mirror`（到 scratchpad） | 0 | 137 个引用，313 个提交，pack 19.47 MiB |
| 4 | `gh api repos/ZeroMatrixTech/ACLt`、`actions/permissions{,/workflow}`、`community/profile` | 0 | 见 A7.10 |
| 5 | `gh api .../branches/main/protection`、`.../rulesets` | 1（HTTP 403） | 私有仓库需 Pro |
| 6 | `gh api .../private-vulnerability-reporting` | 1（HTTP 404） | 不可用 |
| 7 | `gh api --paginate`：issues、issue comments、pulls、discussions | 0 | 131 个正文，59 条评论，1 个 Discussion |
| 8 | 历史扫描脚本，第 1 次 | 144（手动终止） | 正则二次方回溯 |
| 9 | 历史扫描脚本，第 2 次（有界正则） | 0 | 1772 个 blob，约 33 秒 |
| 10 | 主机名与用户名的历史扫描 | 0 | A7.2 |
| 11 | `diff /usr/share/common-licenses/Apache-2.0 LICENSE` | 1 | 只有开头空行和版权行两处差异 |
| 12 | SPDX 统计（`git ls-files` 加 `grep -L`） | 0 | A7.3 |
| 13 | `python3 -B scripts/check-repository-evidence.py --repository .` | 0 | PASS |
| 14 | `make check` | 0 | 115 秒，23 组，643 项 unittest |
| 15 | `make test` | 0 | 447 秒，25 组，755 项 unittest（含重跑的 check），以及 state3、sanitizer、跨语言、FM 公开证据重放 |
| 16 | `make verify-source` | 0 | PASS |
| 17 | `python3 -B scripts/check-environment.py --full` | 0 | Ubuntu 26.04.1、Python 3.14.4、rustc 1.93.1、G++ 15.2.0、OpenSSL 3.5.5、内核 7.0.0-43 |
| 18 | `scripts/package-singlehost.py` 打包两次，再 `cmp` | 0 / 0 / 0 | 769 个文件，63,740,412 字节，SHA-256 `7ae6abfcddb99923476da80349072fa588978493e85ce992b7e4598ced7016f4`（只代表审计基线，不是发布摘要） |
| 19 | Markdown 结构检查（208 份） | 0 | 0 个实际问题 |
| 20 | `git ls-files --eol`、`git diff --check`（空树对 HEAD） | 0 | A8 |
| 21 | `git status --porcelain`（`make test` 之后） | 0 | 空 |

未运行：SSH、双机、VM、外部检索，以及线上 CI 的重新触发。

## 入库后记（2026-11-15）

审计完成后，维护者对三个发现项作出了决定，记录在 [#128](https://github.com/ZeroMatrixTech/ACLt/issues/128#issuecomment-6892751487)。这些决定不改变本报告的审计结论，修复与关闭仍由 P1 条目完成，并经回验确认。

| 发现项 | 维护者决定 |
|---|---|
| AUD-20261115-004 | 缺 SPDX 的文件（含被证据钉住字节的文件）改用文件外声明覆盖 |
| AUD-20261115-003 | 代理产生的提交由维护者签署 DCO |
| AUD-20261115-017 | theory-gap 编号改用前缀 TG（TG-1 至 TG-7）。Issue 标题已于当日改名，仓库内的引用由 P1-d 同步 |
