import os
import json
import numpy as np
from typing import List, Dict, Any
from sentence_transformers import SentenceTransformer, util
import faiss
import hashlib
import logging
from backend.config import Config

logger = logging.getLogger(__name__)

def _str_to_id(s: str) -> int:
    """Deterministic 63-bit int from string (for FAISS IDMap)"""
    m = hashlib.md5(s.encode('utf-8')).hexdigest()
    return int(m[:15], 16)  # fits in 64-bit comfortably

class EmbeddingService:
    def __init__(self):
        model_name = Config.EMBEDDING_MODEL or "all-MiniLM-L6-v2"
        logger.info(f"Loading embedding model: {model_name}")
        self.model = SentenceTransformer(model_name)
        self.dim = self.model.get_sentence_embedding_dimension()

        os.makedirs(Config.FAISS_PERSIST_DIR, exist_ok=True)
        # Two indexes: resumes and jobs
        self.resume_index_path = os.path.join(Config.FAISS_PERSIST_DIR, "resume_index.faiss")
        self.job_index_path = os.path.join(Config.FAISS_PERSIST_DIR, "job_index.faiss")
        self.resume_meta_path = os.path.join(Config.FAISS_PERSIST_DIR, "resume_meta.json")
        self.job_meta_path = os.path.join(Config.FAISS_PERSIST_DIR, "job_meta.json")

        # Load or create index and metadata
        self.resume_index = self._load_or_create_index(self.resume_index_path)
        self.job_index = self._load_or_create_index(self.job_index_path)
        self.resume_meta = self._load_meta(self.resume_meta_path)
        self.job_meta = self._load_meta(self.job_meta_path)

    def _load_or_create_index(self, path: str):
        if os.path.exists(path):
            try:
                idx = faiss.read_index(path)
                logger.info(f"Loaded FAISS index from {path}")
                return idx
            except Exception as e:
                logger.warning(f"Failed to read index at {path}: {e}. Creating new one.")
        # create inner-product index and wrap it into IDMap for stable ids
        index = faiss.IndexFlatIP(self.dim)
        id_index = faiss.IndexIDMap(index)
        return id_index

    def _load_meta(self, path: str) -> Dict[str, Any]:
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_meta(self, path: str, meta: Dict[str, Any]):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

    def _save_index(self, index, path: str):
        try:
            faiss.write_index(index, path)
        except Exception as e:
            logger.error(f"Failed to write FAISS index to {path}: {e}")

    def generate_embeddings(self, text: str) -> List[float]:
        if not text:
            return [0.0] * self.dim
        emb = self.model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
        return emb.tolist()

    def calculate_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        v1 = np.array(embedding1)
        v2 = np.array(embedding2)
        if np.linalg.norm(v1) == 0 or np.linalg.norm(v2) == 0:
            return 0.0
        cosine = float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))
        return cosine * 100.0

    def store_resume_embedding(self, resume_id: str, text: str, metadata: Dict = None):
        embedding = np.array(self.generate_embeddings(text), dtype='float32')
        id_int = _str_to_id(resume_id)
        try:
            self.resume_index.add_with_ids(np.array([embedding]), np.array([id_int], dtype='int64'))
        except Exception as e:
            logger.warning(f"Could not add id {id_int} directly: {e}. Recreating index and re-adding.")
            # fallback: recreate index, re-add existing vectors
            self._rebuild_index_from_meta(self.resume_index, self.resume_meta)
            self.resume_index.add_with_ids(np.array([embedding]), np.array([id_int], dtype='int64'))

        self.resume_meta[str(id_int)] = {'resume_id': resume_id, 'metadata': metadata or {}}
        self._save_meta(self.resume_meta_path, self.resume_meta)
        self._save_index(self.resume_index, self.resume_index_path)
        return embedding.tolist()

    def store_job_embedding(self, job_id: str, text: str, metadata: Dict = None):
        embedding = np.array(self.generate_embeddings(text), dtype='float32')
        id_int = _str_to_id(job_id)
        try:
            self.job_index.add_with_ids(np.array([embedding]), np.array([id_int], dtype='int64'))
        except Exception as e:
            logger.warning(f"Could not add job id {id_int}: {e}. Rebuilding index.")
            self._rebuild_index_from_meta(self.job_index, self.job_meta)
            self.job_index.add_with_ids(np.array([embedding]), np.array([id_int], dtype='int64'))

        self.job_meta[str(id_int)] = {'job_id': job_id, 'metadata': metadata or {}}
        self._save_meta(self.job_meta_path, self.job_meta)
        self._save_index(self.job_index, self.job_index_path)
        return embedding.tolist()

    def _rebuild_index_from_meta(self, index, meta):
        # best-effort: no-op currently; could be extended to re-encode stored documents
        pass

    def find_similar_resumes(self, job_embedding: List[float], top_k: int = 10) -> List[Dict]:
        if len(self.resume_meta) == 0:
            return []
        q = np.array(self.generate_embeddings(job_embedding if isinstance(job_embedding, str) else " ".join(map(str, job_embedding))), dtype='float32') \
            if isinstance(job_embedding, str) else np.array(job_embedding, dtype='float32')
        if q.ndim == 1:
            q = q.reshape(1, -1)
        try:
            distances, ids = self.resume_index.search(q, top_k)
        except Exception as e:
            logger.error(f"FAISS search failed: {e}")
            return []
        results = []
        for distance, id_val in zip(distances[0], ids[0]):
            if id_val == -1:
                continue
            meta = self.resume_meta.get(str(int(id_val)), {})
            results.append({
                'resume_id': meta.get('resume_id'),
                'similarity_score': float(distance) * 100.0,
                'metadata': meta.get('metadata', {})
            })
        return results
