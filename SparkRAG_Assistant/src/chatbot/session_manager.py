"""
Session manager for multi-user chatbot.
"""

from typing import Dict, Optional
from datetime import datetime, timedelta
import threading
from src.chatbot.langchain_chatbot import LangChainChatbot


class SessionManager:
    """
    Manages chatbot sessions for multiple users.
    
    Features:
    - One chatbot instance per user/session
    - Automatic session cleanup
    - Thread-safe operations
    """
    
    def __init__(
        self,
        retriever,
        llm_model: str = "llama3.2",
        base_url: str = "http://localhost:11434",
        memory_type: str = "buffer",
        max_history: int = 10,
        session_timeout_minutes: int = 60,
        max_sessions: int = 1000
    ):
        """
        Initialize session manager.
        
        Args:
            retriever: LangChain retriever
            llm_model: Ollama model name
            base_url: Ollama URL
            memory_type: Memory type for chatbots
            max_history: Max conversation history
            session_timeout_minutes: Session timeout
            max_sessions: Maximum concurrent sessions
        """
        self.retriever = retriever
        self.llm_model = llm_model
        self.base_url = base_url
        self.memory_type = memory_type
        self.max_history = max_history
        self.session_timeout = timedelta(minutes=session_timeout_minutes)
        self.max_sessions = max_sessions
        
        self.sessions: Dict[str, LangChainChatbot] = {}
        self.lock = threading.Lock()
        
        print(f"✅ Session manager initialized")
        print(f"   - Max sessions: {max_sessions}")
        print(f"   - Session timeout: {session_timeout_minutes} minutes")
    
    def get_or_create_session(self, session_id: str) -> LangChainChatbot:
        """
        Get existing session or create new one.
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            LangChainChatbot instance
        """
        with self.lock:
            # Clean up old sessions first
            self._cleanup_old_sessions()
            
            # Check if session exists
            if session_id in self.sessions:
                chatbot = self.sessions[session_id]
                # Update last active time
                chatbot.last_active = datetime.now()
                return chatbot
            
            # Check session limit
            if len(self.sessions) >= self.max_sessions:
                # Remove oldest session
                oldest_id = min(
                    self.sessions.keys(),
                    key=lambda k: self.sessions[k].last_active
                )
                del self.sessions[oldest_id]
                print(f"⚠️  Removed oldest session: {oldest_id}")
            
            # Create new session
            print(f"📝 Creating new session: {session_id}")
            
            chatbot = LangChainChatbot(
                retriever=self.retriever,
                llm=self.llm_model,
                memory_type=self.memory_type,
                max_history=self.max_history,
                base_url=self.base_url
            )
            
            self.sessions[session_id] = chatbot
            return chatbot
    
    def _cleanup_old_sessions(self):
        """Remove sessions that have timed out."""
        now = datetime.now()
        expired_sessions = []
        
        for session_id, chatbot in self.sessions.items():
            if now - chatbot.last_active > self.session_timeout:
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            del self.sessions[session_id]
            if expired_sessions:
                print(f"🧹 Cleaned up {len(expired_sessions)} expired session(s)")
    
    def clear_session(self, session_id: str) -> bool:
        """
        Clear conversation history for a session.
        
        Args:
            session_id: Session to clear
            
        Returns:
            True if cleared, False if session not found
        """
        with self.lock:
            if session_id in self.sessions:
                self.sessions[session_id].clear_history()
                return True
            return False
    
    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session entirely.
        
        Args:
            session_id: Session to delete
            
        Returns:
            True if deleted, False if not found
        """
        with self.lock:
            if session_id in self.sessions:
                del self.sessions[session_id]
                print(f"🗑️  Deleted session: {session_id}")
                return True
            return False
    
    def get_session_stats(self, session_id: str) -> Optional[Dict]:
        """Get stats for a specific session."""
        with self.lock:
            if session_id in self.sessions:
                return self.sessions[session_id].get_stats()
            return None
    
    def get_all_stats(self) -> Dict:
        """Get overall statistics."""
        with self.lock:
            return {
                "total_sessions": len(self.sessions),
                "max_sessions": self.max_sessions,
                "session_timeout_minutes": self.session_timeout.total_seconds() / 60,
                "sessions": {
                    session_id: chatbot.get_stats()
                    for session_id, chatbot in self.sessions.items()
                }
            }