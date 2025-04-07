import json
import asyncio
from fastapi import WebSocket, WebSocketDisconnect
from chatbot import CompanyAIChatbot
from config import logger
import traceback

async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        chatbot = CompanyAIChatbot()
        welcome_message = f"""
        {chatbot.chat_styles}
        <div class="welcome-message">
            Hi there! 👋 <strong class="highlight">I'm LogBinary's virtual assistant</strong>. How can I help you today?
        </div>
        """
        await websocket.send_text(welcome_message)
        while True:
            data = await websocket.receive_text()
            logger.info(f"Received message: {data}")
            
            await websocket.send_text("Typing...")
            
            if data.startswith('{') and data.endswith('}'):
                try:
                    message_data = json.loads(data)
                    # Handle service inquiry submission
                    if message_data.get("action") == "submit_inquiry":
                        inquiry_data = message_data["data"]
                        tool = next(t for t in chatbot.agent.tools.values() if t.name == "submit_service_inquiry")
                        result = tool._run(
                            name=inquiry_data.get("Your_name", inquiry_data.get("name", "")),
                            email=inquiry_data["email"],
                            phone=inquiry_data["phone"],
                            subject=inquiry_data["subject"],
                            message=inquiry_data["message"]
                        )
                        # Send confirmation message
                        # confirmation = f"""
                        # {chatbot.chat_styles}
                        # <div class="inquiry-confirmation">
                        #     <p>Thank you for your inquiry! We've received your information and will get back to you soon.</p>
                        # </div>
                        # """
                        # await websocket.send_text(confirmation)
                        continue
                    
                    # Handle job application submission
                    elif message_data.get("action") == "submit_job_application":
                        from tools import SubmitJobApplicationTool
                        application_data = message_data["data"]
                        tool = SubmitJobApplicationTool()
                        logger.info(f"Calling SubmitJobApplicationTool._run with: {application_data}")
                        result = tool._run(
                            name=application_data["name"],
                            email=application_data["email"],
                            phone=application_data["phone"],
                            resume_file=application_data["resume_file"]
                        )
                        # Send confirmation message
                        # confirmation = f"""
                        # {chatbot.chat_styles}
                        # <div class="application-confirmation">
                        #     <p>Thank you for your application! We've received your information and will review your qualifications soon.</p>
                        # </div>
                        # """
                        # await websocket.send_text(confirmation)
                        continue
                        
                except json.JSONDecodeError:
                    logger.error("Invalid JSON received")
                except Exception as e:
                    logger.error(f"Error processing form submission: {e}")
                    logger.error(traceback.format_exc())
                    error_message = f"""
                    {chatbot.chat_styles}
                    <div class="error-message">
                        <p>There was an error processing your submission. Please try again or contact us directly.</p>
                    </div>
                    """
                    await websocket.send_text(error_message)
                    continue
            
            response = await chatbot.process_message(data)
            await asyncio.sleep(0.5)
            logger.info(f"Sending response: {response[:100]}...")
            await websocket.send_text(response)
    except WebSocketDisconnect:
        logger.info("Client disconnected")
    except Exception as e:
        logger.error(f"Error in websocket: {e}")
        logger.error(traceback.format_exc())
        try:
            await websocket.send_text("I'm having trouble processing your request. Please try again or contact our support team directly.")
        except:
            logger.error("Failed to send error message")