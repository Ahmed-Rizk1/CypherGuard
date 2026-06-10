"""
Lua scripts for atomic Redis operations (SaaS Multi-Tenant).

All scripts use tenant-scoped keys via get_execute_decision_keys().
"""

# ===================================================================
# LUA_EXECUTE_DECISION — Atomic decision execution
# ===================================================================
#
# Atomically executes a decision:
# 1. Checks if the alert has already been processed (idempotency guard)
# 2. If not processed, marks it as executed
# 3. Publishes the decision to the decision log stream
#
# KEYS:
#   [1] = executed flag key (e.g., t:{tid}:executed:{alert_id})
#   [2] = decision payloads hash (e.g., t:{tid}:decision_payloads)
#   [3] = decision log stream (stream:decision_logs)
#   [4] = pending decision key (e.g., t:{tid}:pending_decision:{alert_id})
#   [5] = expiry index sorted set (e.g., t:{tid}:decision_expiry_index)
#
# ARGV:
#   [1] = alert_id
#   [2] = action (BLOCK, ALLOW, APPROVE, REJECT, ESCALATE)
#   [3] = source (mobile, timeout, auto)
#   [4] = trace_id
#   [5] = user_id
#   [6] = timestamp
#
# RETURNS: 1 = executed, 0 = already processed

LUA_EXECUTE_DECISION = """
local executed_key = KEYS[1]
local payloads_hash = KEYS[2]
local log_stream = KEYS[3]
local pending_key = KEYS[4]
local expiry_index = KEYS[5]

local alert_id = ARGV[1]
local action = ARGV[2]
local source = ARGV[3]
local trace_id = ARGV[4]
local user_id = ARGV[5]
local timestamp = ARGV[6]

-- 1. Idempotency guard: check if already executed
if redis.call('EXISTS', executed_key) == 1 then
    return 0
end

-- 2. Mark as executed (TTL = 24 hours for audit trail)
redis.call('SET', executed_key, '1', 'EX', 86400)

-- 3. Publish decision to log stream for async persistence
redis.call('XADD', log_stream, '*',
    'alert_id', alert_id,
    'action', action,
    'source', source,
    'trace_id', trace_id,
    'user_id', user_id,
    'timestamp', timestamp
)

-- 4. Cleanup: remove pending key (may already be expired)
redis.call('DEL', pending_key)

-- 5. Cleanup: remove from expiry index
redis.call('ZREM', expiry_index, alert_id)

return 1
"""


def get_execute_decision_keys(alert_id: str, tenant_id: str = None) -> list:
    """
    Build the 5 Redis keys required by LUA_EXECUTE_DECISION.

    Args:
        alert_id: Unique identifier for the alert/decision.
        tenant_id: Tenant identifier for key scoping.

    Returns:
        List of 5 Redis key strings.
    """
    prefix = f"t:{tenant_id}:" if tenant_id else ""
    return [
        f"{prefix}executed:{alert_id}",
        f"{prefix}decision_payloads",
        "stream:decision_logs",  # Global stream — all tenants write here
        f"{prefix}pending_decision:{alert_id}",
        f"{prefix}decision_expiry_index",
    ]
