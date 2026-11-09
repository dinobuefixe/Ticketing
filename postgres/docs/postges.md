## Indexes and EXPLAIN evidence

| Index | Table | Query it supports |
|---|---|---|
| `orders_customer_created_idx` | `orders (customer_id, created_at DESC)` | Orders of a customer, newest first |
| `tickets_perf_section_active_idx` | `tickets (performance_id, section_id)` partial | Valid/used tickets per section |
| `scan_records_gate_time_idx` | `scan_records (gate_id, scanned_at DESC)` | Check-ins per gate in the last hour |

### Q2: orders of a customer
Without the index: <plano colado>
With the index: <plano colado>
Why it is faster: <1-2 frases>
