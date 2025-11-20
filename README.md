# Personal-Assistant

An intelligent personal assistant built with Python, LangChain, and Google Gemini that helps manage your daily tasks, emails, calendar, and more.

## Features

### 🚀 Core Capabilities
- **Email Management**: Send and receive emails via Gmail IMAP/SMTP
- **Task Management**: Create, track, and manage tasks with Google Tasks integration
- **Calendar**: Schedule meetings with Google Calendar
- **Google Search**: Perform web searches using Google Custom Search API
- **Database Queries**: Execute SQL queries on PostgreSQL database
- **RAG (Retrieval-Augmented Generation)**: Answer questions using stored knowledge base
- **Daily Summaries**: Automated daily email summaries of tasks and important emails
- **Natural Language Processing**: Intelligent query routing powered by Google Gemini

### ✨ Optimizations & Improvements
- **Connection Pooling**: Efficient database connection management
- **Caching**: Email and vectorstore caching for improved performance
- **Rate Limiting**: Built-in rate limiting for API calls
- **Retry Logic**: Automatic retry for failed network operations
- **Input Validation**: Comprehensive validation of user inputs
- **Error Handling**: Robust error handling throughout the application
- **Modular Design**: Clean separation of concerns with config, database, and utility modules
- **Logging**: Detailed logging for debugging and monitoring

## Prerequisites

- Python 3.8+
- PostgreSQL database (Supabase recommended)
- Google Cloud account with API access
- Gmail account with App Password enabled

## Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/abhiramgaddam53/Personal-Assistant.git
   cd Personal-Assistant
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Setup environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your actual credentials
   ```

5. **Configure Google Services**
   - Create a Google Cloud project
   - Enable APIs: Sheets, Tasks, Calendar, Custom Search
   - Create service account and download JSON key
   - Place the JSON file in `data/service-account.json`

6. **Setup Gmail App Password**
   - Go to https://myaccount.google.com/apppasswords
   - Generate an app password for the assistant
   - Add it to your `.env` file

## Configuration

### Environment Variables

Create a `.env` file with the following variables (see `.env.example`):

```env
# Google API
GOOGLE_API_KEY=your_api_key
GOOGLE_CX=your_custom_search_cx

# Gmail
GMAIL_USERNAME=your_email@gmail.com
GMAIL_PASSWORD=your_app_password
GMAIL_RECIPIENT=recipient@gmail.com

# Database
DB_HOST=your_db_host
DB_PORT=6543
DB_NAME=postgres
DB_USER=your_db_user
DB_PASSWORD=your_db_password

# Google Services
SERVICE_ACCOUNT_FILE=./data/service-account.json
SHEET_ID=your_sheet_id

# Configuration
DAILY_SUMMARY_TIME=06:00
LOG_LEVEL=INFO
```

## Usage

### Running the Assistant

```bash
python personal-assistant.py
```

### Example Queries

#### Task Management
```
Add task Buy groceries due tomorrow
Task insights
Retrieve data from sheets
```

#### Email
```
Send email to john@example.com subject: Meeting body: Let's meet tomorrow
What are my top emails?
```

#### Calendar
```
Schedule meeting with jane@example.com at 3:00 PM on 25 Dec
Schedule the time for 8:00 AM
```

#### Search & Database
```
Google search Python tutorials
select * from tasks where status='pending'
```

#### General Queries
```
What is machine learning?
Tell me about yourself
```

## Architecture

### Project Structure
```
Personal-Assistant/
├── personal-assistant.py   # Main application
├── config.py              # Configuration management
├── database.py            # Database connection pooling
├── utils.py               # Utility functions
├── requirements.txt       # Dependencies
├── .env.example          # Environment template
├── .gitignore            # Git ignore rules
└── data/                 # Data directory (created automatically)
    ├── sample.txt        # RAG knowledge base
    ├── vectorstore/      # Cached embeddings
    └── service-account.json  # Google credentials (not in git)
```

### Key Components

1. **Router**: Intelligent query classification using LLM
2. **Database Pool**: Thread-safe connection pooling for PostgreSQL
3. **Rate Limiters**: Prevent API quota exhaustion
4. **Caching**: Reduce redundant API calls
5. **Retry Logic**: Handle transient failures gracefully

## Performance Optimizations

### Database
- ✅ Connection pooling (1-10 connections)
- ✅ Parameterized queries for SQL injection prevention
- ✅ Indexed columns for faster queries
- ✅ Context managers for automatic cleanup

### API Calls
- ✅ Rate limiting (10 emails/min, 100 searches/day)
- ✅ Email caching (5-minute TTL)
- ✅ Vectorstore caching (persisted to disk)
- ✅ Retry logic with exponential backoff

### Code Quality
- ✅ Input validation
- ✅ Comprehensive error handling
- ✅ Structured logging
- ✅ Modular design
- ✅ Type hints (partial)

## Security Considerations

- ✅ Environment variables for credentials
- ✅ No hardcoded secrets
- ✅ SQL injection prevention (parameterized queries)
- ✅ Email validation
- ✅ Input sanitization
- ✅ Secure SSL/TLS connections

## Troubleshooting

### Common Issues

1. **"GOOGLE_API_KEY not configured"**
   - Ensure `.env` file exists and contains `GOOGLE_API_KEY`
   - Check API key is valid at https://aistudio.google.com/app/apikey

2. **"Database connection error"**
   - Verify database credentials in `.env`
   - Check database is accessible and running

3. **"IMAP search failed"**
   - Enable IMAP in Gmail settings
   - Use App Password, not regular password
   - Check https://mail.google.com/mail/u/0/#settings/fwdandpop

4. **"Sheets service unavailable"**
   - Verify `SERVICE_ACCOUNT_FILE` path is correct
   - Ensure service account has access to the sheet
   - Share sheet with service account email

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License.

## Author

**Gaddam Bhanu Venkata Abhiram**
- Email: gaddamabhiram53@gmail.com
- LinkedIn: [linkedin.com/in/abhiramgaddam](https://linkedin.com/in/abhiramgaddam)
- GitHub: [github.com/Abhiram-Gaddam](https://github.com/Abhiram-Gaddam)
- Website: [abhiram-gaddam.github.io](https://abhiram-gaddam.github.io/)

## Acknowledgments

- Google Gemini for LLM capabilities
- LangChain for RAG framework
- HuggingFace for embeddings
- Supabase for PostgreSQL hosting
