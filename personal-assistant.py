import os
import logging
import psycopg2
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2 import service_account
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
from pathlib import Path

# Import custom modules
try:
    from config import Config
    from database import get_db_connection, init_db
    from utils import (
        validate_email, validate_user_id, validate_query,
        parse_time_string, retry_on_failure, extract_email_from_text,
        extract_time_from_text, extract_date_from_text, format_task_list,
        format_email_list, clean_markdown, RateLimiter
    )
except ImportError:
    # Fallback for environments without the new modules
    from dotenv import load_dotenv
    load_dotenv()
    
    class Config:
        BASE_DIR = Path(__file__).parent.absolute()
        DATA_DIR = BASE_DIR / "data"
        SERVICE_ACCOUNT_FILE = os.getenv("SERVICE_ACCOUNT_FILE", "/content/personal-assistance-474105-f1aecdeaab1c.json")
        SAMPLE_DOCS_FILE = "/content/sample.txt"
        VECTORSTORE_PATH = str(DATA_DIR / "vectorstore")
        GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
        GOOGLE_CX = os.getenv("GOOGLE_CX")
        SHEET_ID = os.getenv("SHEET_ID")
        SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/tasks', 'https://www.googleapis.com/auth/calendar']
        GMAIL_USERNAME = os.getenv("GMAIL_USERNAME")
        GMAIL_PASSWORD = os.getenv("GMAIL_PASSWORD")
        GMAIL_RECIPIENT = os.getenv("GMAIL_RECIPIENT")
        IMAP_SERVER = "imap.gmail.com"
        SMTP_SERVER = "smtp.gmail.com"
        SMTP_PORT = 587
        DB_CONFIG = {
            "host": "aws-0-ap-southeast-1.pooler.supabase.com",
            "port": 6543,
            "dbname": "postgres",
            "user": "postgres.ixruzjparquranqfdvdm",
            "password": os.getenv("DB_PASSWORD", "aasp3885@gmail"),
            "sslmode": "require"
        }
        LLM_MODEL = "models/gemini-2.0-flash-exp"
        LLM_TEMPERATURE = 0.1
        EMBEDDINGS_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
        DAILY_SUMMARY_TIME = "06:00"
        LOG_LEVEL = "INFO"
        MAX_EMAILS_TO_FETCH = 5
        EMAIL_CACHE_TIMEOUT = 300
        TIMEZONE = "Asia/Kolkata"
    
    from contextlib import contextmanager
    
    @contextmanager
    def get_db_connection():
        conn = psycopg2.connect(**Config.DB_CONFIG)
        try:
            yield conn
        finally:
            conn.close()
    
    def init_db():
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS chat_history (
                    id SERIAL PRIMARY KEY,
                    user_id TEXT,
                    query TEXT,
                    context TEXT,
                    response TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS general_chat_history (
                    id SERIAL PRIMARY KEY,
                    user_id TEXT,
                    query TEXT,
                    response TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS tasks (
                    id SERIAL PRIMARY KEY,
                    user_id TEXT,
                    task_description TEXT,
                    due_date TIMESTAMP,
                    status TEXT DEFAULT 'pending',
                    priority TEXT DEFAULT 'medium'
                );
                CREATE TABLE IF NOT EXISTS user_profiles (
                    user_id TEXT PRIMARY KEY,
                    email_filters TEXT DEFAULT 'ALL',
                    reminder_preference TEXT DEFAULT 'tasks'
                );
            """)
            cur.execute("INSERT INTO user_profiles (user_id) VALUES (%s) ON CONFLICT DO NOTHING", ("abhiram",))
            conn.commit()
            cur.close()
    
    def validate_email(email):
        return re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email) is not None
    
    def validate_user_id(user_id):
        if not user_id or not isinstance(user_id, str):
            raise ValueError("User ID must be a non-empty string")
        return user_id
    
    def validate_query(query):
        if not query or not isinstance(query, str):
            raise ValueError("Query must be a non-empty string")
        return query.strip()
    
    def retry_on_failure(max_retries=3, delay=1, backoff=2):
        def decorator(func):
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            return wrapper
        return decorator
    
    def extract_email_from_text(text):
        match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
        return match.group(0) if match else None
    
    def extract_time_from_text(text):
        match = re.search(r'\d{1,2}(:\d{2})?\s*(am|pm|AM|PM)', text, re.IGNORECASE)
        return match.group(0).upper() if match else None
    
    def extract_date_from_text(text):
        match = re.search(r'on (\d{1,2}(?:th|st|nd|rd)? \w+)', text, re.IGNORECASE)
        return match.group(1) if match else None
    
    def format_task_list(tasks):
        if not tasks:
            return "No tasks found."
        return "\n".join([f"{i+1}. {t.get('description', 'N/A')} - Due: {t.get('due_date', 'N/A')}" for i, t in enumerate(tasks)])
    
    def format_email_list(emails):
        if not emails:
            return "No emails found."
        return "\n".join([f"{i+1}. {e}" for i, e in enumerate(emails)])
    
    def clean_markdown(text):
        return text
    
    class RateLimiter:
        def __init__(self, max_calls, time_window):
            self.max_calls = max_calls
            self.time_window = time_window
        def is_allowed(self):
            return True

# Apply nest_asyncio for Colab
nest_asyncio.apply()

# Set up logging
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Google services initialization
sheets_service = None
tasks_service = None
calendar_service = None

def initialize_google_services():
    """Initialize Google services with retry logic"""
    global sheets_service, tasks_service, calendar_service
    
    if not os.path.exists(Config.SERVICE_ACCOUNT_FILE):
        logger.warning(f"Service account file not found: {Config.SERVICE_ACCOUNT_FILE}")
        return
    
    try:
        credentials = service_account.Credentials.from_service_account_file(
            Config.SERVICE_ACCOUNT_FILE, 
            scopes=Config.SCOPES
        )
        sheets_service = build('sheets', 'v4', credentials=credentials)
        tasks_service = build('tasks', 'v1', credentials=credentials)
        calendar_service = build('calendar', 'v3', credentials=credentials)
        logger.info("Google services initialized successfully")
    except Exception as e:
        logger.error(f"Google services error: {e}")
        sheets_service = tasks_service = calendar_service = None

# Try to initialize Google services
initialize_google_services()

# Initialize database
init_db()

# RAG setup with FAISS - Optimized with caching
def initialize_vectorstore():
    """Initialize or load cached vectorstore"""
    global vectorstore, retriever
    
    # Prepare sample documents
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
    
    # Check if vectorstore cache exists
    vectorstore_path = Config.VECTORSTORE_PATH
    if os.path.exists(vectorstore_path):
        try:
            logger.info("Loading cached vectorstore...")
            embeddings = HuggingFaceEmbeddings(model_name=Config.EMBEDDINGS_MODEL)
            vectorstore = FAISS.load_local(vectorstore_path, embeddings, allow_dangerous_deserialization=True)
            retriever = vectorstore.as_retriever()
            logger.info("Vectorstore loaded from cache")
            return
        except Exception as e:
            logger.warning(f"Failed to load cached vectorstore: {e}. Creating new one...")
    
    # Create new vectorstore
    try:
        logger.info("Creating new vectorstore...")
        # Ensure data directory exists
        Config.DATA_DIR.mkdir(exist_ok=True)
        
        # Write sample docs to file
        with open(Config.SAMPLE_DOCS_FILE, 'w') as f:
            f.write("\n".join(sample_docs))
        
        embeddings = HuggingFaceEmbeddings(model_name=Config.EMBEDDINGS_MODEL)
        docs = TextLoader(Config.SAMPLE_DOCS_FILE).load()
        vectorstore = FAISS.from_documents(docs, embeddings)
        retriever = vectorstore.as_retriever()
        
        # Cache the vectorstore
        vectorstore.save_local(vectorstore_path)
        logger.info("Vectorstore created and cached successfully")
    except Exception as e:
        logger.error(f"Failed to initialize vectorstore: {e}")
        raise

# Initialize vectorstore (will use cache if available)
vectorstore = None
retriever = None
initialize_vectorstore()

# LLM setup with validation
def initialize_llm():
    """Initialize LLM with proper error handling"""
    try:
        if not Config.GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY not configured")
        
        llm = ChatGoogleGenerativeAI(
            model=Config.LLM_MODEL,
            google_api_key=Config.GOOGLE_API_KEY,
            temperature=Config.LLM_TEMPERATURE
        )
        
        # Test connection
        response = llm.invoke("Test connection")
        logger.info(f"Gemini connected successfully: {response.content[:50]}...")
        return llm
    except Exception as e:
        logger.error(f"Gemini initialization failed: {e}")
        raise RuntimeError(f"Cannot connect to Gemini: {e}. Check API key and quota at https://aistudio.google.com/app/apikey")

llm = initialize_llm()

# Router prompt
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

# Structure response prompt
structure_prompt = PromptTemplate(
    input_variables=["query", "raw_response"],
    template="""You are a helpful personal assistant. The user asked: {query}

The raw result from the system is: {raw_response}

Structure this into a clear, concise, and user-friendly response. Use markdown formatting where appropriate, such as headings, bullet points, numbered lists, or bold text for emphasis. If the raw response indicates success, confirm the action and provide details. If it's an error, explain it politely and suggest possible fixes. Ensure the response directly addresses the user's query and is easy to read.

More Importantly make sure you close all the markdown formatting properly and consistantly .


"""
)

class PersonalAssistant:
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.router_chain = router_prompt | llm
        self.structure_chain = structure_prompt | llm
        self.email_cache = {}
        self.email_rate_limiter = RateLimiter(max_calls=10, time_window=60)  # 10 calls per minute
        self.search_rate_limiter = RateLimiter(max_calls=100, time_window=86400)  # 100 calls per day
        
        # Schedule daily summary at configured time
        self._schedule_daily_summary()
        self.scheduler.start()
        logger.info("Personal Assistant initialized successfully")
    
    def _schedule_daily_summary(self):
        """Schedule daily summary at configured time"""
        try:
            hour, minute = map(int, Config.DAILY_SUMMARY_TIME.split(':'))
            self.scheduler.add_job(
                self.send_daily_summary,
                CronTrigger(hour=hour, minute=minute),
                id='daily_summary'
            )
            logger.info(f"Daily summary scheduled at {Config.DAILY_SUMMARY_TIME}")
        except Exception as e:
            logger.error(f"Failed to schedule daily summary: {e}")

    @retry_on_failure(max_retries=2, delay=1)
    def check_important_emails(self, user_id):
        """Check important emails with caching and rate limiting"""
        try:
            # Check cache first
            cache_key = f"emails_{user_id}"
            if cache_key in self.email_cache:
                cached_time, cached_data = self.email_cache[cache_key]
                if (datetime.now() - cached_time).total_seconds() < Config.EMAIL_CACHE_TIMEOUT:
                    logger.info("Returning cached email data")
                    return cached_data
            
            # Rate limiting
            if not self.email_rate_limiter.is_allowed():
                wait_time = self.email_rate_limiter.wait_time()
                return f"Rate limit exceeded. Please wait {int(wait_time)} seconds before checking emails again."
            
            with get_db_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT email_filters FROM user_profiles WHERE user_id = %s", (user_id,))
                row = cur.fetchone()
                filters = row[0] if row else 'ALL'
                cur.close()
            
            mail = imaplib.IMAP4_SSL(Config.IMAP_SERVER)
            mail.login(Config.GMAIL_USERNAME, Config.GMAIL_PASSWORD)
            mail.select("inbox")
            
            status, messages = mail.search(None, filters)
            if status != 'OK':
                logger.warning(f"IMAP search failed with filter '{filters}'. Falling back to ALL.")
                status, messages = mail.search(None, 'ALL')
                if status != 'OK':
                    raise Exception(f"IMAP fallback search failed: {messages}")
            
            email_ids = messages[0].split()
            summaries = []
            
            # Fetch only the last N emails
            for email_id in email_ids[-Config.MAX_EMAILS_TO_FETCH:]:
                try:
                    status, msg_data = mail.fetch(email_id, "(RFC822)")
                    if status != 'OK':
                        continue
                    msg = msg_data[0][1].decode("utf-8", errors="ignore")
                    subject = next((line.split(": ", 1)[1] for line in msg.split("\n") if line.startswith("Subject:")), "No Subject")
                    summaries.append(f"Subject: {subject}")
                except Exception as e:
                    logger.warning(f"Failed to fetch email {email_id}: {e}")
                    continue
            
            mail.logout()
            
            result = format_email_list(summaries) if summaries else "No emails found."
            
            # Cache the result
            self.email_cache[cache_key] = (datetime.now(), result)
            
            return result
        except Exception as e:
            logger.error(f"Error checking emails: {e}")
            return f"Failed to check emails: {str(e)}. Ensure IMAP is enabled and App Password is valid: https://mail.google.com/mail/u/0/#settings/fwdandpop"

    @retry_on_failure(max_retries=2, delay=1)
    def send_email(self, subject, body, recipient=None):
        """Send email with retry logic"""
        try:
            # Validate recipient email
            recipient = recipient or Config.GMAIL_RECIPIENT
            if not validate_email(recipient):
                return f"Invalid recipient email address: {recipient}"
            
            msg = MIMEMultipart()
            msg['From'] = Config.GMAIL_USERNAME
            msg['To'] = recipient
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))
            
            with smtplib.SMTP(Config.SMTP_SERVER, Config.SMTP_PORT) as server:
                server.starttls()
                server.login(Config.GMAIL_USERNAME, Config.GMAIL_PASSWORD)
                server.sendmail(msg['From'], msg['To'], msg.as_string())
            
            logger.info(f"Email sent successfully to {recipient}")
            return f"Email sent to {recipient}."
        except Exception as e:
            logger.error(f"Error sending email: {e}")
            return f"Failed to send email: {str(e)}"

    @retry_on_failure(max_retries=2, delay=1)
    def perform_google_search(self, query):
        """Perform Google search with rate limiting"""
        try:
            # Rate limiting
            if not self.search_rate_limiter.is_allowed():
                wait_time = self.search_rate_limiter.wait_time()
                return f"Search rate limit exceeded. Please wait {int(wait_time/3600)} hours before searching again."
            
            url = "https://www.googleapis.com/customsearch/v1"
            params = {
                "key": Config.GOOGLE_API_KEY,
                "cx": Config.GOOGLE_CX,
                "q": query,
                "num": 5  # Limit results
            }
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            results = response.json().get("items", [])
            
            formatted_results = "\n".join([
                f"{i+1}. **{result['title']}**\n   {result['link']}" 
                for i, result in enumerate(results[:5])
            ])
            
            return formatted_results or "No search results found."
        except requests.exceptions.Timeout:
            logger.error("Search request timed out")
            return "Search request timed out. Please try again."
        except requests.exceptions.RequestException as e:
            logger.error(f"Search error: {e}")
            return f"Failed to perform search: {str(e)}. Verify API key and CX at https://console.developers.google.com"
        except Exception as e:
            logger.error(f"Unexpected search error: {e}")
            return f"Failed to perform search: {str(e)}"

    def query_database(self, query, user_id):
        """Query database with proper error handling"""
        try:
            with get_db_connection() as conn:
                cur = conn.cursor()
                
                # Handle special case for listing tables
                if query.lower().startswith("select * from tables") or "tables in my database" in query.lower():
                    cur.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
                    tables = cur.fetchall()
                    cur.close()
                    return "Tables in database:\n" + "\n".join([f"- {row[0]}" for row in tables]) if tables else "No tables found."
                
                # Execute the query
                cur.execute(query)
                
                if query.strip().lower().startswith("select"):
                    results = cur.fetchall()
                    if not results:
                        cur.close()
                        return "No results found."
                    
                    columns = [desc[0] for desc in cur.description]
                    formatted_results = []
                    for row in results[:50]:  # Limit to 50 results
                        formatted_results.append(str(dict(zip(columns, row))))
                    
                    cur.close()
                    result_text = "\n".join(formatted_results)
                    if len(results) > 50:
                        result_text += f"\n\n... and {len(results) - 50} more results (showing first 50)"
                    return f"Database query results:\n{result_text}"
                else:
                    conn.commit()
                    cur.close()
                    return "Query executed successfully."
        except psycopg2.Error as e:
            logger.error(f"Database query error: {e}")
            return f"Failed to execute query: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected database error: {e}")
            return f"Failed to execute query: {str(e)}"

    def get_task_insights(self, user_id):
        """Get task insights with improved formatting"""
        try:
            with get_db_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    SELECT status, COUNT(*),
                           ROUND(AVG(EXTRACT(EPOCH FROM (due_date - CURRENT_TIMESTAMP))/86400)::numeric, 1)
                    FROM tasks 
                    WHERE user_id = %s 
                    GROUP BY status
                """, (user_id,))
                stats = cur.fetchall()
                cur.close()
                
                if not stats:
                    return "No task insights available. Add some tasks to get started!"
                
                insights = [f"## Task Insights for {user_id}"]
                for row in stats:
                    status, count, avg_days = row
                    insights.append(f"- **{status.title()}**: {count} tasks, Avg days to due: {avg_days if avg_days else 'N/A'}")
                
                return "\n".join(insights)
        except Exception as e:
            logger.error(f"Error fetching insights: {e}")
            return f"Failed to fetch insights: {str(e)}"

    def add_reminder(self, user_id, task_description, due_date_str=None):
        """Add reminder with improved date parsing"""
        try:
            # Validate inputs
            if not task_description or len(task_description.strip()) == 0:
                return "Task description cannot be empty."
            
            # Parse due date
            if due_date_str:
                due = dateparser.parse(due_date_str)
                if due is None:
                    return f"Invalid due date format: '{due_date_str}'. Try formats like 'tomorrow', '2 days', 'Jan 15', etc."
                due = due.replace(tzinfo=None)
            else:
                due = datetime.now() + timedelta(days=1)
            
            with get_db_connection() as conn:
                cur = conn.cursor()
                
                # Get user preference
                cur.execute("SELECT reminder_preference FROM user_profiles WHERE user_id = %s", (user_id,))
                row = cur.fetchone()
                preference = row[0] if row else "tasks"
                
                # Insert task into database
                cur.execute(
                    "INSERT INTO tasks (user_id, task_description, due_date) VALUES (%s, %s, %s)",
                    (user_id, task_description, due)
                )
                conn.commit()
                
                # Fetch pending tasks for sheets update
                cur.execute(
                    "SELECT task_description, due_date, status, priority FROM tasks WHERE user_id = %s AND status = 'pending'",
                    (user_id,)
                )
                tasks = [{
                    'description': row[0],
                    'due_date': row[1].strftime('%Y-%m-%d'),
                    'status': row[2],
                    'priority': row[3]
                } for row in cur.fetchall()]
                
                cur.close()
            
            # Update sheets
            sheets_result = self.update_sheets(user_id, json.dumps(tasks))
            
            # Add to Google Tasks if preference is set
            if preference == "tasks" and tasks_service:
                try:
                    tasklist = tasks_service.tasklists().list().execute().get('items', [])
                    tasklist_id = tasklist[0]['id'] if tasklist else None
                    if tasklist_id:
                        task = {
                            'title': task_description,
                            'due': due.isoformat() + 'Z'
                        }
                        tasks_service.tasks().insert(tasklist=tasklist_id, body=task).execute()
                        logger.info("Task added to Google Tasks")
                        return f"✓ Reminder added to Google Tasks.\n{sheets_result}"
                except HttpError as he:
                    logger.error(f"Google Tasks API error: {he}")
                    return f"Reminder added to database and sheets, but failed to add to Google Tasks: {str(he)}\n{sheets_result}"
            
            # Send email notification
            email_result = self.send_email(
                "Task Reminder",
                f"Reminder: {task_description}\nDue on: {due.strftime('%Y-%m-%d %H:%M')}",
                Config.GMAIL_RECIPIENT
            )
            return f"✓ {email_result}\n{sheets_result}"
            
        except Exception as e:
            logger.error(f"Error adding reminder: {e}")
            return f"Failed to add reminder: {str(e)}"

    def update_sheets(self, user_id, tasks_json):
        """Update Google Sheets with tasks"""
        if not sheets_service:
            logger.warning("Sheets service unavailable")
            return "Sheets service unavailable."
        
        if not Config.SHEET_ID:
            logger.warning("SHEET_ID not configured")
            return "Sheets not configured (SHEET_ID missing)."
        
        try:
            tasks_list = json.loads(tasks_json)
            if not tasks_list:
                return "No tasks to update in spreadsheet."
            
            spreadsheet_id = Config.SHEET_ID
            
            # Prepare data with headers
            values = [['Task Description', 'Due Date', 'Status', 'Priority']]
            values.extend([[t['description'], t['due_date'], t['status'], t['priority']] for t in tasks_list])
            
            body = {'values': values}
            
            sheets_service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range="Sheet1!A1:D",
                valueInputOption="RAW",
                body=body
            ).execute()
            
            logger.info(f"Spreadsheet updated with {len(tasks_list)} tasks")
            return f"✓ Spreadsheet updated with {len(tasks_list)} tasks."
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in tasks: {e}")
            return f"Failed to parse tasks data: {str(e)}"
        except Exception as e:
            logger.error(f"Error updating Sheets: {e}")
            return f"Failed to update Sheets: {str(e)}"

    def retrieve_sheets_data(self, user_id):
        """Retrieve tasks from Google Sheets"""
        if not sheets_service:
            logger.warning("Sheets service unavailable")
            return "Sheets service unavailable."
        
        if not Config.SHEET_ID:
            logger.warning("SHEET_ID not configured")
            return "Sheets not configured (SHEET_ID missing)."
        
        try:
            spreadsheet_id = Config.SHEET_ID
            result = sheets_service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range="Sheet1!A1:D"
            ).execute()
            
            values = result.get('values', [])
            if not values:
                return "No tasks found in the spreadsheet."
            
            # Skip header row if present
            start_idx = 1 if values[0][0].lower() == 'task description' else 0
            task_rows = values[start_idx:]
            
            if not task_rows:
                return "No tasks found in the spreadsheet."
            
            formatted_tasks = []
            for i, row in enumerate(task_rows, 1):
                if len(row) >= 4:
                    formatted_tasks.append(
                        f"{i}. **{row[0]}**\n"
                        f"   - Due: {row[1]}\n"
                        f"   - Status: {row[2]}\n"
                        f"   - Priority: {row[3]}"
                    )
            
            return "## Tasks in spreadsheet:\n\n" + "\n\n".join(formatted_tasks) if formatted_tasks else "No valid tasks found."
        except Exception as e:
            logger.error(f"Error retrieving Sheets data: {e}")
            return f"Failed to retrieve Sheets data: {str(e)}"

    def schedule_meeting(self, attendee_email, time_str, date_str=None, description="Meeting"):
        """Schedule a meeting in Google Calendar"""
        if not calendar_service:
            logger.warning("Calendar service unavailable")
            return "Calendar service unavailable. Ensure service account file is configured."
        
        try:
            # Validate email
            if not validate_email(attendee_email):
                return f"Invalid attendee email address: {attendee_email}"
            
            now = datetime.now()
            
            # Parse date
            if date_str:
                date_str_cleaned = date_str.lower().replace("th", "").replace("st", "").replace("nd", "").replace("rd", "")
                meeting_date = dateparser.parse(date_str_cleaned)
                if meeting_date is None:
                    return f"Invalid date format: '{date_str}'. Try formats like '6 oct', 'tomorrow', 'next monday', etc."
            else:
                meeting_date = now
            
            # Parse time
            time_parsed = dateparser.parse(time_str)
            if time_parsed is None:
                return f"Invalid time format: '{time_str}'. Use format like '5:00 PM', '17:00', etc."
            
            time = time_parsed.time()
            start_time = datetime.combine(meeting_date.date(), time)
            end_time = start_time + timedelta(hours=1)
            
            event = {
                'summary': description,
                'start': {
                    'dateTime': start_time.isoformat(),
                    'timeZone': Config.TIMEZONE
                },
                'end': {
                    'dateTime': end_time.isoformat(),
                    'timeZone': Config.TIMEZONE
                },
                'attendees': [{'email': attendee_email}],
            }
            
            event = calendar_service.events().insert(calendarId='primary', body=event).execute()
            logger.info(f"Meeting scheduled: {event.get('htmlLink')}")
            
            return f"✓ Meeting scheduled with {attendee_email} at {time_str} on {meeting_date.strftime('%Y-%m-%d')}.\nEvent link: {event.get('htmlLink', 'N/A')}"
        except ValueError as ve:
            logger.error(f"Date/Time parsing error: {ve}")
            return f"Failed to parse date/time: {str(ve)}. Use format like 'at 5:00 PM on 6 oct'."
        except HttpError as he:
            logger.error(f"Calendar API error: {he}")
            return f"Failed to schedule meeting: Calendar API error - {str(he)}"
        except Exception as e:
            logger.error(f"Error scheduling meeting: {e}")
            return f"Failed to schedule meeting: {str(e)}"

    def send_daily_summary(self):
        """Send daily summary to all users"""
        try:
            with get_db_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT user_id FROM user_profiles")
                users = cur.fetchall()
                
                for user_tuple in users:
                    user_id = user_tuple[0]
                    
                    try:
                        # Get email summary
                        email_summary = self.check_important_emails(user_id)
                        
                        # Get tasks
                        cur.execute(
                            "SELECT task_description, due_date, status, priority FROM tasks WHERE user_id = %s AND status = 'pending' ORDER BY due_date",
                            (user_id,)
                        )
                        tasks = [{
                            'description': row[0],
                            'due_date': row[1].strftime('%Y-%m-%d'),
                            'status': row[2],
                            'priority': row[3]
                        } for row in cur.fetchall()]
                        
                        task_summary = format_task_list(tasks) if tasks else "No pending tasks."
                        
                        summary = (
                            f"Daily Summary ({datetime.now().strftime('%Y-%m-%d %H:%M')})\n\n"
                            f"## Important Emails:\n{email_summary}\n\n"
                            f"## Pending Tasks:\n{task_summary}"
                        )
                        
                        # Send email
                        self.send_email("Daily Task Summary", summary, Config.GMAIL_RECIPIENT)
                        
                        # Update sheets
                        if tasks:
                            self.update_sheets(user_id, json.dumps(tasks))
                        
                        logger.info(f"Daily summary sent for user: {user_id}")
                    except Exception as e:
                        logger.error(f"Error sending summary for user {user_id}: {e}")
                        continue
                
                cur.close()
            
            return "Daily summary sent successfully."
        except Exception as e:
            logger.error(f"Daily summary error: {e}")
            return f"Failed to send daily summary: {str(e)}"

    def reschedule_summary(self, time_str):
        """Reschedule daily summary time"""
        try:
            # Parse time
            time = datetime.strptime(time_str, "%I:%M %p").time()
            
            # Remove existing job and add new one
            self.scheduler.remove_job('daily_summary')
            self.scheduler.add_job(
                self.send_daily_summary,
                CronTrigger(hour=time.hour, minute=time.minute),
                id='daily_summary'
            )
            
            if not self.scheduler.running:
                self.scheduler.start()
            
            logger.info(f"Daily summary rescheduled to {time_str}")
            return f"✓ Daily summary rescheduled to {time_str}."
        except ValueError:
            return f"Invalid time format: '{time_str}'. Use format like '6:00 AM' or '18:00'."
        except Exception as e:
            logger.error(f"Error rescheduling summary: {e}")
            return f"Failed to reschedule summary: {str(e)}"

    def rag_query(self, query):
        """Query RAG system for information retrieval"""
        try:
            if not retriever:
                return "RAG system not initialized. Please check the configuration."
            
            docs = retriever.invoke(query)
            if not docs:
                return "No relevant information found in the knowledge base."
            
            context = "\n".join([d.page_content for d in docs])
            prompt = f"Answer the following question using the context provided. Be concise and accurate.\n\nQuestion: {query}\n\nContext: {context}\n\nAnswer:"
            response = llm.invoke(prompt).content
            
            logger.info("RAG query processed successfully")
            return response
        except Exception as e:
            logger.error(f"RAG error: {e}")
            return f"RAG query failed: {str(e)}"

    def route_query(self, query):
        """Route query to appropriate handler"""
        try:
            result = self.router_chain.invoke({"query": query})
            category = result.content.strip().lower()
            
            allowed_categories = ['email', 'task', 'search', 'database', 'calendar', 'rag', 'llm']
            if category not in allowed_categories:
                logger.warning(f"Unknown category '{category}', defaulting to 'llm'")
                category = 'llm'
            
            logger.info(f"Query routed to category: {category}")
            return category
        except Exception as e:
            logger.error(f"Router error: {e}")
            return "llm"  # Fallback to general LLM

    def structure_response(self, query, raw_response):
        """Structure raw response into user-friendly format"""
        try:
            result = self.structure_chain.invoke({"query": query, "raw_response": raw_response})
            structured = result.content
            
            # Ensure markdown is properly closed
            structured = clean_markdown(structured)
            
            return structured
        except Exception as e:
            logger.error(f"Structure response error: {e}")
            return raw_response  # Fallback to raw if structuring fails

    def ask(self, query, user_id="abhiram"):
        """Main entry point for processing user queries"""
        try:
            # Validate inputs
            query = validate_query(query)
            user_id = validate_user_id(user_id)
        except ValueError as e:
            return f"Input validation error: {str(e)}"
        
        query_lower = query.lower()
        
        # Special handling for "about me" queries - use RAG directly
        if any(phrase in query_lower for phrase in ["about me", "tell me about yourself", "who are you", "your details", "resume"]):
            raw_response = self.rag_query(query)
            
            # Save to database
            try:
                with get_db_connection() as conn:
                    cur = conn.cursor()
                    cur.execute(
                        "INSERT INTO chat_history (user_id, query, context, response) VALUES (%s, %s, %s, %s)",
                        (user_id, query, "Retrieved context", raw_response)
                    )
                    conn.commit()
                    cur.close()
            except Exception as e:
                logger.error(f"Database error saving chat history: {e}")
            
            return self.structure_response(query, raw_response)
        
        # Route query to appropriate handler
        query_type = self.route_query(query)
        logger.info(f"Processing query type: {query_type}")
        
        # Process based on query type
        try:
            raw_response = self._process_query_by_type(query, query_lower, query_type, user_id)
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            raw_response = f"An error occurred while processing your request: {str(e)}"
        
        return self.structure_response(query, raw_response)
    
    def _process_query_by_type(self, query, query_lower, query_type, user_id):
        """Process query based on its type"""
        if query_type == "email":
            return self._handle_email_query(query, query_lower, user_id)
        
        elif query_type == "task":
            return self._handle_task_query(query, query_lower, user_id)
        
        elif query_type == "search":
            search_query = re.sub(r"(google search|search for|search|seatch)", "", query, flags=re.IGNORECASE).strip()
            return self.perform_google_search(search_query)
        
        elif query_type == "database":
            return self.query_database(query, user_id)
        
        elif query_type == "calendar":
            return self._handle_calendar_query(query, query_lower, user_id)
        
        elif query_type == "rag":
            raw_response = self.rag_query(query)
            # Save to database
            try:
                with get_db_connection() as conn:
                    cur = conn.cursor()
                    cur.execute(
                        "INSERT INTO chat_history (user_id, query, context, response) VALUES (%s, %s, %s, %s)",
                        (user_id, query, "Retrieved context", raw_response)
                    )
                    conn.commit()
                    cur.close()
            except Exception as e:
                logger.error(f"Database error: {e}")
            return raw_response
        
        else:  # llm
            raw_response = llm.invoke(query).content
            # Save to database
            try:
                with get_db_connection() as conn:
                    cur = conn.cursor()
                    cur.execute(
                        "INSERT INTO general_chat_history (user_id, query, response) VALUES (%s, %s, %s)",
                        (user_id, query, raw_response)
                    )
                    conn.commit()
                    cur.close()
            except Exception as e:
                logger.error(f"Database error: {e}")
            return raw_response
    
    def _handle_email_query(self, query, query_lower, user_id):
        """Handle email-related queries"""
        if "send" in query_lower or "mail to" in query_lower:
            parts = query.lower().split("subject:")
            subject = parts[1].split("body:")[0].strip() if len(parts) > 1 else "Assistant Email"
            body = query.split("body:")[1].strip() if "body:" in query else query.replace("send email", "").replace("send mail", "").strip()
            
            recipient = Config.GMAIL_RECIPIENT
            # Extract recipient if specified
            recipient_match = extract_email_from_text(body.lower())
            if recipient_match:
                recipient = recipient_match
                body = body.replace("to " + recipient, "").strip()
            
            return self.send_email(subject, body, recipient)
        else:
            return self.check_important_emails(user_id)
    
    def _handle_task_query(self, query, query_lower, user_id):
        """Handle task-related queries"""
        if "insights" in query_lower:
            return self.get_task_insights(user_id)
        
        elif "add" in query_lower or "reminder" in query_lower or "update sheets" in query_lower:
            task_desc = re.sub(
                r"(add task|add|reminder|to sheets|update sheets with|that i need to)", 
                "", 
                query, 
                flags=re.IGNORECASE
            ).strip()
            
            due_match = re.search(r"due\s+(on\s+)?([\w\s\d-]+)", query_lower)
            due_date_str = due_match.group(2).strip() if due_match else None
            
            # Remove due date from task description
            if due_date_str:
                task_desc = re.sub(r"due\s+(on\s+)?[\w\s\d-]+", "", task_desc, flags=re.IGNORECASE).strip()
            
            return self.add_reminder(user_id, task_desc, due_date_str)
        
        elif "sheets" in query_lower or "retrieve" in query_lower or "list" in query_lower or "pending" in query_lower or "tasks in" in query_lower:
            return self.retrieve_sheets_data(user_id)
        
        elif "daily summary" in query_lower:
            return self.send_daily_summary()
        
        else:
            return self.get_task_insights(user_id)
    
    def _handle_calendar_query(self, query, query_lower, user_id):
        """Handle calendar-related queries"""
        time_str = extract_time_from_text(query)
        date_str = extract_date_from_text(query)
        
        if "reschedule" in query_lower or "schedule the time" in query_lower:
            if time_str:
                return self.reschedule_summary(time_str)
            else:
                return "Please specify a valid time (e.g., '6:00 AM')."
        
        elif "meeting" in query_lower:
            email = extract_email_from_text(query_lower)
            description = re.sub(
                r"schedule\s+meeting\s+for\s+me\s+with\s+.*?\s+at\s+\d{1,2}(:\d{2})?\s*(am|pm|AM|PM)\s*(on\s+\d{1,2}(?:th|st|nd|rd)? \w+)?",
                "",
                query,
                flags=re.IGNORECASE
            ).strip()
            
            if email and time_str:
                return self.schedule_meeting(email, time_str, date_str, description or "Meeting")
            else:
                return "Please specify attendee email and time (e.g., 'schedule meeting for me with ram@example.com at 5:00 PM on 6 oct')."
        
        else:
            return "Please specify if scheduling a meeting or rescheduling summary."

# Main loop
def main():
    """Main entry point for the Personal Assistant"""
    print("=" * 60)
    print("Personal Assistant started successfully!")
    print("=" * 60)
    print("\nType 'exit' to quit, 'help' for examples\n")
    
    assistant = PersonalAssistant()
    
    while True:
        try:
            query = input("\n🤖 Your query: ").strip()
            
            if not query:
                continue
            
            if query.lower() == 'exit':
                print("\n👋 Exiting assistant. Goodbye!")
                break
            
            if query.lower() == 'help':
                print("\n📚 Example queries:")
                print("  • 'Add task Buy milk due tomorrow'")
                print("  • 'Google search Python tutorials'")
                print("  • 'Task insights'")
                print("  • 'Send mail to email@example.com subject: Hello body: How are you?'")
                print("  • 'What are the top mails for me'")
                print("  • 'What is task management?'")
                print("  • 'select * from tasks'")
                print("  • 'Retrieve data from sheets'")
                print("  • 'Schedule the time for 6:00 AM'")
                print("  • 'Schedule me a meeting with ram@example.com at 5:00 PM on 6 oct'")
                print("  • 'Tell me about yourself'")
                continue
            
            print("\n⏳ Processing...")
            response = assistant.ask(query)
            print(f"\n💡 Response:\n{response}")
            
        except KeyboardInterrupt:
            print("\n\n👋 Exiting assistant. Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {str(e)}")
            logger.error(f"Error in main loop: {e}", exc_info=True)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        print(f"\n❌ Fatal error: {str(e)}")
    finally:
        # Cleanup
        try:
            from database import db_pool
            db_pool.close_all()
        except:
            pass
