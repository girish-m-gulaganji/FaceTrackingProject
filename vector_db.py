import os
import json
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

VECTOR_INDEX_FILE = "dataset/embeddings/osint_vector_index.npz"
METADATA_INDEX_FILE = "dataset/embeddings/osint_metadata.json"

class VectorDBManager:
    """High-performance vector index and OSINT metadata store for reverse facial lookup."""

    def __init__(self, index_path=VECTOR_INDEX_FILE, meta_path=METADATA_INDEX_FILE):
        self.index_path = index_path
        self.meta_path = meta_path
        self.embeddings = np.empty((0, 512), dtype=np.float32)
        self.metadata = []
        self.load()

    def load(self):
        os.makedirs(os.path.dirname(self.index_path), exist_ok=True)
        if os.path.exists(self.index_path) and os.path.exists(self.meta_path):
            try:
                data = np.load(self.index_path)
                self.embeddings = data["embeddings"]
                with open(self.meta_path, "r", encoding="utf-8") as f:
                    self.metadata = json.load(f)
            except Exception as e:
                print(f"[WARN] Vector index load notice: {e}")

    def save(self):
        os.makedirs(os.path.dirname(self.index_path), exist_ok=True)
        np.savez(self.index_path, embeddings=self.embeddings)
        with open(self.meta_path, "w", encoding="utf-8") as f:
            json.dump(self.metadata, f, indent=4)

    def add_profile(self, name: str, username: str, platform: str, profile_url: str, bio: str, location: str, embedding: np.ndarray, avatar_url: str = None):
        """Add face embedding and social metadata to the vector index."""
        emb = embedding.reshape(1, -1).astype(np.float32)

        if len(self.embeddings) > 0:
            self.embeddings = np.vstack([self.embeddings, emb])
        else:
            self.embeddings = emb

        profile_entry = {
            "id": len(self.metadata) + 1,
            "name": name,
            "username": username,
            "platform": platform,
            "profile_url": profile_url,
            "bio": bio or "No bio provided.",
            "location": location or "Unknown",
            "avatar_url": avatar_url or "",
            "enrolled_at": str(np.datetime64('now'))
        }
        self.metadata.append(profile_entry)
        self.save()
        return profile_entry

    def search_profile(self, target_embedding: np.ndarray, top_k: int = 5, threshold: float = 0.45):
        """Search target embedding against vector database using cosine similarity."""
        if len(self.embeddings) == 0:
            return []

        target_emb = target_embedding.reshape(1, -1).astype(np.float32)
        sims = cosine_similarity(target_emb, self.embeddings)[0]

        top_indices = np.argsort(sims)[::-1][:top_k]

        results = []
        for idx in top_indices:
            score = float(sims[idx])
            if score >= threshold:
                meta = self.metadata[idx].copy()
                meta["similarity_score"] = round(score * 100, 2)
                meta["raw_score"] = score
                results.append(meta)

        return results

if __name__ == "__main__":
    db = VectorDBManager()
    print(f"[INFO] VectorDB Initialized. Stored vectors: {len(db.embeddings)}")
