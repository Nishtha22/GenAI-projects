"""
Embedder using sentence-transformers directly to avoid LangChain Pydantic issues.
"""

from sentence_transformers import SentenceTransformer
from typing import List
import numpy as np
from langchain_core.embeddings import Embeddings

class LangChainEmbedder(Embeddings):
    """
    Embedder using sentence-transformers directly.
    
    This avoids LangChain's Pydantic V1 compatibility issues with Python 3.14
    Implements LangChain's Embeddings interface for compatibility.
    """
    
    def __init__(self, model_name: str = "BAAI/bge-base-en-v1.5", device: str = "cpu"):
        super().__init__()
        print(f"Loading embedding model: {model_name}")
        
        # Use sentence-transformers directly
        self.model = SentenceTransformer(model_name, device=device)
        
        # Get dimension
        test_embedding = self.model.encode("test")
        self.dimension = len(test_embedding)
        
        print(f"Model loaded. Dimension: {self.dimension}")
    
    def embed_query(self, text: str) -> List[float]:
        """Embed a single query (LangChain interface)."""
        embedding = self.model.encode(text, normalize_embeddings=True)
        return embedding.tolist()
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed documents (LangChain interface)."""
        embeddings = self.model.encode(texts, normalize_embeddings=True, show_progress_bar=True)
        return [emb.tolist() for emb in embeddings]
    
    def embed_text(self, text: str) -> List[float]:
        """Embed single text (custom interface)."""
        embedding = self.model.encode(text, normalize_embeddings=True)
        return embedding.tolist()
    
    def embed_batch(self, texts: List[str]) -> np.ndarray:
        """Embed multiple texts (custom interface)."""
        print(f"Generating embeddings for {len(texts)} texts...")
        embeddings = self.model.encode(texts, normalize_embeddings=True, show_progress_bar=True)
        print(f"✅ Generated {len(embeddings)} embeddings")
        return embeddings
