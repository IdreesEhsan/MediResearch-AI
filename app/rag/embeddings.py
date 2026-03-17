# ============================================================
# app/rag/embeddings.py
# ============================================================
# Converts text into 384-dimensional vectors using HuggingFace
# all-MiniLM-L6-v2 model. These vectors are stored in Pinecone
# and used for semantic similarity search.
#
# No API key needed — model runs locally on your machine.
# First run downloads the model (~90MB) and caches it.
# ============================================================

from sentence_transformers import SentenceTransformer
from typing import List
from app.utils.config import config

class EmbeddingModel:
    """
    Wrapper around HuggingFace SentenceTransformer.
    Loads the model once and reuses it for all embedding calls.
    """
    def __init__(self):
        # Load model once at startup — cached locally after first download
        print(f"⏳ Loading embedding model: {config.EMBEDDING_MODEL}")
        self.model = SentenceTransformer(config.EMBEDDING_MODEL)
        print("✅ Embedding model loaded successfully")
        
    def embed_text(self, text: str) -> List[float]:
        """
        Convert a single string into a 384-dim vector.

        Args:
            text: Input string to embed.

        Returns:
            List of 384 floats representing the text meaning.
        """
        # encode() returns numpy array — convert to Python list
        # because Pinecone's upsert expects a plain list
        vector = self.model.encode(text, show_progress_bar=False)
        return vector.tolist()
    
    def embed_batch(self, texts: List[str], batch_size: int = 64) -> List[List[float]]:
        """
        Convert a list of strings into vectors in one go.
        Much faster than calling embed_text() in a loop.

        Args:
            texts:      List of strings to embed.
            batch_size: How many texts to process at once.

        Returns:
            List of embedding vectors, one per input string.
        """
        vectors = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=True,     # Shows progress bar for large batches
            convert_to_numpy=True
        )
        # Convert numpy array to list of lists for Pinecone compatibility
        return [v.tolist() for v in vectors]

# ── Shared instance ───────────────────────────────────────────
# Model loads only once when this module is first imported.
# Import anywhere with:  from app.rag.embeddings import embedder
embedder = EmbeddingModel()