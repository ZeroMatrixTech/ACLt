# ACLt 发布后收尾回验

> 编号：AUD-20261118-01  
> 日期：2026-11-18，16:40–16:49 CET（Europe/Budapest，UTC+01:00；GitHub 取证时间 15:41–15:45 UTC）  
> 类别：阶段 #128 的发布后收尾回验，不是 PR 审计，不是 Gate 退出审计  
> 审计代理：Codex；本会话未参与所核对条目的实现  
> 固定 main：`5b3bc9a065b8c78561d67a76ee6694b2f2de5079`（P1-o #199）  
> 交付：供维护者安排归档 PR，归档后加入审计索引；本轮不提交、不发布评论、不关闭 Issue

**一句话结论：本轮审计已无未处理的关闭阻断；维护者明确接受 #196 已合并 PR 的正文补签作为 `cded56d` 的历史 DCO 补救，本报告归档并加入审计索引后，#128 可由维护者关闭。**

> 补充回验：维护者在本会话明确确认“接受正文补签作为历史补救”；本报告据此更新，原始报告副本及失败证据均保留。该决定未写入 GitHub，由本报告归档时形成可引用记录。

## 1. 范围、依据与取证边界

已读取用户级 `~/.codex/AGENTS.md`、`agents/codex/AGENTS.md`，以及 Codex 自有克隆中的 ENV-1、DUALHOST-SSH-1、PARALLEL-1、CONTRIBUTING 和审计程序。按用户本轮指派，应用 aclt-audit 的只读、证据和独立性规则，按阶段回验交付报告；不套用 PR 评论、计划卡和实现验收流程。

执行 `git fetch origin` 后固定上述 main，结束前通过 `gh api --method GET` 再读 main，仍为同一 SHA。原检出 HEAD 为发布提交 `1533290ed82347a5a5006e4d35a5092d02362780`，开始与结束 `git status --porcelain` 均为空。全过程通过固定 SHA 的 `git show`、`git diff`、对象解析及 GET 请求取证，未切换检出、建立分支、修改跟踪文件或标签。仅 fetch 更新 Codex 自有克隆的远端引用；报告、资产副本和证据在仓库外。

主要依据：

- [A15：AUD-20261115 首次审计](https://github.com/ZeroMatrixTech/ACLt/blob/5b3bc9a065b8c78561d67a76ee6694b2f2de5079/docs/08-governance/audits/audit-20261115-01-public-release.md)。该报告发现表从 002 到 027，共 26 项，没有 001；沿用原编号。
- [A02：AUD-20261116-02](https://github.com/ZeroMatrixTech/ACLt/blob/5b3bc9a065b8c78561d67a76ee6694b2f2de5079/docs/08-governance/audits/audit-20261116-02-public-release-recheck.md)、[A03：AUD-20261116-03](https://github.com/ZeroMatrixTech/ACLt/blob/5b3bc9a065b8c78561d67a76ee6694b2f2de5079/docs/08-governance/audits/audit-20261116-03-public-release-recheck.md)，及 [#161 定向复核](https://github.com/ZeroMatrixTech/ACLt/issues/161#issuecomment-6926317381)。
- [Release：research-preview-1](https://github.com/ZeroMatrixTech/ACLt/releases/tag/research-preview-1)，经 Release API 读取完整正文、元数据和资产；不是只读 main 上的发布状态摘要。
- [D16：维护者 2026-11-16 决定](https://github.com/ZeroMatrixTech/ACLt/issues/128#issuecomment-6920084883)、[026 专项决定](https://github.com/ZeroMatrixTech/ACLt/issues/128#issuecomment-6928635421)、[冻结记录](https://github.com/ZeroMatrixTech/ACLt/issues/128#issuecomment-6926480530)。
- [D17：维护者 2026-11-17 决定](https://github.com/ZeroMatrixTech/ACLt/issues/128#issuecomment-6953767333)、[D18：2026-11-18 阶段总结与残余接受](https://github.com/ZeroMatrixTech/ACLt/issues/128#issuecomment-6976415527)、[#195 免做线上实测决定](https://github.com/ZeroMatrixTech/ACLt/issues/195#issuecomment-6976115977)。
- [公开设置清单](https://github.com/ZeroMatrixTech/ACLt/blob/5b3bc9a065b8c78561d67a76ee6694b2f2de5079/docs/08-governance/public-repository-settings.md)、[PARALLEL-1 §2 的 2026-11-18 现状](https://github.com/ZeroMatrixTech/ACLt/blob/5b3bc9a065b8c78561d67a76ee6694b2f2de5079/docs/08-governance/parallel-workflow.md)、[现行第三方材料清单](https://github.com/ZeroMatrixTech/ACLt/blob/5b3bc9a065b8c78561d67a76ee6694b2f2de5079/docs/08-governance/third-party-materials.md)。

本次新执行的是对象、摘要、资产、签署和设置核验。发布前全量测试、凭据扫描、R4 实跑和既有 fork 实测均为历史证据，本次未重跑；未运行 `make check`、`make test`、VM 或物理双机。本轮不重新判断许可或法律结论，也不重新认证协议、部署或完整供应链。未为维护者已免做的实测补建 PR。

偏离记录：本轮不是 PR 审计，依用户明确范围不创建审计 worktree、不运行 PR 全量回归、不发表 PR 评论；以不可变 Git 对象代替检出，下载资产逐文件核对，保留设置读回与失败记录。风险是本轮不新增运行时正确性证据；不把历史运行记录写成本次通过。

## 2. AUD-20261115 发现项最终状态

下表状态截至固定 main 与本次线上读回。`CLOSED_ON_MAIN` 沿用前轮对该发现原始修复范围的判定，不等于所有后续线上行为均已验证；后续新问题单独编号。`ACCEPTED_BY_MAINTAINER` 表示有明确决定，`RESIDUAL_ACCEPTED` 表示技术配置已落实但特定验证或权限边界被接受保留。

| 原发现（AUD-20261115-） | 最终状态 | 本次核对依据及边界 |
|---|---|---|
| 002 安全报告渠道 | CLOSED_ON_MAIN | A02：#142/#148 的 SECURITY、CONTRIBUTING §10、README 与 PREVIEW 已落地。SECURITY 与发布标签字节相同；本次私密漏洞报告 GET `enabled=true`。 |
| 003 DCO 政策、说明及检查缺失 | CLOSED_ON_MAIN | A02：#142/#147/#148 已建立政策、工作流和检查器；#197/#199 进一步明确正文签署及人类/代理分工。原修复仍成立；四次补救见 §6。不得据此声称历史 DCO 全通过，第五次历史漏签及维护者接受的正文补救另见 §7。 |
| 004 SPDX / 文件外覆盖 | CLOSED_ON_MAIN | A02：#145/#155 的 REUSE.toml、许可覆盖检查与 CI 入口；本次 REUSE.toml 与发布标签完全一致，未重新运行全量覆盖测试。 |
| 005 公开发布说明 | CLOSED_ON_MAIN | A02：#148/#160；公开研究快照的许可、计数、限制与清单已落地。标签内仍为冻结 blob；main 仅增状态头注，详见 §3、§5。 |
| 006 成熟度入口 | CLOSED_ON_MAIN | A02：#148/#154；当前 README 保留 draft/research baseline、当前无可部署软件和 P0-1B 未关闭声明。 |
| 007 名称 / 商标 | ACCEPTED_BY_MAINTAINER | A03、D16 决定 1：放弃名称冲突检索，接受同名风险，不声明商标；#176 同步文档，#186 加检索消歧。未开展新的名称检索或判断名称权利。 |
| 008 发布 commit 核验 | CLOSED_ON_MAIN | Release、冻结记录、标签对象、实下载源码包全部文件及发布 commit 两条 push CI 一致；R4 pin 与归档摘要一致，见 §3。 |
| 009 公开仓库设置 | RESIDUAL_ACCEPTED | 本次 GET 与 P1-o #199 的两个现状文档一致；外部 fork 审批和非管理员绕过端到端实测由 D18 明确免做，不能写成已验，见 §4、§8。 |
| 010 决定写入权威文档 | CLOSED_ON_MAIN | A02：#131/#134/#142/#143/#145；现行 current-status 决定日志、ENV-1、DUALHOST-SSH-1 与 DCO 规则保留相应决定和历史边界。 |
| 011 物理机暂停措辞 | CLOSED_ON_MAIN | A02/A03：#134/#142/#143 将 11-12 暂停与后续授权分开记载；#186 仅软件发布术语同步。未由两台物理机推导身份或统计独立。 |
| 012 许可陈述 / 日期 | CLOSED_ON_MAIN | A02：#145/#148；当前许可范围与 LICENSE 一致，LICENSE 与发布标签字节相同。 |
| 013 第三方清单 / Cargo / NOTICE | CLOSED_ON_MAIN | A02：#145/#155；第三方清单与 REUSE 保留，当前 state3 Cargo 元数据声明、历史清单外置覆盖及有范围的 NOTICE 判断仍在；#186 补充 AI 权利依据，没有声称完整法律审查。 |
| 014 贡献署名 | CLOSED_ON_MAIN | A02：#142、#148 维护者确认；#186 进一步更新各代理实际职责与历史作者信息保留。 |
| 015 状态入口过期 | CLOSED_ON_MAIN | A03：#169 修复原问题，#176 定向同步；#186 现行入口记录已发布、已归档审计及线上设置。历史决定日志保留其时点陈述。 |
| 016 codocs 历史横幅 | CLOSED_ON_MAIN | A02：#143；发布后七个合并均未触及 codocs，历史隔离结论仍成立。 |
| 017 theory-gap 与 Gate 编号冲突 | CLOSED_ON_MAIN | A02：维护者 #128 换 TG 前缀决定及 #114/#120–124 核验；本轮未引入新编号混用，现行流程继续区分 TG-6 与 Gate。 |
| 018 CI 漂移与检查 | CLOSED_ON_MAIN | A02：#141/#142/#145；当前清单保留 mutable Ubuntu/APT 和环境检查、漂移处置；DCO 与许可检查入口仍在。未把可变工具链说成完全锁定。 |
| 019 忽略规则 | CLOSED_ON_MAIN | A02：#141；当前 .gitignore 保留 .agents/、IDE、.env* 等规则。本轮不在仓库内创建过程文件。 |
| 020 描述 / topics | CLOSED_ON_MAIN | A03、#128 完成记录；本次 repo GET 仍为 draft 研究与规范基线描述及既定八个 topics。 |
| 021 #101 限制的公开披露 | CLOSED_ON_MAIN | A02：#148；README 与标签发布说明保留固定协调器、证据层级、无许可目标和独立性边界，发布后未上调 Gate/OQ。 |
| 022 凭据扫描观察与发布前复扫 | CLOSED_ON_MAIN | A02 的扫描与 Release §清单第 2 项记载的发布 commit 增量复扫，完成原要求；本次没有重做全历史凭据扫描，不能扩张为当前全历史重新认证。 |
| 023 外部贡献者信息 | CLOSED_ON_MAIN | A03、D16 已告知决定；D17 明确 Ankar 同意随仓库公开，包括历史邮箱；#186 CONTRIBUTORS 同步，Git 历史保留。 |
| 024 内部代理文件交付 | CLOSED_ON_MAIN | A03：#167 移出 main 和交付清单；发布后未重新加入。实下载源码包不含 AGENTS.md 或 .claude/；历史版本按维护者决定保留。 |
| 025 发布签名披露 | CLOSED_ON_MAIN | A02 的 #148 已披露 SHA 和无签名根的边界；本次标签对象为 SSH 签名、GitHub API `verified=true/reason=valid`，Release 保留外部信任根不存在、源码包及 evidence 标签未签名的披露。 |
| 026 外部材料与 AI 权利 | ACCEPTED_BY_MAINTAINER | 026 专项决定接受并要求披露，Release 已披露；字体由 #168 本地化，#186/P1-l 把 DeepSeek 条款及“权利如有”的依据写入 main 第三方清单。发布时与现行措辞分别保留，详见 §4.2。 |
| 027 公开协作入口 | CLOSED_ON_MAIN | A03：#171 行为准则和模板落地；CODE_OF_CONDUCT 与发布标签字节相同。英文适配仍按 D16 暂缓决定接受。 |

原 002–007 的 A02/A03 结论仍成立；本轮没有重新开展这些项目的法律、安全或协议全面审计。003 的原始政策缺失已修复，与本轮发现并由维护者接受正文补救的历史提交是两个不同范围。

### 前两轮回验及其承接项

为避免只关原编号而遗漏续轮发现，附列状态：

| 编号 | 最终状态 | 依据 |
|---|---|---|
| AUD-20261116-02-001 至 004（各项） | CLOSED_ON_MAIN | A03 已逐项关闭：#169 锚点、R4 子场景计数，#169/#170 清单限定，维护者脱敏决定；七个发布后合并未撤销相关修复。 |
| AUD-20261116-03-001 | CLOSED_ON_MAIN | `02476db` 对 `7232164` 的明确认证、可解析签署、空树差异及成功 CI；见 §6。 |
| AUD-20261116-03-002 | CLOSED_ON_MAIN | #176 和 #161 定向复核，#186 后续发布入口同步。 |
| AUD-20261116-03-003 | RESIDUAL_ACCEPTED | #176 修正时序，Release/#181 记录维护者 fork 实验；外部账号范围不足由 D18 接受，#199 明示免做，见 §4。 |
| AUD-20261116-03-004 | RESIDUAL_ACCEPTED | #161 定向复核保留 OFL 原文和归档 Markdown 的历史空格边界；本轮不改写许可或归档字节，不将历史格式失败改判通过。 |
| AUD-20261106-012 | CLOSED_ON_MAIN | 由 008 承接；本次发布 commit、R4 pin、资产、CI 已核对。 |
| AUD-20261106-016 | CLOSED_ON_MAIN | 由 025 承接；披露完整，签名根边界仍在。 |
| AUD-20261106-017 | ACCEPTED_BY_MAINTAINER | 许可决定落地；名称部分由 007 的明确决定接受。OQ-01 整体仍 OPEN。 |
| AUD-20261106-018 | ACCEPTED_BY_MAINTAINER | A02：#128 决定 4 接受历史信息公开；第三方贡献者部分另有 D17 同意记录。 |

## 3. 008：Release、标签、源码包和 CI

| 核对对象 | 本次结果 |
|---|---|
| Release 发布 commit | `1533290ed82347a5a5006e4d35a5092d02362780`，是固定 main 的祖先。API 的 `target_commitish=main` 是创建 Release 的目标字段，不拿它替代标签解引用结果。 |
| 附注标签对象 | `625eb921538fff612378a6c758adcc8feac4db4e`；Git 本地对象与远端 tag ref / tag object GET 一致。 |
| 标签解引用 | `research-preview-1^{}` 为同一个 `1533290...`；API 的标签 verification 为 true / valid。没有建立外部签名信任根。 |
| 冻结发布说明 | 发布提交及标签路径的 blob 均为 `7e79349a28525121124560888d97e4ccfd41b470`；SHA-256 为 `b6ee447ce21060f620100978312fa121de1005b0e431c482753b9da833b92692`，与冻结记录一致。 |
| 源码 ZIP | 实下载资产 `aclt-research-preview-1-src.zip`，65,215,710 字节，804 个成员；SHA-256 为 `0e683b2e3178bc4eec6449f093a0dbc87d1fb5be1fdd2036b8f7bd155133fd3c`，与 Release 正文、API asset digest、标签说明及实下载 .sha256 文件一致。 |
| 包内容与仓库 | ZIP CRC 校验通过；804 个成员的 Git blob 哈希全部与发布提交对应路径相同，差异 0；包含的冻结说明及 SINGLEHOST-SHA256SUMS 亦相同。本次未重新执行两次打包，Release 所记打包对拍为历史执行。 |
| 发布 validation | [run 43943552513](https://github.com/ZeroMatrixTech/ACLt/actions/runs/43943552513)：`head_sha=1533290...`、event=push、completed、success。 |
| 发布 DCO | [run 43943552400](https://github.com/ZeroMatrixTech/ACLt/actions/runs/43943552400)：同一 head_sha、push、completed、success。 |
| R4 | 证据标签 `evidence/20261116-r4-safety-mc` 解引用为 `a9aeddbd706630808bf6a8985646c3075d673d27`；标签快照内公开证据包 SHA-256 为 `8bdf36f4181e23d834621e572299865a676f97fd3c1ed22cc27dbc80546a446a`，与 Release 一致。未重跑双机多 VM。 |

Release 的 `published_at` 和 `updated_at` 都为 `2026-11-16T20:39:30Z`。末次 GET 与初次 GET 正文相同，资产更新时间也仍为发布时点。这些当前读回与七个合并的文件差异共同支持“本轮所查发布对象未被这些发布后条目改动”；本轮未读取完整平台审计日志，不据此保证不存在不可见的历史编辑事件。Release `immutable=false`，不能把当前一致误称为 GitHub 已技术锁定 Release。

## 4. 009 与 026 专项

### 4.1 仓库设置读回

所有设置请求均为 `gh api --method GET repos/ZeroMatrixTech/ACLt/...`，未使用修改请求。

| 项目 / 端点 | 当前值 | 与现行文档对照 |
|---|---|---|
| repo | `visibility=public` | 一致。 |
| `branches/main/protection` | 必需 `local-validation`、`dco`，`strict=true`；要求 PR，经典保护自身批准数 0；`enforce_admins.enabled=true`；force push=false、deletion=false | 与 public-repository-settings 和 PARALLEL-1 §2 一致。 |
| `rulesets/20949967` | Protect main，active，默认分支；批准数 1；stale approvals 作废、last push approval、review thread resolution、extra approval for unattributed changes 均 true；deletion / non_fast_forward 禁止；`bypass_actors=[]`、`current_user_can_bypass=never` | 一致。1 个批准来自规则集，不能误写成经典保护自身要求 1 个。最后一字段只说明当前读回账号，不推导所有 admin 永远不能修改规则。 |
| `actions/permissions` 与 `selected-actions` | enabled=true，allowed_actions=selected，sha_pinning_required=true；patterns=`actions/checkout@*`，github_owned_allowed=false，verified_allowed=false | 一致。 |
| `actions/permissions/workflow` | default_workflow_permissions=read；can_approve_pull_request_reviews=false | 一致。 |
| `actions/permissions/fork-pr-contributor-approval` | approval_policy=all_external_contributors | 已配置；真实外部账号端到端行为未验证，D18 接受免做。 |
| repo `security_and_analysis` | secret_scanning=enabled；secret_scanning_push_protection=enabled | 一致。没有把其他未启用的可选扫描功能泛化为已启用。 |
| `private-vulnerability-reporting` | enabled=true | 一致。未实际发送漏洞报告。 |
| repo 合并设置 | allow_merge_commit=false，allow_rebase_merge=false，allow_squash_merge=true，delete_branch_on_merge=true；squash message=PR_BODY，title=PR_TITLE | 一致。规则集允许方法列表不覆盖仓库级 squash-only 限制。 |
| 合并人限制 | 经典保护无只允许维护者推送的 restrictions；规则集无对应只允许维护者合并的限制 | 与 PARALLEL-1 §4 的“流程约定”一致。 |
| collaborators | Ankarnassia（Ankar）role_name=admin，admin/push=true | 与本轮所列残余事实一致。 |

补充：`web_commit_signoff_required=false`；现行文档实施的是 DCO 工作流及 PR 正文检查，不把这个 Web 编辑器选项等同于已开启。经典保护 `required_signatures=false` 与 DCO 文本签署不是同一机制。

读取 `actions/permissions/fork-pr-workflows-private-repos` 返回 HTTP 422：“Fork PR workflow settings is not allowed for public repositories.” 已保留失败。该端点不适用于公开仓库；本轮外部 fork 审批结论取自上表公共仓库适用端点，不把 422 记成未开启或已通过。

[#181](https://github.com/ZeroMatrixTech/ACLt/pull/181) 的发起者及 head label 为维护者 `tenneidp:dco-fork-test`，closed、未合并；Release 明示其身份偏差。它支持当时缺签阻止、补签通过的限域记录，不能支持真实外部贡献者审批或非管理员绕过实验。D17 原定由非组织成员实测，D18 明确决定不做；采用较新决定，不将其记为仍待实施的阻断项。

### 4.2 外部材料与 AI 产出的权利

事实链一致，但时间层不同：

1. 维护者 2026-11-16 的 026 决定将剩余 AI / 外部审计权利问题记为 `ACCEPTED_BY_MAINTAINER`：AI 内容经审阅并由维护者按 DCO 签署，在其享有权利的范围内 Apache-2.0；DeepSeek 原文保留分发，彼时权利状态未判断；未取得法律意见；后续条款核对不阻断该发布。
2. Release 的“AI 产出与外部材料”段真实披露上述事项，并链接该决定及标签内第三方清单。该发布时记录本次仍相同。
3. #186/P1-l 在 main 的 third-party-materials §1 DeepSeek 一行写明生成来源，引用两份 DeepSeek 条款 §4.2、AI 标识要求 §3.1，表述为“DeepSeek 对输出享有的权利（如有）”转让和合法使用，维护者据此在其享有权利范围内分发；明确未取得法律意见。清单性质段也改为指向这行，没有把权利问题继续全写为未判断。
4. 字体部分已由 #168 本地化并保留 OFL；本轮不重审字体许可或 DeepSeek 条款的法律效力。当前 main 的后续条款依据没有回填发布标签或 Release，不能把它写成发布时已完成的法律结论。

因此 026 维持维护者接受状态；既不标为法律权利已获审计认证，也不因发布时与后续记录的措辞差异重新打开维护者已作出的决定。

## 5. 发布后七个合并逐项核对

`research-preview-1..5b3bc9a` 的 first-parent 历史恰为下列七次合并（表按实际合并顺序，#194 在 #187 之前）。逐项核对真实 main 提交差异，不只看 PR 计划或标题。

共同核对：七个提交之后，发布标签对象、解析提交和标签内发布说明 blob 均保持 §3 的值；main 发布说明均为 `5d4b8a4f51e539df3973ce02fbdb5940b9135a99`。它相对冻结 blob **仅新增四行状态头注**；移除新增头注后逐字节等于冻结文本。其余六个合并没有再修改该文件。Release 当前读回及更新时间见 §3。

| PR / main commit | 实际变化与发布边界 | Gate / OQ 核对 |
|---|---|---|
| [#186](https://github.com/ZeroMatrixTech/ACLt/pull/186) / `c9c1dae` | P1-l：main 头注、入口及术语同步、贡献署名、第三方材料依据、设置记录。冻结说明正文不变，标签与 Release 不回填。该次漏签由 #194 补救。 | OQ-01 仅软件“发行”→“发布”用词；状态未变。 |
| [#194](https://github.com/ZeroMatrixTech/ACLt/pull/194) / `e7051c1` | DCO 补救空提交，树与父提交相同。 | 无文件变化。 |
| [#187](https://github.com/ZeroMatrixTech/ACLt/pull/187) / `27e9718` | B0 盘点、inventory/coverage/依赖数据与历史范围记录；80/36/3 不变，未修改 validator 行为。未改发布说明。 | 未上调 Gate/OQ。 |
| [#188](https://github.com/ZeroMatrixTech/ACLt/pull/188) / `c9a3391` | P1-m：交付分类、摘要清单、打包和检查实现/测试；main 工程规则变化，发布资产仍对应原发布提交。 | 未上调 Gate/OQ。 |
| [#196](https://github.com/ZeroMatrixTech/ACLt/pull/196) / `cded56d` | B0-a：SV-04 从 partial 到 implemented，缺口转记仍为 partial 的 SV-62/SV-118，当前计数 81/35/3；发布快照中的 80/36/3 保留。另有历史 DCO 漏签，维护者接受的正文补救见 §7。 | 这是单条 SV 覆盖登记上调，不能概括为“所有状态均未变”；但 Gate/OQ、完整 SchemaValid、正式接口和主网资格未上调。 |
| [#197](https://github.com/ZeroMatrixTech/ACLt/pull/197) / `b2be03e` | P1-n：PR 正文签署检查、名单、edited 触发、模拟和文档；不改发布说明。线上端到端免做由 #195 后续决定接受。 | 未上调 Gate/OQ。 |
| [#199](https://github.com/ZeroMatrixTech/ACLt/pull/199) / `5b3bc9a` | P1-o：PARALLEL-1 协作规则、当前设置、CONTRIBUTING、残余事项与状态日志。#198 已 closed。 | 未上调 Gate/OQ。 |

机械对照：每个合并前后，open-questions 的 14 行 OQ 索引、current-status 与 README 各 7 行 Gate 表，除软件发布术语归一外完全一致；整个 open-questions 文件相对标签也仅有“发行”→“发布”的替换。审阅 #196 的正式迁移/依赖说明仍写 PLANNED_NOT_RUN、ADR-0006 PROPOSED、OQ/Gate/主网资格不升级。未把覆盖计数变化推导为 Gate 退出。P0-1B 仍 STARTED / NOT CLOSED，OQ-01 仍 OPEN。

## 6. 指定四次 DCO 漏签及补救

以下四次**全部已明确补签**。每个补救提交都在固定 main 上可达，说明明确指向被补签的原完整 SHA 并认证 DCO 1.1；本次用 `git interpret-trailers --parse` 核验签署，补救提交与其父提交树差异均为空。保留原失败，不把补救理解成改写原提交或让原运行转为成功。

| 原漏签 / PR | 原失败证据 | 补救提交 | 本次核对 / 补救 DCO |
|---|---|---|---|
| `29ae7394f0079522403b63a8e09dfc8ce645b3b8` / #168 | [43911879653](https://github.com/ZeroMatrixTech/ACLt/actions/runs/43911879653) failure；签名未被识别为 trailer | `864561a7a13a5055ccb13b631b44c95460c8d47f` | 维护者签署可解析；[43912651361](https://github.com/ZeroMatrixTech/ACLt/actions/runs/43912651361) success。 |
| `723216404fc9683eede7379d6ce5c6dc101856bd` / #167 | [43899444114](https://github.com/ZeroMatrixTech/ACLt/actions/runs/43899444114) failure；签名位于 --- 之后 | `02476db9a14ec53aac1d4c15413cef37e60a0dec` | 维护者签署可解析；[43928075613](https://github.com/ZeroMatrixTech/ACLt/actions/runs/43928075613) success。 |
| `3d12858d5f5379915bac626d5beb7a5247dbf2aa` / #177 | [43943318323](https://github.com/ZeroMatrixTech/ACLt/actions/runs/43943318323) failure；缺 trailer | `1533290ed82347a5a5006e4d35a5092d02362780`（发布提交） | 维护者签署可解析；[43943552400](https://github.com/ZeroMatrixTech/ACLt/actions/runs/43943552400) success。 |
| `c9c1dae389027335e0fb9b0d8907836fd362a0b3` / #186 | [44203447785](https://github.com/ZeroMatrixTech/ACLt/actions/runs/44203447785) failure；缺 trailer | `e7051c1e076cf39c4eab7d660e37fbacb495198c` / #194 | 维护者与 Ankar 两个身份的签署可解析；[44268768553](https://github.com/ZeroMatrixTech/ACLt/actions/runs/44268768553) success。 |

“指定四次均已通过补救提交补签”成立；完整历史还包括 #196 的第五次漏签，现由维护者接受 PR 正文补签作为补救，见 §7。阶段总结的“四次”是此前记录，本报告补全为五次：四次提交补救、一次正文补救。

## 7. 第五次 DCO 漏签与维护者接受的补救

### AUD-20261118-01-001 · MAJOR · ACCEPTED_BY_MAINTAINER

**初审事实（保留）。** [#196 的 main squash 提交](https://github.com/ZeroMatrixTech/ACLt/commit/cded56d753886408e1db45348372258bf62ee66f) 为 `cded56d753886408e1db45348372258bf62ee66f`，2026-11-18T09:34:19Z。其提交说明中签署之后有独立的 badge 段，`git interpret-trailers --parse` 未解析到有效 Signed-off-by。[线上 push DCO run 44277165450](https://github.com/ZeroMatrixTech/ACLt/actions/runs/44277165450/job/134708122665) failure；本轮分别用当时及固定 main 的真实检查器复现该提交 push 范围，退出码均为 1。原提交、原失败和初审报告副本均保留，不改判为历史 CI 通过。

**覆盖。** 对 DCO 引入 `155a752` 之后至固定 main 的 33 个 first-parent 提交逐条解析，共有五个原始缺有效签署的提交：§6 四个，加 `cded56d`。四个已有明确补救提交；#196 采用下面的维护者接受方式，不虚构第五个补救提交。

**补充读回。** [#196 PR 正文](https://github.com/ZeroMatrixTech/ACLt/pull/196) 的 `updated_at=2026-11-18T15:46:58Z`；签署已移到 badge 之后的正文最末尾。重新 GET 并把正文交给 `git interpret-trailers --parse`，退出 0，解析到维护者签署身份，与 `.github/dco-maintainers.txt` 中 signoff 身份一致。该编辑没有修改已经合并的 `cded56d`。

**维护者决定。** 维护者在本审计会话报告“DCO已按照最新协定补签”，并针对明确问题“是否接受对已合并 PR 的正文补签，作为该历史提交的 DCO 补救”回答：**“是，接受正文补签作为历史补救。”** 本轮依该明确决定，将此项从 OPEN 改为 `ACCEPTED_BY_MAINTAINER`，不再作为 #128 的未处理阻断。此为该历史提交的补救决定，不自动改写所有后续 PR 的签署规则。

**记录边界。** 当前 main 仍为 `5b3bc9a`，没有新增补救提交；原 push DCO 失败继续存在，PR 正文补签不是该失败运行重跑通过。本报告归档时应保留本决定、PR 正文读回时间与初审证据，使阶段总结原“四次”记录可由本报告补全为“五次，均已按相应方式处理”。不需为满足本轮审计另行要求维护者采用此前报告建议的补救提交方式。

## 8. 维护者接受的残余事项（按原记录）

以下保持维护者原决定，不评价其取舍；均为 `RESIDUAL_ACCEPTED`：

- **外部贡献者 fork PR 的端到端实测：维护者 2026-11-18 决定不做。#181 是用维护者账号的 fork 做的；组织成员不算外部贡献者。** 当前审批策略已设为所有外部贡献者，但真实外部审批和非管理员不可绕过的端到端行为未实测。依据：D17、D18、Release #181 偏差披露、#199。
- **P1-n 合并后的线上实测：维护者 2026-11-18 决定不做（见 #195）。** 以合并前单元测试、本地模拟为验收依据；未签阻止及 edited 自动重跑的专门端到端实测仍未完成，不能写成已完成。依据：#195 2026-11-18 决定、#199。
- **Ankar 目前是仓库 admin；“只有维护者合并”现在是流程约定，没有技术强制。** 本次 collaborators、保护和规则集读回与 PARALLEL-1 §4 相符。其 admin 身份也意味着可以修改设置，不能用当前无常驻绕过推导不存在管理员管理能力。
- **#186 曾在合并时漏掉签名，已由 #194 补救。** 本次确认空树差异、两身份签署和成功 DCO，原失败仍在。§7 另记 #196 的第五次历史漏签及正文补救接受决定。

另保留既有披露边界：无外部发布签名信任根，evidence 标签未签名、源码包未单独签名；名称同名风险已接受，未取得法律意见；历史许可原文与归档报告的空格诊断不改写。

## 9. 理论缺口、维度结论与关闭条件

本轮未发现新的、为发布收尾验收所依赖而未登记的数学性质。TG-6 [#123](https://github.com/ZeroMatrixTech/ACLt/issues/123) 本次 GET 仍为 open；R4 不报告违反概率、置信区间或上界，只报告限定运行及重放结果，本轮不建模、不选择参数，也不将其关闭。SV-62/SV-118 的迁入缺口仍登记为 partial，未作为已解决。以上不由本报告扩张为新的发布协议保证。

| 维度 | 结论 | 范围 |
|---|---|---|
| 语义连续性 | PASS | 限七个发布后合并及 Gate/OQ 边界；不重新审计协议正确性。 |
| 目标 Gate | NOT_ASSESSED | 本轮不是 Gate 退出审计。 |
| 结构完整性 | PASS | 发布对象、冻结正文、下载资产及设置对照一致；报告编号和证据可定位。DCO 未闭合单列，不以结构通过掩盖。 |
| 历史隔离 | PASS | 冻结标签/正文、历史失败与签署补救原记录保留。 |
| 发布准备 | NOT_ASSESSED | 发布已经发生；本次核对其对象及收尾，不重新宣布历史发布未发生。 |
| 阶段 #128 收尾 | PASS（审计范围） | 新发现的历史 DCO 问题已由维护者明确接受正文补救；无未处理审计阻断。本报告归档及索引仍待维护者安排。 |

本轮新增 0 BLOCKER、1 MAJOR（现为 ACCEPTED_BY_MAINTAINER）、0 MINOR，未处理 OPEN 为 0；不重新打开维护者明确免做的残余实验。P1-o #199 已合并、#198 已关闭；D18 的“回验并归档”前置条件中，回验完成，报告归档及索引尚待安排。

允许开展：维护者安排本报告归档并加入审计索引，然后按其阶段决定关闭 #128。禁止据本报告宣称历史 DCO 全通过、真实外部 fork 或 P1-n 专门线上实测已完成、Gate/OQ 已关闭、完整 conformance、生产就绪、身份/统计独立或全系统安全。关闭阶段属于维护者决定；本轮不执行关闭。

## 10. 本次执行与证据清单

证据目录（本机交付，不写入 ACLt）：`~/Documents/ZeroMatrixTech/agents/codex/logs/AUD-20261118-01/`；资产副本：同代理 `tmp/AUD-20261118-01/`。报告写入 `reports/AUD-20261118-01.md`。归档时保留正文中的固定 SHA 与线上链接，过程日志不必并入源码仓库。

| 本次操作 | 退出码 / 结果 | 主要记录 |
|---|---|---|
| Codex 自有克隆 fetch origin | 0 | origin/main 更新至 5b3bc9a；未改检出 HEAD。 |
| Release、tag、CI、Issue/评论、PR、设置只读 GET | 0；不适用私仓 fork 端点为 1 / HTTP 422 | requests.json、release*.json、tag*.json、ruleset-detail.json、protection.json、actions*.json、fork-approval.json、private-reporting.json、issue*.json、pr*.json、checks-*.json；422 stderr 单独保留。 |
| 下载两个 Release 附件 | 0 / 0 | tmp 内原始 ZIP 与 .sha256。 |
| ZIP SHA-256、CRC、804 个 Git blob 对拍 | 0，差异 0 | asset-and-state-verification.json。 |
| 发布说明 SHA/头注、七次合并差异、祖先关系、四个补救 trailer/空树差异 | 0 | git-verification.json、prNNN-merged.patch。 |
| 每次合并前后 OQ/Gate 索引逐项比较 | 0，均无状态变化 | asset-and-state-verification.json；术语归一仅“发行”→“发布”。 |
| 全段 DCO trailer 枚举 | 0，33 个提交中 5 个原始缺签 | final-verification.json、main-dco-messages.txt；四次补救单列。 |
| #196 当时及当前 DCO 检查器 push 模式 | **1 / 1，失败保留** | cded56d-checker-cded56d.log、cded56d-checker-5b3bc9a.log。 |
| 最终 main / Release GET、git status | 0 | final-verification.json：main 未前进，Release 正文相同，检出仍干净。 |

辅助展示 #181 时遇到其 head repo 已删除返回 null，首次读取 repo.full_name 的展示脚本退出 1；随后改读保留的 head.label 与 user 字段完成核对。此展示失败不作为验证通过证据，也没有通过修改数据规避。

本报告与证据清单均由本次 Codex 审计会话独立核对。未在仓库写入、提交、推送、开 PR、改标签、改 Release、改设置、发送评论或关闭 Issue。

## 11. 补充回验交付记录

补充回验保持仓库只读。已保存 #196 最新 PR 完整 JSON、正文 trailer 解析结果、维护者在本会话的明确接受决定及补充回验元数据，分别见 `pr196-after-body-signoff.json`、`pr196-after-body-signoff-trailers.txt`、`maintainer-body-remediation-acceptance.json`。原初审报告保留在代理 drafts 目录的 `AUD-20261118-01-before-maintainer-acceptance.md`；原报告摘要与原失败日志均保留。更新后的报告另生成新摘要。
