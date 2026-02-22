"""
Redis-based caching and rate limiting for PraisonAI Temporal integration.

This module provides:
1. LLM response caching - reduce duplicate API calls
2. Rate limiting - protect against API quota exhaustion
3. Request queuing - buffer burst traffic
4. Priority queues - handle urgent requests first
"""

import hashlib
import json
import time
import asyncio
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

try:
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    aioredis = None


@dataclass
class CacheConfig:
    enabled: bool = True
    ttl_seconds: int = 3600  # 1 hour default
    max_memory_mb: int = 100
    key_prefix: str = "praisonai:cache:"


@dataclass
class RateLimitConfig:
    enabled: bool = True
    requests_per_minute: int = 1000
    burst_size: int = 100
    key_prefix: str = "praisonai:ratelimit:"


@dataclass
class QueueConfig:
    enabled: bool = True
    max_queue_size: int = 10000
    priority_levels: int = 3  # high, normal, low
    key_prefix: str = "praisonai:queue:"


class RedisCache:
    """Redis-based LLM response cache."""
    
    def __init__(self, redis_url: str, config: CacheConfig = None):
        if not REDIS_AVAILABLE:
            raise ImportError("redis package required. Install with: pip install redis")
        
        self.redis_url = redis_url
        self.config = config or CacheConfig()
        self._client: Optional[aioredis.Redis] = None
    
    async def _get_client(self) -> aioredis.Redis:
        if self._client is None:
            self._client = await aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
        return self._client
    
    def _make_key(self, prompt: str, model: str, **kwargs) -> str:
        content = f"{prompt}:{model}:{json.dumps(kwargs, sort_keys=True)}"
        hash_key = hashlib.sha256(content.encode()).hexdigest()[:16]
        return f"{self.config.key_prefix}{hash_key}"
    
    async def get(self, prompt: str, model: str, **kwargs) -> Optional[str]:
        if not self.config.enabled:
            return None
        
        try:
            client = await self._get_client()
            key = self._make_key(prompt, model, **kwargs)
            cached = await client.get(key)
            
            if cached:
                logger.debug(f"Cache hit for key: {key}")
                return cached
            
            return None
        except Exception as e:
            logger.warning(f"Cache get failed: {e}")
            return None
    
    async def set(self, prompt: str, model: str, response: str, **kwargs) -> bool:
        if not self.config.enabled:
            return False
        
        try:
            client = await self._get_client()
            key = self._make_key(prompt, model, **kwargs)
            await client.setex(key, self.config.ttl_seconds, response)
            logger.debug(f"Cached response for key: {key}")
            return True
        except Exception as e:
            logger.warning(f"Cache set failed: {e}")
            return False
    
    async def invalidate(self, pattern: str = "*") -> int:
        try:
            client = await self._get_client()
            keys = await client.keys(f"{self.config.key_prefix}{pattern}")
            if keys:
                return await client.delete(*keys)
            return 0
        except Exception as e:
            logger.warning(f"Cache invalidation failed: {e}")
            return 0


class TokenBucketRateLimiter:
    """Redis-based token bucket rate limiter."""
    
    def __init__(self, redis_url: str, config: RateLimitConfig = None):
        if not REDIS_AVAILABLE:
            raise ImportError("redis package required")
        
        self.redis_url = redis_url
        self.config = config or RateLimitConfig()
        self._client: Optional[aioredis.Redis] = None
    
    async def _get_client(self) -> aioredis.Redis:
        if self._client is None:
            self._client = await aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
        return self._client
    
    async def acquire(self, key: str, tokens: int = 1) -> bool:
        if not self.config.enabled:
            return True
        
        try:
            client = await self._get_client()
            bucket_key = f"{self.config.key_prefix}{key}"
            
            now = time.time()
            window_start = now - 60
            
            pipe = client.pipeline()
            pipe.zremrangebyscore(bucket_key, 0, window_start)
            pipe.zcard(bucket_key)
            pipe.zadd(bucket_key, {str(now): now})
            pipe.expire(bucket_key, 120)
            
            results = await pipe.execute()
            current_count = results[1]
            
            if current_count >= self.config.requests_per_minute:
                logger.warning(f"Rate limit exceeded for {key}: {current_count}/{self.config.requests_per_minute}")
                return False
            
            return True
        except Exception as e:
            logger.warning(f"Rate limiter error: {e}")
            return True
    
    async def wait_and_acquire(self, key: str, tokens: int = 1, max_wait_seconds: int = 30) -> bool:
        start_time = time.time()
        
        while time.time() - start_time < max_wait_seconds:
            if await self.acquire(key, tokens):
                return True
            await asyncio.sleep(0.1)
        
        return False
    
    async def get_remaining(self, key: str) -> int:
        try:
            client = await self._get_client()
            bucket_key = f"{self.config.key_prefix}{key}"
            
            now = time.time()
            window_start = now - 60
            
            await client.zremrangebyscore(bucket_key, 0, window_start)
            current_count = await client.zcard(bucket_key)
            
            return max(0, self.config.requests_per_minute - current_count)
        except Exception as e:
            logger.warning(f"Get remaining error: {e}")
            return self.config.requests_per_minute


class RequestQueue:
    """Redis-based priority request queue for burst traffic handling."""
    
    PRIORITY_HIGH = 0
    PRIORITY_NORMAL = 1
    PRIORITY_LOW = 2
    
    def __init__(self, redis_url: str, config: QueueConfig = None):
        if not REDIS_AVAILABLE:
            raise ImportError("redis package required")
        
        self.redis_url = redis_url
        self.config = config or QueueConfig()
        self._client: Optional[aioredis.Redis] = None
    
    async def _get_client(self) -> aioredis.Redis:
        if self._client is None:
            self._client = await aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
        return self._client
    
    async def enqueue(self, request: Dict[str, Any], priority: int = PRIORITY_NORMAL) -> bool:
        if not self.config.enabled:
            return False
        
        try:
            client = await self._get_client()
            queue_key = f"{self.config.key_prefix}priority_{priority}"
            
            queue_size = await client.llen(queue_key)
            if queue_size >= self.config.max_queue_size:
                logger.warning(f"Queue full for priority {priority}")
                return False
            
            request_data = json.dumps({
                "data": request,
                "enqueued_at": time.time(),
                "priority": priority
            })
            
            await client.lpush(queue_key, request_data)
            logger.debug(f"Enqueued request to priority {priority}")
            return True
        except Exception as e:
            logger.warning(f"Enqueue failed: {e}")
            return False
    
    async def dequeue(self, timeout_seconds: int = 5) -> Optional[Dict[str, Any]]:
        if not self.config.enabled:
            return None
        
        try:
            client = await self._get_client()
            
            for priority in range(self.config.priority_levels):
                queue_key = f"{self.config.key_prefix}priority_{priority}"
                
                result = await client.rpop(queue_key)
                if result:
                    request = json.loads(result)
                    wait_time = time.time() - request.get("enqueued_at", time.time())
                    logger.debug(f"Dequeued from priority {priority}, wait time: {wait_time:.2f}s")
                    return request
            
            return None
        except Exception as e:
            logger.warning(f"Dequeue failed: {e}")
            return None
    
    async def get_queue_sizes(self) -> Dict[int, int]:
        try:
            client = await self._get_client()
            sizes = {}
            
            for priority in range(self.config.priority_levels):
                queue_key = f"{self.config.key_prefix}priority_{priority}"
                sizes[priority] = await client.llen(queue_key)
            
            return sizes
        except Exception as e:
            logger.warning(f"Get queue sizes failed: {e}")
            return {}


class CacheAsideLLMWrapper:
    """Wrapper that adds caching to LLM calls."""
    
    def __init__(
        self,
        llm_client: Any,
        cache: RedisCache,
        rate_limiter: Optional[TokenBucketRateLimiter] = None
    ):
        self.llm_client = llm_client
        self.cache = cache
        self.rate_limiter = rate_limiter
    
    async def generate(self, prompt: str, model: str = "gpt-4", **kwargs) -> str:
        cached = await self.cache.get(prompt, model, **kwargs)
        if cached:
            return cached
        
        if self.rate_limiter:
            acquired = await self.rate_limiter.wait_and_acquire(
                f"llm:{model}",
                max_wait_seconds=30
            )
            if not acquired:
                raise Exception(f"Rate limit exceeded for model {model}")
        
        if hasattr(self.llm_client, 'generate'):
            response = await self.llm_client.generate(prompt, model=model, **kwargs)
        elif hasattr(self.llm_client, 'acomplete'):
            response = await self.llm_client.acomplete(prompt, model=model, **kwargs)
        elif hasattr(self.llm_client, 'chat'):
            response = await self.llm_client.chat(prompt, model=model, **kwargs)
        else:
            response = self.llm_client(prompt)
        
        if isinstance(response, dict):
            response_text = response.get("content") or response.get("text") or str(response)
        else:
            response_text = str(response)
        
        await self.cache.set(prompt, model, response_text, **kwargs)
        
        return response_text


def create_redis_components(
    redis_url: str,
    cache_config: Optional[CacheConfig] = None,
    rate_limit_config: Optional[RateLimitConfig] = None,
    queue_config: Optional[QueueConfig] = None
) -> tuple:
    """Factory function to create Redis-based components."""
    
    cache = RedisCache(redis_url, cache_config or CacheConfig())
    rate_limiter = TokenBucketRateLimiter(redis_url, rate_limit_config or RateLimitConfig())
    queue = RequestQueue(redis_url, queue_config or QueueConfig())
    
    return cache, rate_limiter, queue
