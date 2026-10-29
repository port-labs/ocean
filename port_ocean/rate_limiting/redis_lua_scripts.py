"""Server-side Lua for cross-pod rate-limit *reserve*.

Many integration pods share one Redis hash per API pool (remaining quota,
block window, etc.). Before each outbound call, a pod must decide whether it may
consume one unit of that shared quota.

That decision is a multi-step read/write on the same key: read whether the pool
is in a block window (``blocked_until``), read ``remaining``, and if allowed,
decrement ``remaining`` by one. If two pods run those steps as separate Redis
commands, they can both observe the same last available slot and both proceed.
Redis runs a Lua script as one atomic unit, so the check and decrement cannot
be interleaved with another client.

Publishing updated quota into the hash is a single ``HSET`` with all fields;
one command is already atomic, so it does not need a script.
"""

RESERVE_POOL_SLOT_SCRIPT = """
-- KEYS[1]: pool hash key
-- ARGV[1]: current unix time (seconds)
-- Returns {1} if a slot was taken, {0} if blocked or remaining <= 0.
-- Sync-tier policy stays in Python; this only re-checks block + decrements.

local key = KEYS[1]
local now = tonumber(ARGV[1])

local blocked_until = tonumber(redis.call('HGET', key, 'blocked_until') or '0')
if blocked_until > now then
  return {0}
end

local remaining = tonumber(redis.call('HGET', key, 'remaining') or '0')
if remaining <= 0 then
  return {0}
end
redis.call('HINCRBY', key, 'remaining', -1)
return {1}
"""
