# ACLt 工作会话入口

- 开始后续开发、验证或交接前，读取 `docs/08-governance/environment-standard.md` 和 `docs/08-governance/dualhost-ssh-validation.md`。
- 多分支并行开发按 `docs/08-governance/parallel-workflow.md`（PARALLEL-1）进行。主检出留在 `main`，作为调度会话。每个条目用一个独立 worktree 会话：先用 `/aclt-plan` 规划，合并前用 `/aclt-sync` 同步。审计在新的只读会话中用 `/aclt-audit <PR>`。Codex 等代理不支持这些命令时，直接按 `.claude/skills/<名称>/SKILL.md` 执行；审计不得由实现该条目的代理承担（PARALLEL-1 §3.1）。
- 推进中遇到的理论缺口——实现、验收或证据依赖某个性质，但它没有模型、推导或估计——必须报告维护者，由维护者做数学建模；条目会话登记 `theory-gap` Issue，审计会话只在审计评论中列出缺口。代理不得自行建模，不得为通过验收挑选参数（PARALLEL-1 §5.6）。
- 2026-11-12 维护者曾因远端算力不足暂停双物理机验证，改用同宿主多虚拟机（见 ENV-1 的「本地多虚拟机验证」）。此后，2026-11-14 的容量对照与 M3 经维护者重新授权使用物理机；2026-11-15 起，维护者授权整个首次公开发行阶段占用物理机（#128）。物理机运行仍按 DUALHOST-SSH-1 执行，并取 PARALLEL-1 §6.4 的锁。
- 本地单元、模型、对拍和回归仍保留；单机阶段、P0-1B、G2 均未因此关闭。
- 两台独立物理主机仅为有限实验接受假设，不得推导身份/统计独立或生产保证。
- 双机约定继续用于解释已有物理主机证据。VM 证据记录共同宿主及各来宾的实际拓扑。SSH 适用时使用严格主机密钥检查，凭据由操作者保管。
- 沿用 CONTRIBUTING.md；保留历史失败证据，不把历史测试通过记录当作本次执行结果。
- DCO（CONTRIBUTING §11）：代理产生的提交不加 `Signed-off-by`，由维护者在 squash 合并时签署。
