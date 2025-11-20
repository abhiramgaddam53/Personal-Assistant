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

# Apply nest_asyncio for Colab
nest_asyncio.apply()

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Google services
SERVICE_ACCOUNT_FILE = '/content/personal-assistance-474105-f1aecdeaab1c.json'
SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/tasks', 'https://www.googleapis.com/auth/calendar']
try:
    credentials = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    sheets_service = build('sheets', 'v4', credentials=credentials)
    tasks_service = build('tasks', 'v1', credentials=credentials)
    calendar_service = build('calendar', 'v3', credentials=credentials)
except Exception as e:
    logger.error(f"Google services error: {e}")
    sheets_service = tasks_service = calendar_service = None

# DB setup
def get_db_connection():
    try:
        conn = psycopg2.connect(
            host="aws-0-ap-southeast-1.pooler.supabase.com",
            port=6543,
            dbname="postgres",
            user= "postgres.ixruzjparquranqfdvdm",
            password= "aasp3885@gmail",
            sslmode="require"
        )
        return conn
    except psycopg2.Error as e:
        logger.error(f"Database connection error: {e}")
        raise

def init_db():
    conn = get_db_connection()
    try:
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
    except psycopg2.Error as e:
        logger.error(f"Database error: {e}")
        raise
    finally:
        cur.close()
        conn.close()

init_db()

# Load env
load_dotenv('/content/.env')

# RAG setup with FAISS
sample_docs = [
    "Personal assistant manages emails via IMAP/SMTP, schedules tasks in Google Tasks, and updates Google Sheets daily.",
    "Tasks are stored in PostgreSQL with fields: user_id, task_description, due_date, status, priority. Query via SQL for retrieval.",
    "Google Search uses Custom Search API. Daily summaries are emailed at 6 AM with task and email updates.",
    "Meetings can be scheduled using Google Calendar API with attendee emails and time slots."
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
with open('/content/sample.txt', 'w') as f:
    f.write("\n".join(sample_docs))
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
docs = TextLoader("/content/sample.txt").load()
vectorstore = FAISS.from_documents(docs, embeddings)
retriever = vectorstore.as_retriever()

# LLM setup
try:
    llm = ChatGoogleGenerativeAI(
        model="models/gemini-2.5-flash",
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        temperature=0.1
    )
    response = llm.invoke("Test connection")
    logger.info(f"Gemini connected: {response.content}")
except Exception as e:
    logger.error(f"Gemini failed: {e}")
    raise RuntimeError("Cannot connect to Gemini. Check API key and quota at https://aistudio.google.com/app/apikey.")

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
        self.scheduler.add_job(self.send_daily_summary, 'date', run_date=datetime.now() + timedelta(seconds=30))
        self.scheduler.start()
        self.router_chain = router_prompt | llm
        self.structure_chain = structure_prompt | llm

    def check_important_emails(self, user_id):
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT email_filters FROM user_profiles WHERE user_id = %s", (user_id,))
            row = cur.fetchone()
            filters = row[0] if row else 'ALL'
            cur.close()
            conn.close()
            mail = imaplib.IMAP4_SSL("imap.gmail.com")
            mail.login(os.getenv("GMAIL_USERNAME"), os.getenv("GMAIL_PASSWORD"))
            mail.select("inbox")
            status, messages = mail.search(None, filters)
            if status != 'OK':
                logger.warning(f"IMAP search failed: {messages}. Falling back to ALL.")
                status, messages = mail.search(None, 'ALL')
                if status != 'OK':
                    raise Exception(f"IMAP fallback search failed: {messages}")
            email_ids = messages[0].split()
            summaries = []
            for email_id in email_ids[-5:]:
                status, msg_data = mail.fetch(email_id, "(RFC822)")
                if status != 'OK':
                    continue
                msg = msg_data[0][1].decode("utf-8", errors="ignore")
                subject = next((line.split(": ", 1)[1] for line in msg.split("\n") if line.startswith("Subject:")), "No Subject")
                summaries.append(f"Subject: {subject}")
            mail.logout()
            return "\n".join(summaries) or "No emails found."
        except Exception as e:
            logger.error(f"Error checking emails: {e}")
            return f"Failed to check emails: {str(e)}. Ensure IMAP is enabled and App Password is valid: https://mail.google.com/mail/u/0/#settings/fwdandpop"

    def send_email(self, subject, body, recipient=None):
        try:
            msg = MIMEMultipart()
            msg['From'] = os.getenv("GMAIL_USERNAME")
            msg['To'] = recipient or os.getenv("GMAIL_RECIPIENT")
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))
            with smtplib.SMTP('smtp.gmail.com', 587) as server:
                server.starttls()
                server.login(os.getenv("GMAIL_USERNAME"), os.getenv("GMAIL_PASSWORD"))
                server.sendmail(msg['From'], msg['To'], msg.as_string())
            return f"Email sent to {msg['To']}."
        except Exception as e:
            logger.error(f"Error sending email: {e}")
            return f"Failed to send email: {str(e)}"

    def perform_google_search(self, query):
        try:
            url = "https://www.googleapis.com/customsearch/v1"
            params = {
                "key": os.getenv("GOOGLE_API_KEY"),
                "cx": os.getenv("GOOGLE_CX"),
                "q": query
            }
            response = requests.get(url, params=params)
            response.raise_for_status()
            results = response.json().get("items", [])
            formatted_results = "\n".join([f"{i+1}. {result['title']} - {result['link']}" for i, result in enumerate(results[:5])])
            return formatted_results or "No search results found."
        except Exception as e:
            logger.error(f"Search error: {e}")
            return f"Failed to perform search: {str(e)}. Verify API key and CX at https://console.developers.google.com"

    def query_database(self, query, user_id):
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            if query.lower().startswith("select * from tables") or "tables in my database" in query.lower():
                cur.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
                tables = cur.fetchall()
                cur.close()
                conn.close()
                return f"Tables in database:\n" + "\n".join([row[0] for row in tables]) or "No tables found."
            cur.execute(query)
            if query.lower().startswith("select"):
                results = cur.fetchall()
                columns = [desc[0] for desc in cur.description]
                formatted_results = "\n".join([str(dict(zip(columns, row))) for row in results])
                cur.close()
                conn.close()
                return f"Database query results:\n{formatted_results}" if results else "No results found."
            else:
                conn.commit()
                cur.close()
                conn.close()
                return "Query executed successfully."
        except psycopg2.Error as e:
            logger.error(f"Database query error: {e}")
            return f"Failed to execute query: {str(e)}"

    def get_task_insights(self, user_id):
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("""
                SELECT status, COUNT(*),
                       ROUND(AVG(EXTRACT(EPOCH FROM (due_date - CURRENT_TIMESTAMP))/86400)::numeric, 1)
                FROM tasks WHERE user_id = %s GROUP BY status
            """, (user_id,))
            stats = cur.fetchall()
            insights = f"Task Insights for {user_id}:\n" + "\n".join([f"{row[0].title()}: {row[1]} tasks, Avg days to due: {row[2]}" for row in stats])
            cur.close()
            conn.close()
            return insights or "No task insights available."
        except Exception as e:
            logger.error(f"Error fetching insights: {e}")
            return f"Failed to fetch insights: {str(e)}"

    def add_reminder(self, user_id, task_description, due_date_str=None):
        try:
            if due_date_str:
                due = dateparser.parse(due_date_str)
                if due is None:
                    raise ValueError("Invalid due date format")
                due = due.replace(tzinfo=None)
            else:
                due = datetime.now() + timedelta(days=1)
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT reminder_preference FROM user_profiles WHERE user_id = %s", (user_id,))
            row = cur.fetchone()
            preference = row[0] if row else "tasks"
            cur.execute("INSERT INTO tasks (user_id, task_description, due_date) VALUES (%s, %s, %s)", (user_id, task_description, due))
            conn.commit()
            # Update Sheets
            cur.execute("SELECT task_description, due_date, status, priority FROM tasks WHERE user_id = %s AND status = 'pending'", (user_id,))
            tasks = [{'description': row[0], 'due_date': row[1].strftime('%Y-%m-%d'), 'status': row[2], 'priority': row[3]} for row in cur.fetchall()]
            sheets_result = self.update_sheets(user_id, json.dumps(tasks))
            cur.close()
            conn.close()
            if preference == "tasks" and tasks_service:
                task = {'title': task_description, 'due': due.isoformat() + 'Z'}
                try:
                    tasklist = tasks_service.tasklists().list().execute().get('items', [])
                    tasklist_id = tasklist[0]['id'] if tasklist else None
                    if tasklist_id:
                        tasks_service.tasks().insert(tasklist=tasklist_id, body=task).execute()
                        return f"Reminder added to Google Tasks.\n{sheets_result}"
                except HttpError as he:
                    logger.error(f"Google Tasks API error: {he}")
                    return f"Failed to add to Google Tasks: {str(he)}. Enable API at https://console.developers.google.com/apis/api/tasks.googleapis.com/overview\n{sheets_result}"
            return self.send_email("Task Reminder", f"Reminder: {task_description} due on {due}", os.getenv("GMAIL_RECIPIENT")) + f"\n{sheets_result}"
        except Exception as e:
            logger.error(f"Error adding reminder: {e}")
            return f"Failed to add reminder: {str(e)}"

    def update_sheets(self, user_id, tasks_json):
        if not sheets_service:
            return "Sheets service unavailable."
        try:
            tasks_list = json.loads(tasks_json)
            spreadsheet_id = os.getenv("SHEET_ID")
            body = {'values': [[t['description'], t['due_date'], t['status'], t['priority']] for t in tasks_list]}
            sheets_service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range="Sheet1!A1:D",
                valueInputOption="RAW",
                body=body
            ).execute()
            return "Spreadsheet updated successfully."
        except Exception as e:
            logger.error(f"Error updating Sheets: {e}")
            return f"Failed to update Sheets: {str(e)}"

    def retrieve_sheets_data(self, user_id):
        if not sheets_service:
            return "Sheets service unavailable."
        try:
            spreadsheet_id = os.getenv("SHEET_ID")
            result = sheets_service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range="Sheet1!A1:D"
            ).execute()
            values = result.get('values', [])
            if not values:
                return "No tasks found in the spreadsheet."
            formatted_tasks = "\n".join([f"Task: {row[0]}, Due: {row[1]}, Status: {row[2]}, Priority: {row[3]}" for row in values if len(row) >= 4])
            return f"Tasks in spreadsheet:\n{formatted_tasks}"
        except Exception as e:
            logger.error(f"Error retrieving Sheets data: {e}")
            return f"Failed to retrieve Sheets data: {str(e)}"

    def schedule_meeting(self, attendee_email, time_str, date_str=None, description="Meeting"):
        if not calendar_service:
            return "Calendar service unavailable."
        try:
            now = datetime.now()
            if date_str:
                # Parse date like "6th oct" to datetime
                date_str = date_str.lower().replace("th", "").replace("st", "").replace("nd", "").replace("rd", "")
                meeting_date = dateparser.parse(date_str)
                if meeting_date is None:
                    raise ValueError("Invalid date format")
            else:
                meeting_date = now
            time_parsed = dateparser.parse(time_str)
            if time_parsed is None:
                raise ValueError("Invalid time format")
            time = time_parsed.time()
            start_time = datetime.combine(meeting_date.date(), time)
            end_time = start_time + timedelta(hours=1)
            event = {
                'summary': description,
                'start': {'dateTime': start_time.isoformat(), 'timeZone': 'Asia/Kolkata'},
                'end': {'dateTime': end_time.isoformat(), 'timeZone': 'Asia/Kolkata'},
                'attendees': [{'email': attendee_email}],
            }
            event = calendar_service.events().insert(calendarId='primary', body=event).execute()
            return f"Meeting scheduled with {attendee_email} at {time_str} on {meeting_date.strftime('%Y-%m-%d')}."
        except ValueError as ve:
            logger.error(f"Date/Time parsing error: {ve}")
            return f"Failed to parse date/time: {str(ve)}. Use format like 'at 5:00 PM on 6 oct'."
        except Exception as e:
            logger.error(f"Error scheduling meeting: {e}")
            return f"Failed to schedule meeting: {str(e)}"

    def send_daily_summary(self):
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT user_id FROM user_profiles")
            users = cur.fetchall()
            for user_tuple in users:
                user_id = user_tuple[0]
                email_summary = self.check_important_emails(user_id)
                cur.execute("SELECT task_description, due_date, status, priority FROM tasks WHERE user_id = %s AND status = 'pending'", (user_id,))
                tasks = [{'description': row[0], 'due_date': row[1].strftime('%Y-%m-%d'), 'status': row[2], 'priority': row[3]} for row in cur.fetchall()]
                task_summary = "\n".join([f"{t['description']} (Due: {t['due_date']}, Priority: {t['priority']})" for t in tasks]) or "No pending tasks."
                summary = f"Daily Summary (6 AM):\n\nImportant Emails:\n{email_summary}\n\nTasks:\n{task_summary}"
                self.send_email("Daily Task Summary", summary)
                self.update_sheets(user_id, json.dumps(tasks))
            cur.close()
            conn.close()
            return "Daily summary sent successfully."
        except Exception as e:
            logger.error(f"Daily summary error: {e}")
            return f"Failed to send daily summary: {str(e)}"

    def reschedule_summary(self, time_str):
        try:
            time = datetime.strptime(time_str, "%I:%M %p").time()
            self.scheduler.remove_all_jobs()
            self.scheduler.add_job(self.send_daily_summary, CronTrigger(hour=time.hour, minute=time.minute))
            if not self.scheduler.running:
                self.scheduler.start()
            return f"Daily summary rescheduled to {time_str}."
        except Exception as e:
            logger.error(f"Error rescheduling summary: {e}")
            return f"Failed to reschedule summary: {str(e)}"

    def rag_query(self, query):
        try:
            docs = retriever.invoke(query)
            context = "\n".join([d.page_content for d in docs])
            prompt = f"Answer {query} using context: {context}"
            response = llm.invoke(prompt).content
            return response
        except Exception as e:
            logger.error(f"RAG error: {e}")
            return f"RAG failed: {str(e)}"

    def route_query(self, query):
        try:
            result = self.router_chain.invoke({"query": query})
            category = result.content.strip().lower()
            allowed_categories = ['email', 'task', 'search', 'database', 'calendar', 'rag', 'llm']
            if category not in allowed_categories:
                category = 'llm'
            return category
        except Exception as e:
            logger.error(f"Router error: {e}")
            return "llm"

    def structure_response(self, query, raw_response):
        try:
            result = self.structure_chain.invoke({"query": query, "raw_response": raw_response})
            return result.content
        except Exception as e:
            logger.error(f"Structure response error: {e}")
            return raw_response  # Fallback to raw if structuring fails

    def about_me(self):
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
        return   about_text

    def ask(self, query, user_id="abhiram"):
        if not query or not isinstance(query, str):
            raise ValueError("Query must be a non-empty string")
        if not user_id or not isinstance(user_id, str):
            raise ValueError("User ID must be a non-empty string")

        query_lower = query.lower()
        if "about me" in query_lower or "tell me about yourself" in query_lower or "who are you" in query_lower or "your details" in query_lower or "resume" in query_lower:
                raw_response = self.rag_query(query)
                conn = get_db_connection()
                try:
                    cur = conn.cursor()
                    cur.execute(
                        "INSERT INTO chat_history (user_id, query, context, response) VALUES (%s, %s, %s, %s)",
                        (user_id, query, "Retrieved context", raw_response)
                    )
                    conn.commit()
                except psycopg2.Error as e:
                    logger.error(f"Database error: {e}")
                finally:
                    cur.close()
                    conn.close()
        else:
            query_type = self.route_query(query)
            logger.info(f"Query type: {query_type}")

            if query_type == "email":
                if "send" in query_lower or "mail to" in query_lower:
                    parts = query.lower().split("subject:")
                    subject = parts[1].split("body:")[0].strip() if len(parts) > 1 else "Assistant Email"
                    body = query.split("body:")[1].strip() if "body:" in query else query.replace("send email", "").replace("send mail", "").strip()
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
                    task_desc_match = re.sub(r"(add task|add|reminder|to sheets|update sheets with|that i need to)", "", query, flags=re.IGNORECASE).strip()
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
                search_query = re.sub(r"(google search|search for|search|seatch)", "", query, flags=re.IGNORECASE).strip()
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
                    description = re.sub(r"schedule\s+meeting\s+for\s+me\s+with\s+.*?\s+at\s+\d{1,2}(:\d{2})?\s*(am|pm|AM|PM)\s*(on\s+\d{1,2}(?:th|st|nd|rd)? \w+)?", "", query, flags=re.IGNORECASE).strip()
                    if email_match and time_match:
                        raw_response = self.schedule_meeting(email_match.group(1), time_match.group(0).upper(), date_str, description or "Meeting")
                    else:
                        raw_response = "Please specify attendee email and time (e.g., 'schedule meeting for me with ram@example.com at 5:00 PM on 6 oct')."
                else:
                    raw_response = "Please specify if scheduling a meeting or rescheduling summary."
            elif query_type == "rag":
                raw_response = self.rag_query(query)
                conn = get_db_connection()
                try:
                    cur = conn.cursor()
                    cur.execute(
                        "INSERT INTO chat_history (user_id, query, context, response) VALUES (%s, %s, %s, %s)",
                        (user_id, query, "Retrieved context", raw_response)
                    )
                    conn.commit()
                except psycopg2.Error as e:
                    logger.error(f"Database error: {e}")
                finally:
                    cur.close()
                    conn.close()
            else:  # llm
                raw_response = llm.invoke(query).content
                conn = get_db_connection()
                try:
                    cur = conn.cursor()
                    cur.execute(
                        "INSERT INTO general_chat_history (user_id, query, response) VALUES (%s, %s, %s)",
                        (user_id, query, raw_response)
                    )
                    conn.commit()
                except psycopg2.Error as e:
                    logger.error(f"Database error: {e}")
                finally:
                    cur.close()
                    conn.close()

        return self.structure_response(query, raw_response)

# Main loop
def main():
    print("Assistant started in Colab. Enter queries (type 'exit' to quit).")
    print("Examples: 'Add task Buy milk due tomorrow', 'Google search Python tutorials', 'Task insights', 'Send mail to aasp3885@gmail.com saying hello', 'What are to top mails for me', 'What is task management?', 'select * from tasks', 'retrive data from sheets', 'schedule the time for 6:00 AM', 'schedule me a meeting with ram@example.com at 5:00 PM', 'Tell me about yourself')")
    assistant = PersonalAssistant()
    while True:
        query = input("Your query: ")
        if query.lower() == 'exit':
            print("Exiting assistant.")
            break
        try:
            response = assistant.ask(query)
            print("Response:", response)
        except Exception as e:
            print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()
