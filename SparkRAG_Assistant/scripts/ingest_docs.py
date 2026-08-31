"""
Complete ingestion pipeline - crawl, parse, chunk, embed, index.
Simplified version without LangChain to avoid Python 3.14 compatibility issues.
"""

import sys
from pathlib import Path

# Add project root to path so imports work when script is run from any directory
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import argparse
import yaml
import json
import pickle
from tqdm import tqdm
import importlib

from src.ingestion.crawler import DocumentCrawler
from src.ingestion.parser import DocumentParser
from src.ingestion.chunker import LangChainChunker
from src.indexing.embedder import LangChainEmbedder

# Import retriever
retriever_module = importlib.import_module('src.retrieval.reranker_retriever')
HybridRerankingRetriever = retriever_module.HybridRerankingRetriever

def main():
    parser = argparse.ArgumentParser(
        description="Ingest documents from any configured source (crawl → parse → chunk → embed → index)"
    )
    parser.add_argument(
        '--source', 
        default='spark',
        help='Source name as defined in configs/config.yaml (e.g., spark, hadoop, custom_source, etc.)'
    )
    parser.add_argument('--skip-crawl', action='store_true', help='Skip crawling step, use existing raw files')
    args = parser.parse_args()
    
    # Load config
    with open('configs/config.yaml') as f:
        config = yaml.safe_load(f)
    
    # Validate source exists in config
    if args.source not in config.get('sources', {}):
        available_sources = list(config.get('sources', {}).keys())
        print(f"\n❌ Error: Source '{args.source}' not found in config!")
        print(f"Available sources: {', '.join(available_sources) if available_sources else 'None configured'}")
        sys.exit(1)
    
    source_config = config['sources'][args.source]
    
    # Paths
    raw_dir = Path(f"data/raw/{args.source}")
    index_dir = Path(config['vector_store']['data_dir'])
    
    # Step 1: Crawl
    if not args.skip_crawl:
        print("\n" + "="*80)
        print("STEP 1: CRAWLING")
        print("="*80)
        
        crawler = DocumentCrawler(
            base_url=source_config['base_url'],
            max_pages=source_config['max_pages'],
            rate_limit=source_config['rate_limit']
        )
        
        files = crawler.crawl(raw_dir)
        print(f"\n✅ Crawled {len(files)} pages")
    
    # Step 2: Parse
    print("\n" + "="*80)
    print("STEP 2: PARSING")
    print("="*80)
    
    parser_obj = DocumentParser()
    documents = []
    
    for filepath in tqdm(list(raw_dir.glob("*.html"))):
        doc = parser_obj.parse_file(filepath)
        if doc:
            documents.append(doc)
    
    print(f"\n✅ Parsed {len(documents)} documents")
    
    # Step 3: Chunk
    print("\n" + "="*80)
    print("STEP 3: CHUNKING")
    print("="*80)
    
    chunker = LangChainChunker(
        chunk_size=config['chunking']['chunk_size'],
        chunk_overlap=config['chunking']['chunk_overlap']
    )
    
    all_chunks = []
    for doc in tqdm(documents):
        chunks = chunker.chunk_document(doc)
        # Extract text from Document objects
        chunk_texts = [chunk.page_content for chunk in chunks]
        all_chunks.extend(chunk_texts)
    
    print(f"\n✅ Created {len(all_chunks)} chunks")
    
    # Step 4: Embed & Index
    print("\n" + "="*80)
    print("STEP 4: EMBEDDING & INDEXING")
    print("="*80)
    
    # Initialize embedder
    print(f"\n🔧 Loading embeddings: {config['embedding']['model']}")
    embedder = LangChainEmbedder(
        model_name=config['embedding']['model'],
        device=config['embedding']['device']
    )
    
    # Convert chunks to LangChain Document objects
    print("\n📄 Creating LangChain documents...")
    from langchain_core.documents import Document
    
    documents_with_meta = []
    for i, chunk in enumerate(all_chunks):
        doc = Document(
            page_content=chunk,
            metadata={"source": f"chunk_{i}", "index": i}
        )
        documents_with_meta.append(doc)
    
    # Step 4a: Create FAISS vectorstore
    print("\n🚀 Building FAISS index...")
    from langchain_community.vectorstores import FAISS
    vectorstore = FAISS.from_documents(
        documents_with_meta,
        embedding=embedder
    )
    print(f"✅ FAISS index created with {len(documents_with_meta)} documents")
    
    # Step 4b: Create BM25 retriever
    print("\n🚀 Building BM25 index...")
    from langchain_community.retrievers import BM25Retriever
    bm25_retriever = BM25Retriever.from_documents(documents_with_meta)
    print(f"✅ BM25 index created with {len(documents_with_meta)} documents")
    
    # Step 4c: Initialize HybridRerankingRetriever
    print("\n🚀 Initializing hybrid retriever...")
    retriever = HybridRerankingRetriever(
        vectorstore=vectorstore,
        bm25_retriever=bm25_retriever,
        reranker=None,  # Optional - for now skip reranking
        initial_k=config['retrieval']['initial_k'],
        rerank_k=config['retrieval'].get('rerank_k', 10),
        final_k=config['retrieval'].get('final_k', 5),
        dense_weight=0.7
    )
    print(f"✅ Hybrid retriever initialized")
    
    # Save
    index_dir.mkdir(parents=True, exist_ok=True)
    vectorstore.save_local(str(index_dir))
    
    # Also save documents for reference (save Document objects, not strings)
    with open(index_dir / "documents.pkl", 'wb') as f:
        pickle.dump(documents_with_meta, f)
    
    # Save retriever config
    with open(index_dir / "config.yaml", 'w') as f:
        yaml.dump(config, f)
    
    print(f"\n💾 Index saved to {index_dir}")
    
    print("\n" + "="*80)
    print("🎉 INGESTION COMPLETE!")
    print("="*80)
    print(f"\nSource: {args.source}")
    print(f"Documents: {len(documents)}")
    print(f"Chunks: {len(all_chunks)}")
    print(f"Vector store: {index_dir}")
    print(f"\nNext: uvicorn src.api.app:app --reload")

if __name__ == "__main__":
    main()