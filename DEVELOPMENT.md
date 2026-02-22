# PraisonAI Fork 开发指南

本文档记录了基于官方 PraisonAI 仓库的 Fork 开发流程。

## 仓库配置

```
origin:   git@github.com:warlockedward/PraisonAI.git (你的 Fork)
upstream: https://github.com/MervinPraison/PraisonAI.git (官方仓库)
```

## 当前状态

- **main 分支**: 已包含 Temporal 执行后端集成 (commit: 79dc6dc5)
- **Temporal 功能**: 44 个新文件，5002 行代码

## 日常工作流程

### 1. 开始新功能开发

```bash
# 确保在 main 分支且是最新的
git checkout main
git pull origin main

# 同步官方仓库更新
git fetch upstream
git merge upstream/main

# 创建新功能分支
git checkout -b feature/your-feature-name

# 开发...
git add .
git commit -m "feat: your feature description"

# 推送到你的 Fork
git push origin feature/your-feature-name
```

### 2. 同步官方仓库更新（定期执行）

```bash
# 切换到 main 分支
git checkout main

# 获取官方仓库更新
git fetch upstream

# 合并官方更新
git merge upstream/main

# 推送到你的 Fork
git push origin main

# 如果有本地功能分支，也需要同步
git checkout feature/your-feature-name
git merge main
```

### 3. 向官方仓库提交 PR（贡献代码）

1. **在 GitHub 上创建 PR**:
   - 访问: https://github.com/warlockedward/PraisonAI
   - 点击 "Pull requests" → "New pull request"
   - 选择 base: `MervinPraison/PraisonAI:main` ← head: `warlockedward/PraisonAI:feature/your-feature-name`
   - 或者直接访问: https://github.com/MervinPraison/PraisonAI/compare/main...warlockedward:PraisonAI:main

2. **PR 模板**:

```markdown
## Summary
- Add Temporal execution backend for durable agent orchestration
- Support sequential and parallel process modes
- Implement human approval workflows via Temporal signals
- Add Redis-based caching, rate limiting, and request queuing

## Changes
- New `execution/` package with `ExecutionBackendProtocol`
- New `temporal/` package with workflows, activities, and backend
- Docker Compose configurations for development and production
- Comprehensive documentation and examples

## Testing
- 22 passing tests for Temporal integration
- 88 passing tests for backward compatibility
- All changes are backward compatible

## Usage
```python
from praisonaiagents import Agent, AgentTeam, Task

team = AgentTeam(
    agents=[agent1, agent2],
    tasks=[task1, task2],
    execution="temporal"  # Enable Temporal backend
)
result = team.start()
```

## Documentation
- `docs/temporal-integration.md` - Complete integration guide
- `docs/temporal-high-concurrency-optimization.md` - Performance tuning
- `examples/python/temporal_examples.py` - 8 runnable examples
```

## 已完成的功能

### Temporal 执行后端集成

| 模块 | 文件 | 说明 |
|------|------|------|
| Execution Protocol | `execution/protocols.py` | 后端抽象接口 |
| Local Backend | `execution/local_backend.py` | 本地执行（默认） |
| Temporal Backend | `temporal/backend.py` | Temporal 执行 |
| Workflow | `temporal/workflows/agent_team_workflow.py` | Agent 团队工作流 |
| Activity | `temporal/activities/agent_activity.py` | Agent 任务执行 |
| Config | `temporal/config.py` | Temporal 配置 |
| Converter | `temporal/converter.py` | Agent/Task 序列化 |
| Redis Support | `temporal/redis_support.py` | 缓存、限流、队列 |
| CLI Commands | `praisonai/cli/commands/temporal.py` | CLI 工具 |
| Docker | `docker/docker-compose.temporal*.yml` | 部署配置 |
| Docs | `docs/temporal-*.md` | 完整文档 |
| Examples | `examples/python/temporal_examples.py` | 示例代码 |

### 功能特性

- ✅ 持久化执行（工作流状态保存）
- ✅ 自动重试（内置重试策略）
- ✅ 人工审批（信号机制）
- ✅ 并行执行（asyncio.gather）
- ✅ 工作流模式（route/loop/repeat）
- ✅ Redis 缓存（减少 30-50% API 调用）
- ✅ 令牌桶限流（防止配额耗尽）
- ✅ 优先级队列（紧急任务优先）
- ✅ 完全向后兼容（无破坏性更改）

## 待开发功能

### 高优先级
- [ ] Hierarchical process mode (层次化处理模式)
- [ ] Workflow UI integration (工作流 UI 集成)
- [ ] Metrics export (Prometheus 指标导出)

### 中优先级
- [ ] Activity result caching in workflow (工作流内活动结果缓存)
- [ ] Dynamic worker scaling (动态 Worker 扩展)
- [ ] Multi-namespace support (多命名空间支持)

### 低优先级
- [ ] Temporal Cloud integration (Temporal 云集成)
- [ ] Custom data converters (自定义数据转换器)
- [ ] Advanced signal patterns (高级信号模式)

## 常用命令

```bash
# 查看当前状态
git status

# 查看远程仓库
git remote -v

# 查看分支
git branch -a

# 同步官方更新
git fetch upstream && git merge upstream/main

# 推送到 Fork
git push origin main

# 运行测试
cd src/praisonai-agents && pytest tests/unit/ -v

# 运行 Temporal 相关测试
cd src/praisonai-agents && pytest tests/unit/temporal/ tests/integration/test_temporal*.py -v
```

## 联系方式

- Fork 仓库: https://github.com/warlockedward/PraisonAI
- 官方仓库: https://github.com/MervinPraison/PraisonAI
