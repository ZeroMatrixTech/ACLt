# ACLt 工作会话入口

- 开始后续开发、验证或交接前，读取 `docs/08-governance/environment-standard.md` 和 `docs/08-governance/dualhost-ssh-validation.md`。
- 多分支并行开发按 `docs/08-governance/parallel-workflow.md`（PARALLEL-1）进行。主检出留在 `main`，作为调度会话。每个条目用一个独立 worktree 会话：先用 `/aclt-plan` 规划，合并前用 `/aclt-sync` 同步。审计在新的只读会话中用 `/aclt-audit <PR>`。
- 2026-11-12 维护者因远端算力不足，暂时暂停双物理机验证，授权后续集成、网络与节点故障实验使用同宿主多虚拟机。当前范围见 ENV-1 的「本地多虚拟机验证」。
- 本地单元、模型、对拍和回归仍保留；单机阶段、P0-1B、G2 均未因此关闭。
- 两台独立物理主机仅为有限实验接受假设，不得推导身份/统计独立或生产保证。
- 双机约定继续用于解释已有物理主机证据。VM 证据记录共同宿主及各来宾的实际拓扑。SSH 适用时使用严格主机密钥检查，凭据由操作者保管。
- 沿用 CONTRIBUTING.md；保留历史失败证据，不把历史测试通过记录当作本次执行结果。
