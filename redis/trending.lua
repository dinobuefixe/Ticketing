local minute_key = KEYS[1]
local sold_key = KEYS[2]
local left_key = KEYS[3]

local event_id = ARGV[1]
local quantity = tonumber(ARGV[2])
local ttl = tonumber(ARGV[3])

redis.call("ZINCRBY", minute_key, quantity, event_id)
redis.call("EXPIRE", minute_key, ttl)
local sold = redis.call("INCRBY", sold_key, quantity)
local left = redis.call("DECRBY", left_key, quantity)

return {sold, left}