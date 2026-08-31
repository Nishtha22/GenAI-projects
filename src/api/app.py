"""
FastAPI server with LangChain and reranking.
"""

import sys
from pathlib import Path
import re

# Add parent directory to path to import src module
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Change to project root for relative paths
import os
project_root = Path(__file__).parent.parent.parent
os.chdir(project_root)

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List
import yaml
import pickle
import time

from langchain_community.vectorstores import FAISS
from langchain_community.llms import Ollama
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

from src.indexing.embedder import LangChainEmbedder
from src.retrieval.reranker_retriever import create_reranking_retriever

# NEW: Import chatbot
from src.chatbot.session_manager import SessionManager

app = FastAPI(
    title="LangChain RAG API with Chat",
    description="Production RAG with Conversational Interface",
    version="2.0.0"
)

# Mount web UI
web_ui_path = Path(__file__).parent / "app" if (Path(__file__).parent / "app").exists() else Path(__file__).parent.parent / "chatbot" / "web"
# Mount the web UI at /ui so API routes (e.g., /health) remain reachable at root
if web_ui_path.exists() and (web_ui_path / "index.html").exists():
    app.mount("/ui", StaticFiles(directory=str(web_ui_path), html=True), name="web")

# Load config
with open("configs/config.yaml") as f:
    config = yaml.safe_load(f)

# Initialize components
print("\n" + "=" * 80)
print("🦜 INITIALIZING LANGCHAIN RAG WITH CHAT")
print("=" * 80)

# Embeddings
print("\n🔧 Loading embeddings...")
embeddings = LangChainEmbedder(
    model_name=config['embedding']['model'],
    device=config['embedding']['device']
)

# Vector store
print("\n📂 Loading FAISS index...")
index_dir = Path("data/faiss")
if not index_dir.exists():
    raise FileNotFoundError(f"Index not found at {index_dir}. Run ingestion first!")

vectorstore = FAISS.load_local(
    str(index_dir),
    embeddings,
    allow_dangerous_deserialization=True
)

# Load documents for BM25
with open(index_dir / "documents.pkl", 'rb') as f:
    documents = pickle.load(f)

print(f"✅ Loaded {vectorstore.index.ntotal} vectors")

# Create reranking retriever
retriever = create_reranking_retriever(vectorstore, documents, config)

# LLM
print("\n🤖 Initializing LLM...")
llm = Ollama(
    model=config['generation']['model'],
    base_url=config['generation']['base_url'],
    temperature=config['generation']['temperature']
)

# Prompt template (for non-chat queries)
prompt_template = """You are a helpful assistant for Apache Spark documentation.

Use the following context to answer the question. If you don't know the answer, say so. 
Be clear and concise. Do not include citations or source references - the system will handle that separately.

Context:
{context}

Question: {question}

Answer:"""

PROMPT = PromptTemplate(
    template=prompt_template,
    input_variables=["context", "question"]
)

# Create RAG chain using modern LangChain pattern
print("\n⛓️  Building RAG chain...")

def format_docs(docs):
    """Format retrieved documents for the LLM."""
    return "\n\n".join([doc.page_content for doc in docs])

# Build the chain: retriever → format docs → LLM → parse output
qa_chain = (
    {
        "context": retriever | format_docs,
        "question": RunnablePassthrough()
    }
    | PROMPT
    | llm
    | StrOutputParser()
)

# NEW: Initialize Session Manager for Chat
print("\n💬 Initializing Chat Session Manager...")
session_manager = SessionManager(
    retriever=retriever,
    llm_model=config['generation']['model'],
    base_url=config['generation']['base_url'],
    memory_type=config['chatbot']['memory_type'],
    max_history=config['chatbot']['max_history_length'],
    session_timeout_minutes=config['chatbot']['session_timeout_minutes'],
    max_sessions=config['chatbot']['max_sessions']
)

print("\n" + "=" * 80)
print("✅ LANGCHAIN RAG WITH CHAT READY")
print("=" * 80)
print(f"\nConfiguration:")
print(f"  - Reranking: {config['retrieval']['use_reranker']}")
print(f"  - Reranker: {config['retrieval']['reranker_model']}")
print(f"  - LLM: {config['generation']['model']}")
print(f"  - Chat enabled: {config['chatbot']['enabled']}")
print(f"  - Memory type: {config['chatbot']['memory_type']}")
print("=" * 80 + "\n")

# ============================================================================
# API MODELS
# ============================================================================

# Explicit model for sources
class Source(BaseModel):
    url: str
    text_preview: str
    rerank_score: float = 0.0

# Existing models
class QueryRequest(BaseModel):
    question: str
    return_sources: bool = True

class QueryResponse(BaseModel):
    answer: str
    sources: list = []
    num_chunks: int
    total_time_ms: float

# NEW: Chat models
class ChatRequest(BaseModel):
    message: str
    session_id: str  # Unique identifier (user_id, slack_user_id, web_session_id, etc.)

class ChatResponse(BaseModel):
    answer: str
    sources: List[Source]
    num_sources: int
    conversation_length: int
    session_id: str
    timestamp: str

class ChatHistoryResponse(BaseModel):
    session_id: str
    history: List[Source]
    conversation_length: int

# ============================================================================
# EXISTING ENDPOINTS
# ============================================================================

@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest):
    """
    Single-turn query (no conversation memory).
    
    Use this for one-off questions without context.
    """
    start_time = time.time()
    
    try:
        if not request.question.strip():
            raise HTTPException(400, "Question cannot be empty")
        
        # Get source documents before invoking the chain
        source_docs = retriever.invoke(request.question)
        
        # Invoke the chain with just the question
        answer = qa_chain.invoke(request.question)
        
        # Clean up the answer
        answer = answer.strip()
        answer = answer.replace('\\n\\n', '\n\n')
        answer = answer.replace('\\n', '\n')
        
        total_time = (time.time() - start_time) * 1000
        
        # Extract sources
        sources = []
        if request.return_sources and source_docs:
            for i, doc in enumerate(source_docs, 1):
                source_url = doc.metadata.get('source_url') or doc.metadata.get('source') or 'Unknown'
                sources.append({
                    'url': source_url,
                    'text_preview': doc.page_content[:150] + "...",
                    'rerank_score': doc.metadata.get('rerank_score', 0.0)
                })
        
        return QueryResponse(
            answer=answer,
            sources=sources,
            num_chunks=len(source_docs),
            total_time_ms=round(total_time, 2)
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# NEW: CHAT ENDPOINTS
# ============================================================================

@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """
    Conversational endpoint with memory.
    
    Maintains conversation history per session.
    Perfect for multi-turn conversations where context matters.
    
    Example:
    - User: "How to cache DataFrame?"
    - Bot: "Use .cache() method..."
    - User: "What about persist?" ← Remembers we're talking about caching!
    """
    try:
        if not request.message.strip():
            raise HTTPException(400, "Message cannot be empty")
        
        if not request.session_id:
            raise HTTPException(400, "Session ID required")
        
        # Get or create session
        chatbot = session_manager.get_or_create_session(request.session_id)
        
        # Chat (memory handled automatically!) -- handle LLM connectivity errors clearly
        try:
            response = chatbot.chat(request.message)
        except Exception as e:
            err_str = str(e)
            if 'Connection refused' in err_str or 'Failed to establish a new connection' in err_str or 'Max retries exceeded' in err_str:
                raise HTTPException(status_code=503, detail=f"LLM unreachable at {config['generation']['base_url']}: {err_str}")
            raise

        # Check for errors
        if "error" in response:
            raise HTTPException(500, response["error"])
        
        # Convert sources to Source models if needed
        sources = [Source(**src) if not isinstance(src, Source) else src for src in response['sources']]
        return ChatResponse(
            answer=response['answer'],
            sources=sources,
            num_sources=response['num_sources'],
            conversation_length=response['conversation_length'],
            session_id=request.session_id,
            timestamp=response['timestamp']
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/chat/history/{session_id}", response_model=ChatHistoryResponse)
def get_chat_history(session_id: str):
    """
    Get conversation history for a session.
    
    Returns all messages in the conversation.
    """
    try:
        chatbot = session_manager.get_or_create_session(session_id)
        history = chatbot.get_history()
        
        # Convert history to Source models if needed
        history_models = [Source(**msg) if not isinstance(msg, Source) else msg for msg in history]
        return ChatHistoryResponse(
            session_id=session_id,
            history=history_models,
            conversation_length=len(history_models)
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat/clear/{session_id}")
def clear_chat_history(session_id: str):
    """
    Clear conversation history for a session.
    
    Keeps the session alive but removes all messages.
    """
    success = session_manager.clear_session(session_id)
    
    if success:
        return {
            "message": "Chat history cleared",
            "session_id": session_id
        }
    else:
        return {
            "message": "Session not found (will be created on next message)",
            "session_id": session_id
        }

@app.delete("/chat/session/{session_id}")
def delete_session(session_id: str):
    """
    Delete a session entirely.
    
    Removes session and all associated data.
    """
    success = session_manager.delete_session(session_id)
    
    if success:
        return {
            "message": "Session deleted",
            "session_id": session_id
        }
    else:
        raise HTTPException(404, f"Session {session_id} not found")

@app.get("/chat/stats/{session_id}")
def get_session_stats(session_id: str):
    """Get statistics for a specific session."""
    stats = session_manager.get_session_stats(session_id)
    
    if stats:
        return stats
    else:
        raise HTTPException(404, f"Session {session_id} not found")

@app.get("/chat/stats")
def get_all_stats():
    """Get statistics for all sessions."""
    return session_manager.get_all_stats()

# ============================================================================
# HEALTH & INFO ENDPOINTS
# ============================================================================

@app.get("/health")
def health():
    """Health check."""
    return {
        "status": "healthy",
        "framework": "LangChain",
        "num_chunks": vectorstore.index.ntotal,
        "reranking_enabled": config['retrieval']['use_reranker'],
        "chat_enabled": config['chatbot']['enabled'],
        "active_sessions": len(session_manager.sessions)
    }

@app.get("/")
def root():
    """API info."""
    return {
        "name": "LangChain RAG API with Chat",
        "version": "2.0.0",
        "features": [
            "LangChain Framework",
            "Hybrid Search (FAISS + BM25)",
            "Cross-Encoder Reranking",
            "Conversational Chat with Memory",
            "Multi-user Session Management",
            "Local LLM (Ollama)",
            "Zero API Costs"
        ],
        "endpoints": {
            "POST /query": "Single-turn query (no memory)",
            "POST /chat": "Conversational chat (with memory)",
            "GET /chat/history/{session_id}": "Get conversation history",
            "POST /chat/clear/{session_id}": "Clear conversation",
            "DELETE /chat/session/{session_id}": "Delete session",
            "GET /chat/stats": "Get all session stats",
            "GET /health": "Health check"
        }
    }


@app.get("/chat/ui", response_class=HTMLResponse)
def chat_ui():
        """Minimal single-file chat UI for quick testing."""
        html = """
<!doctype html>
<html>
    <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width,initial-scale=1" />
        <title>Simple Chat UI</title>
        <style>
            body{font-family:Arial,Helvetica,sans-serif;margin:20px}
            #messages{border:1px solid #ddd;padding:10px;height:300px;overflow:auto;margin-bottom:10px}
            .msg.user{color:#0b66ff}
            .msg.bot{color:#222}
        </style>
    </head>
    <body>
        <h3>Simple Chat</h3>
        <div id="messages"></div>
        <input id="input" placeholder="Type a message" style="width:70%" />
        <button id="send">Send</button>
        <script>
            const API = '/chat';
            let sessionId = localStorage.getItem('simple_session_id');
            if(!sessionId){ sessionId = 'web_'+Date.now(); localStorage.setItem('simple_session_id', sessionId); }
            const messages = document.getElementById('messages');
            const input = document.getElementById('input');
            const send = document.getElementById('send');
            function add(text, cls){ const d=document.createElement('div'); d.className='msg '+cls; d.innerText=text; messages.appendChild(d); messages.scrollTop = messages.scrollHeight; }
            send.onclick = async ()=>{
                const txt = input.value.trim(); if(!txt) return; add('You: '+txt,'user'); input.value='';
                try{
                    const res = await fetch(API, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:txt,session_id:sessionId})});
                    const j = await res.json();
                    if(res.ok){ add('Bot: '+j.answer,'bot'); }
                    else { add('Error: '+(j.detail||JSON.stringify(j)),'bot'); }
                }catch(e){ add('Request failed: '+e,'bot'); }
            }
        </script>
    </body>
</html>
"""
        return HTMLResponse(content=html)