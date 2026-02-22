# Temporal 高并发性能优化指南

## 问题分析

在高并发场景下，Temporal 可能面临以下性能瓶颈：

1. **History Service 瓶颈** - 所有 workflow 状态变更都需要经过 History Service
2. **数据库 I/O 瓶颈** - PostgreSQL 连接数、磁盘 I/O、锁竞争
3. **Worker 资源限制** - 单个 worker 的并发处理能力有限
4. **任务队列饱和** - 大量任务堆积导致延迟增加
5. **网络延迟** - Worker 与 Server 之间的通信开销

## 优化策略

### 1. Temporal Server 配置优化

#### 1.1 History Shards 分片

```
Shard 数量计算公式：
NUM_HISTORY_SHARDS = 预期并发 Workflow 数 / 每个分片处理能力

推荐值：
- 小规模（<1000 并发）: 16-64 shards
- 中规模（1000-10000 并发）: 128-256 shards
- 大规模（>10000 并发）: 512-1024 shards
```

#### 1.2 服务限制配置

| 配置项 | 默认值 | 高并发推荐值 | 说明 |
|--------|--------|--------------|------|
| `LIMIT_MAX_CONCURRENT_WORKFLOW_EXECUTION_SIZE` | 1000 | 100000 | 最大并发 workflow 数 |
| `LIMIT_MAX_CONCURRENT_ACTIVITY_EXECUTION_SIZE` | 1000 | 100000 | 最大并发 activity 数 |
| `LIMIT_MAX_CONCURRENT_ACTIVITY_TASK_QUEUE_POLLERS` | 100 | 1000 | 最大 poller 数 |
| `LIMIT_MAX_CONCURRENT_WORKFLOW_TASK_QUEUE_POLLERS` | 100 | 1000 | 最大 workflow poller 数 |

### 2. PostgreSQL 数据库优化

#### 2.1 连接池配置

```python
# 推荐连接池配置
DATABASE_CONFIG = {
    "max_connections": 500,
    "shared_buffers": "1GB",
    "effective_cache_size": "3GB",
    "work_mem": "16MB",
    "maintenance_work_mem": "256MB",
}
```

#### 2.2 关键 PostgreSQL 参数

| 参数 | 推荐值 | 作用 |
|------|--------|------|
| `max_connections` | 500 | 允许的最大连接数 |
| `shared_buffers` | 1GB | 共享内存缓冲区 |
| `effective_cache_size` | 3GB | 查询优化器假设的缓存大小 |
| `work_mem` | 16MB | 单个查询操作可用内存 |
| `wal_buffers` | 16MB | WAL 缓冲区大小 |
| `checkpoint_completion_target` | 0.9 | 检查点完成时间比例 |
| `max_wal_size` | 4GB | WAL 最大大小 |

### 3. Worker 优化

#### 3.1 并发控制

```python
from praisonaiagents.temporal import TemporalConfig
from datetime import timedelta

config = TemporalConfig(
    address="temporal:7233",
    task_queue="praisonai-agents-high-throughput",
    worker_count=100,  # 每个 worker 进程的最大并发 activity 数
)
```

#### 3.2 水平扩展策略

```bash
# 启动多个 worker 进程
for i in {1..10}; do
    praisonai temporal worker --task-queue "praisonai-agents-$((i % 3))" &
done
```

#### 3.3 任务队列分片

```python
# 根据任务类型使用不同的 task queue
TASK_QUEUES = {
    "quick_tasks": "praisonai-quick",      # 快速任务（<1s）
    "normal_tasks": "praisonai-normal",    # 普通任务（1-60s）
    "slow_tasks": "praisonai-slow",        # 慢任务（>60s）
}

def get_task_queue(task_duration_estimate: float) -> str:
    if task_duration_estimate < 1:
        return TASK_QUEUES["quick_tasks"]
    elif task_duration_estimate < 60:
        return TASK_QUEUES["normal_tasks"]
    else:
        return TASK_QUEUES["slow_tasks"]
```

### 4. Workflow 设计优化

#### 4.1 Continue-As-New 模式

对于长时间运行的 workflow，使用 `continue-as-new` 防止历史记录过大：

```python
from temporalio import workflow
from datetime import timedelta

@workflow.defn
class LongRunningWorkflow:
    MAX_EVENT_COUNT = 10000
    MAX_DURATION = timedelta(days=30)
    
    @workflow.run
    async def run(self, input_data):
        processed = 0
        while True:
            # 处理任务
            processed += 1
            
            # 检查是否需要 continue-as-new
            if workflow.info().get_current_history_length() > self.MAX_EVENT_COUNT:
                workflow.continue_as_new(input_data)
            
            await asyncio.sleep(60)
```

#### 4.2 大任务拆分

```python
# 不推荐：单个大任务
@activity.defn
async def process_large_dataset(data: LargeDataset):
    # 处理大量数据，容易超时
    return process_all(data)

# 推荐：拆分为多个小任务
@activity.defn
async def process_chunk(chunk: DataChunk):
    # 处理小块数据
    return process_single_chunk(chunk)

@workflow.defn
class ChunkedProcessingWorkflow:
    CHUNK_SIZE = 100
    
    @workflow.run
    async def run(self, data: LargeDataset):
        chunks = split_into_chunks(data, self.CHUNK_SIZE)
        
        # 并行处理所有 chunks
        results = await asyncio.gather(*[
            workflow.execute_activity(
                "process_chunk",
                chunk,
                schedule_to_close_timeout=timedelta(minutes=5),
            )
            for chunk in chunks
        ])
        
        return merge_results(results)
```

### 5. Activity 优化

#### 5.1 心跳机制

对于长时间运行的 activity，实现心跳以支持取消和超时：

```python
@activity.defn
async def long_running_activity(input_data):
    total = len(input_data.items)
    
    for i, item in enumerate(input_data.items):
        # 检查是否被取消
        activity.heartbeat(f"{i}/{total}")
        
        # 处理单个项目
        await process_item(item)
    
    return {"processed": total}
```

#### 5.2 超时配置

```python
from temporalio.common import RetryPolicy
from datetime import timedelta

ACTIVITY_OPTIONS = {
    "schedule_to_close_timeout": timedelta(minutes=30),
    "schedule_to_start_timeout": timedelta(minutes=5),
    "start_to_close_timeout": timedelta(minutes=25),
    "heartbeat_timeout": timedelta(seconds=30),
    "retry_policy": RetryPolicy(
        maximum_attempts=3,
        initial_interval=timedelta(seconds=1),
        backoff_coefficient=2.0,
        maximum_interval=timedelta(minutes=1),
    ),
}
```

### 6. 监控和告警

#### 6.1 关键指标

| 指标 | 告警阈值 | 说明 |
|------|----------|------|
| `service_errors` | > 1% | 服务错误率 |
| `persistence_latency` | > 100ms | 持久化延迟 |
| `task_queue_backlog` | > 1000 | 任务队列积压 |
| `workflow_execution_latency` | > 5s | Workflow 启动延迟 |
| `activity_execution_latency` | > 10s | Activity 执行延迟 |

#### 6.2 Prometheus 指标配置

```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'temporal'
    static_configs:
      - targets: ['temporal:9090']
    metrics_path: '/metrics'
```

### 7. 缓存策略

#### 7.1 动态配置缓存

使用 Redis 缓存动态配置，减少数据库查询：

```yaml
environment:
  - DYNAMIC_CONFIG_CLIENT_BACKEND=redis
  - DYNAMIC_CONFIG_CLIENT_REDIS_HOST=redis
  - DYNAMIC_CONFIG_CLIENT_REDIS_PORT=6379
```

#### 7.2 Visibility 缓存

```yaml
environment:
  - VISIBILITY_QUEUE_ENABLED=true
  - VISIBILITY_QUEUE_BUFFER_SIZE=10000
```

## 部署建议

### 1. 生产环境配置

```bash
# 使用高并发配置
docker-compose -f docker/docker-compose.temporal-high-concurrency.yml up -d

# 扩展 worker 数量
docker-compose -f docker/docker-compose.temporal-high-concurrency.yml up -d --scale praisonai-worker=20
```

### 2. 资源规划

| 组件 | CPU | 内存 | 实例数 | 说明 |
|------|-----|------|--------|------|
| Temporal Server | 4核 | 4GB | 3+ | 奇数个实例 |
| PostgreSQL | 8核 | 16GB | 2+ | 主从复制 |
| Redis | 2核 | 4GB | 2+ | 哨兵模式 |
| Worker | 2核 | 2GB | 10+ | 按需扩展 |

### 3. 容量规划

```
单 Temporal 集群理论吞吐量：
- 每秒 Workflow 启动: 10,000+
- 每秒 Activity 执行: 100,000+
- 并发 Workflow 数: 100,000+

实际吞吐量取决于：
- Workflow 复杂度
- Activity 执行时间
- 数据库性能
- 网络延迟
```

## 故障排除

### 1. 常见问题

#### 延迟高

```
检查项：
1. History Shard 数量是否足够
2. PostgreSQL 连接数是否达到上限
3. Worker 数量是否足够
4. 任务队列是否有积压
```

#### 任务丢失

```
检查项：
1. Worker 是否存活
2. Task Queue 配置是否正确
3. Activity 超时配置是否合理
4. 是否有足够的重试
```

### 2. 调优命令

```bash
# 查看 Temporal 集群状态
tctl cluster health

# 查看任务队列统计
tctl taskqueue describe --taskqueue praisonai-agents

# 查看数据库连接数
psql -c "SELECT count(*) FROM pg_stat_activity;"

# 查看 workflow 历史大小
tctl workflow show -w <workflow-id> | wc -l
```

## 最佳实践总结

1. **合理规划 Shard 数量** - 根据预期并发量设置足够的分片
2. **优化数据库配置** - 连接池、缓存、索引
3. **水平扩展 Worker** - 按需动态调整 worker 数量
4. **任务队列分片** - 按任务类型使用不同的队列
5. **合理的超时配置** - 避免超时过短或过长
6. **实现心跳机制** - 支持长时间运行的 Activity
7. **使用 Continue-As-New** - 防止历史记录过大
8. **监控告警** - 实时监控关键指标
9. **压力测试** - 上线前进行充分的压力测试
10. **逐步扩容** - 从小规模开始，逐步扩容

## 8. Redis 缓存与队列策略

### 8.1 为什么需要 Redis？

虽然 Temporal 本身已经使用 Redis 作为动态配置缓存，但在高并发场景下，业务层面还需要 Redis 来处理：

| 问题 | Redis 解决方案 | 效果 |
|------|----------------|------|
| LLM API 限流 | Token Bucket 令牌桶 | 防止 API 配额耗尽 |
| 重复查询 | LLM 响应缓存 | 减少 30-50% API 调用 |
| 突发流量 | 请求队列缓冲 | 削峰填谷，平滑请求 |
| 优先级任务 | 多级优先队列 | 紧急任务优先处理 |

### 8.2 架构设计

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        高并发请求处理架构                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   用户请求                                                                   │
│      │                                                                      │
│      ▼                                                                      │
│   ┌─────────────────┐                                                       │
│   │  API Gateway    │  ← 限流 (5000 req/min)                                │
│   │  (Nginx/FastAPI)│                                                       │
│   └────────┬────────┘                                                       │
│            │                                                                │
│            ▼                                                                │
│   ┌─────────────────────────────────────────────────────────────┐          │
│   │                      Redis Layer                             │          │
│   │                                                              │          │
│   │   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │          │
│   │   │ LLM Cache    │  │ Rate Limiter │  │ Request Queue│     │          │
│   │   │ (响应缓存)   │  │ (令牌桶)     │  │ (优先队列)   │     │          │
│   │   └──────────────┘  └──────────────┘  └──────────────┘     │          │
│   │                                                              │          │
│   └─────────────────────────────────────────────────────────────┘          │
│            │                                                                │
│            ▼                                                                │
│   ┌─────────────────────────────────────────────────────────────┐          │
│   │                    Temporal Server                           │          │
│   │                                                              │          │
│   │   Workflow Execution → Activity Tasks → Worker Pool         │          │
│   │                                                              │          │
│   └─────────────────────────────────────────────────────────────┘          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 8.3 使用方式

```python
from praisonaiagents.temporal.redis_support import (
    create_redis_components,
    CacheConfig,
    RateLimitConfig,
    QueueConfig,
    CacheAsideLLMWrapper,
    RequestQueue
)

cache_config = CacheConfig(
    enabled=True,
    ttl_seconds=3600,  # 1 hour cache
    key_prefix="praisonai:llm:"
)

rate_limit_config = RateLimitConfig(
    enabled=True,
    requests_per_minute=1000,  # Adjust based on your API quota
    burst_size=100
)

queue_config = QueueConfig(
    enabled=True,
    max_queue_size=10000,
    priority_levels=3  # high, normal, low
)

cache, rate_limiter, queue = create_redis_components(
    redis_url="redis://localhost:6379",
    cache_config=cache_config,
    rate_limit_config=rate_limit_config,
    queue_config=queue_config
)

cached_llm = CacheAsideLLMWrapper(
    llm_client=your_llm_client,
    cache=cache,
    rate_limiter=rate_limiter
)

response = await cached_llm.generate(
    prompt="What is AI?",
    model="gpt-4"
)
```

### 8.4 优先级队列使用

```python
from praisonaiagents.temporal.redis_support import RequestQueue

queue = RequestQueue("redis://localhost:6379")

await queue.enqueue(
    {"task": "urgent_analysis", "data": {...}},
    priority=RequestQueue.PRIORITY_HIGH
)

await queue.enqueue(
    {"task": "batch_processing", "data": {...}},
    priority=RequestQueue.PRIORITY_LOW
)

request = await queue.dequeue()
```

### 8.5 配置建议

| 场景 | Redis 内存 | 缓存 TTL | 限流配置 | 队列大小 |
|------|-----------|----------|----------|----------|
| 小规模 | 1GB | 1 hour | 500/min | 1,000 |
| 中规模 | 2GB | 30 min | 2,000/min | 5,000 |
| 大规模 | 4GB+ | 15 min | 5,000+/min | 10,000+ |

### 8.6 生产环境部署

```bash
docker-compose -f docker/docker-compose.temporal-production.yml up -d

docker-compose -f docker/docker-compose.temporal-production.yml up -d \
    --scale praisonai-worker=10 \
    --scale api-gateway=3
```
