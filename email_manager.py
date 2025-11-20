"""
Email utilities for Personal Assistant
"""
import logging
import smtplib
import imaplib
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional, Dict

logger = logging.getLogger(__name__)

class EmailManager:
    """Manages email operations with connection reuse"""
    
    def __init__(self, username: str, password: str, default_recipient: Optional[str] = None):
        self.username = username
        self.password = password
        self.default_recipient = default_recipient or username
        self._imap_connection = None
    
    def _get_imap_connection(self):
        """Get or create IMAP connection"""
        if self._imap_connection is None:
            try:
                self._imap_connection = imaplib.IMAP4_SSL("imap.gmail.com")
                self._imap_connection.login(self.username, self.password)
                logger.info("IMAP connection established")
            except Exception as e:
                logger.error(f"Failed to connect to IMAP: {e}")
                raise
        return self._imap_connection
    
    def close_imap_connection(self):
        """Close IMAP connection"""
        if self._imap_connection:
            try:
                self._imap_connection.logout()
                self._imap_connection = None
                logger.info("IMAP connection closed")
            except Exception as e:
                logger.warning(f"Error closing IMAP connection: {e}")
    
    def check_emails(self, filters: str = 'ALL', limit: int = 5) -> List[Dict[str, str]]:
        """
        Check emails with filters and return summaries
        
        Args:
            filters: IMAP search filters (e.g., 'ALL', 'UNSEEN', 'FROM "someone@example.com"')
            limit: Number of recent emails to return
            
        Returns:
            List of email summaries with subject, from, and date
        """
        try:
            mail = self._get_imap_connection()
            mail.select("inbox")
            
            # Search for emails
            status, messages = mail.search(None, filters)
            if status != 'OK':
                logger.warning(f"IMAP search failed with filters '{filters}', falling back to ALL")
                status, messages = mail.search(None, 'ALL')
                if status != 'OK':
                    raise Exception(f"IMAP search failed: {messages}")
            
            email_ids = messages[0].split()
            if not email_ids:
                return []
            
            # Get the last 'limit' emails
            email_ids_to_fetch = email_ids[-limit:] if len(email_ids) > limit else email_ids
            
            summaries = []
            for email_id in reversed(email_ids_to_fetch):  # Most recent first
                try:
                    status, msg_data = mail.fetch(email_id, "(RFC822)")
                    if status != 'OK':
                        continue
                    
                    msg = msg_data[0][1].decode("utf-8", errors="ignore")
                    
                    # Extract email headers
                    subject = self._extract_header(msg, "Subject")
                    from_addr = self._extract_header(msg, "From")
                    date = self._extract_header(msg, "Date")
                    
                    summaries.append({
                        'subject': subject,
                        'from': from_addr,
                        'date': date
                    })
                except Exception as e:
                    logger.warning(f"Failed to parse email {email_id}: {e}")
                    continue
            
            return summaries
            
        except Exception as e:
            logger.error(f"Error checking emails: {e}")
            raise
    
    @staticmethod
    def _extract_header(msg: str, header: str) -> str:
        """Extract a header value from email message"""
        for line in msg.split("\n"):
            if line.startswith(f"{header}:"):
                return line.split(": ", 1)[1].strip()
        return f"No {header}"
    
    def send_email(self, subject: str, body: str, recipient: Optional[str] = None) -> bool:
        """
        Send an email
        
        Args:
            subject: Email subject
            body: Email body
            recipient: Recipient email address (uses default if None)
            
        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            msg = MIMEMultipart()
            msg['From'] = self.username
            msg['To'] = recipient or self.default_recipient
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))
            
            with smtplib.SMTP('smtp.gmail.com', 587) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.sendmail(msg['From'], msg['To'], msg.as_string())
            
            logger.info(f"Email sent to {msg['To']}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending email: {e}")
            raise
    
    def format_email_summary(self, emails: List[Dict[str, str]]) -> str:
        """Format email summaries for display"""
        if not emails:
            return "No emails found."
        
        formatted = []
        for i, email in enumerate(emails, 1):
            formatted.append(
                f"{i}. **Subject:** {email['subject']}\n"
                f"   **From:** {email['from']}\n"
                f"   **Date:** {email['date']}"
            )
        
        return "\n\n".join(formatted)
