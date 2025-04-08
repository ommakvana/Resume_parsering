import os 
from pymongo import MongoClient
from datetime import datetime
from config import logger
import re
from urllib.parse import quote_plus
import html2text

username = "logbinary"
password = "LogBinary@123"
host = "192.168.1.41"
port = "27018"
auth_source = "admin"

# URL-encode the username and password
encoded_username = quote_plus(username)
encoded_password = quote_plus(password)

# Construct the MongoDB URI
MONGODB_URI = f"mongodb://{encoded_username}:{encoded_password}@{host}:{port}/?authSource={auth_source}"
# MongoDB connection settings
# MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://logbinary:LogBinary%40123@192.168.1.41:27018/?authSource=admin")
DB_NAME = os.getenv("MONGODB_DB", "logbinary_chatbot")

try:
    #connect to mongodb
    cilent = MongoClient(MONGODB_URI)
    db = cilent[DB_NAME]
    chat_history_collection = db["chat_history"]

    # Create indexes for efficient querying
    chat_history_collection.create_index("session_id")
    chat_history_collection.create_index("timestamp")

    logger.info(f"Connected to MongoDB database: {DB_NAME}")

except Exception as e:
    logger.error(f"Failed to connect to MongoDB: {str(e)}")
    raise

def extract_plain_text(html_content):
    """
    Extract plain text from HTML content
    """
    try:
        # Use html2text to convert HTML to markdown/plain text
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = True
        h.ignore_tables = False
        text = h.handle(html_content)
        
        # Clean up extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    except Exception as e:
        logger.error(f"Error extracting plain text from HTML: {e}")
        # Fallback to simple regex-based extraction if html2text fails
        try:
            # Remove style tags and their contents
            no_style = re.sub(r'<style[^>]*>.*?</style>', '', html_content, flags=re.DOTALL)
            # Remove script tags and their contents
            no_script = re.sub(r'<script[^>]*>.*?</script>', '', no_style, flags=re.DOTALL)
            # Remove HTML tags
            plain_text = re.sub(r'<[^>]*>', ' ', no_script)
            # Clean up whitespace
            clean_text = re.sub(r'\s+', ' ', plain_text).strip()
            return clean_text
        except:
            return "Error extracting text from HTML content"
        
def save_message(session_id, message_type, content, metadata=None):
    """
    Save a chat message to MongoDB
    
    Args:
        session_id (str): Unique identifier for the chat session
        message_type (str): Type of message (user, bot, form_submission, system)
        content (str): Message content (may include HTML for bot messages)
        metadata (dict, optional): Additional metadata about the message
    
    Returns:
        str: ID of the inserted document
    """
    try:
        if metadata is None:
            metadata = {}
            
        # For bot messages with HTML content, extract plain text and store it in metadata
        if message_type == "bot" and ("<div" in content or "<style" in content):
            plain_text = extract_plain_text(content)
            metadata["plain_text"] = plain_text
            metadata["content_type"] = "html"
            # Store the original content length
            metadata["content_length"] = len(content)
        # For user messages, just make sure we have the plain text version
        elif message_type == "user":
            # Check if the user message is HTML (unlikely but possible)
            if content.startswith("<") and (">" in content):
                plain_text = extract_plain_text(content)
                metadata["plain_text"] = plain_text
                metadata["content_type"] = "html"
            else:
                # Regular text message
                metadata["plain_text"] = content
                metadata["content_type"] = "text"
        
        document = {
            "session_id": session_id,
            "message_type": message_type,
            "content": content,
            "timestamp": datetime.now(),
            "metadata": metadata
        }
        
        result = chat_history_collection.insert_one(document)
        logger.debug(f"Saved message to MongoDB with ID: {result.inserted_id}")
        return str(result.inserted_id)
    except Exception as e:
        logger.error(f"Failed to save message to MongoDB: {str(e)}")
        return None
    
def get_chat_history(session_id):
    """
    Retrieve chat history for a session
    
    Args:
        session_id (str): Session ID to retrieve history for
        
    Returns:
        list: List of chat messages
    """
    try:
        cursor = chat_history_collection(
            {"session_id": session_id},
            {"_id": 0}
        ).sort ("timestamp",1)

        return list(cursor)
    
    except Exception as e:
        logger.error(f"failed to retrieve chat history from MongoDB: {str(e)}")
        return []
    
# Add these functions to your mongodb.py file

def get_user_messages(session_id):
    """
    Get only user messages from a specific chat session
    
    Args:
        session_id (str): Session ID to retrieve messages from
        
    Returns:
        list: List of user messages with timestamps
    """
    try:
        cursor = chat_history_collection.find(
            {
                "session_id": session_id, 
                "message_type": "user"
            },
            {
                "_id": 0,
                "content": 1,
                "timestamp": 1,
                "metadata": 1
            }
        ).sort("timestamp", 1)
        
        return list(cursor)
    except Exception as e:
        logger.error(f"Failed to retrieve user messages: {str(e)}")
        return []

def get_bot_messages(session_id):
    """
    Get only bot messages from a specific chat session
    
    Args:
        session_id (str): Session ID to retrieve messages from
        
    Returns:
        list: List of bot messages with timestamps
    """
    try:
        cursor = chat_history_collection.find(
            {
                "session_id": session_id, 
                "message_type": "bot"
            },
            {
                "_id": 0,
                "content": 1,
                "timestamp": 1,
                "metadata": 1
            }
        ).sort("timestamp", 1)
        
        return list(cursor)
    except Exception as e:
        logger.error(f"Failed to retrieve bot messages: {str(e)}")
        return []

def get_form_submissions(filter_criteria=None):
    """
    Get form submissions with optional filtering
    
    Args:
        filter_criteria (dict, optional): Additional MongoDB filter criteria
        
    Returns:
        list: List of form submissions
    """
    try:
        base_query = {"message_type": "form_submission"}
        
        if filter_criteria:
            base_query.update(filter_criteria)
            
        cursor = chat_history_collection.find(
            base_query,
            {"_id": 0}
        ).sort("timestamp", -1)  # Most recent first
        
        return list(cursor)
    except Exception as e:
        logger.error(f"Failed to retrieve form submissions: {str(e)}")
        return []

def search_conversations(query_text, days=30, limit=100):
    """
    Search for specific text in conversations
    
    Args:
        query_text (str): Text to search for
        days (int): Number of days to look back
        limit (int): Maximum number of results to return
        
    Returns:
        list: List of matching messages with session context
    """
    try:
        from datetime import datetime, timedelta
        cutoff_date = datetime.now() - timedelta(days=days)
        
        # Create text index if it doesn't already exist
        if "content_text" not in chat_history_collection.index_information():
            chat_history_collection.create_index([("content", "text")])
        
        # Find messages matching the text query
        cursor = chat_history_collection.find(
            {
                "$text": {"$search": query_text},
                "timestamp": {"$gte": cutoff_date}
            },
            {
                "score": {"$meta": "textScore"},
                "_id": 0,
                "session_id": 1,
                "message_type": 1,
                "content": 1, 
                "timestamp": 1
            }
        ).sort([("score", {"$meta": "textScore"})]).limit(limit)
        
        results = list(cursor)
        
        # Add surrounding messages for context
        conversations = []
        for result in results:
            session_id = result["session_id"]
            timestamp = result["timestamp"]
            
            # Get messages before and after the matching message
            context_before = list(chat_history_collection.find(
                {
                    "session_id": session_id,
                    "timestamp": {"$lt": timestamp}
                }
            ).sort("timestamp", -1).limit(2))
            
            context_after = list(chat_history_collection.find(
                {
                    "session_id": session_id,
                    "timestamp": {"$gt": timestamp}
                }
            ).sort("timestamp", 1).limit(2))
            
            conversation = {
                "matching_message": result,
                "context_before": sorted(context_before, key=lambda x: x["timestamp"]),
                "context_after": context_after,
                "session_id": session_id
            }
            
            conversations.append(conversation)
            
        return conversations
    except Exception as e:
        logger.error(f"Error searching conversations: {e}")
        return []

def delete_old_conversations(days=90):
    """
    Delete conversations older than the specified number of days
    
    Args:
        days (int): Age threshold in days for deletion
        
    Returns:
        int: Number of deleted documents
    """
    try:
        from datetime import datetime, timedelta
        cutoff_date = datetime.now() - timedelta(days=days)
        
        # Find sessions that are old enough to delete
        old_sessions = chat_history_collection.distinct(
            "session_id", 
            {"timestamp": {"$lt": cutoff_date}}
        )
        
        if not old_sessions:
            return 0
            
        # Delete all messages from those sessions
        result = chat_history_collection.delete_many(
            {"session_id": {"$in": old_sessions}}
        )
        
        logger.info(f"Deleted {result.deleted_count} messages from {len(old_sessions)} old sessions")
        return result.deleted_count
    except Exception as e:
        logger.error(f"Error deleting old conversations: {e}")
        return 0