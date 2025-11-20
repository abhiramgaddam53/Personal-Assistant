"""
RAG (Retrieval Augmented Generation) utilities with caching
"""
import logging
import pickle
from pathlib import Path
from typing import List, Optional
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import TextLoader
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document

logger = logging.getLogger(__name__)

class RAGManager:
    """Manages document retrieval and RAG operations with caching"""
    
    def __init__(self, cache_dir: str = ".cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
        self.embeddings = None
        self.vectorstore = None
        self.retriever = None
        
        self._initialize_embeddings()
    
    def _initialize_embeddings(self):
        """Initialize embeddings model (cached)"""
        try:
            # Use a lightweight model for efficiency
            self.embeddings = HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2",
                cache_folder=str(self.cache_dir / "embeddings")
            )
            logger.info("Embeddings model initialized")
        except Exception as e:
            logger.error(f"Failed to initialize embeddings: {e}")
            raise
    
    def load_documents_from_file(self, file_path: str) -> List[Document]:
        """Load documents from a text file"""
        try:
            loader = TextLoader(file_path)
            documents = loader.load()
            logger.info(f"Loaded {len(documents)} documents from {file_path}")
            return documents
        except Exception as e:
            logger.error(f"Failed to load documents: {e}")
            raise
    
    def load_documents_from_list(self, texts: List[str]) -> List[Document]:
        """Create documents from a list of texts"""
        return [Document(page_content=text) for text in texts]
    
    def create_vectorstore(self, documents: List[Document], 
                          vectorstore_name: str = "default") -> None:
        """
        Create a FAISS vectorstore from documents
        
        Args:
            documents: List of documents to index
            vectorstore_name: Name for caching the vectorstore
        """
        cache_path = self.cache_dir / f"vectorstore_{vectorstore_name}.pkl"
        
        # Try to load from cache first
        if cache_path.exists():
            try:
                logger.info(f"Loading vectorstore from cache: {cache_path}")
                self.vectorstore = FAISS.load_local(
                    str(self.cache_dir / f"vectorstore_{vectorstore_name}"),
                    self.embeddings,
                    allow_dangerous_deserialization=True
                )
                self.retriever = self.vectorstore.as_retriever()
                logger.info("Vectorstore loaded from cache")
                return
            except Exception as e:
                logger.warning(f"Failed to load cached vectorstore: {e}")
        
        # Create new vectorstore
        try:
            logger.info("Creating new vectorstore...")
            self.vectorstore = FAISS.from_documents(documents, self.embeddings)
            self.retriever = self.vectorstore.as_retriever()
            
            # Save to cache
            self.vectorstore.save_local(
                str(self.cache_dir / f"vectorstore_{vectorstore_name}")
            )
            logger.info(f"Vectorstore created and cached at {cache_path}")
            
        except Exception as e:
            logger.error(f"Failed to create vectorstore: {e}")
            raise
    
    def add_documents(self, documents: List[Document]) -> None:
        """Add documents to existing vectorstore"""
        if not self.vectorstore:
            raise RuntimeError("Vectorstore not initialized. Call create_vectorstore first.")
        
        try:
            self.vectorstore.add_documents(documents)
            logger.info(f"Added {len(documents)} documents to vectorstore")
        except Exception as e:
            logger.error(f"Failed to add documents: {e}")
            raise
    
    def retrieve(self, query: str, k: int = 4) -> List[Document]:
        """
        Retrieve relevant documents for a query
        
        Args:
            query: Search query
            k: Number of documents to retrieve
            
        Returns:
            List of relevant documents
        """
        if not self.retriever:
            raise RuntimeError("Retriever not initialized. Call create_vectorstore first.")
        
        try:
            documents = self.retriever.invoke(query)
            return documents[:k]
        except Exception as e:
            logger.error(f"Retrieval error: {e}")
            raise
    
    def format_context(self, documents: List[Document]) -> str:
        """Format retrieved documents as context string"""
        return "\n\n".join([doc.page_content for doc in documents])
    
    def clear_cache(self):
        """Clear all cached vectorstores"""
        import shutil
        try:
            shutil.rmtree(self.cache_dir)
            self.cache_dir.mkdir(exist_ok=True)
            logger.info("Cache cleared")
        except Exception as e:
            logger.warning(f"Failed to clear cache: {e}")


def get_default_knowledge_base() -> List[str]:
    """Get default knowledge base for the personal assistant"""
    return [
        """
        Personal Assistant Features:
        - Email management: Send and receive emails via IMAP/SMTP
        - Task management: Create, list, and track tasks with due dates
        - Google Sheets integration: Automatically update task spreadsheets
        - Google Calendar: Schedule meetings and events
        - Google Search: Web search functionality
        - Database queries: PostgreSQL database access
        - RAG: Document retrieval for answering questions
        - Daily summaries: Automated email summaries and task reports
        """,
        """
        Database Schema:
        - chat_history: Stores conversation history with context
        - general_chat_history: General chat logs
        - tasks: Task information with user_id, description, due_date, status, priority
        - user_profiles: User preferences for email filters and reminders
        """,
        """
        Gaddam Bhanu Venkata Abhiram
        
        Contact Information:
        - Phone: +91 9398982703
        - Email: gaddamabhiram53@gmail.com
        - LinkedIn: linkedin.com/in/abhiramgaddam
        - Website: https://abhiram-gaddam.github.io/
        - GitHub: https://github.com/Abhiram-Gaddam
        
        Education:
        - Bachelor of Computer Science and Business Systems
        - R.V.R & J.C College of Engineering, Guntur
        - 2022 – Present, CGPA: 8.63/10
        
        Skills:
        - Technical: Java, SQL, ReactJs, Python, HTML, CSS (Tailwind), JavaScript
        - Tools: Git, GitHub, Colab
        
        Internships:
        - Technical Associate at 4Sight AI (AI4AndhraPolice Hackathon), May 2025 – Jun 2025
        - Built 2 web-based admin panels, cutting manual work by 80%
        - Managed 400+ dignitaries with QR tracking system
        
        Projects:
        1. Credit Card Fraud Detection - 99.9% accuracy using Isolation Forest and XGBoost
        2. Personal Chat Assistant - Multi-featured AI assistant with email, tasks, RAG
        3. Document Chatbot - RAG-based system using LlamaIndex and LangChain
        
        Certifications:
        - Java Object-Oriented Programming (LinkedIn Learning)
        - React Js (Infosys Springboard)
        - NPTEL Programming In Java
        - MySQL Bootcamp (Udemy)
        - Machine Learning (Kaggle)
        """
    ]
