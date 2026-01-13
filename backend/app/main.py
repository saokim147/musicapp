from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import os

import torch

from app.config import settings
from app.api import routes
from app.services.inteference import InferenceService
from app.services.preprocessing import PreprocessingService
from app.services.search import SearchService


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events
    """

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.CACHE_DIR, exist_ok=True)
    routes.preprocessing_service = PreprocessingService()

    # Initialize inference service (load model)
    routes.inference_service = InferenceService(
        device="cuda" if  torch.cuda.is_available() else "cpu",
    )
    logger.info("Building/loading FAISS index...")
    routes.search_service = SearchService(
        inference_service=routes.inference_service,
        use_cache=True
    )
    index_info = routes.search_service.get_index_info()
    logger.info(f"FAISS index ready with {index_info['song_count']} songs")
    logger.info("=" * 60)
    logger.info("Backend service started successfully!")
    logger.info(f"Model: {settings.BACKBONE}")
    logger.info(f"Device: {routes.inference_service.device}")
    logger.info(f"Index size: {index_info['song_count']} songs")
    logger.info(f"Using cache: {index_info['cached']}")
    logger.info("=" * 60)
    
    yield
    

# Create FastAPI app
app = FastAPI(
    title="Hum2Song API",
    description="API for hum-to-song matching using deep learning",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(routes.router)


# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "Hum2Song API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/health"
    }


if __name__ == "__main__":
    import uvicorn

    # Run with uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
        log_level="info"
    )
