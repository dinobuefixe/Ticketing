"""índices para as queries frequentes e para as FKs

Revision ID: 0020
Revises: 0015
"""

from alembic import op

revision = "0020"
down_revision = "0015"  
branch_labels = None
depends_on = None

INDEXES = [
    
    ("orders_customer_created_idx",
     "CREATE INDEX orders_customer_created_idx ON orders (customer_id, created_at DESC)"),
   
    ("tickets_perf_section_active_idx",
     "CREATE INDEX tickets_perf_section_active_idx ON tickets (performance_id, section_id) "
     "WHERE status IN ('valid', 'used')"),
    
    ("scan_records_gate_time_idx",
     "CREATE INDEX scan_records_gate_time_idx ON scan_records (gate_id, scanned_at DESC)"),
    
    ("performances_on_sale_starts_idx",
     "CREATE INDEX performances_on_sale_starts_idx ON performances (starts_at) WHERE status = 'on_sale'"),
    ("venues_city_idx", "CREATE INDEX venues_city_idx ON venues (city)"),
    
    ("orders_perf_status_idx", "CREATE INDEX orders_perf_status_idx ON orders (performance_id, status)"),
    ("payments_order_idx", "CREATE INDEX payments_order_idx ON payments (order_id)"),
    
    ("tickets_order_idx", "CREATE INDEX tickets_order_idx ON tickets (order_id)"),
    ("holds_perf_status_idx", "CREATE INDEX holds_perf_status_idx ON holds (performance_id, status)"),
    ("hold_items_hold_idx", "CREATE INDEX hold_items_hold_idx ON hold_items (hold_id)"),
    ("events_organiser_idx", "CREATE INDEX events_organiser_idx ON events (organiser_id)"),
    ("performances_event_idx", "CREATE INDEX performances_event_idx ON performances (event_id)"),
]


def upgrade():
    for _name, sql in INDEXES:
        op.execute(sql)


def downgrade():
    for name, _sql in reversed(INDEXES):
        op.execute(f"DROP INDEX IF EXISTS {name}")