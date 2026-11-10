from typing import Annotated
from uuid import UUID

from fastapi import Header

# Quem está a agir: o cliente (ou o funcionário) é indicado pelo header X-User-Id
CurrentUser = Annotated[UUID, Header(alias="X-User-Id")]