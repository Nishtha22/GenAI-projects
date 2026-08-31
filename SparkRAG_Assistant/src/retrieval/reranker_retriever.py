"""
LangChain retriever with cross-encoder reranking.
"""

from typing import List, Optional
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_core.callbacks.manager import CallbackManagerForRetrieverRun
from langchain_community.vectorstores import FAISS
from langchain_community.retrievers import BM25Retriever
from sentence_transformers import CrossEncoder
import numpy as np

class HybridRerankingRetriever(BaseRetriever):
    """
    Custom LangChain retriever with:
    1. Hybrid search (FAISS + BM25)
    2. Cross-encoder reranking
    
    This is a LangChain BaseRetriever, so it works with all LangChain chains!
    """
    
    vectorstore: FAISS
    bm25_retriever: BM25Retriever
    reranker: Optional[CrossEncoder] = None
    initial_k: int = 50
    rerank_k: int = 10
    final_k: int = 5
    dense_weight: float = 0.7
    
    class Config:
        arbitrary_types_allowed = True
    
    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun = None
    ) -> List[Document]:
        """
        Retrieve and rerank documents.
        
        Pipeline:
        1. Get candidates from FAISS (semantic)
        2. Get candidates from BM25 (keyword)
        3. Merge and deduplicate
        4. Rerank with cross-encoder
        5. Return top-k
        """
        # Stage 1: Dense retrieval (FAISS)
        dense_docs = self.vectorstore.similarity_search_with_score(
            query,
            k=self.initial_k
        )
        
        # Stage 2: Sparse retrieval (BM25)
        try:
            # Try invoke() first (newer LangChain)
            sparse_docs = self.bm25_retriever.invoke(query)
        except (AttributeError, TypeError):
            try:
                
                sparse_docs = self.bm25_retriever.get_relevant_documents(query)
            except AttributeError:
                
                sparse_docs = self.bm25_retriever._get_relevant_documents(query)
        
        # Merge results (deduplicate by content)
        seen_content = set()
        merged_docs = []
        
        # Add dense results with scores
        for doc, score in dense_docs:
            content_key = doc.page_content[:100]
            if content_key not in seen_content:
                seen_content.add(content_key)
                # Store original dense score in metadata
                doc.metadata['dense_score'] = float(score)
                merged_docs.append(doc)
        
        # Add sparse results (if not already in merged)
        for doc in sparse_docs[:self.initial_k]:
            content_key = doc.page_content[:100]
            if content_key not in seen_content:
                seen_content.add(content_key)
                doc.metadata['sparse_score'] = 1.0
                merged_docs.append(doc)
        
        # Take top initial_k candidates
        candidates = merged_docs[:self.initial_k]
        
        # Stage 3: Reranking (if reranker is provided)
        if len(candidates) == 0:
            return []
        
        if self.reranker is not None:
            # Prepare pairs for cross-encoder
            pairs = [[query, doc.page_content] for doc in candidates]
            
            # Get reranker scores
            rerank_scores = self.reranker.predict(pairs)
            
            # Combine documents with rerank scores
            scored_docs = list(zip(rerank_scores, candidates))
            
            # Sort by rerank score
            scored_docs.sort(key=lambda x: x[0], reverse=True)
            
            # Add rerank scores to metadata
            for score, doc in scored_docs:
                doc.metadata['rerank_score'] = float(score)
            
            # Return top-k reranked documents
            reranked_docs = [doc for _, doc in scored_docs[:self.final_k]]
        else:
            # No reranking - just return top candidates
            reranked_docs = candidates[:self.final_k]
        
        return reranked_docs


def create_reranking_retriever(
    vectorstore: FAISS,
    documents: List[Document],
    config: dict
) -> HybridRerankingRetriever:
    """
    Factory function to create a reranking retriever.
    
    Args:
        vectorstore: FAISS vector store
        documents: All documents for BM25
        config: Configuration dict
        
    Returns:
        HybridRerankingRetriever
    """
    print("\n🔧 Creating hybrid retriever with reranking...")
    
    # Create BM25 retriever
    print("  Building BM25 index...")
    bm25_retriever = BM25Retriever.from_documents(documents)
    bm25_retriever.k = config['retrieval']['initial_k']
    
    # Load cross-encoder
    print(f"  Loading reranker: {config['retrieval']['reranker_model']}...")
    reranker = CrossEncoder(
        config['retrieval']['reranker_model'],
        device=config['embedding']['device']
    )
    
    # Create retriever
    retriever = HybridRerankingRetriever(
        vectorstore=vectorstore,
        bm25_retriever=bm25_retriever,
        reranker=reranker,
        initial_k=config['retrieval']['initial_k'],
        rerank_k=config['retrieval']['rerank_k'],
        final_k=config['retrieval']['final_k']
    )
    
    print("✅ Hybrid reranking retriever ready!")
    
    return retriever