"""
Generator using LangChain's Ollama wrapper.
"""

from langchain_community.llms import Ollama
from langchain_core.prompts import PromptTemplate
from typing import List, Dict

class LangChainGenerator:
    """
    Generator using LangChain's Ollama LLM.
    
    Advantages:
    - Cleaner interface
    - Built-in prompt templates
    - Easy to swap LLMs
    - Better error handling
    """
    
    def __init__(self, model: str = "llama3.2", base_url: str = "http://localhost:11434"):
        print(f"Initializing Ollama LLM: {model}")
        
        # LangChain Ollama wrapper
        self.llm = Ollama(
            model=model,
            base_url=base_url,
            temperature=0.1,
            num_predict=1000
        )
        
        # Define prompt template
        self.prompt_template = PromptTemplate(
            input_variables=["context", "question"],
            template="""You are a helpful assistant for Apache Spark documentation.

Answer the user's question using ONLY the information from the context below.

IMPORTANT RULES:
1. Only use information from the provided context
2. If the answer is not in the context, say "I don't have enough information"
3. Cite sources using [Source N] notation
4. Be concise and accurate
5. Include code examples from context if relevant

Context:
{context}

Question: {question}

Answer (remember to cite sources):"""
        )
        
        # Create LLM chain using modern LangChain Runnable pattern
        self.chain = self.prompt_template | self.llm
        
        print("✅ LLM initialized")
    
    def generate(self, query: str, chunks: List[Dict]) -> Dict:
        """
        Generate answer using LangChain.
        
        Args:
            query: User question
            chunks: Retrieved chunks
            
        Returns:
            Dict with answer and metadata
        """
        # Build context from chunks
        context_parts = []
        for i, chunk in enumerate(chunks, 1):
            source = chunk['metadata']['source_url']
            text = chunk['text']
            context_parts.append(f"[Source {i}] {source}\n{text}")
        
        context = "\n\n---\n\n".join(context_parts)
        
        # Generate using chain (Runnable pattern)
        result = self.chain.invoke({"context": context, "question": query})
        
        return {
            'answer': result,
            'model': self.llm.model,
            'sources': [c['metadata']['source_url'] for c in chunks]
        }