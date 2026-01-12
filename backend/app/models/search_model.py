from typing import Optional
from pydantic import BaseModel, Field
class SearchResult(BaseModel):
    rank: int = Field(..., description="Rank of the result (1-10)")
    song_id: str = Field(..., description="Unique song identifier")
    song_name: Optional[str] = Field(None, description="Human-readable song name (if available)")


class SearchResponse(BaseModel):
    success: bool
    results: list[SearchResult]
    processing_time_ms: int = Field(..., description="Total processing time in milliseconds")
    message: Optional[str] = Field(None, description="Optional message or warnings")

