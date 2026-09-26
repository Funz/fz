"""Cache calculator: cache lookups happen at the fzr level, see ``fz.core``."""

from .base import Calculator


def run_cache_calculation(*args, **kwargs):
    """Cache handling is done at fzr level; reaching this is a cache miss."""
    return {"status": "cache_miss"}


class CacheCalculator(Calculator):
    scheme = "cache"

    def run(self, *args, **kwargs):
        return run_cache_calculation(*args, **kwargs)
