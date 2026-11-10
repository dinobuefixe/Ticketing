-- Reserva lugares (ou places em standing) de forma atómica.
-- ARGV: 1 hold_id, 2 ttl (s), 3 dados JSON, 4 section_id (vazio se sentada),
--       5 places (0 se sentada), 6.. seat_ids
local hold_id = ARGV[1]
local ttl = tonumber(ARGV[2])
local section_id = ARGV[4]
local places = tonumber(ARGV[5])

-- 1. Nenhum lugar pode estar vendido nem reservado por um hold ainda ativo
for i = 6, #ARGV do
  local seat = ARGV[i]
  if redis.call('SISMEMBER', KEYS[2], seat) == 1 then
    return {'SOLD', seat}
  end
  local holder = redis.call('HGET', KEYS[1], seat)
  if holder and redis.call('EXISTS', 'hold:' .. holder) == 1 then
    return {'HELD', seat}
  end
end

-- 2. Standing: lugares livres suficientes
if places > 0 then
  local left = tonumber(redis.call('HGET', KEYS[3], section_id) or '0')
  if left < places then
    return {'NO_PLACES', section_id}
  end
  redis.call('HINCRBY', KEYS[3], section_id, -places)
  redis.call('HSET', KEYS[4], hold_id, section_id .. ':' .. places)
end

-- 3. Marcar os lugares e criar a chave do hold com TTL, tudo no mesmo script
for i = 6, #ARGV do
  redis.call('HSET', KEYS[1], ARGV[i], hold_id)
end
redis.call('SET', 'hold:' .. hold_id, ARGV[3], 'EX', ttl)
return {'OK'}