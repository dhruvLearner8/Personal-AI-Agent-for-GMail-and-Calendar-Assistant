import os
import json
import datetime
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
import asyncio
from google import genai
from concurrent.futures import TimeoutError
from functools import partial

# Load environment variables from .env file
load_dotenv()

# Access your API key and initialize Gemini client correctly
api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

max_iterations = 5
last_response = None
iteration = 0
iteration_response = []

async def generate_with_timeout(client, prompt, timeout=10):
    """Generate content with a timeout"""
    print("Starting LLM generation...")
    try:
        # Convert the synchronous generate_content call to run in a thread
        loop = asyncio.get_event_loop()
        response = await asyncio.wait_for(
            loop.run_in_executor(
                None, 
                lambda: client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=prompt
                )
            ),
            timeout=timeout
        )
        print("LLM generation completed")
        return response
    except TimeoutError:
        print("LLM generation timed out!")
        raise
    except Exception as e:
        print(f"Error in LLM generation: {e}")
        raise

def reset_state():
    """Reset all global variables to their initial state"""
    global last_response, iteration, iteration_response
    last_response = None
    iteration = 0
    iteration_response = []

def _build_context(tool_results: dict) -> dict | None:
    """
    Build structured context from the last tool call results
    so the frontend can render a side panel.
    """
    # Map tool names to context types
    TOOL_TO_CONTEXT = {
        "get_todays_events": "calendar_events",
        "get_events_for_date": "calendar_events",
        "check_free_slots": "free_slots",
        "create_event": "event_created",
        "get_unread_emails_today": "email_list",
        "get_emails_by_date_range": "email_list",
        "search_emails": "email_list",
        "get_email_thread": "email_thread",
        "get_email_attachments": "email_attachments",
        "send_email": "email_sent",
    }

    # Walk tool_results in reverse priority — last called tool wins
    last_tool = None
    for tool_name in TOOL_TO_CONTEXT:
        if tool_name in tool_results:
            last_tool = tool_name

    if not last_tool:
        return None

    raw = tool_results[last_tool]
    try:
        if isinstance(raw, list):
            parsed = json.loads(raw[0])
        else:
            parsed = json.loads(raw)
    except (json.JSONDecodeError, IndexError):
        return None

    context_type = TOOL_TO_CONTEXT[last_tool]

    # Extract the relevant data array/object
    if context_type == "calendar_events":
        data = parsed.get("events", [])
    elif context_type == "free_slots":
        data = parsed  # already has {date, busy, free}
    elif context_type == "event_created":
        data = parsed  # single event confirmation
    elif context_type == "email_list":
        data = parsed.get("emails", [])
    elif context_type == "email_thread":
        data = parsed  # {thread_id, subject, message_count, messages}
    elif context_type == "email_attachments":
        data = parsed  # {message_id, subject, from, attachment_count, attachments}
    elif context_type == "email_sent":
        data = parsed  # {status, to, subject, message_id}
    else:
        data = parsed

    return {"type": context_type, "data": data}


async def handle_chat(user_message: str) -> dict:
    reset_state()  # Reset at the start of main
    print("Starting main execution...")
    try:
        # Create a single MCP server connection
        print("Establishing connection to MCP server...")
        server_params = StdioServerParameters(
            command="python",
            args=["mcp_tools.py"]
        )

        async with stdio_client(server_params) as (read, write):
            print("Connection established, creating session...")
            async with ClientSession(read, write) as session:
                print("Session created, initializing...")
                await session.initialize()
                
                # Get available tools
                print("Requesting tool list...")
                tools_result = await session.list_tools()
                tools = tools_result.tools
                print(f"Successfully retrieved {len(tools)} tools")
                

                # Create system prompt with available tools
                print("Creating system prompt...")
                print(f"Number of tools: {len(tools)}")
                
                try:
                    # First, let's inspect what a tool object looks like
                    # if tools:
                    #     print(f"First tool properties: {dir(tools[0])}")
                    #     print(f"First tool example: {tools[0]}")
                    
                    tools_description = []
                    for i, tool in enumerate(tools):
                        try:
                            # Get tool properties
                            params = tool.inputSchema
                            desc = getattr(tool, 'description', 'No description available')
                            name = getattr(tool, 'name', f'tool_{i}')
                            
                            # Format the input schema in a more readable way
                            if 'properties' in params:
                                param_details = []
                                for param_name, param_info in params['properties'].items():
                                    param_type = param_info.get('type', 'unknown')
                                    param_details.append(f"{param_name}: {param_type}")
                                params_str = ', '.join(param_details)
                            else:
                                params_str = 'no parameters'

                            tool_desc = f"{i+1}. {name}({params_str}) - {desc}"
                            tools_description.append(tool_desc)
                            print(f"Added description for tool: {tool_desc}")
                        except Exception as e:
                            print(f"Error processing tool {i}: {e}")
                            tools_description.append(f"{i+1}. Error processing tool")
                    
                    tools_description = "\n".join(tools_description)
                    print("Successfully created tools description")
                except Exception as e:
                    print(f"Error creating tools description: {e}")
                    tools_description = "Error loading tools"
                
                print("Created system prompt...")
                # import pdb; pdb.set_trace()
                
                today_str = datetime.date.today().strftime("%Y-%m-%d")
                system_prompt = f"""You are a smart personal assistant that manages the user's Gmail inbox and Google Calendar. Today's date is {today_str}.

Available tools:
{tools_description}

You must respond with EXACTLY ONE line in one of these formats (no additional text):
1. For function calls:
   FUNCTION_CALL: function_name|param1|param2|...
   
2. For final answers (a human-readable response to the user):
   FINAL_ANSWER: [your response text here]

DECISION FLOW:

1. UNDERSTAND the user's intent:
   - READ EMAIL: "check emails", "unread", "inbox", "summarize emails"
   - SEARCH EMAIL: "emails from", "emails about", "find email"
   - THREAD / CONVERSATION: "conversation with", "thread with", "summarize thread", "summarise the conversation"
   - ATTACHMENT / DOCUMENT: "document", "attachment", "file sent", "pdf", "summarize the file"
   - WRITE EMAIL: "send email", "write email", "email someone", "tell them", "message"
   - READ CALENDAR: "schedule", "meetings", "events", "busy", "free", "available", "what's on"
   - WRITE CALENDAR: "schedule a meeting", "add event", "create", "book", "set up"
   - UNRELATED: anything else

2. PICK the right tool:

   READ EMAIL (today / unread):
   → Call get_unread_emails_today (no params)

   READ EMAIL (specific time period):
   → Call get_emails_by_date_range|YYYY-MM-DD|YYYY-MM-DD
   → e.g. "emails from last week" → calculate start and end dates from {today_str}

   SEARCH EMAIL (by person, topic, or keyword):
   → Call search_emails|gmail_query
   → Build a Gmail search query from the user's request:
     - "emails from dhruv" → search_emails|from:dhruv
     - "emails about invoices" → search_emails|subject:invoice
     - "conversation with sarah" → search_emails|from:sarah OR to:sarah
     - "emails from boss since last Monday" → search_emails|from:boss after:YYYY/MM/DD

   SUMMARISE A THREAD / CONVERSATION:
   This is a TWO-STEP flow:
   Step 1 → Call search_emails to find emails matching the person/topic. Results include a threadId field.
   Step 2 → Pick the most relevant threadId from the results and call get_email_thread|<threadId>
   Step 3 → You will receive full message bodies. Give a FINAL_ANSWER summarising the conversation.

   READ ATTACHMENT / DOCUMENT:
   This is a TWO-STEP flow:
   Step 1 → Call search_emails with "has:attachment" plus the person/topic (e.g. search_emails|from:dhruv has:attachment)
   Step 2 → Pick the most relevant messageId from the results and call get_email_attachments|<messageId>
   Step 3 → You will receive extracted text content from the documents. Give a FINAL_ANSWER summarising what the document is about.

   After receiving email data (non-thread), give a FINAL_ANSWER summarizing the emails yourself.

   WRITE EMAIL:
   → Call send_email|to_address|subject|body
   → The body should be professional and well-written
   → If the user gives a rough idea ("tell John I'll be late"), craft a polite email from it

   READ CALENDAR (today):
   → Call get_todays_events (no params)

   READ CALENDAR (specific date):
   → Call get_events_for_date|YYYY-MM-DD

   READ CALENDAR (free/busy check):
   → Call check_free_slots|YYYY-MM-DD

   WRITE CALENDAR:
   → Call create_event|title|YYYY-MM-DD|HH:MM|HH:MM|attendee_emails
   → If no attendees, leave last param empty
   → If no end time given, assume 1 hour duration
   → When attendees are included, Google Calendar sends them invite emails automatically

   UNRELATED:
   → Give a FINAL_ANSWER directly

3. After receiving tool results, give a FINAL_ANSWER with a clear, friendly summary.
   Do NOT call another tool unless absolutely necessary.

DATE PARSING (today is {today_str}):
- Convert all natural dates to YYYY-MM-DD format
- "5th Feb" or "Feb 5th" or "February 5" → 2026-02-05
- "March 10" or "10th March" → 2026-03-10
- "tomorrow" → calculate from {today_str}
- "next Friday" → calculate from {today_str}
- Time must be HH:MM in 24-hour format (e.g. 14:00 for 2 PM)

EXAMPLES:
- FUNCTION_CALL: get_unread_emails_today
- FUNCTION_CALL: get_emails_by_date_range|2026-02-01|2026-02-07
- FUNCTION_CALL: search_emails|from:dhruv
- FUNCTION_CALL: search_emails|from:sarah OR to:sarah
- FUNCTION_CALL: search_emails|subject:invoice after:2026/02/01
- FUNCTION_CALL: get_email_thread|18d1a2b3c4e5f678
- FUNCTION_CALL: search_emails|from:dhruv has:attachment
- FUNCTION_CALL: get_email_attachments|18d1a2b3c4e5f678
- FUNCTION_CALL: send_email|john@example.com|Meeting follow-up|Hi John, just following up on our meeting. Let me know if you need anything.
- FUNCTION_CALL: get_todays_events
- FUNCTION_CALL: get_events_for_date|2026-03-05
- FUNCTION_CALL: check_free_slots|2026-02-10
- FUNCTION_CALL: create_event|Dentist appointment|2026-03-05|14:00|15:00|
- FUNCTION_CALL: create_event|Team sync|2026-03-05|10:00|11:00|john@co.com,sara@co.com
- FINAL_ANSWER: [You have 3 meetings today. The first one is a standup at 9 AM.]



DO NOT include any explanations or additional text.
Your entire response should be a single line starting with either FUNCTION_CALL: or FINAL_ANSWER:"""
               
                query = user_message
                print("Starting iteration loop...")
                
                # Use global iteration variables
                global iteration, last_response
                tool_results = {}
                
                while iteration < max_iterations:
                    print(f"\n--- Iteration {iteration + 1} ---")
                    if last_response is None:
                        current_query = query
                    else:
                        current_query = current_query + "\n\n" + " ".join(iteration_response)
                        current_query = current_query + "  What should I do next?"

                    # Get model's response with timeout
                    print("Preparing to generate LLM response...")
                    prompt = f"{system_prompt}\n\nQuery: {current_query}"
                    try:
                        response = await generate_with_timeout(client, prompt)
                        response_text = response.text.strip()
                        print(f"LLM Response: {response_text}")
                        
                        # Find the FUNCTION_CALL line in the response
                        for line in response_text.split('\n'):
                            line = line.strip()
                            if line.startswith("FUNCTION_CALL:"):
                                response_text = line
                                break
                        
                    except Exception as e:
                        print(f"Failed to get LLM response: {e}")
                        break


                    if response_text.startswith("FUNCTION_CALL:"):
                        _, function_info = response_text.split(":", 1)
                        parts = [p.strip() for p in function_info.split("|")]
                        func_name, params = parts[0], parts[1:]
                        
                        print(f"\nDEBUG: Raw function info: {function_info}")
                        print(f"DEBUG: Split parts: {parts}")
                        print(f"DEBUG: Function name: {func_name}")
                        print(f"DEBUG: Raw parameters: {params}")
                        
                        try:
                            # Find the matching tool to get its input schema
                            tool = next((t for t in tools if t.name == func_name), None)
                            if not tool:
                                print(f"DEBUG: Available tools: {[t.name for t in tools]}")
                                raise ValueError(f"Unknown tool: {func_name}")

                            print(f"DEBUG: Found tool: {tool.name}")
                            print(f"DEBUG: Tool schema: {tool.inputSchema}")

                            # Prepare arguments according to the tool's input schema
                            arguments = {}
                            schema_properties = tool.inputSchema.get('properties', {})
                            print(f"DEBUG: Schema properties: {schema_properties}")

                            for param_name, param_info in schema_properties.items():
                                param_type = param_info.get('type', 'string')
                                if not params and (param_type == 'array' or param_type == 'object'):
                                    value = None  # will be filled from tool_results
                                elif not params:
                                    raise ValueError(f"Not enough parameters provided for {func_name}")
                                else:
                                    value = params.pop(0)
                                
                                
                                print(f"DEBUG: Converting parameter {param_name} with value {value} to type {param_type}")
                                
                                # Convert the value to the correct type based on the schema
                                if param_type == 'integer':
                                    arguments[param_name] = int(value)
                                elif param_type == 'number':
                                    arguments[param_name] = float(value)
                                elif param_type == 'array' or param_type == 'object':
                                    # Pull complex data from stored tool results
                                    injected = False
                                    for prev_tool, prev_result in tool_results.items():
                                        if not injected:
                                            raw = prev_result
                                            if isinstance(raw, list):
                                                parsed_data = json.loads(raw[0])
                                            else:
                                                parsed_data = json.loads(raw)
                                            if isinstance(parsed_data, dict) and param_name in parsed_data:
                                                arguments[param_name] = parsed_data[param_name]
                                                injected = True
                                    if not injected:
                                        # Fallback for simple arrays
                                        if isinstance(value, str):
                                            value = value.strip('[]').split(',')
                                        arguments[param_name] = value
                                else:
                                    arguments[param_name] = str(value)

                            print(f"DEBUG: Final arguments: {arguments}")
                            print(f"DEBUG: Calling tool {func_name}")
                            
                            result = await session.call_tool(func_name, arguments=arguments)
                            print(f"DEBUG: Raw result: {result}")
                            
                            # Get the full result content
                            if hasattr(result, 'content'):
                                print(f"DEBUG: Result has content attribute")
                                # Handle multiple content items
                                if isinstance(result.content, list):
                                    iteration_result = [
                                        item.text if hasattr(item, 'text') else str(item)
                                        for item in result.content
                                    ]
                                else:
                                    iteration_result = str(result.content)
                            else:
                                print(f"DEBUG: Result has no content attribute")
                                iteration_result = str(result)
                                
                            print(f"DEBUG: Final iteration result: {iteration_result}")
                            
                            # Format the response based on result type
                            if isinstance(iteration_result, list):
                                result_str = f"[{', '.join(iteration_result)}]"
                            else:
                                result_str = str(iteration_result)
                            
                            iteration_response.append(
                                f"In the {iteration + 1} iteration you called {func_name} with {arguments} parameters, "
                                f"and the function returned {result_str}."
                            )
                            tool_results[func_name] = iteration_result 
                            last_response = iteration_result

                        except Exception as e:
                            print(f"DEBUG: Error details: {str(e)}")
                            print(f"DEBUG: Error type: {type(e)}")
                            import traceback
                            traceback.print_exc()
                            iteration_response.append(f"Error in iteration {iteration + 1}: {str(e)}")
                            break

                    elif response_text.startswith("FINAL_ANSWER:"):
                        answer = response_text.split("FINAL_ANSWER:", 1)[1].strip()
                        if answer.startswith("[") and answer.endswith("]"):
                            answer = answer[1:-1].strip()
                        print(f"\n=== Agent Complete: {answer} ===")
                        context = _build_context(tool_results)
                        return {"reply": answer, "context": context}

                    iteration += 1

                # Exhausted iterations without a FINAL_ANSWER
                context = _build_context(tool_results)
                return {"reply": "Sorry, I couldn't complete your request. Please try again.", "context": context}

    except Exception as e:
        print(f"Error in main execution: {e}")
        import traceback
        traceback.print_exc()
        return {"reply": f"Something went wrong: {str(e)}", "context": None}
    finally:
        reset_state()

if __name__ == "__main__":
    asyncio.run(main())
    
    
