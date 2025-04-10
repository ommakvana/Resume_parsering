import argparse
from datetime import datetime, timedelta
from chat_analytics import get_recent_conversations, get_conversation_by_id, get_conversation_by_date
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax
from rich.markdown import Markdown
from rich import box
import html2text
import re

console = Console()

def format_timestamp(timestamp):
    """Format timestamp to readable format"""
    return timestamp.strftime("%Y-%m-%d %H:%M:%S")

def get_display_content(message):
    """Get the appropriate display content from a message"""
    # First check if we have plain text in metadata
    if "metadata" in message and message["metadata"] and "plain_text" in message["metadata"]:
        return message["metadata"]["plain_text"]
    
    # Otherwise, try to extract text from content
    content = message["content"]
    
    # If it looks like HTML, convert it to plain text
    if content.strip().startswith("<") and (">" in content):
        h = html2text.HTML2Text()
        h.ignore_links = False
        return h.handle(content)
    
    # Otherwise return as is
    return content

def view_recent_sessions(days=7, limit=10):
    """View recent chat sessions"""
    console.print(f"[bold]Recent Chat Sessions (Past {days} days)[/bold]")
    
    recent_sessions = get_recent_conversations(days=days, limit=limit)
    
    if not recent_sessions:
        console.print("[italic]No recent sessions found[/italic]")
        return
    
    table = Table(box=box.ROUNDED)
    table.add_column("Session ID", style="cyan")
    table.add_column("Start Time", style="green")
    table.add_column("Messages", style="yellow")
    
    for session in recent_sessions:
        table.add_row(
            session["_id"],
            format_timestamp(session["start_time"]),
            str(session["message_count"])
        )
    
    console.print(table)
    console.print("\nUse --session <SESSION_ID> to view a specific conversation\n")

def view_session(session_id):
    """View a specific chat session"""
    conversation = get_conversation_by_id(session_id)
    
    if not conversation:
        console.print(f"[bold red]No conversation found with ID: {session_id}[/bold red]")
        return
    
    start_time = min(msg["timestamp"] for msg in conversation)
    end_time = max(msg["timestamp"] for msg in conversation)
    duration = end_time - start_time
    
    console.print(Panel(
        f"Chat Session: {session_id}\n"
        f"Started: {format_timestamp(start_time)}\n"
        f"Duration: {duration}\n"
        f"Messages: {len(conversation)}",
        title="Conversation Details",
        border_style="blue"
    ))
    
    for i, msg in enumerate(conversation):
        message_type = msg["message_type"]
        timestamp = format_timestamp(msg["timestamp"])
        
        if message_type == "user":
            content = get_display_content(msg)
            console.print(f"[{timestamp}] [bold blue]User:[/bold blue]")
            console.print(Panel(content, border_style="blue", width=100))
        
        elif message_type == "bot":
            content = get_display_content(msg)
            
            # Content might be markdown or plain text
            if "**" in content or "_" in content:
                try:
                    md = Markdown(content)
                    console.print(f"[{timestamp}] [bold green]Bot:[/bold green]")
                    console.print(Panel(md, border_style="green", width=100))
                except:
                    console.print(f"[{timestamp}] [bold green]Bot:[/bold green]")
                    console.print(Panel(content, border_style="green", width=100))
            else:
                console.print(f"[{timestamp}] [bold green]Bot:[/bold green]")
                console.print(Panel(content, border_style="green", width=100))
            
            # Show some metadata if present
            if "metadata" in msg and msg["metadata"]:
                if "content_type" in msg["metadata"] and msg["metadata"]["content_type"] == "html":
                    console.print("[dim](HTML content)[/dim]")
                if "content_length" in msg["metadata"]:
                    console.print(f"[dim](Content length: {msg['metadata']['content_length']} characters)[/dim]")
        
        elif message_type == "form_submission":
            form_type = msg.get("metadata", {}).get("form_type", "Unknown")
            console.print(f"[{timestamp}] [bold yellow]Form Submission:[/bold yellow] {form_type}")
            
            form_data = msg.get("metadata", {}).get("form_data", {})
            if form_data:
                data_table = Table(box=box.SIMPLE)
                data_table.add_column("Field", style="yellow")
                data_table.add_column("Value", style="white")
                
                for key, value in form_data.items():
                    # Truncate very long values
                    value_str = str(value)
                    if len(value_str) > 50:
                        value_str = value_str[:47] + "..."
                    data_table.add_row(key, value_str)
                
                console.print(data_table)
        
        elif message_type == "system":
            console.print(f"[{timestamp}] [bold red]System:[/bold red] {msg['content']}")
            
        # Add a separator between messages
        if i < len(conversation) - 1:
            console.print("─" * 100)

def view_statistics(days=30):
    """View conversation statistics"""
    stats = get_conversation_by_date(days=days)
    
    if not stats:
        console.print("[bold red]Error retrieving statistics[/bold red]")
        return
    
    console.print(Panel(
        f"Period: Past {stats['period_days']} days\n"
        f"Total Sessions: {stats['total_sessions']}\n"
        f"Total Messages: {stats['total_messages']}\n"
        f"User Messages: {stats['user_messages']}\n"
        f"Bot Messages: {stats['bot_messages']}\n"
        f"Service Inquiries: {stats['service_inquiries']}\n"
        f"Job Applications: {stats['job_applications']}\n"
        f"Messages per Session: {stats['messages_per_session']}",
        title="Chat Statistics",
        border_style="green"
    ))

def search_chats(query, days=30, limit=20):
    """Search for text in chat histories"""
    from mongodb import search_conversations
    
    console.print(f'[bold]Searching for "{query}" in chats from the past {days} days[/bold]')
    
    results = search_conversations(query, days=days, limit=limit)
    
    if not results:
        console.print("[italic]No matches found[/italic]")
        return
        
    console.print(f"[green]Found {len(results)} matching conversations[/green]")
    
    for i, result in enumerate(results):
        matching_msg = result["matching_message"]
        session_id = result["session_id"]
        msg_type = matching_msg["message_type"]
        timestamp = format_timestamp(matching_msg["timestamp"])
        
        # Display header
        console.print(f"\n[bold cyan]Match {i+1} - Session {session_id} - {timestamp}[/bold cyan]")
        
        # Display context before
        if result["context_before"]:
            console.print("[dim]--- Context before ---[/dim]")
            for ctx_msg in result["context_before"]:
                ctx_type = ctx_msg["message_type"]
                ctx_content = get_display_content(ctx_msg)
                ctx_time = format_timestamp(ctx_msg["timestamp"])
                console.print(f"[{ctx_time}] [dim]{ctx_type.upper()}:[/dim] {ctx_content[:100]}...")
        
        # Display matching message
        content = get_display_content(matching_msg)
        console.print(f"[bold yellow]--- MATCHING MESSAGE ({msg_type.upper()}) ---[/bold yellow]")
        console.print(Panel(content, border_style="yellow"))
        
        # Display context after
        if result["context_after"]:
            console.print("[dim]--- Context after ---[/dim]")
            for ctx_msg in result["context_after"]:
                ctx_type = ctx_msg["message_type"]
                ctx_content = get_display_content(ctx_msg)
                ctx_time = format_timestamp(ctx_msg["timestamp"])
                console.print(f"[{ctx_time}] [dim]{ctx_type.upper()}:[/dim] {ctx_content[:100]}...")
        
        # Display separator between results
        if i < len(results) - 1:
            console.print("\n" + "═" * 100)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Chat History Viewer")
    parser.add_argument("--recent", type=int, help="Show recent sessions (number of days)")
    parser.add_argument("--session", type=str, help="View specific session by ID")
    parser.add_argument("--stats", type=int, help="Show statistics for the specified days")
    parser.add_argument("--search", type=str, help="Search for text in chat histories")
    parser.add_argument("--days", type=int, default=30, help="Number of days to look back for search")
    parser.add_argument("--limit", type=int, default=10, help="Limit number of results")
    
    args = parser.parse_args()
    
    if args.session:
        view_session(args.session)
    elif args.recent is not None:
        view_recent_sessions(days=args.recent, limit=args.limit)
    elif args.stats is not None:
        view_statistics(days=args.stats)
    elif args.search:
        search_chats(args.search, days=args.days, limit=args.limit)
    else:
        # Default to showing recent sessions from the past 7 days
        view_recent_sessions(days=7, limit=args.limit)