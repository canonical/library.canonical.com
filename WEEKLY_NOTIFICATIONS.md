# Weekly Comment Notifications

## Overview

This feature automatically checks for documents modified in the last week that have unresolved comments, then sends notification emails to document owners grouped by owner.

## How It Works

1. **Weekly Scan**: Every Monday at 09:00 UTC, the system:
   - Fetches all documents modified in the last 7 days from Google Drive
   - Filters for Google Docs only (not folders or other file types)
   - Checks each document for unresolved comments

2. **Comment Check**: For each modified document:
   - Uses Google Drive Comments API to fetch all comments
   - Counts unresolved comments (resolved=false)
   - Skips documents with zero unresolved comments

3. **Owner Grouping**: Documents are grouped by owner email:
   - Each document can have multiple owners
   - A document appears in the email for all its owners
   - Owners only receive one email with all their documents

4. **Email Notification**: Each owner receives:
   - Summary of how many documents have comments
   - Total count of unresolved comments across all their documents
   - List of each document with:
     - Document name
     - Number of unresolved comments
     - Direct link to open the document

## Email Configuration

The system uses SMTP to send emails. Configure in `.env` or `.env.local`:

```bash
# SMTP Server Configuration
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587  # Use 465 for SSL, 587 for STARTTLS
SMTP_USER=your-email@canonical.com
SMTP_PASSWORD=your-app-password  # For Gmail, generate App Password

# Email Settings
EMAIL_FROM=library-notifications@canonical.com
```

### Google Workspace Setup

1. Go to [Google Account Security](https://myaccount.google.com/security)
2. Enable 2-Step Verification (required)
3. Go to [App Passwords](https://myaccount.google.com/apppasswords)
4. Create new app password for "Mail"
5. Copy the 16-character password to `SMTP_PASSWORD` in `.env.local`

## Google Drive API Permissions

The Service Account needs the following scopes:
- `https://www.googleapis.com/auth/drive` - Access Drive files
- `https://www.googleapis.com/auth/drive.comments.readonly` - Read comments

These scopes are automatically configured in `webapp/googledrive.py`.

## HTML View

You can view the current status of documents with unresolved comments in a web browser:

**URL**: `http://localhost:8051/notifications/weekly-comments-view`

The page displays:
- **Statistics**: Total modified documents, documents with comments, owners, and total comments
- **Documents grouped by owner**: Each owner's section shows all their documents with unresolved comments
- **Direct links**: Click "Review Comments" to open each document in Google Drive
- **Send notifications button**: Manually trigger email notifications from the page

This view is helpful for:
- Checking the current status without waiting for the weekly email
- Previewing what will be sent in the next scheduled notification
- Quick access to all documents needing attention

**Note**: This page requires authentication and shows real-time data from Google Drive.

## Manual Trigger

You can manually trigger the notification check at any time:

```bash
curl -X POST http://localhost:8051/notifications/weekly-comments
```

Or visit the URL in your browser (requires authentication).

### Response Format

```json
{
  "status": "success",
  "message": "Sent 5 notification(s) to 3 owner(s)",
  "stats": {
    "total_modified": 25,
    "with_comments": 8,
    "total_owners": 3,
    "emails_sent": 3,
    "emails_failed": 0,
    "total_comments": 15
  }
}
```

## Scheduled Job

The notification job runs automatically every Monday at 09:00 UTC. This is configured in `webapp/app.py` in the `init_scheduler()` function:

```python
scheduler.add_job(
    weekly_comment_notifications,
    trigger="cron",
    day_of_week="mon",
    hour=9,
    minute=0,
)
```

### Customizing the Schedule

To change when notifications are sent:

- **day_of_week**: "mon" (Monday), "tue", "wed", "thu", "fri", "sat", "sun"
- **hour**: 0-23 (UTC time)
- **minute**: 0-59

Example: Send on Wednesday at 14:30 UTC:
```python
day_of_week="wed",
hour=14,
minute=30,
```

## Architecture

### Components

1. **GoogleDrive Class** (`webapp/googledrive.py`):
   - `get_changes_last_week()` - Fetches modified documents from last 7 days
   - `get_document_comments(document_id)` - Gets all comments for a document
   - `get_unresolved_comments_count(document_id)` - Counts unresolved comments

2. **NotificationService Class** (`webapp/notification_service.py`):
   - `send_email()` - Sends individual emails via SMTP
   - `group_documents_by_owner()` - Groups documents by owner email
   - `generate_email_html()` - Creates HTML email content
   - `send_weekly_comment_notifications()` - Orchestrates the full process

3. **Flask Routes** (`webapp/app.py`):
   - `/notifications/weekly-comments` - Manual trigger endpoint

4. **Scheduled Job** (`webapp/app.py`):
   - `weekly_comment_notifications()` - Function called by scheduler

### Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Scheduled Job Trigger (Monday 09:00 UTC)                 │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. GoogleDrive.get_changes_last_week()                      │
│    - Queries Drive Changes API                              │
│    - Filters last 7 days                                    │
│    - Returns list of modified Google Docs                   │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. For each document:                                        │
│    GoogleDrive.get_unresolved_comments_count()              │
│    - Queries Drive Comments API                             │
│    - Counts unresolved comments                             │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. NotificationService.group_documents_by_owner()           │
│    - Groups documents by owner email                        │
│    - Creates owner → [documents] mapping                    │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. For each owner:                                           │
│    NotificationService.send_email()                         │
│    - Generates HTML email                                   │
│    - Sends via SMTP                                         │
└─────────────────────────────────────────────────────────────┘
```

## Email Template

The email is styled with Ubuntu fonts and Canonical orange (`#E95420`). It includes:

- **Header**: "Library Documents - Unresolved Comments"
- **Summary**: Total document and comment counts
- **Document List**: Each document in a card with:
  - Document name
  - Number of unresolved comments
  - "Review Comments" button linking to the document
- **Footer**: Timestamp and automated message notice

## Troubleshooting

### No emails being sent

1. Check SMTP credentials are set in `.env.local`:
   ```bash
   echo $SMTP_USER
   echo $SMTP_PASSWORD
   ```

2. Check application logs for SMTP errors:
   ```bash
   tail -f /path/to/app/logs
   ```

3. For Gmail, ensure App Password is used (not regular password)

### Comments not being detected

1. Verify Service Account has Comments API scope enabled
2. Check Service Account has access to the shared drive
3. Test manually:
   ```bash
   curl http://localhost:8051/notifications/weekly-comments
   ```

### Wrong owners receiving emails

- Google Drive API returns owners from file metadata
- Ensure document ownership is correctly set in Google Drive
- Check the response from manual trigger to see which owners are detected

### Emails going to spam

1. Configure SPF records for your domain
2. Use a verified sender email address
3. Consider using a proper transactional email service (SendGrid, AWS SES, etc.)

## Testing

### Test with manual trigger

```bash
# Trigger notification check
curl -X POST http://localhost:8051/notifications/weekly-comments

# Response shows stats
{
  "status": "success",
  "message": "Sent 2 notification(s) to 2 owner(s)",
  "stats": {
    "total_modified": 10,
    "with_comments": 3,
    "total_owners": 2,
    "emails_sent": 2,
    "emails_failed": 0,
    "total_comments": 7
  }
}
```

### Test email configuration

Create a test route in `webapp/app.py`:

```python
@app.route("/test-email")
def test_email():
    from webapp.notification_service import NotificationService
    service = NotificationService()
    
    test_docs = [{
        "id": "test123",
        "name": "Test Document",
        "unresolved_count": 5,
        "url": "https://docs.google.com/document/d/test123/edit"
    }]
    
    html = service.generate_email_html("test@example.com", test_docs)
    success = service.send_email(
        "your-email@canonical.com",
        "Test: Library Comment Notification",
        html
    )
    
    return f"Email sent: {success}"
```

## Future Enhancements

Possible improvements:

1. **Configurable timeframe**: Allow checking for different periods (3 days, 2 weeks, etc.)
2. **Comment context**: Include snippet of actual comment text in email
3. **Priority levels**: Flag urgent documents with many unresolved comments
4. **Digest opt-out**: Allow users to unsubscribe from notifications
5. **Slack integration**: Send notifications to Slack channels instead of/in addition to email
6. **Comment age**: Highlight comments that have been unresolved for a long time
7. **Summary dashboard**: Web page showing current status of all documents with comments
