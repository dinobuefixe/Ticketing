"""Mini app do Projeto A (Ticketing).

Cada fluxo tem o seu router em app/routes/. Este ficheiro só cria a app e liga os routers.
Quem age é indicado pelo header X-User-Id (sem autenticação).
"""

from fastapi import FastAPI, HTTPException, Query, status
from uuid import UUID

from app.deps import CurrentUser
from app.routes.health import router as health_router
from app.routes.cancel import router as cancel_router          # F4 e F6
from app.routes.checkin import router as checkin_router        # F5
from app.routes.checkout import router as checkout_router      # F3
from app.routes.holds import router as holds_router            # F2
from app.routes.reports import router as reports_router        # F7
from app.routes.seat_map import router as seat_map_router      # F1

app = FastAPI(title="Ticketing API", version="0.1.0")

app.include_router(health_router)     # GET /health/services
app.include_router(seat_map_router)   # F1: GET /performances/{id}/seat-map
app.include_router(holds_router)      # F2: POST /performances/{id}/holds
app.include_router(checkout_router)   # F3: POST /holds/{id}/checkout
app.include_router(cancel_router)     # F4 e F6: cancelar encomenda e performance
app.include_router(checkin_router)    # F5: POST /check-in
app.include_router(reports_router)    # F7: relatórios


# ---------- Endpoints que ainda não têm ficheiro de router ----------
# Quando forem implementados, mudam para um ficheiro em app/routes/ e são incluídos acima.

def not_implemented(name: str) -> None:
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=f"{name}: por implementar")


@app.get("/customers/me/orders", tags=["Orders"])
def list_my_orders(
    user_id: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=20),
):
    not_implemented("listar encomendas")


@app.get("/orders/{order_id}", tags=["Orders"])
def get_order(order_id: UUID, user_id: CurrentUser):
    not_implemented("ver encomenda")
