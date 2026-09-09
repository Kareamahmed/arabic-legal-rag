from pydantic import BaseModel
from typing import Optional


class PushRequest(BaseModel):
    do_reset: Optional[int] = 0


class SearchRequest(BaseModel):
    text: str
    top_n: int = 5
    rerank_candidates: Optional[int] = 10
    vector_limit: Optional[int] = 20,
    keyword_limit: Optional[int] = 20,
    rrf_k: Optional[int] = 60,
    vector_weight: Optional[float] = 0.7,
    keyword_weight: Optional[float] = 0.3,
