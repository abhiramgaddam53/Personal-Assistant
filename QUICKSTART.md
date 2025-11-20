# Quick Start Guide

Get your Personal Assistant up and running in 5 minutes!

## Prerequisites

- Python 3.8 or higher
- PostgreSQL database (or Supabase account)
- Gmail account with App Password
- Google Cloud account (for API keys)

## Step 1: Clone and Install

```bash
# Clone the repository
git clone https://github.com/abhiramgaddam53/Personal-Assistant.git
cd Personal-Assistant

# Install dependencies
pip install -r requirements.txt
```

## Step 2: Configure Environment

```bash
# Copy the template
cp .env.template .env

# Edit .env with your favorite editor
nano .env  # or vim, code, etc.
```

### Minimum Required Configuration

Edit `.env` and set these values:

```env
# Database (required for tasks)
DB_HOST=your-database-host
DB_USER=your-database-user
DB_PASSWORD=your-database-password

# Email (required for email features)
GMAIL_USERNAME=your-email@gmail.com
GMAIL_PASSWORD=your-app-password

# Google API (required for search, sheets, calendar)
GOOGLE_API_KEY=your-google-api-key
```

### Optional Configuration

```env
# Google Custom Search (optional - for web search)
GOOGLE_CX=your-custom-search-engine-id

# Google Sheets (optional - for task sync)
SHEET_ID=your-google-sheet-id

# Service Account (optional - for Google services)
SERVICE_ACCOUNT_FILE=/path/to/service-account.json

# Email recipient (optional - defaults to sender)
GMAIL_RECIPIENT=recipient@gmail.com

# Daily summary time (optional - defaults to 06:00)
DAILY_SUMMARY_TIME=07:00
```

## Step 3: Get API Keys

### Gmail App Password

1. Go to [Google Account Security](https://myaccount.google.com/security)
2. Enable 2-Step Verification
3. Go to [App Passwords](https://myaccount.google.com/apppasswords)
4. Generate a new app password
5. Copy the 16-character password to `GMAIL_PASSWORD` in `.env`

### Google API Key

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing)
3. Go to APIs & Services → Credentials
4. Click "Create Credentials" → "API Key"
5. Copy the API key to `GOOGLE_API_KEY` in `.env`
6. Enable required APIs:
   - Custom Search API (for search)
   - Google Sheets API (for sheets)
   - Google Tasks API (for tasks)
   - Google Calendar API (for calendar)

### Custom Search CX (Optional)

1. Go to [Programmable Search Engine](https://programmablesearchengine.google.com/)
2. Create a new search engine
3. Copy the Search Engine ID to `GOOGLE_CX` in `.env`

### Service Account (Optional)

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Go to IAM & Admin → Service Accounts
3. Create a new service account
4. Download the JSON key file
5. Set `SERVICE_ACCOUNT_FILE=/path/to/downloaded-file.json` in `.env`

## Step 4: Run the Assistant

```bash
# Run the optimized version (recommended)
python personal_assistant_optimized.py
```

You should see:
```
================================================================================
Personal Assistant - Optimized Version
================================================================================

Initializing...
Assistant started successfully!

Example queries:
- 'Check my emails'
- 'Add task: Buy groceries due tomorrow'
- 'Google search Python tutorials'
...

Your query:
```

## Step 5: Try Some Queries

### Basic Queries

```
Your query: Check my emails
Your query: Add task: Test the assistant due tomorrow
Your query: Task insights
Your query: Tell me about yourself
```

### Advanced Queries

```
Your query: Send email to friend@example.com subject: Hello body: Testing my assistant!
Your query: Google search latest AI news
Your query: Schedule meeting with colleague@company.com at 3:00 PM tomorrow
Your query: List my pending tasks
```

## Troubleshooting

### Database Connection Errors

**Error:** `Database connection failed`

**Solution:**
1. Check `DB_HOST`, `DB_USER`, `DB_PASSWORD` in `.env`
2. Verify database is running and accessible
3. Check if port 6543 (or your DB port) is open
4. Try: `psql -h DB_HOST -U DB_USER -d postgres` to test connection

### Email Errors

**Error:** `Failed to connect to IMAP`

**Solution:**
1. Verify `GMAIL_USERNAME` and `GMAIL_PASSWORD` in `.env`
2. Use App Password, not account password
3. Enable IMAP in Gmail settings: Settings → Forwarding and POP/IMAP
4. Check 2-Step Verification is enabled

### Google API Errors

**Error:** `Failed to perform search: 403`

**Solution:**
1. Verify `GOOGLE_API_KEY` in `.env`
2. Enable Custom Search API in Google Cloud Console
3. Check API quota at [Google Cloud Console](https://console.cloud.google.com/)

**Error:** `Sheets service unavailable`

**Solution:**
1. Set `SERVICE_ACCOUNT_FILE` path in `.env`
2. Verify JSON file exists and is valid
3. Enable Google Sheets API in Cloud Console
4. Share the sheet with service account email

### Import Errors

**Error:** `ModuleNotFoundError: No module named 'xyz'`

**Solution:**
```bash
pip install -r requirements.txt
```

If still fails, install manually:
```bash
pip install psycopg2-binary python-dotenv langchain langchain-google-genai
```

### Cache Issues

**Error:** `Failed to load cached vectorstore`

**Solution:**
```bash
# Clear cache and rebuild
rm -rf .cache/
python personal_assistant_optimized.py
```

## Performance Tips

### First Run
The first run will be slower as it:
- Downloads embeddings model (~80 MB)
- Creates vectorstore cache
- Initializes database tables

**Typical first run:** 30-60 seconds

### Subsequent Runs
After first run, startup is much faster:
- Uses cached embeddings (instant)
- Uses cached vectorstore (instant)
- Database pool ready (instant)

**Typical subsequent runs:** 3-5 seconds

### Optimization Checklist

✅ Use the optimized version (`personal_assistant_optimized.py`)  
✅ Let embeddings cache on first run  
✅ Don't delete `.cache/` directory  
✅ Use connection pooling (automatic)  
✅ Configure all environment variables  

## Next Steps

1. **Read the Documentation**
   - `README.md` - Complete feature documentation
   - `MIGRATION.md` - Migration from original version
   - `OPTIMIZATION_SUMMARY.md` - Technical details

2. **Explore Usage Examples**
   ```bash
   python usage_examples.py
   ```

3. **Compare Versions**
   ```bash
   python compare_versions.py
   ```

4. **Customize**
   - Add your own knowledge base to RAG
   - Modify query routing logic
   - Add new service integrations
   - Customize daily summary format

5. **Deploy**
   - Run on a server (Linux/Windows)
   - Set up as a service
   - Configure daily summaries
   - Add monitoring

## Feature Checklist

Test each feature to ensure it works:

- [ ] Email: "Check my emails"
- [ ] Task: "Add task: Test due tomorrow"
- [ ] Search: "Google search test"
- [ ] Database: "Show tables in my database"
- [ ] RAG: "Tell me about yourself"
- [ ] Calendar: "Schedule meeting with test@example.com at 5:00 PM"
- [ ] LLM: "What is the capital of France?"

## Getting Help

### Resources
- 📖 README.md - Full documentation
- 🔄 MIGRATION.md - Migration guide
- 📊 OPTIMIZATION_SUMMARY.md - Technical details
- 💡 usage_examples.py - Usage patterns

### Common Issues
- Check `.env` configuration first
- Verify all API keys are valid
- Ensure services are enabled in Google Cloud Console
- Check database connection and permissions
- Review logs for detailed error messages

### Support
- GitHub Issues: [Report bugs or request features](https://github.com/abhiramgaddam53/Personal-Assistant/issues)
- Email: gaddamabhiram53@gmail.com

## Success Indicators

You know everything is working when:

✅ Assistant starts without errors  
✅ You can check emails  
✅ You can add and list tasks  
✅ Google search returns results  
✅ Database queries work  
✅ RAG answers questions  
✅ No error messages in logs  

Congratulations! Your Personal Assistant is ready to boost your productivity! 🚀
