from pydantic import BaseModel
from typing import Optional


class ProcessRequest(BaseModel):
    do_reset: Optional[int] = 0
