--[[
KRW Transfer Lua Script - Atomic Balance Transfer with Distributed Lock

Phase 5.6: Redis Lua script for atomic KRW balance operations.

Features:
- Acquire distributed lock before transfer
- Atomic debit and credit operations
- Balance validation (prevent negative balance)
- Automatic lock release on completion

Arguments:
  KEYS[1] = lock key (e.g., "wallet:lock:user_id")
  KEYS[2] = source balance key (e.g., "wallet:balance:user_id_1")
  KEYS[3] = dest balance key (e.g., "wallet:balance:user_id_2") [optional for single-user operations]
  
  ARGV[1] = lock token (unique identifier for this lock)
  ARGV[2] = lock TTL in seconds
  ARGV[3] = amount to transfer (positive integer)
  ARGV[4] = operation type: "debit", "credit", or "transfer"
  ARGV[5] = current timestamp (for audit)

Returns:
  {status, source_balance_after, dest_balance_after, error_message}
  status: 1 = success, 0 = failure
--]]

local lock_key = KEYS[1]
local source_key = KEYS[2]
local dest_key = KEYS[3]

local lock_token = ARGV[1]
local lock_ttl = tonumber(ARGV[2])
local amount = tonumber(ARGV[3])
local operation = ARGV[4]
local timestamp = ARGV[5]

-- Helper function to return error
local function error_result(message)
    return {0, -1, -1, message}
end

-- Acquire lock with NX and EX
local lock_acquired = redis.call("SET", lock_key, lock_token, "NX", "EX", lock_ttl)
if not lock_acquired then
    return error_result("LOCK_FAILED: Could not acquire lock")
end

-- Get current source balance
local source_balance = tonumber(redis.call("GET", source_key) or "0")

-- Validate operation
if operation == "debit" then
    -- Check sufficient balance
    if source_balance < amount then
        redis.call("DEL", lock_key)
        return error_result("INSUFFICIENT_BALANCE: Current=" .. source_balance .. ", Required=" .. amount)
    end
    
    -- Perform debit
    local new_balance = source_balance - amount
    redis.call("SET", source_key, new_balance)
    redis.call("DEL", lock_key)
    
    return {1, new_balance, -1, "OK"}
    
elseif operation == "credit" then
    -- Perform credit
    local new_balance = source_balance + amount
    redis.call("SET", source_key, new_balance)
    redis.call("DEL", lock_key)
    
    return {1, new_balance, -1, "OK"}
    
elseif operation == "transfer" then
    -- Validate destination key
    if not dest_key or dest_key == "" then
        redis.call("DEL", lock_key)
        return error_result("INVALID_DEST: Destination key required for transfer")
    end
    
    -- Check sufficient balance
    if source_balance < amount then
        redis.call("DEL", lock_key)
        return error_result("INSUFFICIENT_BALANCE: Current=" .. source_balance .. ", Required=" .. amount)
    end
    
    -- Get destination balance
    local dest_balance = tonumber(redis.call("GET", dest_key) or "0")
    
    -- Perform atomic transfer
    local new_source_balance = source_balance - amount
    local new_dest_balance = dest_balance + amount
    
    redis.call("SET", source_key, new_source_balance)
    redis.call("SET", dest_key, new_dest_balance)
    redis.call("DEL", lock_key)
    
    return {1, new_source_balance, new_dest_balance, "OK"}
    
else
    redis.call("DEL", lock_key)
    return error_result("INVALID_OPERATION: " .. operation)
end
