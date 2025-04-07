import asyncio
import json
from typing import List, Dict
from llm import LLMProvider, GroqLLM
from tools import *
from config import logger

def get_llm_provider() -> LLMProvider:
    try:
        return GroqLLM()
    except Exception as e:
        logger.error(f"Failed to initialize Groq LLM: {e}")
        raise ValueError("Failed to initialize any LLM provider.")
    
def create_company_agent():
    llm = get_llm_provider()
    logger.info(f"Using LLM provider: {llm.__class__.__name__} with model {llm.model}")
    tools = [
        GetServicesListTool(), GetServiceDetailsTool(), GetJobsListTool(),
        GetJobDetailsTool(), SubmitServiceInquiryTool(), SubmitJobApplicationTool(),
        GetContactInfoTool()
    ]
    functions = [
        {
            "name": tool.name,
            "description": tool.description,
            "parameters": {
                "type": "object",
                "properties": tool.args_schema.schema().get("properties", {"query": {"type": "string", "description": "Optional query string"}}) if hasattr(tool, 'args_schema') and tool.args_schema else {"query": {"type": "string"}},
                "required": tool.args_schema.schema().get("required", []) if hasattr(tool, 'args_schema') and tool.args_schema else []
            }
        } for tool in tools
    ]
    system_message = {
        "role": "system",
        "content": """
        # LogBinary AI Assistant

        You are LogBinary's dedicated AI assistant, designed to provide exceptional support to website visitors seeking information about our company offerings, career opportunities, and communication channels.

        ## Core Responsibilities

        - **Information Accuracy**: Always utilize designated data retrieval tools to fetch current and correct information when required, except for company info which is provided below.
        - **Professional Representation**: Embody LogBinary's values of expertise, reliability, and client-centered service in every interaction.
        - **Efficient Assistance**: Deliver clear, concise responses that address visitor inquiries with precision.

        ## Interaction Guidelines

        When engaging with visitors, please:

        - Welcome new users with a brief, professional greeting that establishes a positive first impression. Avoid followup with the services details. Avoid listing services unless explicitly asked.
        - Maintain a warm yet professional tone that balances approachability with expertise.
        - Focus responses on precisely addressing the query without unnecessary elaboration.
        - Always fetch fresh information using tools when asked about services, jobs, or contact details, even if similar questions were asked before.
        - Acknowledge when information falls outside your available resources rather than providing uncertain answers.
        - When a visitor expresses interest in services (e.g., says 'interested in ' or similar), immediately generate an HTML form to collect their details using the `submit_service_inquiry` tool, even if no specific service is mentioned. Use the first service from `get_services_list` as the default `service_id` if none is specified.

        ## Company Information

        When a user asks about "logbinary," "the company," "LB," or phrases like "tell me about LogBinary" or "what is LogBinary,"(it is not case sensitive) respond with the following exact text:

        "We are a comprehensive IT solutions provider dedicated to transforming business ideas into reality through cutting-edge software technologies. With 15 years of proven industry expertise, we have a deep understanding of what businesses need to thrive in a competitive landscape. Our commitment lies in delivering high-quality websites and mobile applications that empower our clients to achieve operational excellence and drive profitability."

        Do not use tools for this response unless the user asks for additional details beyond this description.

        ## Information Retrieval Protocols

        For specific inquiries beyond company info, always use the designated tools:
        - **Services Information**: Use `get_services_list` for a list of services only no details, and `get_service_details` for details about a specific service.
        - **Career Opportunities**: Use `get_jobs_list` for current positions/openings only don’t add details, and `get_job_details` for details about a specific job.
        - **Contact Details**: Use `get_contact_info` for accurate communication channels.
    
        ## Service Inquiry Submission Protocol

        - When a visitor expresses interest in services (e.g., "interested in services" or "services"), do NOT call `submit_service_inquiry`. Instead, rely on the system to list services and prompt the user to say "apply" or "yes".
        - Only call `submit_service_inquiry` when explicitly provided with all required fields (`name`, `email`, `phone`, `subject`, `message`) via a form submission, not during initial interest.

        ## Job Application Protocol

        - When-dont-do-this When a visitor expresses interest in applying for a job, do NOT call `submit_job_application` immediately. Rely on the system to list jobs and prompt the user to say "apply" or "yes".
        - Upon form submission, use `submit_job_application` to save the data.

        When faced with specialized technical questions beyond available information, offer to connect visitors with appropriate LogBinary specialists.

        Your ultimate purpose is to deliver a seamless, informative experience that enhances LogBinary's professional reputation while efficiently addressing visitor needs.
        """
    }
    

    class CustomAgentExecutor:
        def __init__(self, llm, tools, system_message):
            self.llm = llm
            self.tools = {tool.name: tool for tool in tools}
            self.system_message = system_message
            self.memory = []
            self.functions = functions
            self.max_retries = 2
        
        async def ainvoke(self, input_data):
            user_input = input_data.get("input", "")
            for retry in range(self.max_retries + 1):
                try:
                    messages = [self.system_message] + self.memory + [{"role": "user", "content": user_input}]
                    response = self.llm.invoke(messages=messages, functions=self.functions)
                    logger.debug(f"Agent raw response: {response}")
                    
                    function_calls = []
                    if hasattr(response, 'function_call') and response.function_call:
                        function_calls.append({
                            'name': response.function_call.name,
                            'arguments': response.function_call.arguments
                        })
                    elif hasattr(response, 'tool_calls') and response.tool_calls:
                        for tool_call in response.tool_calls:
                            function_calls.append({
                                'name': tool_call.function.name,
                                'arguments': tool_call.function.arguments
                            })

                    if function_calls:
                        tool_responses = []
                        for fc in function_calls:
                            function_name = fc['name']
                            try:
                                function_args = json.loads(fc['arguments'])
                            except json.JSONDecodeError:
                                logger.error(f"Failed to parse function arguments: {fc['arguments']}")
                                function_args = {}

                            if function_name == "submit_service_inquiry":
                                # Check if all required args are present
                                required_args = ["name", "email", "phone", "subject", "message"]
                                if not all(arg in function_args for arg in required_args):
                                    # Redirect to form flow instead of failing
                                    output = "It looks like you're interested! Please say 'apply' or 'yes' to provide your details via a form."
                                    self.memory.append({"role": "user", "content": user_input})
                                    self.memory.append({"role": "assistant", "content": output})
                                    return {"output": output}

                            if function_name in self.tools:
                                tool_response = self.tools[function_name]._run(**function_args)
                                tool_responses.append({
                                    "role": "function", 
                                    "name": function_name, 
                                    "content": json.dumps(tool_response)
                                })
                        
                        if tool_responses:
                            messages.extend(tool_responses)
                            final_response = self.llm.invoke(messages=messages)
                            output = final_response.get('content') if isinstance(final_response, dict) else getattr(final_response, 'content', "I'm having trouble processing that request.")
                            self.memory.append({"role": "user", "content": user_input})
                            self.memory.append({"role": "assistant", "content": output})
                            if len(self.memory) > 10:
                                self.memory = self.memory[-10:]
                            return {"output": output}
                    
                    output = response.get('content') if isinstance(response, dict) else getattr(response, 'content', "I'm having trouble understanding right now.")
                    self.memory.append({"role": "user", "content": user_input})
                    self.memory.append({"role": "assistant", "content": output})
                    if len(self.memory) > 10:
                        self.memory = self.memory[-10:]
                    return {"output": output}
                    
                except Exception as e:
                    logger.error(f"Error in agent invocation (attempt {retry+1}/{self.max_retries+1}): {str(e)}")
                    if retry < self.max_retries:
                        logger.info(f"Retrying agent invocation...")
                        await asyncio.sleep(1)
                    else:
                        return {"output": "I'm sorry, I encountered an unexpected error. Please try again or contact our support team."}

    return CustomAgentExecutor(llm, tools, system_message)
