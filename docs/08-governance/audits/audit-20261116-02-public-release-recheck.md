# ACLt 首次公开发布准备增量回验

> 编号：AUD-20261116-02 · 状态：供维护者审阅，待 dsh 入库  
> 类别：发布准备审计；审计代理：Codex  
> 基线：`origin/main` `d0bf56e8fa8bd1fdfe4903c198b1898dd6d9930b`（#160）  
> 增量：`5235424c83d0028d57695219aef86e7df62d8f77..d0bf56e8fa8bd1fdfe4903c198b1898dd6d9930b`  
> 审计时间：2026-11-16T15:17:54+01:00 至 2026-11-16T15:31:17+01:00，Europe/Budapest（CET，UTC+01:00）  
> 授权：[计划卡 #161](https://github.com/ZeroMatrixTech/ACLt/issues/161)、[阶段 #128](https://github.com/ZeroMatrixTech/ACLt/issues/128)。程序：[`audit-procedure.md`](../audit-procedure.md)。对照报告：[`audit-20261115-01-public-release.md`](audit-20261115-01-public-release.md)。

## A0 — 授权、权限与偏离

维护者在 #161 的批准评论中写明“Approve, create issue”，并指定 Codex 只读执行、dsh 入库、维护者复核入库件。审计在远端镜像执行 `git fetch origin`，从镜像的 `refs/heads/main` 建分离 worktree。镜像和 worktree 都在仓库外，避免更改原检出的 Git 元数据。测试和拆包产物只写到该临时目录。

没有执行 SSH、QEMU 实验、VM、物理双机或新 R4 campaign。没有提交、推送、开 PR、修改 Issue、修改仓库设置或标签，也没有进行名称、商标或法律检索。冻结的 `PREVIEW-20261106.md` 只读检查。证据复放使用留存执行器。本地全量测试使用能够创建本地套接字的权限直接运行。

清理结果：审计 worktree 在全量测试结束后 `git status --porcelain` 为空，`git worktree remove` 成功，列表仅余临时 bare 镜像，检出目录已不存在。原检出开始已有未跟踪的 `.claude/` 工作材料，未清理、未纳入报告或发布基线。其检查结果与审计 worktree 的干净状态分别记录。

## A1 — 仓库与文件盘点

基线为 790 个跟踪文件，其中 Markdown 216 份，`docs/testing/public-evidence/` 下 tar.gz 28 个。增量 17 个 first-parent 提交，56 个文件，7,833 行新增、196 行删除，无删除或改名路径。仓库根目录许可证、`docs/01-requirements/`、`docs/03-protocol/`、现行 ADR 的文件字节无增量修改。

| 区域 | 增量内容 | 可追溯提交或 PR |
|---|---|---|
| 审计与闭合 | P0 报告、C1 闭合、OQ 与状态同步 | #135、#131、#143、#154 |
| 公开入口与许可 | SECURITY、DCO、README、PREVIEW、REUSE 与第三方材料表 | #142、#147、#148、#145、#155 |
| 发布设置与 CI | Actions SHA、漂移处理、忽略表、公开后设置检查表 | #141 |
| 实跑与验收 | R2 LAN、R3 驱动、R1 规格及修订、R4a、负例 CLI、R4 | #134、#140、#152、#158、#156、#159、#160 |
| 新增公开证据 | `DUALHOST-MULTIVM-R2-public-evidence.tar.gz`、`R4-SAFETY-MC-public-evidence.tar.gz` | #134、#160；A7 逐个展开 |

## A2 — 时间戳与来源

P0 基线为 `5235424`。本轮基线 `d0bf56e` 的 Git 提交时间为 2026-11-16 14:57:51 CET，读取 GitHub API 时该 SHA 的 `dco` 与 `local-validation` 均为 `success`。本轮没有重新触发 CI。R4 报告记录 2026-11-16 UTC 的四个运行窗口；实跑源码是 `a9aeddb`，R4 报告在之后以 #160 合入。证据标签及原始日志没有移到报告提交来冒充实跑版本。

README 与 CONTRIBUTING 的文首更新日为 2026-11-15。`current-status.md:5,9,15,206` 同时记录 11-13 快照、已完成的 R4 以及把 R4 列作下一步的入口，详见 AUD-20261115-015。OQ-01 的两个数字集合是带来源的历史基线，现时覆盖数另记于 A7.3。

## A3 — 语义差异矩阵

| 主题 | P0 到本轮的变化 | 连续性证据 |
|---|---|---|
| 许可和贡献 | 全部工件采用 Apache-2.0 的仓库声明，第三方 Unicode 数据单列；DCO 和安全报告落地 | README:198–204、CONTRIBUTING §10–11、OQ-01、REUSE.toml、审核与 CI |
| 实验成熟度 | C1 确认限定基线闭合，新增 R2/R4 跨 VM 工程证据 | README:3–17、OQ-04/OQ-06 带日期注记、状态日志 Gate 为“不变” |
| 协调及安全层 | R1/修订 1 固定角色和预算，R4a 实现受信协调与独立检查，R4 复用冻结方案 | R1 §§4–8；#158、#156、#159、#160；既有通用契约和规范对象未替换 |
| 统计 | 固定种子运行只报告次数、违反和复现，另可列终态与故障触发计数 | #128 决定 3；R1 §6.6、R4 报告第 5–7 行、PREVIEW §7 |
| 发布来源 | GitHub Release 作为状态与元数据记录；仓库内 PREVIEW 冻结为候选 | #128、#148 维护者决定、PREVIEW:3–5,29–39,169–197 |

## A4 — 跨文档连续性

README 文首的 v0.5 draft/research baseline、无可部署软件、非生产与非主网，与 SECURITY 范围、PREVIEW §§1、7–8 及 OQ-01 相符。README:17、PREVIEW:136 均列 #101 的固定协调者和角色、同宿主证据只到来宾级，以及故障域、无许可协调和统计独立仍未建立。R2/R4 报告分别标示了宿主、角色、实际拓扑与故障口径。R4 仅宣称有限实跑与离线复现，R4a 冒烟不进入 R4 计数。

R4 给出每 pass 32 次带种子运行、违反 0 次、可复现；附终态和触发计数。没有将 0 次违反解释为概率、置信度、覆盖率、故障率、性能或成本，也没有把同宿主或双宿主环境解释为独立故障域。当前状态入口的叙述滞后和 R4 文档的两个表格细节分别登记，均未改变实验数据。

## A5 — 威胁、不变量、实现证据与理论边界

| 局部性质 | 规范及证据 | 边界 |
|---|---|---|
| 错绑、错误完整产物、重复接纳 | R1 §3 S1/S3/S4；`montecarlo.py` 独立重建，#159 CLI 负例，R4 两遍留存重放 | 固定输入、固定指派及受信服务方留证 |
| 超预算、无答复、停止仍发布 | S2/S5；冻结 T1 补算反例，账目前缀与逐尝试注入绑定 | 硬预算检查，非故障概率或成本估计 |
| 并存写者、交接、归档 | S6/S7；轮次、宿主/来宾日志、双份 trace 检查、两种子按稳定投影比较 | 固定协调与可信宿主下的有限证据；M4 探针只支持 fail-closed |
| 公开供应链 | DCO 脚本与工作流、文件外许可覆盖、来源标签、发布清单 | 阻断外部 fork 合并的门禁实测及线上设置由维护者完成 |

本轮未发现发布验收依赖新的待证明数学性质。TG-5（#122）、TG-6（#123）、TG-7（#124）仍开放。R1 §8 的固定派活、协调者可信是明确有限实验前提；本回验不建模、不选参数，不从固定种子推断总体性质。

## A6 — 历史档案与权威

`docs/codocs/README.md:11,26–33` 指向现行入口，区分历史 ADR 编号；四份 codocs 的差异仅为开头的 `SUPERSEDED` 横幅和空行，历史正文保留（#143）。旧 P0、失败证据、先前 R4a 未达条件的冒烟、首次外部中断的 R4 目录均保留且与通过矩阵隔离。维护者 #128 决定 4 已接受的历史信息按原范围保留。R1 的新编号和安全判据为现行试验规格，不追改旧证据。

## A7 — 许可、发布与外部事实

### A7.1 凭据重扫

在只读远端镜像枚举全部可达引用：159 个引用、442 个提交、30 个附注标签对象、2,081 个 blob 和 830 个历史路径。递归展开历史中的 35 个 tar 归档版本和 1 个 ZIP 格式 DOCX；扫描条目内容、成员名及 tar 元数据。当前 28 个公开包均在覆盖范围内，新增 R2 和 R4 又单独扫描，合计 2,645 个普通文件（R2 198，R4 2,447；扫描记录另含两个归档自身）。文档、日志、CBOR 和非文本字节均经过有界模式。规则包括 PEM/编码私钥标记、常见 GitHub/云/聊天及 API token、JWT、带口令 URL、SSH IdentityFile、敏感文件名与通用带引号赋值。各字段设定长度上限，扫描未尝试认证或验证凭据。

唯一 URL 类型命中是 P0 A7.1 自身的示例语法；14 个通用赋值候选均定位至历史实验夹具、参数对象、测试记录或生成路径。未发现可认定为凭据的值，没有把候选值写入报告。此结果是已枚举对象上的检测结论。选定最终发布 commit 后仍需按 §10 重扫。

GitHub 通过分页读取 160 条 Issue 接口记录（含 PR 条目）、127 个 PR 正文、187 条 Issue/PR 普通及行内评论、127 个 PR 的审查接口（85 条审查记录）和 1 个 Discussion。分页和最终扫描均成功，未发现凭据模式。Discussion 首次请求超限，缩小每页讨论数后成功；再次运行扫描时一次把既有扫描输出当作输入，修正为显式 API 文件集合后通过。API 和历史数据只在临时目录读取，没有写回。

### A7.2 P0 后新增范围的个人信息

核查主线新增 7,833 行、P0 完成时点之后远端可达的 125 个提交及其正文和元数据、GitHub 增量正文/评论，以及新增两个公开包。在报告中仅登记类别和位置：

| 位置 | 新增范围的发现 |
|---|---|
| R2 公共包 | `failed/diagnostic/*-serial.log` 等串口记录包含上游内核联系人地址；来宾 IP 为实验虚拟网段。未核出实际物理 SSH/LAN 地址、操作者本地路径或凭据。 |
| R4 公共包 | 真实地址、用户名、构建路径和执行器未进入包。数字形式的 QEMU 版本与虚拟拓扑标记不作为真实地址。 |
| 代码、Git 与 GitHub | 虚拟网段和文档测试地址出现在测试及 #134/#156 的证据讨论；DCO 测试邮箱是夹具。新增提交有署名及服务账号元数据，未复制具体地址或旧个人信息。 |
| 外部贡献者 | P0 已登记的第三方历史邮箱由维护者处理，#128 决定 4 不扩张为代替第三方的决定。新增 R2 包复用的上游联系人作为新增分发表面单独登记。 |

2026-11-16 补记：维护者决定不保留这些新增联系人字段；P1-g（#163）已按 #128 对 R2 及 9 个 MULTIVM 公开包的串口日志邮箱字段统一替换为 `<redacted-email>` 并重打包，包摘要与脱敏说明见各测试报告。

### A7.3 许可证与物料

`make check-license-coverage` 通过：342 个检查对象 = 252 个文件头 + 90 个显式路径声明；448 个有据排除，缺失 0。OQ-01:75–89 中的 341/251/90/444 是 `52883d6` 盘点，不是本轮 790 文件的现值。当前检查在有 Git 元数据时按跟踪树运行，未分类文件失败。声明覆盖历史钉住文件，state3 的 Cargo 清单有许可字段，state1/state2 保持历史字节。根 `LICENSE` 相对 P0 不变；相对本机 Apache-2.0 标准副本只有起始空行与附录版权示例之差。`third-party-materials.md:13–45` 记录 Unicode、外部材料、字体及本轮范围内的 NOTICE 判断。此处核对项目的许可陈述和机器覆盖，法律判断留给维护者。

### A7.4 R4 证据、许可留存与发布渠道

从远端附注标签解引用得到 `a9aeddbd706630808bf6a8985646c3075d673d27`，与 R4 报告和完成的四个 campaign 一致。当前检查器 blob `4993c08b5decd9463ae211f049ced6b13f038093` 对实跑提交一致。R4 公开包 362,440 字节，SHA-256 `8bdf36f4181e23d834621e572299865a676f97fd3c1ed22cc27dbc80546a446a`。四份公开清单逐一以 `--ignore-missing` 通过：

| campaign | 清单文件 SHA-256 |
|---|---|
| pass1 / 20261115 | `87571df03a969fb942f736134287d130ace25bc90bef37062d385f4ff24f5726` |
| pass1 / 20261116 | `35fa1e3a6a3212977336e5a9fd12f66741563afeb57b119488fb016ebe165fbc` |
| pass2 / 20261115 | `5b97b9f6af97052023f6dfa8ce035e939788100c55b5eae1ff99b9909ad3d7ad` |
| pass2 / 20261116 | `755c8a3acea1497e8e5f193da2e3b6f145d464744e36484a8b0d2ca119682c51` |

报告 §证据与标签、包内 README、PREVIEW §5 均说明缺失项为嵌有本机路径的执行器，记载摘要、公开包可校验的范围和完整重放的先决条件。披露足以区分公开核对与完整复放；外部读者仍缺摘要相同的执行器。本轮使用仓库外四份完整留存件，两个种子的 `check --backend dualhost --compare` 均返回 `violations=0 reproducible=yes`，合计核对 64 次运行。R2 包扫描并核对摘要 `81b325f3275574a615cae24b7b216c9a55d6da253ab5658b639901546a8b2f9a`；该包于 2026-11-16 按 #128 脱敏后重打包，现摘要 `bfff182e64340be122b92b2bd9e806b5f9b120a38b703eccfb4ea206aceae4a7`，与报告相符。没有把 R2 或 R4a 冒烟当作 R4 验收件。

### A7.5 GitHub 设置、披露与外部事实

| 一手来源 | 已观察 | 维护者动作 |
|---|---|---|
| GitHub 仓库 REST API | private；只 squash、合后删分支；描述仍为旧文案，topics 空 | 更新描述和 topics；按 §10 有序转公开 |
| GitHub Actions 权限 API，`.github/workflows/` | 允许 all actions，`sha_pinning_required=false`；默认权限 read；已跟踪 workflow 的 checkout 均为完整 SHA | 生效 allowlist、强制 SHA，核对 fork 审批 |
| main protection / rulesets、secret scanning、私密报告 API | protection/rulesets 403，secret scanning 与私密报告端点 404；当前访问不能确认这些控制已启用 | 转公开后按设置文档实测并记录保护、扫描、私密报告 |
| CONTRIB §11、SECURITY:19–33 | 仓库内 DCO 检查和安全渠道说明已建立；尚待公开后真实 fork 路径验证 | 缺签阻合并、补签解锁；启用并验证私密漏洞报告 |
| 31 个远端 evidence refs、PREVIEW:39,143–145 | 附注标签 30 个，轻量标签 1 个，未找到签名块；说明披露未有发布签名根 | 选定发布 commit、记录带外摘要和标签签名状态 |
| #128、OQ-01、PREVIEW §10 | 名称、商标、兼容性和发布步骤仍交维护者 | 执行检索和决定，本轮未查询外部名称数据库 |

## A8 — 机械一致性

- `make test` 退出 0，25 组 unittest、880 项，另含跨语言、C++、sanitizer 和公开证据检查。单独 `make check` 退出 0，23 组 unittest、692 项。另行运行 `make verify-source`、许可覆盖、交付清单与仓库证据检查均退出 0。CI 的 DCO、local-validation 在基线 SHA 通过。
- Markdown 解析 216 份文档、231 个围栏、1,194 个相对链接或本地锚点。四个 H1 规则候选在 P0 同样存在：三个 GitHub 模板和一份历史数学稿。围栏配对与相对目标文件通过；新增一个无效章节锚点，详见新发现 001。默认严格扫描退出 1。
- `git diff --check` 空树对 HEAD 退出 2，194 个诊断与 P0 相同（历史 Markdown 硬换行及 EOF 空行）；P0 到 HEAD 的默认 `git diff --check` 退出 0。没有用格式整理改写历史。 `git ls-files --eol` 退出 0：758 LF、30 非文本、2 无行尾标记，索引与工作树类型相同。
- 权威登记按文件核对无重复：DP 17、TH 39、INV 16、ADR 9、CLM 27、PO 18、OQ 14、Gate 7。对应编号来源为 `design-principles.md`、`threat-model.md`、`invariants.md`、`docs/05-decisions/`、`claims-and-sources.md`、`robustness.md`、`open-questions.md` 与 `current-status.md`。仓库证据及交付清单检查确认了本轮归档路径。阶段入口过期和 R1 锚点已登记。

## A9 — 发现与结论

### P0 发现逐项回验

下表的状态均指本轮固定的 main。关闭仓库内修复项不代表对应的线上发布门禁已经实测。命令证据编号见附录。

| 编号 | 本轮状态 | 定位与证据；尚需动作 |
|---|---|---|
| AUD-20261115-002 | CLOSED_ON_MAIN | `SECURITY.md:19–35`、CONTRIBUTING §10、README:202 和 PREVIEW §9 可定位渠道、备选私下流程和响应边界；#142/#148，M4/M8。启用真实私密报告归 009。 |
| AUD-20261115-003 | CLOSED_ON_MAIN | CONTRIBUTING:184–195、`.github/workflows/dco.yml`、`scripts/check-dco.py`、PR 模板；#142/#147/#148。当前基线 push DCO 及本地检查通过（M6/M8）。外部 fork 阻合并实测归 §10。 |
| AUD-20261115-004 | CLOSED_ON_MAIN | `REUSE.toml:3–126`、`Makefile` 的 `check-license-coverage`、OQ-01:75–89；#145/#155、#128 文件外声明决定。M4 覆盖 342、缺失 0。 |
| AUD-20261115-005 | CLOSED_ON_MAIN | PREVIEW:3–39、§§5、7–10；#148/#160。公开研究快照、元数据权威、可见性与打标签分段、撤回和 DCO 实测均已写明，旧受邀/不得再分发措辞退出当前说明（M7）。 |
| AUD-20261115-006 | CLOSED_ON_MAIN | README:3–17、OQ-01:77、PREVIEW §1；#148/#154。统一成熟度声明和无可部署软件已落位（M7）。 |
| AUD-20261115-007 | OPEN | OQ-01:63–77、current-status:160–164、PREVIEW §10 A 第 1 项。名称、商标、软件包名与兼容性政策由维护者处理，本轮排除检索（#128/#161）。仍为原发布 BLOCKER。 |
| AUD-20261115-008 | OPEN | R4 证据部分已完成：#159/#160、R4 报告 §§结论、证据与标签、M5/M6。最终发布 commit 尚待维护者选定并依 PREVIEW §10 第 9–15 项复核 CI、证据和发行资产。第 7 项现在要求 R4，历史 FM-S3 结论保留。 |
| AUD-20261115-009 | OPEN | `public-repository-settings.md:3–15` 已规划（#141）；API 实测当前 private、Actions all、SHA 强制关闭，保护/规则集 403，私密报告等端点 404（M8）。由维护者完成线上落地、核对与记录。 |
| AUD-20261115-010 | CLOSED_ON_MAIN | `current-status.md:211–216`、OQ-01:72–77、ENV-1 的阶段授权、DUALHOST-SSH-1:70–72；#128、#131/#134/#142/#143/#145。DCO、历史、实机权限与安全层统计各有决定入口（M7）。 |
| AUD-20261115-011 | CLOSED_ON_MAIN | AGENTS:6、ENV-1 的本地多 VM 段、DUALHOST-SSH-1:6–10,70–72、minimal-verifier-baseline 的验证路径段。历史暂停、11-14 恢复和 11-15 阶段授权已区分（#134/#142/#143、M7）。 |
| AUD-20261115-012 | CLOSED_ON_MAIN | OQ-01:75 与 README:200–204 许可陈述一致；README:7、CONTRIBUTING:5 已更新。LICENSE 字节保持（#145/#148、M4/M7）。 |
| AUD-20261115-013 | CLOSED_ON_MAIN | `third-party-materials.md:13–45`、state3 `Cargo.toml`、REUSE.toml、OQ-01:77。历史两份 Cargo 清单由外置声明覆盖，NOTICE 判断有适用边界（#145/#155、M4）。 |
| AUD-20261115-014 | CLOSED_ON_MAIN | CONTRIBUTORS:10,24–32；#142 补 Copilot 和维护主体说明；DeepSeek 归因以 #148 维护者明确确认评论为据（M7/M8）。 |
| AUD-20261115-015 | OPEN | current-status:5,9,15 保留 11-13 日期并仍把安全层蒙特卡洛列为下一步，第 206 行已记录 R4 完成。C1 #131 已移除原 M1/M2/M9 的“下一动作”正文。剩余入口同步由 P1-g 处理，保留日志原日期（M7）。 |
| AUD-20261115-016 | CLOSED_ON_MAIN | codocs README:11,26–33 及四份 `SUPERSEDED` 横幅；#143。历史正文未动，现行 ADR 范围到 0009（M7）。 |
| AUD-20261115-017 | CLOSED_ON_MAIN | P0 后记及 #128 维护者换前缀决定；current-status:212、R1 §8、#114/#120–124 的现行题名对照（M7/M8）。历史决定原话的旧称保留。 |
| AUD-20261115-018 | CLOSED_ON_MAIN | `.github/workflows/validate.yml:15–38`、公开设置 §CI toolchain drift、DCO workflow、许可 Make target。已采用 P0 允许的漂移处置，保留 Ubuntu tag/APT 的可变性并记录控制；Checkout 以 SHA 固定（#141/#142/#145、M4/M8）。 |
| AUD-20261115-019 | CLOSED_ON_MAIN | `.gitignore:36–45` 覆盖本地代理、IDE 和 `.env*`，M7 的 `git check-ignore -vn` 验证命中（#141）。 |
| AUD-20261115-020 | OPEN | GitHub 仓库 API 的现用描述和空 topics（M8）。由维护者修改，无仓库写操作。 |
| AUD-20261115-021 | CLOSED_ON_MAIN | README:9,17、PREVIEW:136、#101 仍 OPEN。#148 明示固定协调器、来宾级证据和独立性边界（M7/M8）。 |
| AUD-20261115-022 | CLOSED_ON_MAIN | A7.1 在本基线重扫 Git 历史、证据包及 GitHub 正文和评论，未发现凭据（M2/M3）。选定发布 commit 后重扫是维护者发布步骤。 |
| AUD-20261115-023 | OPEN | P0 A7.2 仍记录第三方历史邮箱；A7.2 的 R2 新增包也带上游内核联系人。维护者决定公开前是否告知、如何登记。本报告仅列范围（#128 决定 4、M2/M3）。 |
| AUD-20261115-024 | OPEN | AGENTS、`.claude/skills/` 与交付范围为跟踪内容；镜像 refs 单独枚举（M1/M7）。维护者确认代理流程公开及推送范围。不得将本地 `refs/agents/*` 或本地工作分支镜像推送。 |
| AUD-20261115-025 | CLOSED_ON_MAIN | PREVIEW:39,143–145 已披露来源未签名和 SHA 的限度（#148，M7/M8）。最终发布标签采用何种签名及 Release 披露仍由维护者决定。 |
| AUD-20261115-026 | OPEN | `docs/00-overview/aclt-theater.html:8–10` 有 Google Fonts 运行时请求；third-party-materials:13–21 记录字体与外部审计来源（M7）。字体本地化、外部材料及 AI 产出权利是否另行审阅由维护者决定。 |
| AUD-20261115-027 | OPEN | README 为中文入口；CONTRIBUTING §10 有行为要求；`.github/ISSUE_TEMPLATE/` 两份，无独立 CODE_OF_CONDUCT（M7）。由维护者决定协作入口范围。 |

### 前次审计遗留项

| 编号 | 本轮状态 | 依据 |
|---|---|---|
| AUD-20261106-012 | OPEN | 由 AUD-20261115-008 承接。R4 替换发布清单的主要双机证据要求，实跑、SHA 与复放已核对，最终发布 commit 的清单步骤尚待维护者执行（PREVIEW §10、#160、M5/M6）。 |
| AUD-20261106-016 | CLOSED_ON_MAIN | 披露要求由 P1-c #148 落地，见 PREVIEW:39,143–145 与本轮 025；签名根依旧不存在，最终标签状态由 Release 记录（M7/M8）。 |
| AUD-20261106-017 | OPEN | 2026-11-14 许可决定已写入 README:200–204、CONTRIBUTING §11、OQ-01:68–77（#145/#148、M4/M7）。名称、商标、兼容性政策仍归 007。 |
| AUD-20261106-018 | ACCEPTED_BY_MAINTAINER | #128 2026-11-15 决定 4 接受维护者的历史内容随仓库公开，并在 current-status:211 及 PREVIEW:145 落地（#143/#148，M7/M8）。他人信息的决定仍归 023。 |

### 本轮新增发现

| 编号 | 级别／状态 | 证据、影响及处置 |
|---|---|---|
| AUD-20261116-02-001 | MINOR／OPEN | R1 `first-public-release-safety-plan.md:306` 的 §5.6 相对锚点缺少标题日期后缀，目标 `parallel-workflow.md:155` 实在。点击不能定位理论缺口规则。P1-g 修链接并复验（M7）。 |
| AUD-20261116-02-002 | MINOR／OPEN | R4 报告第 187 行写第 12 类 13 个子场景，`test_negative_exit_codes.py:446–585` 注册 14 个。13 是该测试模块方法数。#160 增量审计 PRA-160-03 已指出，本基线仍在。P1-g 修报告计数，现有测试和运行记录可继续使用（M6/M7）。 |
| AUD-20261116-02-003 | MINOR／OPEN | R4 报告第 199 行和冻结的 PREVIEW 第 36 行把首次中断目录写入使用“四份清单”的叙述。报告历史段已说明中断，仓库外的中断目录亦没有清单；清单只对应四个完成的 campaign。P1-g 修 R4 报告。冻结 PREVIEW 的措辞由维护者决定如何记录，本回验未改（M5/M7）。 |
| AUD-20261116-02-004 | NOTE／OPEN | 新增 R2 包的串口记录复制了上游内核联系人字段，见 A7.2。它是新增分发范围的登记，维护者在处理 AUD-023 时一并决定。与物理 SSH 地址、凭据无关（M2）。2026-11-16 维护者决定：不保留；P1-g（#163）已按 #128 将公开包中的邮箱字段替换为 `<redacted-email>` 并重打包。 |

本轮新增计数：0 BLOCKER、0 MAJOR、3 MINOR、1 NOTE。P0 及更早遗留项按上表保留原编号及责任归属。

### 分维度结论

| 维度 | 结果 | 理由 |
|---|---|---|
| 语义连续性 | PASS | 现行规范对象不变，R1/R4 公开结论与阶段决定及实际证据相符。 |
| 目标 Gate 退出 | NOT_ASSESSED | #161 不包含 Gate 验收。 |
| 结构完整性 | FAIL | R1 新增失效章节锚点。绝对空树 diff 检出 P0 已有格式，增量 diff 清洁。 |
| 历史隔离 | PASS | 旧正文、失败与中断证据保留，证据来源区分明确，详见 A6 与发现 003。 |
| 发布准备 | FAIL | 原 BLOCKER 007 未关闭，且 008 的最终发布核验、线上 009 等维护者工作尚未完成。 |

**代理侧剩余工作。** P1-g 更新状态入口（015），修 R1 相对锚点和 R4 报告计数，澄清四份完整清单范围。没有新增代理侧 BLOCKER 或 MAJOR。按正常 PR 审查，合入后增量核对。

**维护者侧剩余工作。** 完成 007 的检索与政策、009 的线上设置、020 的描述与 topics、023 的第三方历史与新增范围决定、024 的公开文件及 refs 范围、026 的字体和第三方权利决定、027 的协作入口决定。确认冻结 PREVIEW 的可接受记录方式。选定承载报告的发布 commit，执行 §10 从转公开前检查、转公开后实测到发布前复跑、源码包对拍、DCO 门禁、签名状态和 Release 资产核对的步骤；在目标提交上重扫凭据。008 与前次 012 的发布步骤随此验收。

**允许开展。** 交 dsh 原样入库并更新状态日志；另开 P1-g 和维护者准备事项；在所选发布 commit 上按发行说明完成验证。

**禁止宣称。** 仓库已具备公开条件、名称可用、已通过法律审查、任何 Gate 退出、conformance、生产或主网可用、身份独立或统计独立。R4 的有限实验结论也不提供总体安全或概率保证。

## A10 — 交付、限制与审计签署

Codex 仅交付这份中文报告及仓库外摘要和 SHA-256 清单。交付映射为本文件进入 `docs/08-governance/audits/audit-20261116-02-public-release-recheck.md`；dsh 独立完成入库、状态日志一行与交付清单维护，Gate 列为“不变”。本轮没有准备仓库修订、报告 PR 或发布资产，没有改变 Issue 状态。

签署：Codex，#161 只读回验代理。凭据模式扫描的覆盖范围见 A7，不对不可见引用、私有第三方账户或未选定的未来发布提交作结论。归档扫描和复放只处理留存证据。

## 附录：命令与退出码

| 编号 | 命令或类别 | 退出码 | 结果 |
|---|---|---|---|
| M1 | `git clone --mirror`；临时镜像内 `git fetch origin`、`git worktree add --detach <临时树> refs/heads/main`、`git rev-parse HEAD` / `git status --porcelain` | 0 | 固定 `d0bf56e`，开始时干净。 |
| M2 | `git rev-list --objects --all`、`git cat-file --batch`、历史路径枚举、Python tar/zip 递归及有界模式重扫 | 0 | A7.1–2 的历史、凭据和新增个人信息。 |
| M3 | `gh api --paginate --slurp` 的 issues、pulls、issues/comments、pulls/comments、逐 PR reviews；GraphQL discussions；正文离线扫描 | 0（重试后） | 127 个 PR review 请求均成功。讨论首次超限退出 1；正文扫描重跑曾因输入 glob 自包含退出 1，修正后通过。 |
| M4 | `make check-license-coverage`；`python3 -B scripts/update-manifests.py --check`；`make verify-source`；`python3 -B scripts/check-repository-evidence.py --repository .` | 0 / 0 / 0 / 0 | 342 覆盖、缺失 0；清单及来源通过。 |
| M4a | `git diff --quiet 5235424 HEAD -- LICENSE`；`diff -u /usr/share/common-licenses/Apache-2.0 LICENSE` | 0 / 1 | LICENSE 字节与 P0 一致；本机对照只有开头空行和版权示例差别。 |
| M5 | `git rev-parse evidence/20261116-r4-safety-mc^{commit}`；`sha256sum` R2/R4；`tar -xzf` R4 至临时目录；四次 `sha256sum -c --ignore-missing manifest.sha256` | 均 0 | 标签 `a9aeddb`，两包摘要、四清单匹配。 |
| M6 | 按两个种子执行 `python3 -B experiments/aclt-minimal-verifier-baseline/montecarlo.py check --backend dualhost --output <pass1/seed> --compare <pass2/seed>`；`python3 -B scripts/check-dco.py push --before 480bbc4 --after HEAD` | 0 / 0；0 | 两个种子的完整留存件分别复放通过；DCO 基线通过。 |
| M7 | MarkdownIt CommonMark/H1/fence、相对链接与 GitHub 风格标题锚点；登记表与归档差异；`git check-ignore -vn`；`git ls-files --eol` | 1（Markdown）；其余 0 | A8。P0 复核复现四个既有 H1 候选；新增一个失效锚点。 |
| M7a | `git diff --check <空树> HEAD`、`git diff --check <空树> 5235424`、`git diff --check 5235424..HEAD` | 2 / 2 / 0 | 两份空树比对各 194 个历史诊断，增量 0。 |
| M8 | GitHub repo、Actions 权限/默认值、基线 check-runs、#128/#161、远端主线与标签等只读查询 | 0；保护等子端点 1 | `local-validation` 和 `dco` 均通过。上文区分无法取证的私仓设置。 |
| M9 | `make test`；`make check` | 0 / 0 | A8；本地套接字可用，未触发远端实验。 |
| M10 | `git status --porcelain`（审计树、测试后）、`git worktree remove <临时树>`、`git worktree list --porcelain` | 0 / 0 / 0 | 清理结果见 A0；原检出预存未跟踪文件保留。 |
