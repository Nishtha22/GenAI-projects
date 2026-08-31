"""
LangChain-based conversational chatbot.
"""

from typing import Dict, List, Optional
from datetime import datetime

from langchain_community.llms import Ollama
from langchain_core.prompts import PromptTemplate
from langchain_core.documents import Document
from langchain_community.llms import Ollama
from langchain_core.prompts import PromptTemplate


class LangChainChatbot:
    """
    Conversational chatbot using LangChain.
    
    Features:
    - Multi-turn conversations
    - Context awareness
    - Automatic memory management
    - Source tracking
    """
    
    def __init__(self, retriever, llm, memory_type="buffer", max_history=5, base_url=None):
        self.retriever = retriever
        
        # If llm is a string (model name), create Ollama instance
        if isinstance(llm, str):
            self.llm = Ollama(model=llm, base_url=base_url or "http://localhost:11434")
        else:
            self.llm = llm
            
        self.max_history = max_history
        self.memory = self._create_memory(memory_type, max_history)
        self.prompt = self._create_prompt()
        self.chain = None  # Placeholder
        self._history = []
        self.created_at = datetime.now()
        self.last_active = datetime.now()
    
    def _create_memory(self, memory_type: str, max_history: int):
        """Create appropriate memory type."""
        base_kwargs = {
            "memory_key": "chat_history",
            "return_messages": True,
            "output_key": "answer"
        }
        
        # Memory classes are not available in this LangChain version
        # You can implement your own memory or return None
        return None
    
    def _create_prompt(self) -> PromptTemplate:
        """Create custom prompt template."""
        template = """You are a helpful assistant for Apache Spark documentation.

You're having a conversation with a user. Use the conversation history to understand context and references.

Previous conversation:
{chat_history}

Use the following retrieved context to answer the current question. 

IMPORTANT RULES:
1. Use information from both the context AND conversation history
2. If the user refers to something from earlier ("it", "that", "the method you mentioned"), use chat history
3. Be conversational and natural
4. Cite sources using [Source N] notation
5. If you don't know, say so clearly
6. Stay focused on Apache Spark topics

Retrieved Context:
{context}

Current Question: {question}

Answer (be conversational and cite sources):"""
        
        return PromptTemplate(
            input_variables=["context", "chat_history", "question"],
            template=template
        )
    
    def chat(self, message: str) -> Dict:
        """
        Send a message and get response.
        
        Args:
            message: User message
            
        Returns:
            Dict with answer, sources, metadata
        """
        self.last_active = datetime.now()
        
        try:
            # Add the new message to history
            self._history.append({"role": "user", "content": message})

            # Only keep the last N exchanges (user+bot)
            self._history = self._history[-2*self.max_history:]

            # Build chat history string
            chat_history = ""
            for turn in self._history:
                prefix = "User:" if turn["role"] == "user" else "Bot:"
                chat_history += f"{prefix} {turn['content']}\n"

            # Retrieve context docs
            docs = self.retriever.invoke(message)
            context = "\n\n".join([doc.page_content for doc in docs])

            # Build prompt
            prompt = self.prompt.format(context=context, chat_history=chat_history, question=message)

            # Generate answer using Ollama LLM
            answer = self.llm.invoke(prompt)

            # Add bot response to history
            self._history.append({"role": "bot", "content": answer})

            sources = self._format_sources(docs)
            return {
                "answer": answer.strip(),
                "sources": sources,
                "num_sources": len(sources),
                "conversation_length": len(self._history) // 2,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "error": str(e),
                "answer": "I apologize, but I encountered an error processing your message. Please try again.",
                "sources": [],
                "num_sources": 0
            }
    
    def _format_sources(self, documents: List[Document]) -> List[Dict]:
        """Format source documents."""
        sources = []
        
        for doc in documents:
            sources.append({
                "url": doc.metadata.get("source_url", "Unknown"),
                "text_preview": doc.page_content[:200] + "...",
                "rerank_score": doc.metadata.get("rerank_score", 0.0),
                "chunk_index": doc.metadata.get("chunk_index", 0)
            })
        
        return sources
    
    def get_history(self) -> List[Dict]:
        """
        Get conversation history.
        
        Returns:
            List of message dicts with role and content
        """
        return self._history
    
    def clear_history(self):
        """Clear conversation history."""
        self._history = []
        self.last_active = datetime.now()
    
    def get_stats(self) -> Dict:
        """Get chatbot statistics."""
        return {
            "created_at": self.created_at.isoformat(),
            "last_active": self.last_active.isoformat(),
            "conversation_length": len(self._history) // 2,
            "memory_type": "custom_buffer"
        }