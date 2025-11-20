import os
import logging
import psycopg2
from psycopg2 import pool
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2 import service_account
from dotenv import load_dotenv
import imaplib
import nest_asyncio
import re
import requests
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import TextLoader
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.prompts import PromptTemplate
import json
import dateparser
from functools import lru_cache
from pathlib import Path

# Apply nest_asyncio for Colab
nest_asyncio.apply()

# Load environment variables first
load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
SERVICE_ACCOUNT_FILE = os.getenv("SERVICE_ACCOUNT_FILE", "./service-account.json")

# Google services - Lazy loading for better performance
SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/tasks', 'https://www.googleapis.com/auth/calendar']
_credentials = None
_sheets_service = None
_tasks_service = None
_calendar_service = None

def get_google_credentials():
    """Lazy load Google credentials"""
    global _credentials
    if _credentials is None:
        try:
            if os.path.exists(SERVICE_ACCOUNT_FILE):
                _credentials = service_account.Credentials.from_service_account_file(
                    SERVICE_ACCOUNT_FILE, scopes=SCOPES
                )
                logger.info("Google credentials loaded successfully")
            else:
                logger.warning(f"Service account file not found: {SERVICE_ACCOUNT_FILE}")
        except Exception as e:
            logger.error(f"Failed to load Google credentials: {e}")
    return _credentials

def get_sheets_service():
    """Lazy load Google Sheets service"""
    global _sheets_service
    if _sheets_service is None:
        creds = get_google_credentials()
        if creds:
            try:
                _sheets_service = build('sheets', 'v4', credentials=creds)
            except Exception as e:
                logger.error(f"Failed to build Sheets service: {e}")
    return _sheets_service

def get_tasks_service():
    """Lazy load Google Tasks service"""
    global _tasks_service
    if _tasks_service is None:
        creds = get_google_credentials()
        if creds:
            try:
                _tasks_service = build('tasks', 'v1', credentials=creds)
            except Exception as e:
                logger.error(f"Failed to build Tasks service: {e}")
    return _tasks_service

def get_calendar_service():
    """Lazy load Google Calendar service"""
    global _calendar_service
    if _calendar_service is None:
        creds = get_google_credentials()
        if creds:
            try:
                _calendar_service = build('calendar', 'v3', credentials=creds)
            except Exception as e:
                logger.error(f"Failed to build Calendar service: {e}")
    return _calendar_service

# DB setup with connection pooling for better performance
_db_pool = None

def get_db_pool():
    """Get or create database connection pool"""
    global _db_pool
    if _db_pool is None:
        try:
            _db_pool = psycopg2.pool.SimpleConnectionPool(
                1,  # minconn
                10,  # maxconn
                host=os.getenv("DB_HOST", "aws-0-ap-southeast-1.pooler.supabase.com"),
                port=int(os.getenv("DB_PORT", 6543)),
                dbname=os.getenv("DB_NAME", "postgres"),
                user=os.getenv("DB_USER", "postgres.ixruzjparquranqfdvdm"),
                password=os.getenv("DB_PASSWORD", "aasp3885@gmail"),
                sslmode=os.getenv("DB_SSLMODE", "require")
            )
            logger.info("Database connection pool created")
        except psycopg2.Error as e:
            logger.error(f"Failed to create database pool: {e}")
            raise
    return _db_pool

def get_db_connection():
    """Get a connection from the pool"""
    try:
        pool = get_db_pool()
        conn = pool.getconn()
        return conn
    except psycopg2.Error as e:
        logger.error(f"Database connection error: {e}")
        raise

def release_db_connection(conn):
    """Return connection to the pool"""
    try:
        if conn and _db_pool:
            _db_pool.putconn(conn)
    except Exception as e:
        logger.error(f"Error releasing connection: {e}")

def init_db():
    """Initialize database tables"""
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                id SERIAL PRIMARY KEY,
                user_id TEXT NOT NULL,
                query TEXT NOT NULL,
                context TEXT,
                response TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_user_created (user_id, created_at)
            );
            CREATE TABLE IF NOT EXISTS general_chat_history (
                id SERIAL PRIMARY KEY,
                user_id TEXT NOT NULL,
                query TEXT NOT NULL,
                response TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_user_created (user_id, created_at)
            );
            CREATE TABLE IF NOT EXISTS tasks (
                id SERIAL PRIMARY KEY,
                user_id TEXT NOT NULL,
                task_description TEXT NOT NULL,
                due_date TIMESTAMP,
                status TEXT DEFAULT 'pending',
                priority TEXT DEFAULT 'medium',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_user_status (user_id, status),
                INDEX idx_user_due (user_id, due_date)
            );
            CREATE TABLE IF NOT EXISTS user_profiles (
                user_id TEXT PRIMARY KEY,
                email_filters TEXT DEFAULT 'ALL',
                reminder_preference TEXT DEFAULT 'tasks',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cur.execute("INSERT INTO user_profiles (user_id) VALUES (%s) ON CONFLICT DO NOTHING", ("abhiram",))
        conn.commit()
        logger.info("Database initialized successfully")
    except psycopg2.Error as e:
        logger.error(f"Database initialization error: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if cur:
            cur.close()
        if conn:
            release_db_connection(conn)

# Initialize database on module load
try:
    init_db()
except Exception as e:
    logger.error(f"Failed to initialize database: {e}")

# RAG setup with FAISS - Lazy loading for better startup performance
_embeddings = None
_vectorstore = None
_retriever = None
_llm = None

@lru_cache(maxsize=1)
def get_embeddings():
    """Lazy load embeddings model"""
    global _embeddings
    if _embeddings is None:
        try:
            _embeddings = HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2"
            )
            logger.info("Embeddings model loaded")
        except Exception as e:
            logger.error(f"Failed to load embeddings: {e}")
            raise
    return _embeddings

def get_vectorstore():
    """Lazy load vector store"""
    global _vectorstore, _retriever
    if _vectorstore is None:
        try:
            sample_docs_path = DATA_DIR / "sample.txt"
            
            # Create sample docs if not exists
            if not sample_docs_path.exists():
                sample_docs = [
                    "Personal assistant manages emails via IMAP/SMTP, schedules tasks in Google Tasks, and updates Google Sheets daily.",
                    "Tasks are stored in PostgreSQL with fields: user_id, task_description, due_date, status, priority. Query via SQL for retrieval.",
                    "Google Search uses Custom Search API. Daily summaries are emailed at 6 AM with task and email updates.",
                    "Meetings can be scheduled using Google Calendar API with attendee emails and time slots.",
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
            - 2022 – Present
            - CGPA: 8.63/10
            
            Skills:
            - Technical Skills: Java, SQL, ReactJs, Python, HTML, CSS (Tailwind), JavaScript
            - Tools & Technologies: Git, GitHub, Colab
            
            Internships:
            - Technical Associate - 4Sight AI (AI4AndhraPolice Hackathon)
            - May 2025 – Jun 2025
            - Built 2 web-based admin panels for invitations and certificates, cutting manual work by 80%.
            - Enabled bulk invitations via Excel with QR tracking, managing 400+ dignitaries including IPS officers.
            - Contributed to 2+ real-time AI use cases during a hackathon, supporting law enforcement solutions.
            
            Projects:
            - Credit Card Fraud Detection
              - Engineered a fraud detection model using Isolation Forest and XGBoost on 284,000+ transactions.
              - Collaborated with team to address data imbalance, reducing false positives by 10% improving reliability.
              - Streamlined preprocessing with feature scaling and outlier elimination, improving model precision by 15%.
              - Evaluated model performance with precision, recall, and F1-score metrics, achieving 99.9% detection accuracy.
            
            - Personal Chat Assistant
              - Built a personal chat assistant using Python and Gemini API capable of handling general queries and interacting naturally with users.
              - Integrated advanced features such as answering from PDFs, sending emails, displaying top mails, maintaining a task spreadsheet, and setting reminders.
              - Designed to improve productivity by automating repetitive tasks and exploring the practical applications of conversational AI in daily use.
            
            - Document Chatbot
              - Developed a document-based chatbot using LlamaIndex and LangChain for accurate query answering.
              - Applied the system on academic materials and project documents, enabling efficient retrieval of relevant information from uploaded files.
              - Gained practical exposure to retrieval-augmented generation (RAG) methods, highlighting how AI can support students and researchers in academic tasks.
            
            Certifications:
            - Java Object-Oriented Programming from LinkedIn Learning
            - React Js from Infosys Springboard
            - NPTEL Programming In Java
            - The Complete MySQL Bootcamp from Udemy
            - NPTEL Introduction to IoT 4.0
            - Machine Learning from Kaggle
            
            GitHub Profile Overview:
            - Popular repositories: Abhiram (Python), Portfolio (CSS), Abhiram-Gaddam, kota (forked, HTML), gitWorkshop (forked), git-workshop (forked, HTML)
            - Connect with me on LinkedIn: https://www.linkedin.com/in/abhiramgaddam/
            - Languages and Tools: bash, css3, figma, git, html5, javascript, mongodb, mysql, nodejs, pandas, python, react, scikit_learn, tailwind
                    """
                ]
                sample_docs_path.write_text("\n".join(sample_docs))
            
            embeddings = get_embeddings()
            docs = TextLoader(str(sample_docs_path)).load()
            _vectorstore = FAISS.from_documents(docs, embeddings)
            _retriever = _vectorstore.as_retriever()
            logger.info("Vector store initialized")
        except Exception as e:
            logger.error(f"Failed to initialize vector store: {e}")
            raise
    return _vectorstore

def get_retriever():
    """Get retriever for RAG"""
    global _retriever
    if _retriever is None:
        get_vectorstore()
    return _retriever

def get_llm():
    """Lazy load LLM"""
    global _llm
    if _llm is None:
        try:
            api_key = os.getenv("GOOGLE_API_KEY")
            if not api_key:
                raise ValueError("GOOGLE_API_KEY not found in environment")
            
            _llm = ChatGoogleGenerativeAI(
                model="gemini-1.5-flash",
                google_api_key=api_key,
                temperature=0.1
            )
            # Test connection
            response = _llm.invoke("Test connection")
            logger.info(f"Gemini LLM connected successfully")
        except Exception as e:
            logger.error(f"Failed to initialize LLM: {e}")
            raise RuntimeError(
                f"Cannot connect to Gemini. Check API key and quota at https://aistudio.google.com/app/apikey. Error: {e}"
            )
    return _llm

class PersonalAssistant:
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.scheduler.add_job(
            self.send_daily_summary, 
            'date', 
            run_date=datetime.now() + timedelta(seconds=30)
        )
        self.scheduler.start()
        
        # Initialize chains lazily
        self._router_chain = None
        self._structure_chain = None
        
        logger.info("Personal Assistant initialized")
    
    @property
    def router_chain(self):
        """Lazy load router chain"""
        if self._router_chain is None:
            llm = get_llm()
            router_prompt = PromptTemplate(
                input_variables=["query"],
                template="""Classify the following user query into exactly one of these categories: email, task, search, database, calendar, rag, llm.

Categories:
- email: sending, receiving, summarizing emails
- task: tasks, reminders, task insights, adding tasks, listing tasks, Google Sheets management for tasks
- search: Google or web search
- database: SQL queries, database access
- calendar: scheduling or rescheduling meetings/events
- rag: document retrieval (RAG), general knowledge questions like what is, explain, define, how does, why is
- llm: general fallback chat, daily summaries

Return only the category name, nothing else. No explanations.

Query: {query}"""
            )
            self._router_chain = router_prompt | llm
        return self._router_chain
    
    @property
    def structure_chain(self):
        """Lazy load structure chain"""
        if self._structure_chain is None:
            llm = get_llm()
            structure_prompt = PromptTemplate(
                input_variables=["query", "raw_response"],
                template="""You are a helpful personal assistant. The user asked: {query}

The raw result from the system is: {raw_response}

Structure this into a clear, concise, and user-friendly response. Use markdown formatting where appropriate, such as headings, bullet points, numbered lists, or bold text for emphasis. If the raw response indicates success, confirm the action and provide details. If it's an error, explain it politely and suggest possible fixes. Ensure the response directly addresses the user's query and is easy to read.

More Importantly make sure you close all the markdown formatting properly and consistantly.

"""
            )
            self._structure_chain = structure_prompt | llm
        return self._structure_chain

    def check_important_emails(self, user_id, limit=5):
        """Check important emails with improved error handling and caching"""
        conn = None
        cur = None
        mail = None
        try:
            # Get user email filters
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT email_filters FROM user_profiles WHERE user_id = %s", (user_id,))
            row = cur.fetchone()
            filters = row[0] if row else 'ALL'
            
            # Validate environment variables
            gmail_user = os.getenv("GMAIL_USERNAME")
            gmail_pass = os.getenv("GMAIL_PASSWORD")
            if not gmail_user or not gmail_pass:
                return "Gmail credentials not configured. Please set GMAIL_USERNAME and GMAIL_PASSWORD in .env"
            
            # Connect to IMAP
            mail = imaplib.IMAP4_SSL("imap.gmail.com")
            mail.login(gmail_user, gmail_pass)
            mail.select("inbox")
            
            # Search for emails
            status, messages = mail.search(None, filters)
            if status != 'OK':
                logger.warning(f"IMAP search failed with filter '{filters}', falling back to ALL")
                status, messages = mail.search(None, 'ALL')
                if status != 'OK':
                    raise Exception(f"IMAP fallback search failed: {messages}")
            
            email_ids = messages[0].split()
            if not email_ids:
                return "No emails found in inbox."
            
            # Get last N emails (more efficient than fetching all)
            summaries = []
            for email_id in email_ids[-limit:]:
                try:
                    status, msg_data = mail.fetch(email_id, "(RFC822)")
                    if status != 'OK':
                        continue
                    
                    msg = msg_data[0][1].decode("utf-8", errors="ignore")
                    
                    # Extract subject efficiently
                    subject = "No Subject"
                    for line in msg.split("\n"):
                        if line.startswith("Subject:"):
                            subject = line.split(": ", 1)[1] if ": " in line else "No Subject"
                            break
                    
                    summaries.append(f"Subject: {subject}")
                except Exception as e:
                    logger.error(f"Error processing email {email_id}: {e}")
                    continue
            
            return "\n".join(summaries) if summaries else "No emails found."
            
        except imaplib.IMAP4.error as e:
            logger.error(f"IMAP error: {e}")
            return f"Failed to check emails: {str(e)}. Ensure IMAP is enabled and App Password is valid: https://mail.google.com/mail/u/0/#settings/fwdandpop"
        except Exception as e:
            logger.error(f"Error checking emails: {e}")
            return f"Failed to check emails: {str(e)}"
        finally:
            if mail:
                try:
                    mail.logout()
                except:
                    pass
            if cur:
                cur.close()
            if conn:
                release_db_connection(conn)

    def send_email(self, subject, body, recipient=None):
        """Send email with improved error handling"""
        try:
            gmail_user = os.getenv("GMAIL_USERNAME")
            gmail_pass = os.getenv("GMAIL_PASSWORD")
            default_recipient = os.getenv("GMAIL_RECIPIENT")
            
            if not gmail_user or not gmail_pass:
                return "Gmail credentials not configured. Please set GMAIL_USERNAME and GMAIL_PASSWORD in .env"
            
            recipient = recipient or default_recipient
            if not recipient:
                return "No recipient specified and GMAIL_RECIPIENT not configured in .env"
            
            msg = MIMEMultipart()
            msg['From'] = gmail_user
            msg['To'] = recipient
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))
            
            with smtplib.SMTP('smtp.gmail.com', 587) as server:
                server.starttls()
                server.login(gmail_user, gmail_pass)
                server.sendmail(msg['From'], msg['To'], msg.as_string())
            
            logger.info(f"Email sent to {recipient}")
            return f"Email sent successfully to {recipient}."
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error sending email: {e}")
            return f"Failed to send email: {str(e)}. Check Gmail credentials and ensure 'Less secure app access' or App Password is configured."
        except Exception as e:
            logger.error(f"Error sending email: {e}")
            return f"Failed to send email: {str(e)}"

    def perform_google_search(self, query):
        """Perform Google search with better error handling and validation"""
        try:
            api_key = os.getenv("GOOGLE_API_KEY")
            cx = os.getenv("GOOGLE_CX")
            
            if not api_key or not cx:
                return "Google Search not configured. Please set GOOGLE_API_KEY and GOOGLE_CX in .env"
            
            if not query or not query.strip():
                return "Search query cannot be empty."
            
            url = "https://www.googleapis.com/customsearch/v1"
            params = {
                "key": api_key,
                "cx": cx,
                "q": query.strip()
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            results = response.json().get("items", [])
            
            if not results:
                return f"No search results found for '{query}'."
            
            formatted_results = "\n".join([
                f"{i+1}. {result['title']} - {result['link']}" 
                for i, result in enumerate(results[:5])
            ])
            return formatted_results
            
        except requests.exceptions.Timeout:
            logger.error("Google search timed out")
            return "Search request timed out. Please try again."
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error in search: {e}")
            if e.response.status_code == 403:
                return "API quota exceeded or invalid API key. Verify at https://console.developers.google.com"
            return f"Search failed with HTTP error: {e.response.status_code}"
        except Exception as e:
            logger.error(f"Search error: {e}")
            return f"Failed to perform search: {str(e)}"

    def query_database(self, query, user_id):
        """Execute database queries with improved security and error handling"""
        conn = None
        cur = None
        try:
            # Basic SQL injection prevention
            dangerous_keywords = ['DROP', 'DELETE', 'TRUNCATE', 'ALTER', 'CREATE', 'INSERT', 'UPDATE']
            query_upper = query.upper()
            
            # Allow only SELECT for safety unless explicitly approved operations
            if any(keyword in query_upper for keyword in dangerous_keywords):
                if not query_upper.startswith(('INSERT INTO TASKS', 'UPDATE TASKS', 'DELETE FROM TASKS')):
                    return "For security reasons, only SELECT queries and task-related modifications are allowed. Use the task management features for modifications."
            
            conn = get_db_connection()
            cur = conn.cursor()
            
            # Handle special queries
            if "tables in my database" in query.lower() or query.lower().startswith("select * from tables"):
                cur.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
                tables = cur.fetchall()
                if not tables:
                    return "No tables found in database."
                return "Tables in database:\n" + "\n".join([row[0] for row in tables])
            
            # Execute query
            cur.execute(query)
            
            if query_upper.strip().startswith("SELECT"):
                results = cur.fetchall()
                if not results:
                    return "No results found."
                
                columns = [desc[0] for desc in cur.description]
                formatted_results = "\n".join([
                    str(dict(zip(columns, row))) for row in results
                ])
                return f"Database query results:\n{formatted_results}"
            else:
                conn.commit()
                return "Query executed successfully."
                
        except psycopg2.Error as e:
            logger.error(f"Database query error: {e}")
            if conn:
                conn.rollback()
            return f"Failed to execute query: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error in query_database: {e}")
            return f"Failed to execute query: {str(e)}"
        finally:
            if cur:
                cur.close()
            if conn:
                release_db_connection(conn)

    def get_task_insights(self, user_id):
        """Get task insights with improved query performance"""
        conn = None
        cur = None
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            # Optimized query with proper aggregation
            cur.execute("""
                SELECT 
                    status, 
                    COUNT(*) as count,
                    ROUND(AVG(EXTRACT(EPOCH FROM (due_date - CURRENT_TIMESTAMP))/86400)::numeric, 1) as avg_days
                FROM tasks 
                WHERE user_id = %s 
                GROUP BY status
                ORDER BY count DESC
            """, (user_id,))
            
            stats = cur.fetchall()
            
            if not stats:
                return f"No tasks found for user {user_id}."
            
            insights = [f"Task Insights for {user_id}:"]
            for row in stats:
                status, count, avg_days = row
                avg_days_str = f"{avg_days} days" if avg_days is not None else "N/A"
                insights.append(f"- {status.title()}: {count} task(s), Avg days to due: {avg_days_str}")
            
            return "\n".join(insights)
            
        except psycopg2.Error as e:
            logger.error(f"Error fetching task insights: {e}")
            return f"Failed to fetch insights: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error in get_task_insights: {e}")
            return f"Failed to fetch insights: {str(e)}"
        finally:
            if cur:
                cur.close()
            if conn:
                release_db_connection(conn)

    def add_reminder(self, user_id, task_description, due_date_str=None):
        """Add reminder with improved error handling and validation"""
        conn = None
        cur = None
        try:
            # Validate inputs
            if not task_description or not task_description.strip():
                return "Task description cannot be empty."
            
            # Parse due date
            if due_date_str:
                due = dateparser.parse(due_date_str)
                if due is None:
                    return f"Invalid due date format: '{due_date_str}'. Use natural language like 'tomorrow', '2 days', 'next Monday'."
                due = due.replace(tzinfo=None)
            else:
                due = datetime.now() + timedelta(days=1)
            
            # Get user preferences
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT reminder_preference FROM user_profiles WHERE user_id = %s", (user_id,))
            row = cur.fetchone()
            preference = row[0] if row else "tasks"
            
            # Insert task
            cur.execute(
                "INSERT INTO tasks (user_id, task_description, due_date) VALUES (%s, %s, %s)",
                (user_id, task_description.strip(), due)
            )
            conn.commit()
            
            # Get all pending tasks for sheets update
            cur.execute(
                "SELECT task_description, due_date, status, priority FROM tasks WHERE user_id = %s AND status = 'pending'",
                (user_id,)
            )
            tasks = [
                {
                    'description': row[0],
                    'due_date': row[1].strftime('%Y-%m-%d'),
                    'status': row[2],
                    'priority': row[3]
                } for row in cur.fetchall()
            ]
            
            sheets_result = self.update_sheets(user_id, json.dumps(tasks))
            
            # Add to Google Tasks if preference is set
            result_message = f"Reminder added: '{task_description}' due on {due.strftime('%Y-%m-%d')}.\n{sheets_result}"
            
            if preference == "tasks":
                tasks_service = get_tasks_service()
                if tasks_service:
                    try:
                        tasklist_result = tasks_service.tasklists().list().execute()
                        tasklists = tasklist_result.get('items', [])
                        if tasklists:
                            tasklist_id = tasklists[0]['id']
                            task = {
                                'title': task_description.strip(),
                                'due': due.isoformat() + 'Z'
                            }
                            tasks_service.tasks().insert(tasklist=tasklist_id, body=task).execute()
                            result_message = f"Reminder added to Google Tasks and local database.\n{sheets_result}"
                    except HttpError as he:
                        logger.error(f"Google Tasks API error: {he}")
                        result_message += f"\nNote: Could not add to Google Tasks: {str(he)}"
            
            return result_message
            
        except psycopg2.Error as e:
            logger.error(f"Database error adding reminder: {e}")
            if conn:
                conn.rollback()
            return f"Failed to add reminder: {str(e)}"
        except Exception as e:
            logger.error(f"Error adding reminder: {e}")
            return f"Failed to add reminder: {str(e)}"
        finally:
            if cur:
                cur.close()
            if conn:
                release_db_connection(conn)

    def update_sheets(self, user_id, tasks_json):
        """Update Google Sheets with improved error handling"""
        sheets_service = get_sheets_service()
        if not sheets_service:
            logger.warning("Sheets service unavailable")
            return "Sheets service unavailable. Check service account configuration."
        
        try:
            tasks_list = json.loads(tasks_json)
            spreadsheet_id = os.getenv("SHEET_ID")
            
            if not spreadsheet_id:
                return "SHEET_ID not configured in .env"
            
            if not tasks_list:
                return "No tasks to update in spreadsheet."
            
            # Prepare data with headers
            values = [['Description', 'Due Date', 'Status', 'Priority']]
            values.extend([
                [t['description'], t['due_date'], t['status'], t['priority']] 
                for t in tasks_list
            ])
            
            body = {'values': values}
            
            sheets_service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range="Sheet1!A1:D",
                valueInputOption="RAW",
                body=body
            ).execute()
            
            logger.info(f"Updated {len(tasks_list)} tasks in spreadsheet")
            return f"Spreadsheet updated successfully with {len(tasks_list)} task(s)."
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in tasks_json: {e}")
            return f"Failed to parse tasks data: {str(e)}"
        except HttpError as e:
            logger.error(f"Google Sheets API error: {e}")
            return f"Failed to update Sheets: {str(e)}. Verify SHEET_ID and permissions."
        except Exception as e:
            logger.error(f"Error updating Sheets: {e}")
            return f"Failed to update Sheets: {str(e)}"

    def retrieve_sheets_data(self, user_id):
        """Retrieve data from Google Sheets with improved error handling"""
        sheets_service = get_sheets_service()
        if not sheets_service:
            logger.warning("Sheets service unavailable")
            return "Sheets service unavailable. Check service account configuration."
        
        try:
            spreadsheet_id = os.getenv("SHEET_ID")
            if not spreadsheet_id:
                return "SHEET_ID not configured in .env"
            
            result = sheets_service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range="Sheet1!A1:D"
            ).execute()
            
            values = result.get('values', [])
            
            if not values:
                return "No tasks found in the spreadsheet."
            
            # Skip header row if present
            data_rows = values[1:] if values[0] == ['Description', 'Due Date', 'Status', 'Priority'] else values
            
            if not data_rows:
                return "No tasks found in the spreadsheet (only headers present)."
            
            formatted_tasks = []
            for row in data_rows:
                if len(row) >= 4:
                    formatted_tasks.append(
                        f"- Task: {row[0]}, Due: {row[1]}, Status: {row[2]}, Priority: {row[3]}"
                    )
                elif len(row) >= 1:
                    # Handle incomplete rows
                    formatted_tasks.append(f"- Task: {row[0]} (incomplete data)")
            
            return "Tasks in spreadsheet:\n" + "\n".join(formatted_tasks)
            
        except HttpError as e:
            logger.error(f"Google Sheets API error: {e}")
            return f"Failed to retrieve Sheets data: {str(e)}. Verify SHEET_ID and permissions."
        except Exception as e:
            logger.error(f"Error retrieving Sheets data: {e}")
            return f"Failed to retrieve Sheets data: {str(e)}"

    def schedule_meeting(self, attendee_email, time_str, date_str=None, description="Meeting"):
        """Schedule meeting with improved error handling and validation"""
        calendar_service = get_calendar_service()
        if not calendar_service:
            logger.warning("Calendar service unavailable")
            return "Calendar service unavailable. Check service account configuration."
        
        try:
            # Validate email format
            if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', attendee_email):
                return f"Invalid email address: {attendee_email}"
            
            now = datetime.now()
            
            # Parse date
            if date_str:
                # Remove ordinal suffixes
                date_str_clean = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', date_str.lower())
                meeting_date = dateparser.parse(date_str_clean)
                if meeting_date is None:
                    return f"Invalid date format: '{date_str}'. Use format like '6 oct', 'tomorrow', or 'next Monday'."
            else:
                meeting_date = now
            
            # Parse time
            time_parsed = dateparser.parse(time_str)
            if time_parsed is None:
                return f"Invalid time format: '{time_str}'. Use format like '5:00 PM' or '17:00'."
            
            time = time_parsed.time()
            start_time = datetime.combine(meeting_date.date(), time)
            
            # Check if meeting is in the past
            if start_time < now:
                return f"Cannot schedule meeting in the past. Specified time: {start_time.strftime('%Y-%m-%d %H:%M')}"
            
            end_time = start_time + timedelta(hours=1)
            
            event = {
                'summary': description,
                'start': {
                    'dateTime': start_time.isoformat(),
                    'timeZone': 'Asia/Kolkata'
                },
                'end': {
                    'dateTime': end_time.isoformat(),
                    'timeZone': 'Asia/Kolkata'
                },
                'attendees': [{'email': attendee_email}],
            }
            
            created_event = calendar_service.events().insert(
                calendarId='primary',
                body=event
            ).execute()
            
            logger.info(f"Meeting scheduled: {created_event.get('htmlLink')}")
            return f"Meeting '{description}' scheduled with {attendee_email} on {start_time.strftime('%Y-%m-%d at %I:%M %p')}."
            
        except ValueError as ve:
            logger.error(f"Date/Time parsing error: {ve}")
            return f"Failed to parse date/time: {str(ve)}"
        except HttpError as e:
            logger.error(f"Google Calendar API error: {e}")
            return f"Failed to schedule meeting: {str(e)}. Verify calendar permissions."
        except Exception as e:
            logger.error(f"Error scheduling meeting: {e}")
            return f"Failed to schedule meeting: {str(e)}"

    def send_daily_summary(self):
        """Send daily summary with improved efficiency"""
        conn = None
        cur = None
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT user_id FROM user_profiles")
            users = cur.fetchall()
            
            if not users:
                logger.warning("No users found in user_profiles")
                return "No users configured for daily summary."
            
            for user_tuple in users:
                user_id = user_tuple[0]
                
                try:
                    # Get email summary
                    email_summary = self.check_important_emails(user_id, limit=5)
                    
                    # Get pending tasks
                    cur.execute(
                        "SELECT task_description, due_date, status, priority FROM tasks WHERE user_id = %s AND status = 'pending' ORDER BY due_date",
                        (user_id,)
                    )
                    task_rows = cur.fetchall()
                    
                    tasks = [
                        {
                            'description': row[0],
                            'due_date': row[1].strftime('%Y-%m-%d') if row[1] else 'No due date',
                            'status': row[2],
                            'priority': row[3]
                        } for row in task_rows
                    ]
                    
                    task_summary = "\n".join([
                        f"- {t['description']} (Due: {t['due_date']}, Priority: {t['priority']})"
                        for t in tasks
                    ]) if tasks else "No pending tasks."
                    
                    # Create summary
                    summary = f"""Daily Summary (6 AM):

Important Emails:
{email_summary}

Pending Tasks:
{task_summary}
"""
                    
                    # Send email
                    self.send_email("Daily Task Summary", summary)
                    
                    # Update sheets
                    if tasks:
                        self.update_sheets(user_id, json.dumps(tasks))
                    
                    logger.info(f"Daily summary sent for user: {user_id}")
                    
                except Exception as e:
                    logger.error(f"Error sending summary for user {user_id}: {e}")
                    continue
            
            return "Daily summary sent successfully to all users."
            
        except psycopg2.Error as e:
            logger.error(f"Database error in send_daily_summary: {e}")
            return f"Failed to send daily summary: {str(e)}"
        except Exception as e:
            logger.error(f"Daily summary error: {e}")
            return f"Failed to send daily summary: {str(e)}"
        finally:
            if cur:
                cur.close()
            if conn:
                release_db_connection(conn)

    def reschedule_summary(self, time_str):
        """Reschedule daily summary with improved validation"""
        try:
            # Parse time string
            try:
                time = datetime.strptime(time_str.strip(), "%I:%M %p").time()
            except ValueError:
                # Try 24-hour format
                try:
                    time = datetime.strptime(time_str.strip(), "%H:%M").time()
                except ValueError:
                    return f"Invalid time format: '{time_str}'. Use format like '6:00 AM' or '18:00'."
            
            # Remove existing jobs and add new one
            self.scheduler.remove_all_jobs()
            self.scheduler.add_job(
                self.send_daily_summary,
                CronTrigger(hour=time.hour, minute=time.minute)
            )
            
            if not self.scheduler.running:
                self.scheduler.start()
            
            logger.info(f"Daily summary rescheduled to {time.strftime('%I:%M %p')}")
            return f"Daily summary rescheduled to {time.strftime('%I:%M %p')}."
            
        except Exception as e:
            logger.error(f"Error rescheduling summary: {e}")
            return f"Failed to reschedule summary: {str(e)}"

    def rag_query(self, query):
        """Perform RAG query with improved error handling"""
        try:
            if not query or not query.strip():
                return "Query cannot be empty."
            
            retriever = get_retriever()
            llm = get_llm()
            
            docs = retriever.invoke(query.strip())
            
            if not docs:
                return "No relevant information found in the knowledge base."
            
            context = "\n".join([d.page_content for d in docs])
            prompt = f"Answer the following question using the provided context. Be concise and accurate.\n\nContext: {context}\n\nQuestion: {query}\n\nAnswer:"
            
            response = llm.invoke(prompt).content
            logger.info(f"RAG query completed for: {query[:50]}...")
            return response
            
        except Exception as e:
            logger.error(f"RAG error: {e}")
            return f"RAG query failed: {str(e)}"

    def route_query(self, query):
        """Route query to appropriate handler with improved reliability"""
        try:
            if not query or not query.strip():
                return "llm"
            
            result = self.router_chain.invoke({"query": query.strip()})
            category = result.content.strip().lower()
            
            allowed_categories = ['email', 'task', 'search', 'database', 'calendar', 'rag', 'llm']
            
            if category not in allowed_categories:
                logger.warning(f"Router returned invalid category: {category}, defaulting to llm")
                category = 'llm'
            
            logger.info(f"Query routed to: {category}")
            return category
            
        except Exception as e:
            logger.error(f"Router error: {e}")
            return "llm"  # Default fallback

    def structure_response(self, query, raw_response):
        """Structure response with improved error handling"""
        try:
            if not raw_response:
                return "No response generated."
            
            result = self.structure_chain.invoke({
                "query": query,
                "raw_response": raw_response
            })
            return result.content
            
        except Exception as e:
            logger.error(f"Structure response error: {e}")
            # Fallback to raw response if structuring fails
            return raw_response

    @lru_cache(maxsize=1)
    def about_me(self):
        """Return information about the user (cached for performance)"""
        about_text = """
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
- 2022 – Present
- CGPA: 8.63/10

Skills:
- Technical Skills: Java, SQL, ReactJs, Python, HTML, CSS (Tailwind), JavaScript
- Tools & Technologies: Git, GitHub, Colab

Internships:
- Technical Associate - 4Sight AI (AI4AndhraPolice Hackathon)
- May 2025 – Jun 2025
- Built 2 web-based admin panels for invitations and certificates, cutting manual work by 80%.
- Enabled bulk invitations via Excel with QR tracking, managing 400+ dignitaries including IPS officers.
- Contributed to 2+ real-time AI use cases during a hackathon, supporting law enforcement solutions.

Projects:
- Credit Card Fraud Detection
  - Engineered a fraud detection model using Isolation Forest and XGBoost on 284,000+ transactions.
  - Collaborated with team to address data imbalance, reducing false positives by 10% improving reliability.
  - Streamlined preprocessing with feature scaling and outlier elimination, improving model precision by 15%.
  - Evaluated model performance with precision, recall, and F1-score metrics, achieving 99.9% detection accuracy.

- Personal Chat Assistant
  - Built a personal chat assistant using Python and Gemini API capable of handling general queries and interacting naturally with users.
  - Integrated advanced features such as answering from PDFs, sending emails, displaying top mails, maintaining a task spreadsheet, and setting reminders.
  - Designed to improve productivity by automating repetitive tasks and exploring the practical applications of conversational AI in daily use.

- Document Chatbot
  - Developed a document-based chatbot using LlamaIndex and LangChain for accurate query answering.
  - Applied the system on academic materials and project documents, enabling efficient retrieval of relevant information from uploaded files.
  - Gained practical exposure to retrieval-augmented generation (RAG) methods, highlighting how AI can support students and researchers in academic tasks.

Certifications:
- Java Object-Oriented Programming from LinkedIn Learning
- React Js from Infosys Springboard
- NPTEL Programming In Java
- The Complete MySQL Bootcamp from Udemy
- NPTEL Introduction to IoT 4.0
- Machine Learning from Kaggle

GitHub Profile Overview:
- Popular repositories: Abhiram (Python), Portfolio (CSS), Abhiram-Gaddam, kota (forked, HTML), gitWorkshop (forked), git-workshop (forked, HTML)
- Connect with me on LinkedIn: https://www.linkedin.com/in/abhiramgaddam/
- Languages and Tools: bash, css3, figma, git, html5, javascript, mongodb, mysql, nodejs, pandas, python, react, scikit_learn, tailwind
        """
        return about_text

    def ask(self, query, user_id="abhiram"):
        """Main query handler with improved efficiency and error handling"""
        # Input validation
        if not query or not isinstance(query, str):
            raise ValueError("Query must be a non-empty string")
        if not user_id or not isinstance(user_id, str):
            raise ValueError("User ID must be a non-empty string")

        query = query.strip()
        query_lower = query.lower()
        raw_response = None
        conn = None
        cur = None
        
        try:
            # Handle "about me" queries with RAG
            if any(keyword in query_lower for keyword in ["about me", "tell me about yourself", "who are you", "your details", "resume"]):
                raw_response = self.rag_query(query)
                # Log to chat history
                try:
                    conn = get_db_connection()
                    cur = conn.cursor()
                    cur.execute(
                        "INSERT INTO chat_history (user_id, query, context, response) VALUES (%s, %s, %s, %s)",
                        (user_id, query, "Retrieved context", raw_response)
                    )
                    conn.commit()
                except psycopg2.Error as e:
                    logger.error(f"Database error logging chat: {e}")
                finally:
                    if cur:
                        cur.close()
                    if conn:
                        release_db_connection(conn)
                        conn = None
                        cur = None
            else:
                # Route query to appropriate handler
                query_type = self.route_query(query)
                logger.info(f"Query routed to: {query_type}")

                if query_type == "email":
                    if "send" in query_lower or "mail to" in query_lower:
                        # Parse email components
                        parts = query.lower().split("subject:")
                        subject = parts[1].split("body:")[0].strip() if len(parts) > 1 else "Assistant Email"
                        body = query.split("body:")[1].strip() if "body:" in query else query.replace("send email", "").replace("send mail", "").strip()
                        
                        # Extract recipient
                        recipient = os.getenv("GMAIL_RECIPIENT")
                        if "to" in body.lower():
                            recipient_match = re.search(r'to ([\w\.-]+@[\w\.-]+)', body.lower())
                            if recipient_match:
                                recipient = recipient_match.group(1)
                                body = body.replace("to " + recipient, "").strip()
                        
                        raw_response = self.send_email(subject, body, recipient)
                    else:
                        raw_response = self.check_important_emails(user_id)
                
                elif query_type == "task":
                    if "insights" in query_lower:
                        raw_response = self.get_task_insights(user_id)
                    elif "add" in query_lower or "reminder" in query_lower or "update sheets" in query_lower:
                        # Extract task description and due date
                        task_desc_match = re.sub(
                            r"(add task|add|reminder|to sheets|update sheets with|that i need to)", 
                            "", 
                            query, 
                            flags=re.IGNORECASE
                        ).strip()
                        
                        due_match = re.search(r"due\s+(on\s+)?([\w\s\d-]+)", query_lower)
                        due_date_str = due_match.group(2).strip() if due_match else None
                        
                        raw_response = self.add_reminder(user_id, task_desc_match, due_date_str)
                    elif "sheets" in query_lower or "retrieve" in query_lower or "list" in query_lower or "pending" in query_lower or "tasks in" in query_lower:
                        raw_response = self.retrieve_sheets_data(user_id)
                    elif "daily summary" in query_lower:
                        raw_response = self.send_daily_summary()
                    else:
                        raw_response = self.get_task_insights(user_id)
                
                elif query_type == "search":
                    search_query = re.sub(
                        r"(google search|search for|search|seatch)", 
                        "", 
                        query, 
                        flags=re.IGNORECASE
                    ).strip()
                    raw_response = self.perform_google_search(search_query)
                
                elif query_type == "database":
                    raw_response = self.query_database(query, user_id)
                
                elif query_type == "calendar":
                    time_match = re.search(r"\d{1,2}(:\d{2})?\s*(am|pm|AM|PM)", query, re.IGNORECASE)
                    date_match = re.search(r"on (\d{1,2}(?:th|st|nd|rd)? \w+)", query, re.IGNORECASE)
                    date_str = date_match.group(1) if date_match else None
                    
                    if "reschedule" in query_lower or "schedule the time" in query_lower:
                        if time_match:
                            raw_response = self.reschedule_summary(time_match.group(0).upper())
                        else:
                            raw_response = "Please specify a valid time (e.g., '6:00 AM')."
                    elif "meeting" in query_lower:
                        email_match = re.search(r"with .*?([\w\.-]+@[\w\.-]+)", query_lower)
                        description = re.sub(
                            r"schedule\s+meeting\s+for\s+me\s+with\s+.*?\s+at\s+\d{1,2}(:\d{2})?\s*(am|pm|AM|PM)\s*(on\s+\d{1,2}(?:th|st|nd|rd)? \w+)?", 
                            "", 
                            query, 
                            flags=re.IGNORECASE
                        ).strip()
                        
                        if email_match and time_match:
                            raw_response = self.schedule_meeting(
                                email_match.group(1), 
                                time_match.group(0).upper(), 
                                date_str, 
                                description or "Meeting"
                            )
                        else:
                            raw_response = "Please specify attendee email and time (e.g., 'schedule meeting for me with ram@example.com at 5:00 PM on 6 oct')."
                    else:
                        raw_response = "Please specify if scheduling a meeting or rescheduling summary."
                
                elif query_type == "rag":
                    raw_response = self.rag_query(query)
                    # Log to chat history
                    try:
                        conn = get_db_connection()
                        cur = conn.cursor()
                        cur.execute(
                            "INSERT INTO chat_history (user_id, query, context, response) VALUES (%s, %s, %s, %s)",
                            (user_id, query, "Retrieved context", raw_response)
                        )
                        conn.commit()
                    except psycopg2.Error as e:
                        logger.error(f"Database error logging RAG chat: {e}")
                    finally:
                        if cur:
                            cur.close()
                        if conn:
                            release_db_connection(conn)
                            conn = None
                            cur = None
                
                else:  # llm fallback
                    llm = get_llm()
                    raw_response = llm.invoke(query).content
                    # Log to general chat history
                    try:
                        conn = get_db_connection()
                        cur = conn.cursor()
                        cur.execute(
                            "INSERT INTO general_chat_history (user_id, query, response) VALUES (%s, %s, %s)",
                            (user_id, query, raw_response)
                        )
                        conn.commit()
                    except psycopg2.Error as e:
                        logger.error(f"Database error logging general chat: {e}")
                    finally:
                        if cur:
                            cur.close()
                        if conn:
                            release_db_connection(conn)
                            conn = None
                            cur = None

            # Structure and return response
            return self.structure_response(query, raw_response)
            
        except Exception as e:
            logger.error(f"Error in ask method: {e}")
            return f"Sorry, an error occurred: {str(e)}"
        finally:
            # Ensure resources are cleaned up
            if cur:
                try:
                    cur.close()
                except:
                    pass
            if conn:
                try:
                    release_db_connection(conn)
                except:
                    pass

# Main loop
def main():
    """Main entry point for the Personal Assistant"""
    print("=" * 60)
    print("Personal Assistant Started")
    print("=" * 60)
    print("\nAvailable Commands:")
    print("- Email: 'What are my top emails', 'Send mail to user@example.com saying hello'")
    print("- Tasks: 'Add task Buy milk due tomorrow', 'Task insights', 'List pending tasks'")
    print("- Search: 'Google search Python tutorials'")
    print("- Database: 'select * from tasks', 'What tables are in my database'")
    print("- Calendar: 'Schedule meeting with user@example.com at 5:00 PM', 'Schedule time for 6:00 AM'")
    print("- General: 'Tell me about yourself', 'What is task management?'")
    print("\nType 'exit' or 'quit' to quit.\n")
    
    try:
        assistant = PersonalAssistant()
        logger.info("Personal Assistant initialized successfully")
    except Exception as e:
        print(f"Failed to initialize Personal Assistant: {e}")
        print("Please check your configuration and try again.")
        return
    
    while True:
        try:
            query = input("\nYour query: ").strip()
            
            if not query:
                continue
            
            if query.lower() in ['exit', 'quit', 'q']:
                print("Exiting Personal Assistant. Goodbye!")
                break
            
            try:
                response = assistant.ask(query)
                print(f"\nResponse:\n{response}")
            except Exception as e:
                logger.error(f"Error processing query: {e}")
                print(f"Error: {str(e)}")
        
        except KeyboardInterrupt:
            print("\n\nInterrupted. Exiting Personal Assistant.")
            break
        except EOFError:
            print("\nExiting Personal Assistant.")
            break
        except Exception as e:
            logger.error(f"Unexpected error in main loop: {e}")
            print(f"Unexpected error: {str(e)}")

if __name__ == "__main__":
    main()
