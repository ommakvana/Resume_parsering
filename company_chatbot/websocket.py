import json
import asyncio
import uuid
from fastapi import WebSocket, WebSocketDisconnect
from chatbot import CompanyAIChatbot
from config import logger
import traceback
from database.mongodb import save_message
import re

def clean_html_styles(html_content):
    """
    Extract just the content part of HTML responses, removing redundant styles
    
    This keeps the <style> tag content separate in the metadata instead of 
    duplicating it with every message.
    """
    try:
        # Check if this is HTML content
        if not (html_content.strip().startswith("<") and "<style" in html_content):
            return html_content
            
        # Extract style content
        style_match = re.search(r'<style>(.*?)</style>', html_content, re.DOTALL)
        style_content = style_match.group(1) if style_match else ""
        
        # Remove style tag and its content
        content_without_style = re.sub(r'<style>.*?</style>', '', html_content, flags=re.DOTALL)
        
        return {
            "content": content_without_style.strip(),
            "style": style_content.strip()
        }
    except Exception as e:
        logger.error(f"Error cleaning HTML styles: {e}")
        return html_content
    

async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    # Generate a unique session ID for this connection
    session_id = str(uuid.uuid4())
    logger.info(f"New WebSocket connection established: {session_id}")
    
    try:
        chatbot = CompanyAIChatbot()
        welcome_message = f"""
        {chatbot.chat_styles}
        <div class="welcome-message">
            Hi there! 👋 <strong class="highlight">I'm LogBinary's virtual assistant</strong>. How can I help you today?
        </div>
        """
        
        # Save welcome message to MongoDB
        save_message(
            session_id=session_id,
            message_type="bot",
            content=welcome_message,
            metadata={"message_category": "welcome"}
        )
        
        await websocket.send_text(welcome_message)
        
        while True:
            data = await websocket.receive_text()
            logger.info(f"Received message: {data[:100]}...")  # Truncate long messages in logs
            
            # Process and store user message
            try:
                # Check if the message is JSON (form submission or structured data)
                if data.startswith('{') and data.endswith('}'):
                    try:
                        message_data = json.loads(data)
                        if message_data.get("action") == "submit_inquiry":
                            inquiry_data = message_data["data"]
                            # Save form submission to MongoDB
                            save_message(
                                session_id=session_id,
                                message_type="form_submission",
                                content="Service inquiry form submitted",
                                metadata={
                                    "form_type": "service_inquiry",
                                    "form_data": inquiry_data
                                }
                            )
                            
                            tool = next(t for t in chatbot.agent.tools.values() if t.name == "submit_service_inquiry")
                            result = tool._run(
                                name=inquiry_data.get("Your_name", inquiry_data.get("name", "")),
                                email=inquiry_data["email"],
                                phone=inquiry_data["phone"],
                                subject=inquiry_data["subject"],
                                message=inquiry_data["message"]
                            )
                            
                            # Create and save confirmation response
                            # confirmation = f"""
                            # {chatbot.chat_styles}
                            # <div class="inquiry-confirmation">
                            #     <p>Thank you for your inquiry! We've received your information and will get back to you soon.</p>
                            # </div>
                            # """
                            
                            save_message(
                                session_id=session_id,
                                message_type="bot",
                                content="Thank you for your inquiry! We've received your information and will get back to you soon.",
                                metadata={"message_category": "form_confirmation"}
                            )
                            
                            # await websocket.send_text(confirmation)
                            continue
                            
                        elif message_data.get("action") == "submit_job_application":
                            from tools import SubmitJobApplicationTool
                            application_data = message_data["data"]
                            
                            # Save job application to MongoDB
                            save_message(
                                session_id=session_id,
                                message_type="form_submission",
                                content="Job application form submitted",
                                metadata={
                                    "form_type": "job_application",
                                    "form_data": {k: v for k, v in application_data.items() if k != "resume_file"},
                                    "resume_filename": application_data.get("resume_file", "")
                                }
                            )
                            
                            # Process the job application
                            tool = SubmitJobApplicationTool()
                            logger.info(f"Calling SubmitJobApplicationTool._run with: {application_data}")
                            result = tool._run(
                                name=application_data["name"],
                                email=application_data["email"],
                                phone=application_data["phone"],
                                resume_file=application_data["resume_file"]
                            )
                            
                            # # Create and save confirmation response
                            # confirmation = f"""
                            # {chatbot.chat_styles}
                            # <div class="application-confirmation">
                            #     <p>Thank you for your application! We've received your information and will review your qualifications soon.</p>
                            # </div>
                            # """
                            
                            save_message(
                                session_id=session_id,
                                message_type="bot",
                                content="Thank you for your application! We've received your information and will review your qualifications soon.",
                                metadata={"message_category": "form_confirmation"}
                            )
                            
                            # await websocket.send_text(confirmation)
                            continue
                        
                        # For other JSON messages, try to extract meaningful content
                        elif "message" in message_data:
                            user_content = message_data["message"]
                        elif "input" in message_data:
                            user_content = message_data["input"]
                        else:
                            # If we can't identify specific fields, store the raw JSON
                            user_content = data
                    except json.JSONDecodeError:
                        # If JSON parsing fails, treat as plain text
                        user_content = data
                else:
                    # Plain text message
                    user_content = data
                
                # Save user message to MongoDB
                save_message(
                    session_id=session_id,
                    message_type="user",
                    content=user_content,
                    metadata={"raw_message": data}
                )
                
            except Exception as e:
                logger.error(f"Error processing user message: {e}")
                logger.error(traceback.format_exc())
                # Still save the raw message
                save_message(
                    session_id=session_id,
                    message_type="user",
                    content=data,
                    metadata={"error_processing": str(e)}
                )
            
            # Send typing indicator
            await websocket.send_text("Typing...")
            
            # If it's JSON data and we've already handled it above, continue to next iteration
            if data.startswith('{') and data.endswith('}'):
                try:
                    message_data = json.loads(data)
                    if message_data.get("action") in ["submit_inquiry", "submit_job_application"]:
                        # We've already processed this form submission above
                        continue
                except:
                    # If JSON parsing fails, continue with normal message processing
                    pass
            
            # Process message through chatbot
            response = await chatbot.process_message(data)
            await asyncio.sleep(0.5)
            logger.info(f"Sending response: {response[:100]}...")
            
            # Clean HTML and save bot response to MongoDB
            if response.strip().startswith("<") and "<style" in response:
                cleaned = clean_html_styles(response)
                if isinstance(cleaned, dict):
                    save_message(
                        session_id=session_id,
                        message_type="bot",
                        content=cleaned["content"],
                        metadata={
                            "response_length": len(response),
                            "style": cleaned["style"],
                            "has_style": True
                        }
                    )
                else:
                    # If cleaning failed, save the original
                    save_message(
                        session_id=session_id,
                        message_type="bot",
                        content=response,
                        metadata={"response_length": len(response)}
                    )
            else:
                # For non-HTML responses
                save_message(
                    session_id=session_id,
                    message_type="bot",
                    content=response,
                    metadata={"response_length": len(response)}
                )

            await websocket.send_text(response)
            
    except WebSocketDisconnect:
        logger.info(f"Client disconnected: {session_id}")
        
        # Save disconnect event to MongoDB
        save_message(
            session_id=session_id,
            message_type="system",
            content="User disconnected",
            metadata={"event_type": "disconnect"}
        )
        
    except Exception as e:
        logger.error(f"Error in websocket: {e}")
        logger.error(traceback.format_exc())
        
        # Save error to MongoDB
        save_message(
            session_id=session_id,
            message_type="system",
            content="System error",
            metadata={"error": str(e), "traceback": traceback.format_exc()}
        )
        
        try:
            error_message = "I'm having trouble processing your request. Please try again or contact our support team directly."
            
            # Save error message to MongoDB
            save_message(
                session_id=session_id,
                message_type="bot",
                content=error_message,
                metadata={"message_category": "error"}
            )
            
            await websocket.send_text(error_message)
        except:
            logger.error("Failed to send error message")