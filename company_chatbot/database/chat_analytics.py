from mongodb import chat_history_collection
from datetime import datetime, timedelta
from bson import ObjectId
from config import logger

def get_conversation_by_id(session_id):
    """
    Retrieve a complete conversation by session ID
    
    Args:
        session_id (str): Session ID to retrieve
        
    Returns:
        list: List of messages in the conversation
    """
    try :
        message = list(chat_history_collection.find(
            {"session_id": session_id}
        ).sort("timestamp", 1)
        )

        return message
    except Exception as e:
        logger.error(f"Error reteiving conversation :{e}")
        return []
    
def get_recent_conversations(days=7,limit=100):
    """
    Get recent conversations within the specified time period
    
    Args:
        days (int): Number of days to look back
        limit (int): Maximum number of sessions to return
        
    Returns:
        list: List of unique session IDs with their start time
    """
    try:
        cutoff_time = datetime.now() - timedelta(days=days)

        #Find the first message of each session
        pipeline = [
            {"$match": {"timestamp": {"$gte": cutoff_time}}},
            {"$sort": {"timestamp": 1,}},
            {"$group": {
                "_id": "$session_id",
                "start_time" : {"$first": "$timestamp"},
                "message_count" : {"$sum": 1}
            }},
            {"$sort": {"start_time": -1}},
            {"$limit": limit}
        ]
        result = list(chat_history_collection.aggregate(pipeline))
        return result
    except Exception as e:
        logger.error(f"Error retrieving recent conversations: {e}")
        return []
    
def get_conversation_by_date(days=30):
    """
    Get statistics about conversations
    
    Args:
        days (int): Number of days to analyze
        
    Returns:
        dict: Statistics about conversations
    """
    try:
        cutoff_date = datetime.now() - timedelta(days=days)

        #count total session
        total_sessions = len(set(chat_history_collection.distinct(
            "session_id",
            {"timestamp": {"$gte": cutoff_date}}
        )))

        #count total messages
        total_message = chat_history_collection.count_documents(
            {"timestamp": {"$gte": cutoff_date}}
        )

        #count messages by type
        user_messages = chat_history_collection.count_documents({
            "timestamp": {"$gte": cutoff_date},
            "message_type": "user"
        })

        bot_messages = chat_history_collection.count_documents({
            "timestamp": {"$gte": cutoff_date},
            "message_type": "bot"
        })

        #count from submissions
        services_inquiries = chat_history_collection.count_documents({
            "timestamp": {"$gte": cutoff_date},
            "message_type": "form_submission",
            "metadata.form_type": "service_inquiry"
        })

        job_applications = chat_history_collection.count_documents({
            "timestamp": {"$gte": cutoff_date},
            "message_type": "form_submission",
            "metadata.form_type": "job_application"
        })

        #calculate averages
        messages_per_session = total_message / total_sessions if total_sessions > 0 else 0 

        return {
            "period_days": days,
            "total_sessions" : total_sessions,
            "total_messages" : total_message,
            "user_messages" : user_messages,
            "bot_messages" : bot_messages,
            "services_inquiries" : services_inquiries,
            "job_applications" : job_applications,
            "messages_per_session" : messages_per_session,
        }
    except Exception as e:
        logger.error(f"Error generating conversation statistics: {e}")
        return {}