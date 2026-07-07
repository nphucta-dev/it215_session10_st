from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime


class MembershipCreateRequest(BaseModel):
    card_number: str = Field(..., min_length=1, max_length=50)
    customer_id: int


class StandardResponse(BaseModel):
    status: str
    status_code: int
    message: str
    data: Optional[Any] = None
    error: Optional[str] = None
    timestamp: str