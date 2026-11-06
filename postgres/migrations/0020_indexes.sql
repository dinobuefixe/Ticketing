CREATE INDEX idx_orders_costomers_create
    ON orders (costumer_id, created_at DESC);

    