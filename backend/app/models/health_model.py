from pydantic import BaseModel
class HealthResponse(BaseModel):
    """Health check response model"""
    status: str
    model_loaded: bool
    index_size: int
    backend_version: str = "1.0.0"
