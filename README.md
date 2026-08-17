# RUDCP
An Distributed Computing Solution

[中文 v0.4 文档](https://github.com/tenneidp/RUDCP/blob/main/Project_DOcuments/Cooperate_Files/RUDCP_%E5%AE%8C%E6%95%B4%E9%A1%B9%E7%9B%AE%E6%80%9D%E8%B7%AF%E6%9E%B6%E6%9E%84%E4%B8%8E%E8%AE%BA%E8%AF%81%E6%98%A0%E5%B0%84_v0.4_%E4%B8%AD%E6%96%87.md)

[English v0.4 Documentation](https://github.com/tenneidp/RUDCP/blob/main/Project_DOcuments/Cooperate_Files/RUDCP_Complete_Project_Architecture_and_Argument_Mapping_v0.4_EN.md)

distributed-compute/
├── README.md
├── LICENSE
├── CONTRIBUTING.md
├── SECURITY.md
├── CODE_OF_CONDUCT.md
├── CHANGELOG.md
├── CITATION.cff
│
├── docs/                           # 项目的权威文档中心
│   ├── README.md                   # 文档目录、阅读顺序、文档状态
│   │
│   ├── 00-overview/
│   │   ├── project-overview.md     # 项目目标、边界与非目标
│   │   ├── design-principles.md    # “如无必要勿增实体”等原则
│   │   ├── terminology.md          # 仓单、Provider、Rank 等术语
│   │   └── system-context.md       # 系统参与者及外部环境
│   │
│   ├── 01-requirements/
│   │   ├── functional.md           # 功能需求
│   │   ├── non-functional.md       # 安全、性能、可用性等要求
│   │   ├── threat-model.md         # 攻击者能力、信任假设
│   │   └── invariants.md           # 系统必须始终成立的性质
│   │
│   ├── 02-architecture/
│   │   ├── system-architecture.md  # 完整架构
│   │   ├── identities-and-roles.md # 身份组、职能、权限边界
│   │   ├── trust-model.md          # 信任与去信任化模型
│   │   ├── task-lifecycle.md       # 仓单/任务生命周期
│   │   ├── data-model.md           # 核心数据结构
│   │   └── protocol-flow.md        # 协议交互流程
│   │
│   ├── 03-protocol/
│   │   ├── protocol-spec.md        # 规范性协议正文
│   │   ├── task-assignment.md      # 任务分配
│   │   ├── result-validation.md    # 结果验证与最大验证轮
│   │   ├── reputation.md           # 信用、Rank、升降级
│   │   ├── rewards-penalties.md    # 报酬、惩罚与成本模型
│   │   ├── disputes-disclosure.md  # 争议及道德披露机制
│   │   └── protocol-parameters.md  # 参数定义及约束
│   │
│   ├── 04-analysis/
│   │   ├── robustness.md           # 鲁棒性论证
│   │   ├── incentive-compatibility.md
│   │   ├── sybil-resistance.md
│   │   ├── collusion-analysis.md
│   │   ├── economic-security.md
│   │   ├── administrative-cost.md  # 行政成本是否值得
│   │   └── proof-obligations.md    # 待证明命题与证明状态
│   │
│   ├── 05-decisions/
│   │   ├── README.md               # ADR 使用规则与索引
│   │   ├── ADR-0001-single-repository.md
│   │   ├── ADR-0002-no-unnecessary-entities.md
│   │   └── ADR-xxxx-template.md
│   │
│   ├── 06-research/
│   │   ├── literature-review.md    # 文献综述
│   │   ├── related-systems.md      # BOINC、Golem 等相关系统
│   │   ├── claims-and-sources.md   # 论断—来源对应表
│   │   └── bibliography.bib        # BibTeX 参考文献
│   │
│   ├── 07-roadmap/
│   │   ├── current-status.md       # 已确定、暂定、未解决
│   │   ├── open-questions.md       # 未解决问题及建议
│   │   ├── milestones.md
│   │   └── collaboration-guide.md  # 与合作者交接和分工
│   │
│   ├── 08-operations/
│   │   ├── deployment.md
│   │   ├── observability.md
│   │   ├── incident-response.md
│   │   └── governance.md
│   │
│   └── diagrams/
│       ├── source/                  # Mermaid/PlantUML 等源文件
│       └── exported/                # 导出的 SVG/PNG
│
├── spec/                            # 可被实现和测试引用的形式规范
│   ├── schemas/                     # JSON Schema / Protobuf
│   ├── state-machines/              # 状态机定义
│   ├── algorithms/                  # 协议算法伪代码
│   ├── test-vectors/                # 标准输入、输出与边界案例
│   └── protocol-version.md
│
├── src/                             # 正式实现
│   ├── core/                        # 纯协议逻辑，不依赖网络或存储
│   ├── node/                        # 计算节点
│   ├── coordinator/                 # 若最终确有必要才保留
│   ├── verification/                # 验证、复验、结果聚合
│   ├── reputation/                  # 信用与 Rank
│   ├── ledger/                      # 仓单及参与历史
│   ├── economics/                   # 报酬、成本、惩罚
│   ├── networking/                  # 节点通信
│   ├── storage/                     # 持久化适配层
│   └── api/                         # 对外接口
│
├── simulations/                     # 协议与经济模型仿真
│   ├── scenarios/
│   ├── attacks/
│   ├── parameters/
│   ├── notebooks/
│   └── results/
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── protocol/
│   ├── adversarial/
│   ├── property/                    # 属性测试/不变量测试
│   └── fixtures/
│
├── tools/                           # 开发和研究辅助工具
│   ├── parameter-analysis/
│   ├── data-generation/
│   └── documentation/
│
├── examples/
│   ├── minimal-network/
│   ├── task-provider/
│   └── compute-node/
│
├── config/
│   ├── development/
│   ├── simulation/
│   └── production.example/
│
├── scripts/
│   ├── test.sh
│   ├── simulate.sh
│   └── build-docs.sh
│
├── .github/
│   ├── ISSUE_TEMPLATE/
│   ├── pull_request_template.md
│   └── workflows/
│
└── .gitignore