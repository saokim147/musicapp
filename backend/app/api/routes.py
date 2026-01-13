
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from typing import Optional
import time
import logging
from app.config import settings
from app.models.health_model import HealthResponse
from app.models.search_model import SearchResponse, SearchResult
from app.services.inteference import InferenceService
from app.services.preprocessing import PreprocessingError, PreprocessingService
from app.services.search import SearchService
from app.utils.file_manager import cleanup_file, save_upload_file
from audios.utils import validate_audio_file

logger = logging.getLogger(__name__)

router = APIRouter()

preprocessing_service: Optional[PreprocessingService] = None
inference_service: Optional[InferenceService] = None
search_service: Optional[SearchService] = None


def get_preprocessing_service() -> PreprocessingService:
    if preprocessing_service is None:
        raise HTTPException(status_code=503, detail="Preprocessing service not initialized")
    return preprocessing_service

def get_inference_service() -> InferenceService:
    if inference_service is None:
        raise HTTPException(status_code=503, detail="Inference service not initialized")
    return inference_service

def get_search_service() -> SearchService:
    if search_service is None:
        raise HTTPException(status_code=503, detail="Search service not initialized")
    return search_service

@router.get("/api/health", response_model=HealthResponse)
async def health_check():
    services_healthy = all([
        preprocessing_service is not None,
        inference_service is not None,
        search_service is not None
    ])
    index_size = 0
    if search_service is not None:
        index_size = search_service.song_count

    return HealthResponse(
        status="healthy" if services_healthy else "unhealthy",
        model_loaded=inference_service is not None,
        index_size=index_size
    )

@router.post("/api/search", response_model=SearchResponse)
async def search_song(
    file: UploadFile = File(...),
    preprocess_svc: PreprocessingService = Depends(get_preprocessing_service),
    inference_svc: InferenceService = Depends(get_inference_service),
    search_svc: SearchService = Depends(get_search_service)
):
    start_time = time.time()
    temp_file_path = None

    try:    
        validate_audio_file(file, max_size=settings.MAX_UPLOAD_SIZE)
        temp_file_path = save_upload_file(file, settings.UPLOAD_DIR)
        logger.info(f"Saved upload to {temp_file_path}")

        try:
            mel_spec, preprocess_meta = preprocess_svc.preprocess_for_inference(temp_file_path)
            logger.info(f"Mel-spectrogram shape: {preprocess_meta['original_shape']}")
        except PreprocessingError as e:
            raise HTTPException(status_code=422, detail=f"Preprocessing failed: {str(e)}")

        # 4. Model inference → embedding
        logger.info("Extracting embedding...")
        embedding, inference_meta = inference_svc.process_audio_to_embedding(mel_spec)
        logger.info(f"Embedding shape: {embedding.shape}")


        # 5. FAISS search
        search_results = search_svc.search(embedding, k=settings.TOP_K_SEARCH)

        # 6. Format results
        results = [
            SearchResult(
                rank=result['rank'],
                song_id=result['song_id'],
                song_name=result.get('song_name')
            )
            for result in search_results
        ]

        processing_time_ms = int((time.time() - start_time) * 1000)

        logger.info(f"Search completed in {processing_time_ms}ms with {len(results)} results")

        return SearchResponse(
            success=True,
            results=results,
            processing_time_ms=processing_time_ms,
            message="Search completed successfully"
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Search request failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

    finally:
        if temp_file_path:
            cleanup_file(temp_file_path)
