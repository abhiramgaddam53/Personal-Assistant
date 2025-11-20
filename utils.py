"""
Utility functions for Personal Assistant
"""
import re
import logging
from datetime import datetime, timedelta
from functools import wraps
import time

logger = logging.getLogger(__name__)


def validate_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validate_user_id(user_id):
    """Validate user ID"""
    if not user_id or not isinstance(user_id, str):
        raise ValueError("User ID must be a non-empty string")
    if len(user_id) > 100:
        raise ValueError("User ID too long")
    return user_id


def validate_query(query):
    """Validate query string"""
    if not query or not isinstance(query, str):
        raise ValueError("Query must be a non-empty string")
    if len(query) > 5000:
        raise ValueError("Query too long (max 5000 characters)")
    return query.strip()


def parse_time_string(time_str):
    """Parse time string to time object"""
    try:
        return datetime.strptime(time_str, "%I:%M %p").time()
    except ValueError:
        try:
            return datetime.strptime(time_str, "%H:%M").time()
        except ValueError:
            raise ValueError(f"Invalid time format: {time_str}. Use 'HH:MM AM/PM' or 'HH:MM'")


def retry_on_failure(max_retries=3, delay=1, backoff=2):
    """Decorator to retry function on failure with exponential backoff"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            current_delay = delay
            
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    retries += 1
                    if retries >= max_retries:
                        logger.error(f"{func.__name__} failed after {max_retries} retries: {e}")
                        raise
                    
                    logger.warning(f"{func.__name__} failed (attempt {retries}/{max_retries}): {e}. Retrying in {current_delay}s...")
                    time.sleep(current_delay)
                    current_delay *= backoff
            
        return wrapper
    return decorator


def extract_email_from_text(text):
    """Extract email address from text"""
    pattern = r'[\w\.-]+@[\w\.-]+\.\w+'
    match = re.search(pattern, text)
    return match.group(0) if match else None


def extract_time_from_text(text):
    """Extract time from text"""
    pattern = r'\d{1,2}(:\d{2})?\s*(am|pm|AM|PM)'
    match = re.search(pattern, text, re.IGNORECASE)
    return match.group(0).upper() if match else None


def extract_date_from_text(text):
    """Extract date from text"""
    pattern = r'on (\d{1,2}(?:th|st|nd|rd)? \w+)'
    match = re.search(pattern, text, re.IGNORECASE)
    return match.group(1) if match else None


def sanitize_sql_identifier(identifier):
    """Sanitize SQL identifiers (table/column names)"""
    # Only allow alphanumeric and underscore
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', identifier):
        raise ValueError(f"Invalid SQL identifier: {identifier}")
    return identifier


def format_task_list(tasks):
    """Format task list for display"""
    if not tasks:
        return "No tasks found."
    
    formatted = []
    for i, task in enumerate(tasks, 1):
        formatted.append(
            f"{i}. **{task.get('description', 'N/A')}**\n"
            f"   - Due: {task.get('due_date', 'N/A')}\n"
            f"   - Status: {task.get('status', 'N/A')}\n"
            f"   - Priority: {task.get('priority', 'N/A')}"
        )
    
    return "\n\n".join(formatted)


def format_email_list(emails):
    """Format email list for display"""
    if not emails:
        return "No emails found."
    
    formatted = []
    for i, email in enumerate(emails, 1):
        formatted.append(f"{i}. {email}")
    
    return "\n".join(formatted)


def clean_markdown(text):
    """Ensure markdown is properly closed"""
    # Count and balance markdown formatting
    for marker in ['**', '__', '*', '_', '`', '```']:
        count = text.count(marker)
        if count % 2 != 0 and marker in ['**', '__', '*', '_', '`']:
            # Add closing marker if odd count
            text += marker
    
    return text


class RateLimiter:
    """Simple rate limiter for API calls"""
    
    def __init__(self, max_calls, time_window):
        """
        Initialize rate limiter
        
        Args:
            max_calls: Maximum number of calls allowed
            time_window: Time window in seconds
        """
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls = []
    
    def is_allowed(self):
        """Check if a call is allowed"""
        now = time.time()
        
        # Remove old calls outside the time window
        self.calls = [call_time for call_time in self.calls if now - call_time < self.time_window]
        
        if len(self.calls) < self.max_calls:
            self.calls.append(now)
            return True
        
        return False
    
    def wait_time(self):
        """Get time to wait before next call is allowed"""
        if not self.calls:
            return 0
        
        oldest_call = min(self.calls)
        wait = self.time_window - (time.time() - oldest_call)
        return max(0, wait)
