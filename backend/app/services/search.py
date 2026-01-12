import os
import numpy as np
from backend.app.services.inteference import InferenceService
import faiss
import pickle
import logging
import pandas as pd
from tqdm import tqdm

from app.config import settings

logger = logging.getLogger(__name__)

class SearchService:
    def __init__(self, inference_service: InferenceService, use_cache:bool):
        self.inference_service = inference_service
        self.songs_dir =settings.SONGS_DIR
        self.embedding_dim = settings.EMBEDDING_DIM

        # FAISS index and mappings  
        self.index = None
        self.index2id = {}  # Maps FAISS index → song filename
        self.song_count:int = 0
        self.group_to_title = {}  # Maps group_id → song title
        self._load_group_title_mapping()

        # Load or build index
        if use_cache and self._cache_exists():
            self._load_from_cache()
        else:
            self._build_index()
            if use_cache:
                self._save_to_cache()

        logger.info(f"SearchService initialized with {self.song_count} songs")

    def _load_group_title_mapping(self):
        group_title_path = settings.GROUP_TITLE_CSV_PATH
        if os.path.exists(group_title_path):
            df = pd.read_csv(group_title_path)
            self.group_to_title = dict(zip(df['group_id'], df['song_title']))
            logger.info(f"Loaded {len(self.group_to_title)} group_id to title mappings")
        else:
            logger.warning(f"Group title CSV not found at {group_title_path}")
  

    def _cache_exists(self) -> bool:
        return (
            os.path.exists(settings.FAISS_INDEX_CACHE) and
            os.path.exists(settings.FAISS_METADATA_CACHE)
        )

    def _build_index(self):
        self.index = faiss.IndexFlatL2(self.embedding_dim)
        if not os.path.exists(self.songs_dir):
            raise FileNotFoundError(f"Songs directory not found: {self.songs_dir}")

        song_files = sorted([f for f in os.listdir(self.songs_dir) if f.endswith('.npy')])

        if len(song_files) == 0:
            raise ValueError(f"No .npy files found in {self.songs_dir}")

        logger.info(f"Found {len(song_files)} song files")

        for idx, filename in enumerate(tqdm(song_files, desc="Building index")):
            try:
                file_path = os.path.join(self.songs_dir, filename)
                mel_spec = np.load(file_path)
                embedding = self.inference_service.get_embedding(mel_spec)
                embedding_matrix = np.matrix(embedding) 
                self.index.add(embedding_matrix) # type: ignore
                song_id = filename.replace('.npy', '')
                self.index2id[str(idx)] = song_id

            except Exception as e:
                logger.warning(f"Failed to process {filename}: {str(e)}")
                continue

        self.song_count = self.index.ntotal
        logger.info(f"Successfully built index with {self.song_count} songs")

    def _save_to_cache(self):
        try:
            os.makedirs(os.path.dirname(settings.FAISS_INDEX_CACHE), exist_ok=True)
            faiss.write_index(self.index, settings.FAISS_INDEX_CACHE)
            metadata = {
                'index2id': self.index2id,
                'song_count': self.song_count,
                'embedding_dim': self.embedding_dim
            }
            with open(settings.FAISS_METADATA_CACHE, 'wb') as f:
                pickle.dump(metadata, f)

            logger.info(f"Cached index to {settings.FAISS_INDEX_CACHE}")

        except Exception as e:
            logger.warning(f"Failed to save cache: {str(e)}")

    def _load_from_cache(self):
        logger.info("Loading FAISS index from cache...")
        self.index = faiss.read_index(settings.FAISS_INDEX_CACHE)
        with open(settings.FAISS_METADATA_CACHE, 'rb') as f:
            metadata = pickle.load(f)
        self.index2id = metadata['index2id']
        self.song_count = metadata['song_count']
        logger.info(f"Loaded cached index with {self.song_count} songs")


    def search(self, query_embedding: np.ndarray, k: int ) -> list[dict]:
        k = k or settings.TOP_K_SEARCH

        try:
            if query_embedding.ndim == 1:
                query_embedding = np.matrix(query_embedding)
            distances, indices = self.index.search(query_embedding, k=k) # type: ignore
            unique_results = self._deduplicate_results(indices[0], distances[0])

            return unique_results

        except Exception as e:
            logger.error(f"Search failed: {str(e)}")
            raise

    def _deduplicate_results(self, indices: np.ndarray, distances: np.ndarray) -> list[dict]:
        unique_ids = []
        unique_results = []
        top_n = settings.TOP_N_RESULTS

        for idx, distance in zip(indices, distances):
            full_id = self.index2id.get(str(idx), "")
            if not full_id:
                continue
            song_id = full_id.split('_')[0]
            if song_id not in unique_ids:
                unique_ids.append(song_id)
                song_name = self.group_to_title.get(song_id, None)

                unique_results.append({
                    'rank': len(unique_results) + 1,
                    'song_id': song_id,
                    'song_name': song_name,
                    'distance': float(distance)
                })

            if len(unique_results) >= top_n:
                break
        logger.info(f"Found {len(unique_results)} unique results")
        return unique_results

    def get_index_info(self) -> dict:
        return {
            'song_count': self.song_count,
            'embedding_dim': self.embedding_dim,
            'index_size': self.index.ntotal if self.index else 0,
            'cached': self._cache_exists()
        }
