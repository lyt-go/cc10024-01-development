"""内容缓存领域服务：缓存管理和淘汰策略，服务数据导出和页面去重的缓存需求。"""
from __future__ import annotations

import time
from typing import Any

from app.store import store
from app.services.base import BaseModuleService
from app import persistence as persist


class ContentCacheService(BaseModuleService):
    MODULE = "content_cache"
    ENTITY = "缓存配置"
    OPERATION_TERM = "存储"
    LIST_FIELDS = ["配置编号", "缓存类型", "过期策略", "最大容量", "淘汰算法", "预热策略", "命中率", "刷新间隔"]
    REQUIRED_FIELDS = ["配置编号", "缓存类型", "过期策略"]
    STATUS_ORDER = ["草稿", "待校验", "已生效", "已停用"]
    ACTION_RULES = {"提交校验": "待校验", "标记生效": "已生效", "停用配置": "已停用"}
    NEGATIVE_ACTIONS = ["停用配置"]

    # 简单内存缓存实现
    _cache: dict[str, tuple[Any, float]] = {}
    _hit_count: int = 0
    _miss_count: int = 0

    def get_or_fetch(self, cache_key: str, fetcher_func) -> Any:
        """缓存读取：命中返回缓存值，未命中调用fetcher获取并缓存。"""
        if cache_key in self._cache:
            value, expire_at = self._cache[cache_key]
            if expire_at == 0 or time.time() < expire_at:
                self._hit_count += 1
                return value
            del self._cache[cache_key]
        self._miss_count += 1
        value = fetcher_func()
        configs = [c for c in store.rows(self.MODULE) if c.get("status") == "已生效"]
        ttl = 3600
        if configs:
            ttl_str = configs[0].get("刷新间隔", "3600")
            try:
                ttl = int(ttl_str)
            except (ValueError, TypeError):
                ttl = 3600
        self._cache[cache_key] = (value, time.time() + ttl)
        return value

    def domain_snapshot(self) -> dict[str, Any]:
        base = super().domain_snapshot()
        base["cache_hit"] = self._hit_count
        base["cache_miss"] = self._miss_count
        base["cache_size"] = len(self._cache)
        total = self._hit_count + self._miss_count
        base["hit_rate"] = round(self._hit_count / max(total, 1), 4)
        # 出口关联
        channels = store.rows("export_channel")
        base["active_exports"] = sum(1 for c in channels if c.get("status") == "已启用")
        return base