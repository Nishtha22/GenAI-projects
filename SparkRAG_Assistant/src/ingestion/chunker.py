"""
Text chunking using LangChain.
"""

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from typing import List

class LangChainChunker:
    """Chunk documents using LangChain's text splitter."""
    
    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 64):
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
    
    def chunk_document(self, document: dict) -> List[Document]:
        """
        Chunk a single document.
        
        Returns LangChain Documents (not dicts).
        """
        # Create LangChain Document
        doc = Document(
            page_content=document['text'],
            metadata={
                'source_url': document['source_url'],
                'source_file': document['source_file']
            }
        )
        
        # Split
        chunks = self.text_splitter.split_documents([doc])
        
        # Add chunk index to metadata
        for i, chunk in enumerate(chunks):
            chunk.metadata['chunk_index'] = i
            chunk.metadata['total_chunks'] = len(chunks)
        
        return chunks