class CacheError(Exception):
    pass


class FailedToReadCacheError(CacheError):
    pass


class FailedToWriteCacheError(CacheError):
    pass
