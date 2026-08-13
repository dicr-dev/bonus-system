from typing import Any

from pydantic import BaseModel, Field


class EmptyListResponse(BaseModel):
    items: list[Any] = Field(default_factory=list)
