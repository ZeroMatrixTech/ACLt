# 仓库维护与开发者预览发布准备记录

> 编号：AUD-20261106-001
> 日期：2026-11-06（CET，UTC+01:00）
> 基线：main `b05d567d070ab0cadbdc82346909331005b5164b`（#69），开始时工作区干净。变更准备在本地分支 `docs/preview-maintenance`。
> 类别：文档变更审计，加限域发布准备审计。
> 审计者：Claude（Claude Code）。程序：[审计程序](../audit-procedure.md)。

## 授权与范围

维护者要求“对仓库进行一个总维护更新，然后起草发行说明”。本轮允许读取仓库、在本地分支修改文件、运行本地检查和打包。本轮不做以下事情：

- 推送、PR、标签或发布；
- 双机或 VM 运行；
- 协议语义、对象、状态机、权限、验证数学、资金语义或 V1 能力映射的变化。

审计范围包括：入口与索引的连续性、Markdown 结构与链接、交付范围陈述、许可陈述，以及开发者预览的发布准备。历史报告正文、原日期与失败证据保持不变。

## 发现与处理

| 编号 | 级别 | 发现 | 处理 | 状态 |
|---|---|---|---|---|
| AUD-20261106-002 | MINOR | 根 README 的当前工程入口停留在 2026-10-07 的 state3，没有提到 FM 主线和 P0-1B 新计数 | 改为指向当前状态页，补 FM-S3 摘要与目录行；state3 计数标为历史 | RESOLVED_IN_PREPARED_CHANGE |
| AUD-20261106-003 | MINOR | README 称 LICENSE“未经修改”，但 #69 已填写附录示例版权行 | 改为如实描述；许可条款正文未改 | RESOLVED_IN_PREPARED_CHANGE |
| AUD-20261106-004 | MINOR | 开发指南称更新包不含旧实验和 codocs，与 DELIVERY-SCOPE 及实际包内容冲突（564 个文件，含 codocs 9 个、state1/state2 69 个） | 改写范围说明，并标明 10-14 版范围已被替代 | RESOLVED_IN_PREPARED_CHANGE |
| AUD-20261106-005 | MINOR | 开发指南缺少 FM-S3b/S3c、Task trap 与双机入口 | 新增入口一节和预览打包一节 | RESOLVED_IN_PREPARED_CHANGE |
| AUD-20261106-006 | MINOR | 文档中心“研究与决策”列表有两个“10.” | 重新编号 11～17 | RESOLVED_IN_PREPARED_CHANGE |
| AUD-20261106-007 | MINOR | 文档中心证据列表缺 FM-S3a、S3 收尾、接口切片、Task trap 和 CI 源码修复；CI 修复报告没有任何入口；接口备忘只被 ADR-0008 引用；目录表写“ADR-0001—0007” | 补齐条目与目录行，新增 `releases` 目录行 | RESOLVED_IN_PREPARED_CHANGE |
| AUD-20261106-008 | MINOR | state3 README 链接 `STRICT-POLICY.md` 指向不存在的路径（实际在 `docs/` 下） | 修正链接 | RESOLVED_IN_PREPARED_CHANGE |
| AUD-20261106-009 | MINOR | 状态页快照日期仍为 11-05；主线行仍把已完成的 Task trap 列为待补 | 更新日期和该行；新增“开发者预览”行 | RESOLVED_IN_PREPARED_CHANGE |
| AUD-20261106-010 | MINOR | 环境规范称当前主线为“FM-S3 前的候选 FM-S2” | 更新为候选 FM-S3 audit-only | RESOLVED_IN_PREPARED_CHANGE |
| AUD-20261106-011 | NOTE | AUDIT-FIXES-20261105 依据的外部审计 AUDIT-20261105-01 原文未归档 | 在审计索引登记为已知缺项，不补造原文 | OPEN |
| AUD-20261106-012 | BLOCKER（发布） | Task trap 双机证据的源码基线为 #69 分支（base 3275a63），合并后的 main 只做了快照重放；发布 commit 尚无双机运行 | 列入发行说明检查清单第 4 项 | OPEN |
| AUD-20261106-013 | BLOCKER（发布） | 本轮无法看到 `b05d567` 上的线上 CI 结果（私有仓库，匿名 API 返回 404） | 列入检查清单第 2 项，由维护者确认 | OPEN |
| AUD-20261106-014 | MAJOR（发布） | 没有版本标识、发行说明、反馈渠道或撤回流程 | 起草[发行说明](../../releases/PREVIEW-20261106.md)；标签、渠道和接收者待维护者填写 | RESOLVED_IN_PREPARED_CHANGE（草案）；占位项 OPEN |
| AUD-20261106-015 | MAJOR（发布） | S3 公开证据（config/snapshot/anchor）只以哈希记录，不在源码包中，接收者无法复核 | 发行说明要求作为附件提供，pin 走带外渠道 | OPEN |
| AUD-20261106-016 | NOTE | 发布来源没有签名根，SHA 只证明一致性 | 在发行说明中披露；建议使用签名标签，SHA 走带外渠道 | OPEN |
| AUD-20261106-017 | NOTE | 规范、文档、名称和商标的许可未定 | 预览限定为受邀内部、不得再分发 | OPEN |
| AUD-20261106-018 | NOTE | 历史证据含维护者主机名和本地路径 | 内部预览可以接受；对外发布前另行复审，不改写历史正文 | OPEN |
| AUD-20261106-019 | NOTE | 解包目录中 `make verify-source` 因没有 Git 而失败，这符合设计 | 在发行说明中说明 | RESOLVED_IN_PREPARED_CHANGE |

## 验证

基线 `b05d567`，修改前：

- **本地检查**：`make check` 共 22 组、449 项 unittest 通过（约 51 秒），`make verify-source` 通过，P0-1B 计数为 3/24/92，共 18 个摘要。
- **打包**：`scripts/package-singlehost.py` 连续两次输出逐字节一致：564 个文件，SHA-256 为 `b4572600754fd94a4a4ce27223b27f038666ac6a87bdad364ae8890007e433ef`。
- **解包试跑**：解包到无 Git 的新目录后，`make check` 449 项通过，Git 源码维度为 `NOT_RUN`；`make verify-source` 按设计失败（exit 2）。
- **Markdown 检查**：对 157 份受管 Markdown 做 H1、代码块配对、相对链接和末尾换行检查，发现 1 个断链（AUD-20261106-008）。
- **敏感信息扫描**：没有受管私钥；文档中的 IP 已占位。

修改后：见下文“回验”。另有一次过早启动的 `make test`：在发行说明文件写入之前运行，`check-repository-hardening` 报告 `docs/development.md` 指向尚不存在的 `releases/PREVIEW-20261106.md`，exit 2。这次失败属于运行顺序问题，保留在本节，不作为回验结果。

## 回验

在 `docs/preview-maintenance` 分支的未提交工作树上运行。代码、Schema、向量和证据与 `b05d567` 相同，只有文档和清单不同。

- **清单刷新**：`make manifests` 后，`SINGLEHOST-SHA256SUMS` 与 state3 `SHA256SUMS` 的变动正好对应本轮修改的 8 个文件和 2 个新文件，没有意外项。
- **结构检查**：对 159 份 Markdown（含两份新文件）复检，0 个问题；`git diff --check` 无输出。
- **本地检查**：`make check` 共 22 组、449 项通过。
- **完整测试**：`make test` 通过，约 1 分 46 秒。共 23 组、474 项 unittest；state3 覆盖 68 个验证用例、133 项严格接纳、10 项对抗、204 组精确数据与 408 份畸变结果、20 次 sanitizer 运行和 22 个 Rust/C++ reducer 向量；多节点 32 项检查、24 种顺序和 96 次转换；claim 编码跨语言 29766 例；FM-S1a 179 例；FM-S1b 196 例；RIR 独立核心 161 例。
- **源码校验**：`make verify-source` 通过。
- **打包**：两次打包逐字节一致，566 个文件。因为本节随后又有修改，这个包的摘要不作为发布摘要；发布摘要以发布 commit 上的打包为准。

未运行：双机、VM、线上 CI。本轮不产生新的双机结论。

## 结论

> 语义连续性：PASS（只同步入口、索引和陈述，无协议语义变化）；目标 Gate：NOT_ASSESSED；结构完整性：PASS（以回验为准）；历史隔离：PASS；发布准备：FAIL（AUD-20261106-012、013 两个 BLOCKER 未关闭）。
> 允许开展：合入本维护变更；按发行说明的检查清单准备开发者预览。
> 禁止宣称：预览已发布；任何 Gate 退出、conformance、正式接口准入；生产或主网可用；身份或统计独立。

## 交付与偏离

本记录采用限域格式，没有逐项复制完整模板，也没有独立审计签署。A7 只核对了仓库内的许可文本与陈述，没有做外部法律、名称或商标核查。不涉及双机或 VM 运行。提交、推送、PR、标签和发布均由维护者完成。
