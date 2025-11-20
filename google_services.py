"""
Google services integration (Sheets, Tasks, Calendar, Search)
"""
import logging
import json
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2 import service_account
import requests

logger = logging.getLogger(__name__)

class GoogleServicesManager:
    """Manages all Google service integrations"""
    
    def __init__(self, api_key: str, service_account_file: Optional[str] = None, 
                 custom_search_cx: Optional[str] = None):
        self.api_key = api_key
        self.custom_search_cx = custom_search_cx
        
        # Initialize Google services if service account file is provided
        self.sheets_service = None
        self.tasks_service = None
        self.calendar_service = None
        
        if service_account_file:
            self._initialize_services(service_account_file)
    
    def _initialize_services(self, service_account_file: str):
        """Initialize Google services with service account"""
        try:
            scopes = [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/tasks',
                'https://www.googleapis.com/auth/calendar'
            ]
            credentials = service_account.Credentials.from_service_account_file(
                service_account_file, scopes=scopes
            )
            
            self.sheets_service = build('sheets', 'v4', credentials=credentials)
            self.tasks_service = build('tasks', 'v1', credentials=credentials)
            self.calendar_service = build('calendar', 'v3', credentials=credentials)
            
            logger.info("Google services initialized successfully")
        except Exception as e:
            logger.warning(f"Could not initialize Google services: {e}")
    
    # Google Search
    def search(self, query: str, num_results: int = 5) -> List[Dict[str, str]]:
        """
        Perform Google Custom Search
        
        Args:
            query: Search query
            num_results: Number of results to return
            
        Returns:
            List of search results with title, link, and snippet
        """
        if not self.custom_search_cx:
            raise ValueError("Custom Search CX not configured")
        
        try:
            url = "https://www.googleapis.com/customsearch/v1"
            params = {
                "key": self.api_key,
                "cx": self.custom_search_cx,
                "q": query,
                "num": min(num_results, 10)  # API limit is 10
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            results = response.json().get("items", [])
            return [
                {
                    'title': result.get('title', 'No title'),
                    'link': result.get('link', ''),
                    'snippet': result.get('snippet', '')
                }
                for result in results[:num_results]
            ]
            
        except requests.RequestException as e:
            logger.error(f"Search error: {e}")
            raise
    
    def format_search_results(self, results: List[Dict[str, str]]) -> str:
        """Format search results for display"""
        if not results:
            return "No search results found."
        
        formatted = []
        for i, result in enumerate(results, 1):
            formatted.append(
                f"{i}. **{result['title']}**\n"
                f"   {result['link']}\n"
                f"   _{result['snippet']}_"
            )
        
        return "\n\n".join(formatted)
    
    # Google Sheets
    def update_sheet(self, spreadsheet_id: str, range_name: str, 
                     values: List[List[Any]]) -> bool:
        """
        Update Google Sheets with values
        
        Args:
            spreadsheet_id: The spreadsheet ID
            range_name: Range in A1 notation (e.g., 'Sheet1!A1:D')
            values: 2D list of values to write
            
        Returns:
            True if successful
        """
        if not self.sheets_service:
            raise RuntimeError("Google Sheets service not initialized")
        
        try:
            body = {'values': values}
            self.sheets_service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption="RAW",
                body=body
            ).execute()
            
            logger.info(f"Updated sheet {spreadsheet_id} range {range_name}")
            return True
            
        except HttpError as e:
            logger.error(f"Sheets API error: {e}")
            raise
    
    def read_sheet(self, spreadsheet_id: str, range_name: str) -> List[List[Any]]:
        """
        Read values from Google Sheets
        
        Args:
            spreadsheet_id: The spreadsheet ID
            range_name: Range in A1 notation
            
        Returns:
            2D list of values
        """
        if not self.sheets_service:
            raise RuntimeError("Google Sheets service not initialized")
        
        try:
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=range_name
            ).execute()
            
            return result.get('values', [])
            
        except HttpError as e:
            logger.error(f"Sheets API error: {e}")
            raise
    
    # Google Tasks
    def add_task(self, title: str, due_date: Optional[datetime] = None,
                 notes: Optional[str] = None) -> bool:
        """
        Add a task to Google Tasks
        
        Args:
            title: Task title
            due_date: Optional due date
            notes: Optional notes
            
        Returns:
            True if successful
        """
        if not self.tasks_service:
            raise RuntimeError("Google Tasks service not initialized")
        
        try:
            # Get default task list
            tasklists = self.tasks_service.tasklists().list().execute()
            tasklist_id = tasklists.get('items', [])[0]['id'] if tasklists.get('items') else None
            
            if not tasklist_id:
                raise RuntimeError("No task list found")
            
            task = {'title': title}
            if due_date:
                task['due'] = due_date.isoformat() + 'Z'
            if notes:
                task['notes'] = notes
            
            self.tasks_service.tasks().insert(
                tasklist=tasklist_id,
                body=task
            ).execute()
            
            logger.info(f"Added task: {title}")
            return True
            
        except HttpError as e:
            logger.error(f"Tasks API error: {e}")
            raise
    
    # Google Calendar
    def schedule_event(self, summary: str, start_time: datetime, 
                      end_time: datetime, attendees: Optional[List[str]] = None,
                      description: Optional[str] = None) -> Dict[str, Any]:
        """
        Schedule an event in Google Calendar
        
        Args:
            summary: Event summary/title
            start_time: Event start time
            end_time: Event end time
            attendees: List of attendee email addresses
            description: Event description
            
        Returns:
            Event details
        """
        if not self.calendar_service:
            raise RuntimeError("Google Calendar service not initialized")
        
        try:
            event = {
                'summary': summary,
                'start': {
                    'dateTime': start_time.isoformat(),
                    'timeZone': 'Asia/Kolkata'
                },
                'end': {
                    'dateTime': end_time.isoformat(),
                    'timeZone': 'Asia/Kolkata'
                }
            }
            
            if attendees:
                event['attendees'] = [{'email': email} for email in attendees]
            
            if description:
                event['description'] = description
            
            result = self.calendar_service.events().insert(
                calendarId='primary',
                body=event
            ).execute()
            
            logger.info(f"Scheduled event: {summary}")
            return result
            
        except HttpError as e:
            logger.error(f"Calendar API error: {e}")
            raise
