"""
Inbox Statistics Helper Utility.
Retrieves and prints current mailbox message totals.
"""
import os
import sys

# Ensure check_emails can be imported from current directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check_emails import get_gmail_service


def main():
    service = get_gmail_service()

    # Fetch INBOX label details
    inbox_info = service.users().labels().get(userId='me', id='INBOX').execute()
    total_messages = inbox_info.get('messagesTotal', 0)
    unread_messages = inbox_info.get('messagesUnread', 0)
    read_messages = total_messages - unread_messages

    # Fetch SPAM label details
    try:
        spam_info = service.users().labels().get(userId='me', id='SPAM').execute()
        spam_total = spam_info.get('messagesTotal', 0)
    except Exception:
        spam_total = "N/A"

    # Fetch TRASH label details
    try:
        trash_info = service.users().labels().get(userId='me', id='TRASH').execute()
        trash_total = trash_info.get('messagesTotal', 0)
    except Exception:
        trash_total = "N/A"

    print("=" * 40)
    print("📊 GMAIL MAILBOX SUMMARY")
    print("=" * 40)
    print(f"Total Inbox Messages:  {total_messages}")
    print(f"Unread Inbox Messages: {unread_messages}")
    print(f"Read Inbox Messages:   {read_messages}")
    print(f"Spam Messages:         {spam_total}")
    print(f"Trash Messages:        {trash_total}")
    print("=" * 40)


if __name__ == '__main__':
    main()
