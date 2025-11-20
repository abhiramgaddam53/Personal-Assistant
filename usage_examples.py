"""
Usage Examples for Personal Assistant

This file demonstrates various use cases and query patterns for the optimized
Personal Assistant.
"""

def print_section(title):
    """Print a formatted section header"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70 + "\n")


def email_examples():
    """Email operation examples"""
    print_section("EMAIL OPERATIONS")
    
    examples = [
        ("Check recent emails", 
         "Check my emails"),
        
        ("Check important/unread emails",
         "Show me important emails"),
        
        ("Send simple email",
         "Send email to john@example.com subject: Meeting body: Let's meet tomorrow at 3 PM"),
        
        ("Send email to default recipient",
         "Send email subject: Reminder body: Don't forget the deadline"),
    ]
    
    for i, (description, query) in enumerate(examples, 1):
        print(f"{i}. {description}")
        print(f"   Query: \"{query}\"")
        print()


def task_examples():
    """Task management examples"""
    print_section("TASK MANAGEMENT")
    
    examples = [
        ("Add task with due date",
         "Add task: Buy groceries due tomorrow"),
        
        ("Add task with specific date",
         "Add reminder: Submit report due on 25th December"),
        
        ("Add task without due date (defaults to tomorrow)",
         "Add task: Call dentist"),
        
        ("List all pending tasks",
         "List my pending tasks"),
        
        ("Get task statistics",
         "Task insights"),
        
        ("Get task summary",
         "Show me my tasks"),
        
        ("Retrieve tasks from sheets",
         "Retrieve data from sheets"),
    ]
    
    for i, (description, query) in enumerate(examples, 1):
        print(f"{i}. {description}")
        print(f"   Query: \"{query}\"")
        print()


def search_examples():
    """Web search examples"""
    print_section("WEB SEARCH")
    
    examples = [
        ("Simple search",
         "Google search Python tutorials"),
        
        ("Search for news",
         "Search for latest AI news"),
        
        ("Search technical topics",
         "Search LangChain documentation"),
    ]
    
    for i, (description, query) in enumerate(examples, 1):
        print(f"{i}. {description}")
        print(f"   Query: \"{query}\"")
        print()


def calendar_examples():
    """Calendar and scheduling examples"""
    print_section("CALENDAR & SCHEDULING")
    
    examples = [
        ("Schedule meeting with specific date",
         "Schedule meeting with john@example.com at 5:00 PM on 6th October"),
        
        ("Schedule meeting for today",
         "Schedule meeting with sarah@company.com at 2:30 PM"),
        
        ("Reschedule daily summary",
         "Reschedule daily summary to 7:00 AM"),
        
        ("Change summary time",
         "Schedule the time for 6:30 AM"),
    ]
    
    for i, (description, query) in enumerate(examples, 1):
        print(f"{i}. {description}")
        print(f"   Query: \"{query}\"")
        print()


def database_examples():
    """Database query examples"""
    print_section("DATABASE OPERATIONS")
    
    examples = [
        ("List all tables",
         "Show tables in my database"),
        
        ("Query tasks",
         "SELECT * FROM tasks WHERE status='pending'"),
        
        ("Get user profiles",
         "SELECT * FROM user_profiles"),
        
        ("Count tasks by status",
         "SELECT status, COUNT(*) FROM tasks GROUP BY status"),
        
        ("Get recent chat history",
         "SELECT * FROM general_chat_history ORDER BY created_at DESC LIMIT 10"),
    ]
    
    for i, (description, query) in enumerate(examples, 1):
        print(f"{i}. {description}")
        print(f"   Query: \"{query}\"")
        print()


def rag_examples():
    """RAG and knowledge questions examples"""
    print_section("KNOWLEDGE & RAG QUERIES")
    
    examples = [
        ("Ask about the assistant",
         "Tell me about yourself"),
        
        ("Get personal information",
         "What is your resume?"),
        
        ("Ask about features",
         "What features do you have?"),
        
        ("Explain concepts",
         "Explain what is task management"),
        
        ("Technical questions",
         "What is RAG and how does it work?"),
        
        ("Get contact details",
         "What are your contact details?"),
    ]
    
    for i, (description, query) in enumerate(examples, 1):
        print(f"{i}. {description}")
        print(f"   Query: \"{query}\"")
        print()


def llm_examples():
    """General LLM conversation examples"""
    print_section("GENERAL CONVERSATION")
    
    examples = [
        ("General questions",
         "What is the capital of France?"),
        
        ("Get recommendations",
         "Recommend some good books on AI"),
        
        ("Brainstorming",
         "Give me ideas for a birthday party"),
        
        ("Explanations",
         "Explain quantum computing in simple terms"),
        
        ("Creative tasks",
         "Write a haiku about programming"),
    ]
    
    for i, (description, query) in enumerate(examples, 1):
        print(f"{i}. {description}")
        print(f"   Query: \"{query}\"")
        print()


def integration_examples():
    """Complex multi-step examples"""
    print_section("INTEGRATION EXAMPLES")
    
    print("Scenario 1: Daily Productivity Workflow")
    print("-" * 70)
    workflow1 = [
        "Check my emails",
        "Add task: Respond to client emails due today",
        "Add task: Prepare presentation due tomorrow",
        "Task insights",
        "Schedule meeting with team@company.com at 3:00 PM",
    ]
    for step in workflow1:
        print(f"  → {step}")
    print()
    
    print("Scenario 2: Research and Learning")
    print("-" * 70)
    workflow2 = [
        "Google search machine learning courses",
        "Add task: Enroll in ML course due next week",
        "What is machine learning?",
        "Explain neural networks",
    ]
    for step in workflow2:
        print(f"  → {step}")
    print()
    
    print("Scenario 3: Meeting Preparation")
    print("-" * 70)
    workflow3 = [
        "List my pending tasks",
        "Schedule meeting with manager@company.com at 10:00 AM tomorrow",
        "Send email to manager@company.com subject: Meeting Agenda body: Discuss Q4 goals",
        "Add task: Prepare meeting notes due tomorrow",
    ]
    for step in workflow3:
        print(f"  → {step}")
    print()


def tips_and_tricks():
    """Tips for effective usage"""
    print_section("TIPS & TRICKS")
    
    tips = [
        ("Natural Language", 
         "You can use natural language - the assistant understands context"),
        
        ("Date Parsing",
         "Dates are flexible: 'tomorrow', '25th Dec', 'next Monday', 'in 3 days'"),
        
        ("Email Recipients",
         "If you don't specify a recipient, emails go to the default recipient"),
        
        ("Task Priorities",
         "Tasks default to 'medium' priority - you can manually update in the database"),
        
        ("Google Sheets",
         "Tasks are automatically synced to Google Sheets when you add them"),
        
        ("Daily Summaries",
         "Configure DAILY_SUMMARY_TIME in .env for automated daily reports"),
        
        ("Error Recovery",
         "If a service fails, the assistant continues with available services"),
        
        ("Query Routing",
         "The assistant automatically routes queries to the right handler"),
    ]
    
    for i, (category, tip) in enumerate(tips, 1):
        print(f"{i}. {category}:")
        print(f"   {tip}")
        print()


def common_patterns():
    """Common query patterns"""
    print_section("COMMON QUERY PATTERNS")
    
    patterns = {
        "Email Operations": [
            "check [my] emails",
            "send email to <email> subject: <subject> body: <body>",
            "show me [important] emails",
        ],
        
        "Task Management": [
            "add task: <description> [due <date>]",
            "list [my] [pending] tasks",
            "task insights",
            "show [me] [my] tasks",
        ],
        
        "Search": [
            "google search <query>",
            "search [for] <query>",
        ],
        
        "Calendar": [
            "schedule meeting with <email> at <time> [on <date>]",
            "reschedule [daily summary] to <time>",
        ],
        
        "Database": [
            "SELECT * FROM <table>",
            "show tables in [my] database",
        ],
        
        "Knowledge": [
            "tell me about <topic>",
            "what is <concept>",
            "explain <concept>",
        ],
    }
    
    for category, pattern_list in patterns.items():
        print(f"{category}:")
        for pattern in pattern_list:
            print(f"  • {pattern}")
        print()


def main():
    """Main function to display all examples"""
    print("\n" + "=" * 70)
    print("  PERSONAL ASSISTANT - USAGE EXAMPLES")
    print("=" * 70)
    
    email_examples()
    task_examples()
    search_examples()
    calendar_examples()
    database_examples()
    rag_examples()
    llm_examples()
    integration_examples()
    tips_and_tricks()
    common_patterns()
    
    print("\n" + "=" * 70)
    print("  For more information, see README.md and MIGRATION.md")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
