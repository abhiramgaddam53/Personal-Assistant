"""
Optimized Personal Assistant with improved performance and features

Key Improvements:
1. Connection pooling for database operations
2. Cached embeddings and vectorstore
3. Better error handling and validation
4. Configuration management
5. Modular architecture
6. Proper resource management
7. Input sanitization
8. Better logging
"""

import os
import logging
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
import dateparser

# Import our modular components
from config import Config
from database import DatabaseManager, init_database
from email_manager import EmailManager
from google_services import GoogleServicesManager
from rag_manager import RAGManager, get_default_knowledge_base

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PersonalAssistant:
    """Optimized Personal Assistant with modular architecture"""
    
    def __init__(self, config: Optional[Config] = None):
        """
        Initialize Personal Assistant
        
        Args:
            config: Configuration object. If None, loads from environment.
        """
        # Load configuration
        self.config = config or Config()
        
        # Initialize database with connection pooling
        self.db = DatabaseManager()
        try:
            self.db.initialize(self.config.db_connection_params)
            init_database(self.db)
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            self.db = None
        
        # Initialize email manager
        try:
            self.email_manager = EmailManager(
                username=self.config.GMAIL_USERNAME,
                password=self.config.GMAIL_PASSWORD,
                default_recipient=self.config.GMAIL_RECIPIENT
            )
        except Exception as e:
            logger.warning(f"Email manager initialization failed: {e}")
            self.email_manager = None
        
        # Initialize Google services
        try:
            self.google_services = GoogleServicesManager(
                api_key=self.config.GOOGLE_API_KEY,
                service_account_file=self.config.SERVICE_ACCOUNT_FILE,
                custom_search_cx=self.config.GOOGLE_CX
            )
        except Exception as e:
            logger.warning(f"Google services initialization failed: {e}")
            self.google_services = None
        
        # Initialize RAG with caching
        try:
            self.rag_manager = RAGManager()
            knowledge_base = get_default_knowledge_base()
            documents = self.rag_manager.load_documents_from_list(knowledge_base)
            self.rag_manager.create_vectorstore(documents, vectorstore_name="assistant_kb")
        except Exception as e:
            logger.warning(f"RAG manager initialization failed: {e}")
            self.rag_manager = None
        
        # Initialize LLM
        try:
            self.llm = ChatGoogleGenerativeAI(
                model="models/gemini-2.5-flash",
                google_api_key=self.config.GOOGLE_API_KEY,
                temperature=0.1
            )
            # Test connection
            response = self.llm.invoke("Test")
            logger.info("LLM initialized successfully")
        except Exception as e:
            logger.error(f"LLM initialization failed: {e}")
            raise RuntimeError("Cannot initialize LLM. Check API key.")
        
        # Set up prompts
        self.router_prompt = PromptTemplate(
            input_variables=["query"],
            template="""Classify the user query into ONE category: email, task, search, database, calendar, rag, or llm.

Categories:
- email: sending/receiving/checking emails
- task: managing tasks, reminders, spreadsheets
- search: web/Google search
- database: SQL queries, database operations
- calendar: scheduling meetings/events
- rag: questions requiring document retrieval (what is, explain, tell me about)
- llm: general conversation, summaries

Query: {query}

Return ONLY the category name."""
        )
        
        self.structure_prompt = PromptTemplate(
            input_variables=["query", "raw_response"],
            template="""You are a helpful personal assistant. 

User query: {query}
System response: {raw_response}

Format this into a clear, user-friendly response using markdown. Use:
- **Bold** for emphasis
- Bullet points for lists
- Proper spacing and formatting

Ensure markdown is properly closed and response directly addresses the query."""
        )
        
        self.router_chain = self.router_prompt | self.llm
        self.structure_chain = self.structure_prompt | self.llm
        
        # Initialize scheduler
        self.scheduler = BackgroundScheduler()
        self._setup_scheduler()
        self.scheduler.start()
        
        logger.info("Personal Assistant initialized successfully")
    
    def _setup_scheduler(self):
        """Set up daily summary scheduler"""
        try:
            # Parse time from config (format: HH:MM)
            time_parts = self.config.DAILY_SUMMARY_TIME.split(':')
            hour = int(time_parts[0])
            minute = int(time_parts[1]) if len(time_parts) > 1 else 0
            
            self.scheduler.add_job(
                self.send_daily_summary,
                CronTrigger(hour=hour, minute=minute),
                id='daily_summary',
                replace_existing=True
            )
            logger.info(f"Scheduler set for {hour:02d}:{minute:02d} daily")
        except Exception as e:
            logger.warning(f"Failed to set up scheduler: {e}")
    
    def route_query(self, query: str) -> str:
        """Route query to appropriate handler"""
        try:
            result = self.router_chain.invoke({"query": query})
            category = result.content.strip().lower()
            
            valid_categories = ['email', 'task', 'search', 'database', 'calendar', 'rag', 'llm']
            if category not in valid_categories:
                logger.warning(f"Invalid category '{category}', defaulting to llm")
                return 'llm'
            
            return category
        except Exception as e:
            logger.error(f"Routing error: {e}")
            return 'llm'
    
    def structure_response(self, query: str, raw_response: str) -> str:
        """Structure raw response into user-friendly format"""
        try:
            result = self.structure_chain.invoke({
                "query": query,
                "raw_response": raw_response
            })
            return result.content
        except Exception as e:
            logger.error(f"Response structuring error: {e}")
            return raw_response
    
    # Email operations
    def handle_email_query(self, query: str, user_id: str) -> str:
        """Handle email-related queries"""
        if not self.email_manager:
            return "Email service not configured. Please check GMAIL_USERNAME and GMAIL_PASSWORD in .env"
        
        query_lower = query.lower()
        
        try:
            if "send" in query_lower or "mail to" in query_lower:
                return self._send_email_from_query(query)
            else:
                return self._check_emails(user_id)
        except Exception as e:
            return f"Email operation failed: {str(e)}"
    
    def _send_email_from_query(self, query: str) -> str:
        """Parse query and send email"""
        # Extract subject
        subject_match = re.search(r'subject:\s*(.+?)(?:body:|$)', query, re.IGNORECASE)
        subject = subject_match.group(1).strip() if subject_match else "Assistant Email"
        
        # Extract body
        body_match = re.search(r'body:\s*(.+)', query, re.IGNORECASE)
        body = body_match.group(1).strip() if body_match else query
        
        # Extract recipient
        recipient_match = re.search(r'to\s+([\w\.-]+@[\w\.-]+)', query)
        recipient = recipient_match.group(1) if recipient_match else None
        
        # Send email
        self.email_manager.send_email(subject, body, recipient)
        return f"Email sent successfully to {recipient or self.config.GMAIL_RECIPIENT}"
    
    def _check_emails(self, user_id: str) -> str:
        """Check and return email summaries"""
        # Get user's email filters from database
        filters = 'ALL'
        if self.db:
            try:
                result = self.db.execute_query(
                    "SELECT email_filters FROM user_profiles WHERE user_id = %s",
                    (user_id,),
                    fetch_one=True
                )
                if result:
                    filters = result['email_filters']
            except Exception as e:
                logger.warning(f"Failed to get email filters: {e}")
        
        emails = self.email_manager.check_emails(filters=filters, limit=5)
        return self.email_manager.format_email_summary(emails)
    
    # Task operations
    def handle_task_query(self, query: str, user_id: str) -> str:
        """Handle task-related queries"""
        if not self.db:
            return "Database not configured. Task operations unavailable."
        
        query_lower = query.lower()
        
        try:
            if "insights" in query_lower:
                return self._get_task_insights(user_id)
            elif "add" in query_lower or "reminder" in query_lower:
                return self._add_task(query, user_id)
            elif "list" in query_lower or "pending" in query_lower or "retrieve" in query_lower:
                return self._list_tasks(user_id)
            elif "daily summary" in query_lower:
                return self.send_daily_summary()
            else:
                return self._get_task_insights(user_id)
        except Exception as e:
            return f"Task operation failed: {str(e)}"
    
    def _add_task(self, query: str, user_id: str) -> str:
        """Add a new task"""
        # Extract task description
        task_desc = re.sub(
            r'(add task|add|reminder|to sheets|update sheets|that i need to)',
            '',
            query,
            flags=re.IGNORECASE
        ).strip()
        
        # Extract due date
        due_match = re.search(r'due\s+(on\s+)?([\w\s\d-]+)', query.lower())
        due_date_str = due_match.group(2).strip() if due_match else None
        
        # Parse due date
        if due_date_str:
            due_date = dateparser.parse(due_date_str)
            if not due_date:
                due_date = datetime.now() + timedelta(days=1)
        else:
            due_date = datetime.now() + timedelta(days=1)
        
        # Insert task into database
        self.db.execute_update(
            "INSERT INTO tasks (user_id, task_description, due_date, status, priority) "
            "VALUES (%s, %s, %s, %s, %s)",
            (user_id, task_desc, due_date, 'pending', 'medium')
        )
        
        # Update Google Sheets if available
        sheets_msg = ""
        if self.google_services and self.google_services.sheets_service and self.config.SHEET_ID:
            try:
                tasks = self._get_pending_tasks(user_id)
                task_rows = [[t['description'], t['due_date'], t['status'], t['priority']] 
                            for t in tasks]
                self.google_services.update_sheet(
                    self.config.SHEET_ID,
                    'Sheet1!A1:D',
                    task_rows
                )
                sheets_msg = "\nSpreadsheet updated."
            except Exception as e:
                logger.warning(f"Failed to update sheets: {e}")
        
        # Add to Google Tasks if available
        gtasks_msg = ""
        if self.google_services and self.google_services.tasks_service:
            try:
                self.google_services.add_task(task_desc, due_date)
                gtasks_msg = "\nAdded to Google Tasks."
            except Exception as e:
                logger.warning(f"Failed to add to Google Tasks: {e}")
        
        return f"Task added: {task_desc} (Due: {due_date.strftime('%Y-%m-%d')}){sheets_msg}{gtasks_msg}"
    
    def _get_pending_tasks(self, user_id: str) -> list:
        """Get all pending tasks for a user"""
        results = self.db.execute_query(
            "SELECT task_description as description, "
            "to_char(due_date, 'YYYY-MM-DD') as due_date, status, priority "
            "FROM tasks WHERE user_id = %s AND status = 'pending' "
            "ORDER BY due_date",
            (user_id,)
        )
        return [dict(row) for row in results]
    
    def _list_tasks(self, user_id: str) -> str:
        """List all pending tasks"""
        tasks = self._get_pending_tasks(user_id)
        
        if not tasks:
            return "No pending tasks found."
        
        formatted = ["**Your Pending Tasks:**\n"]
        for i, task in enumerate(tasks, 1):
            formatted.append(
                f"{i}. **{task['description']}**\n"
                f"   Due: {task['due_date']} | Priority: {task['priority']}"
            )
        
        return "\n".join(formatted)
    
    def _get_task_insights(self, user_id: str) -> str:
        """Get task statistics and insights"""
        try:
            results = self.db.execute_query("""
                SELECT status, COUNT(*) as count,
                       ROUND(AVG(EXTRACT(EPOCH FROM (due_date - CURRENT_TIMESTAMP))/86400)::numeric, 1) as avg_days
                FROM tasks 
                WHERE user_id = %s 
                GROUP BY status
            """, (user_id,))
            
            if not results:
                return "No tasks found."
            
            insights = ["**Task Insights:**\n"]
            for row in results:
                insights.append(
                    f"- **{row['status'].title()}**: {row['count']} tasks "
                    f"(Avg days to due: {row['avg_days']})"
                )
            
            return "\n".join(insights)
        except Exception as e:
            logger.error(f"Error getting insights: {e}")
            return f"Failed to get insights: {str(e)}"
    
    # Search operations
    def handle_search_query(self, query: str) -> str:
        """Handle search queries"""
        if not self.google_services:
            return "Google services not configured. Check GOOGLE_API_KEY and GOOGLE_CX."
        
        # Extract search query
        search_query = re.sub(
            r'(google search|search for|search|seatch)',
            '',
            query,
            flags=re.IGNORECASE
        ).strip()
        
        try:
            results = self.google_services.search(search_query)
            return self.google_services.format_search_results(results)
        except Exception as e:
            return f"Search failed: {str(e)}"
    
    # Database operations
    def handle_database_query(self, query: str, user_id: str) -> str:
        """Handle database queries"""
        if not self.db:
            return "Database not configured."
        
        try:
            # Special case: list tables
            if "tables in my database" in query.lower() or "select * from tables" in query.lower():
                results = self.db.execute_query(
                    "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
                )
                tables = [row['tablename'] for row in results]
                return "**Tables in database:**\n" + "\n".join(f"- {t}" for t in tables)
            
            # Execute query (with basic validation)
            if not query.strip().lower().startswith(('select', 'insert', 'update', 'delete')):
                return "Only SELECT, INSERT, UPDATE, DELETE queries are allowed."
            
            if query.strip().lower().startswith('select'):
                results = self.db.execute_query(query)
                if not results:
                    return "No results found."
                
                # Format results
                formatted = ["**Query Results:**\n"]
                for i, row in enumerate(results, 1):
                    formatted.append(f"{i}. {dict(row)}")
                
                return "\n".join(formatted)
            else:
                rowcount = self.db.execute_update(query)
                return f"Query executed successfully. {rowcount} rows affected."
                
        except Exception as e:
            logger.error(f"Database query error: {e}")
            return f"Database error: {str(e)}"
    
    # Calendar operations
    def handle_calendar_query(self, query: str, user_id: str) -> str:
        """Handle calendar/scheduling queries"""
        query_lower = query.lower()
        
        try:
            # Reschedule daily summary
            if "reschedule" in query_lower or "schedule the time" in query_lower:
                time_match = re.search(r'(\d{1,2}):(\d{2})\s*(am|pm)', query, re.IGNORECASE)
                if not time_match:
                    return "Please specify time in format HH:MM AM/PM (e.g., '6:00 AM')"
                
                hour = int(time_match.group(1))
                minute = int(time_match.group(2))
                period = time_match.group(3).lower()
                
                if period == 'pm' and hour != 12:
                    hour += 12
                elif period == 'am' and hour == 12:
                    hour = 0
                
                self.scheduler.reschedule_job(
                    'daily_summary',
                    trigger=CronTrigger(hour=hour, minute=minute)
                )
                
                return f"Daily summary rescheduled to {hour:02d}:{minute:02d}"
            
            # Schedule meeting
            elif "meeting" in query_lower:
                if not self.google_services or not self.google_services.calendar_service:
                    return "Calendar service not configured."
                
                # Extract email
                email_match = re.search(r'([\w\.-]+@[\w\.-]+)', query)
                if not email_match:
                    return "Please specify attendee email address."
                
                attendee_email = email_match.group(1)
                
                # Extract time
                time_match = re.search(r'at\s+(\d{1,2}:\d{2}\s*(?:am|pm))', query, re.IGNORECASE)
                if not time_match:
                    return "Please specify meeting time (e.g., 'at 5:00 PM')"
                
                time_str = time_match.group(1)
                
                # Extract date
                date_match = re.search(r'on\s+(\d{1,2}(?:st|nd|rd|th)?\s+\w+)', query, re.IGNORECASE)
                date_str = date_match.group(1) if date_match else None
                
                # Parse date and time
                if date_str:
                    date_str_clean = re.sub(r'(st|nd|rd|th)', '', date_str)
                    meeting_date = dateparser.parse(date_str_clean)
                else:
                    meeting_date = datetime.now()
                
                time_parsed = dateparser.parse(time_str)
                if not time_parsed:
                    return "Invalid time format."
                
                start_time = datetime.combine(meeting_date.date(), time_parsed.time())
                end_time = start_time + timedelta(hours=1)
                
                # Schedule the meeting
                self.google_services.schedule_event(
                    summary="Meeting",
                    start_time=start_time,
                    end_time=end_time,
                    attendees=[attendee_email]
                )
                
                return f"Meeting scheduled with {attendee_email} on {start_time.strftime('%Y-%m-%d at %I:%M %p')}"
            
            else:
                return "Please specify if scheduling a meeting or rescheduling summary."
                
        except Exception as e:
            logger.error(f"Calendar operation error: {e}")
            return f"Calendar operation failed: {str(e)}"
    
    # RAG operations
    def handle_rag_query(self, query: str, user_id: str) -> str:
        """Handle RAG/knowledge retrieval queries"""
        if not self.rag_manager:
            return "RAG service not available."
        
        try:
            # Retrieve relevant documents
            docs = self.rag_manager.retrieve(query, k=3)
            context = self.rag_manager.format_context(docs)
            
            # Generate response with context
            prompt = f"Answer the following question using the provided context.\n\nContext:\n{context}\n\nQuestion: {query}\n\nAnswer:"
            response = self.llm.invoke(prompt).content
            
            # Store in chat history
            if self.db:
                try:
                    self.db.execute_update(
                        "INSERT INTO chat_history (user_id, query, context, response) "
                        "VALUES (%s, %s, %s, %s)",
                        (user_id, query, context[:1000], response)
                    )
                except Exception as e:
                    logger.warning(f"Failed to store chat history: {e}")
            
            return response
            
        except Exception as e:
            logger.error(f"RAG query error: {e}")
            return f"RAG query failed: {str(e)}"
    
    # General LLM operations
    def handle_llm_query(self, query: str, user_id: str) -> str:
        """Handle general LLM queries"""
        try:
            response = self.llm.invoke(query).content
            
            # Store in general chat history
            if self.db:
                try:
                    self.db.execute_update(
                        "INSERT INTO general_chat_history (user_id, query, response) "
                        "VALUES (%s, %s, %s)",
                        (user_id, query, response)
                    )
                except Exception as e:
                    logger.warning(f"Failed to store chat history: {e}")
            
            return response
            
        except Exception as e:
            logger.error(f"LLM query error: {e}")
            return f"LLM query failed: {str(e)}"
    
    # Daily summary
    def send_daily_summary(self) -> str:
        """Send daily summary to all users"""
        if not self.db or not self.email_manager:
            return "Daily summary requires database and email configuration."
        
        try:
            # Get all users
            users = self.db.execute_query("SELECT user_id FROM user_profiles")
            
            for user_row in users:
                user_id = user_row['user_id']
                
                # Get email summary
                try:
                    emails = self.email_manager.check_emails(limit=5)
                    email_summary = self.email_manager.format_email_summary(emails)
                except Exception as e:
                    email_summary = f"Failed to fetch emails: {str(e)}"
                
                # Get task summary
                try:
                    tasks = self._get_pending_tasks(user_id)
                    if tasks:
                        task_lines = [
                            f"- {t['description']} (Due: {t['due_date']}, Priority: {t['priority']})"
                            for t in tasks
                        ]
                        task_summary = "\n".join(task_lines)
                    else:
                        task_summary = "No pending tasks"
                except Exception as e:
                    task_summary = f"Failed to fetch tasks: {str(e)}"
                
                # Send summary email
                summary = f"""Daily Summary

**Recent Emails:**
{email_summary}

**Pending Tasks:**
{task_summary}
"""
                
                try:
                    self.email_manager.send_email(
                        "Daily Summary",
                        summary,
                        self.config.GMAIL_RECIPIENT
                    )
                except Exception as e:
                    logger.error(f"Failed to send summary for {user_id}: {e}")
            
            return "Daily summary sent successfully"
            
        except Exception as e:
            logger.error(f"Daily summary error: {e}")
            return f"Failed to send daily summary: {str(e)}"
    
    # Main query handler
    def ask(self, query: str, user_id: str = "abhiram") -> str:
        """
        Main entry point for handling user queries
        
        Args:
            query: User's query string
            user_id: User identifier
            
        Returns:
            Formatted response string
        """
        # Validate inputs
        if not query or not isinstance(query, str):
            raise ValueError("Query must be a non-empty string")
        if not user_id or not isinstance(user_id, str):
            raise ValueError("User ID must be a non-empty string")
        
        query = query.strip()
        query_lower = query.lower()
        
        # Special cases
        if any(keyword in query_lower for keyword in ["about me", "tell me about yourself", 
                                                       "who are you", "your details", "resume"]):
            return self.handle_rag_query(query, user_id)
        
        # Route query
        query_type = self.route_query(query)
        logger.info(f"Query type: {query_type} for query: {query[:50]}")
        
        # Handle query based on type
        try:
            if query_type == "email":
                raw_response = self.handle_email_query(query, user_id)
            elif query_type == "task":
                raw_response = self.handle_task_query(query, user_id)
            elif query_type == "search":
                raw_response = self.handle_search_query(query)
            elif query_type == "database":
                raw_response = self.handle_database_query(query, user_id)
            elif query_type == "calendar":
                raw_response = self.handle_calendar_query(query, user_id)
            elif query_type == "rag":
                raw_response = self.handle_rag_query(query, user_id)
            else:  # llm
                raw_response = self.handle_llm_query(query, user_id)
            
            # Structure the response
            return self.structure_response(query, raw_response)
            
        except Exception as e:
            logger.error(f"Error handling query: {e}")
            return f"Sorry, I encountered an error: {str(e)}"
    
    def cleanup(self):
        """Clean up resources"""
        if self.scheduler.running:
            self.scheduler.shutdown()
        
        if self.email_manager:
            self.email_manager.close_imap_connection()
        
        if self.db:
            self.db.close_all()
        
        logger.info("Personal Assistant cleaned up")


def main():
    """Main entry point for the assistant"""
    print("=" * 60)
    print("Personal Assistant - Optimized Version")
    print("=" * 60)
    print("\nInitializing...")
    
    try:
        # Initialize assistant
        assistant = PersonalAssistant()
        
        print("\nAssistant started successfully!")
        print("\nExample queries:")
        print("- 'Check my emails'")
        print("- 'Add task: Buy groceries due tomorrow'")
        print("- 'Google search Python tutorials'")
        print("- 'Task insights'")
        print("- 'Send email to user@example.com subject: Hello body: Test message'")
        print("- 'Tell me about yourself'")
        print("- 'Schedule meeting with user@example.com at 5:00 PM on Oct 6'")
        print("\nType 'exit' or 'quit' to stop.\n")
        
        # Main loop
        while True:
            try:
                query = input("\nYour query: ").strip()
                
                if not query:
                    continue
                
                if query.lower() in ['exit', 'quit', 'q']:
                    print("\nGoodbye!")
                    break
                
                # Process query
                response = assistant.ask(query)
                print(f"\nResponse:\n{response}")
                
            except KeyboardInterrupt:
                print("\n\nInterrupted. Goodbye!")
                break
            except Exception as e:
                print(f"\nError: {str(e)}")
        
        # Cleanup
        assistant.cleanup()
        
    except Exception as e:
        print(f"\nFailed to initialize assistant: {str(e)}")
        print("\nPlease check your .env configuration file.")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
