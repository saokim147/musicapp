from pydantic_settings import BaseSettings
import os

# Get project root dynamically (3 levels up from this file: backend/app/config.py -> musicapp)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class Settings(BaseSettings):

    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Paths - all relative to PROJECT_ROOT unless absolute
    PROJECT_ROOT: str = _PROJECT_ROOT
    CHECKPOINT_PATH: str = "{PROJECT_ROOT}/checkpoints/resnet18_best.pth"   
    SONGS_DIR: str = "{PROJECT_ROOT}/preprocessed/train/song" 
    GROUP_TITLE_CSV_PATH: str = "{PROJECT_ROOT}/preprocessed/group_to_title.csv"  
    UPLOAD_DIR: str = "./uploads"
    CACHE_DIR: str = "./cache"
    # Model configuration
    INPUT_SHAPE:  tuple[int, int] = (630, 80)
    EMBEDDING_DIM: int = 512
    BACKBONE: str = "resnet18"  # Match checkpoint file

    # Audio processing parameters
    SAMPLING_RATE: int = 16000
    MAX_WAV_VALUE: float = 32767.0
    FILTER_LENGTH: int = 1024
    HOP_LENGTH: int = 256
    WIN_LENGTH: int = 1024
    N_MEL_CHANNELS: int = 80
    MEL_FMIN: int = 0
    MEL_FMAX: int = 8000

    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB
    CORS_ORIGINS: list = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8081",     
        "http://127.0.0.1:8081",
        "http://localhost:19000",     
        "http://localhost:19006",     
    ]

    # Search configuration
    FAISS_INDEX_CACHE: str = "./cache/faiss_index.bin"
    FAISS_METADATA_CACHE: str = "./cache/faiss_metadata.pkl"
    TOP_K_SEARCH: int = 30
    TOP_N_RESULTS: int = 10

    class Config:
        env_file = ".env"
        extra = "allow"


# Global settings instance
settings = Settings()
