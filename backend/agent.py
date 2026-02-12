"""
Agent orchestrator — coordinates the perception → memory → decision → action loop.

This is the brain of the assistant. It:
1. Receives a user message
2. Extracts perception (intent, entities, tool hints)
3. Retrieves relevant memories from past interactions
4. Asks the LLM for a decision (FUNCTION_CALL or FINAL_ANSWER)
5. Executes tools via MCP
6. Stores results in memory
7. Loops until FINAL_ANSWER or max iterations
"""

import json
import time
import asyncio
import logging
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from perception import extract_perception
from memory import MemoryManager, MemoryItem
from decision import generate_plan
from action import execute_tool

load_dotenv()
log = logging.getLogger("email-assistant.agent")

MAX_ITERATIONS = 10

# Shared memory — persists across chat messages within a server session
memory = MemoryManager()


def _build_context(tool_results: dict) -> dict | None:
    """
    Build structured context from the last tool call results
    so the frontend can render a side panel (emails, events, etc.).
    """
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
        "search_indexed_documents": "rag_results",
    }

    # Last called tool wins
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

    if context_type == "calendar_events":
        data = parsed.get("events", [])
    elif context_type == "email_list":
        data = parsed.get("emails", [])
    elif context_type == "rag_results":
        data = parsed.get("results", [])
    else:
        data = parsed

    return {"type": context_type, "data": data}


def _format_tool_descriptions(tools) -> str:
    """Format MCP tools into a readable string for the LLM."""
    descriptions = []
    for i, tool in enumerate(tools):
        params = tool.inputSchema
        desc = getattr(tool, "description", "No description")
        name = getattr(tool, "name", f"tool_{i}")

        if "properties" in params:
            param_details = []
            for p_name, p_info in params["properties"].items():
                p_type = p_info.get("type", "unknown")
                param_details.append(f"{p_name}: {p_type}")
            params_str = ", ".join(param_details)
        else:
            params_str = "no parameters"

        descriptions.append(f"{i+1}. {name}({params_str}) - {desc}")

    return "\n".join(descriptions)


async def handle_chat(user_message: str) -> dict:
    """
    Main agent loop:
      1. PERCEPTION — extract intent, entities, tool hints
      2. MEMORY RETRIEVE — get relevant past context
      3. DECISION — LLM picks FUNCTION_CALL or FINAL_ANSWER
      4. ACTION — execute tool via MCP
      5. MEMORY STORE — save result for future retrieval
      6. Loop back to step 3 with updated context
    """
    log.info("=== New chat: %s ===", user_message)
    session_id = f"session-{int(time.time())}"

    try:
        # Connect to MCP server
        server_params = StdioServerParameters(
            command="python",
            args=["mcp_tools.py"],
        )

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # Get available tools
                tools_result = await session.list_tools()
                tools = tools_result.tools
                tool_descriptions = _format_tool_descriptions(tools)
                log.info("Loaded %d MCP tools", len(tools))

                # ── Step 1: PERCEPTION (once at the start) ────────────
                perception = extract_perception(user_message)
                log.info(
                    "[Perception] Intent: %s | Entities: %s | Tool hint: %s",
                    perception.intent,
                    perception.entities,
                    perception.tool_hint,
                )

                # Store user query in memory
                memory.add(MemoryItem(
                    text=f"User asked: {user_message}",
                    type="user_query",
                    user_query=user_message,
                    tags=[perception.intent or "general"],
                    session_id=session_id,
                ))

                tool_results = {}
                iteration_context_parts = []
                current_query = user_message

                for iteration in range(MAX_ITERATIONS):
                    log.info("--- Iteration %d ---", iteration + 1)

                    # ── Step 2: MEMORY RETRIEVE ───────────────────────
                    retrieved = memory.retrieve(
                        query=current_query,
                        top_k=3,
                        session_filter=session_id,
                    )
                    log.info("[Memory] Retrieved %d relevant items", len(retrieved))

                    # ── Step 3: DECISION ──────────────────────────────
                    iteration_context = "\n".join(iteration_context_parts)
                    plan = generate_plan(
                        perception=perception,
                        memory_items=retrieved,
                        tool_descriptions=tool_descriptions,
                        iteration_context=iteration_context,
                    )
                    log.info("[Decision] Plan: %s", plan)

                    # ── Check for FINAL_ANSWER ────────────────────────
                    if plan.startswith("FINAL_ANSWER:"):
                        answer = plan.split("FINAL_ANSWER:", 1)[1].strip()
                        if answer.startswith("[") and answer.endswith("]"):
                            answer = answer[1:-1].strip()
                        log.info("=== Agent Complete: %s ===", answer[:100])
                        context = _build_context(tool_results)
                        return {"reply": answer, "context": context}

                    # ── Step 4: ACTION — Execute tool ─────────────────
                    if plan.startswith("FUNCTION_CALL:"):
                        try:
                            result = await execute_tool(
                                session=session,
                                tools=tools,
                                response=plan,
                                tool_results=tool_results,
                            )
                            log.info("[Action] %s returned successfully", result.tool_name)

                            # Format result string
                            if isinstance(result.result, list):
                                result_str = f"[{', '.join(result.result)}]"
                            else:
                                result_str = str(result.result)

                            # Store in tool_results for context building
                            tool_results[result.tool_name] = result.result

                            # Update iteration context for next decision
                            iteration_context_parts.append(
                                f"Step {iteration + 1}: Called {result.tool_name}({result.arguments}) "
                                f"→ {result_str}"
                            )

                            # ── Step 5: MEMORY STORE ──────────────────
                            memory.add(MemoryItem(
                                text=f"Tool: {result.tool_name} with {result.arguments} → {result_str[:300]}",
                                type="tool_output",
                                tool_name=result.tool_name,
                                user_query=user_message,
                                tags=[result.tool_name, perception.intent or "unknown"],
                                session_id=session_id,
                            ))

                            # Update query for next perception/decision cycle
                            current_query = (
                                f"Original request: {user_message}\n"
                                f"Previous result from {result.tool_name}: {result_str}\n"
                                f"What should I do next?"
                            )

                        except Exception as e:
                            log.error("[Action] Tool execution failed: %s", e)
                            import traceback
                            traceback.print_exc()
                            return {
                                "reply": f"Tool execution failed: {str(e)}",
                                "context": _build_context(tool_results),
                            }
                    else:
                        # Unexpected response format — treat as answer
                        log.warning("Unexpected plan format: %s", plan[:100])
                        context = _build_context(tool_results)
                        return {"reply": plan, "context": context}

                # Exhausted iterations
                log.warning("Max iterations reached without FINAL_ANSWER")
                context = _build_context(tool_results)
                return {
                    "reply": "I wasn't able to complete your request within the step limit. Please try a simpler query.",
                    "context": context,
                }

    except Exception as e:
        log.error("Agent error: %s", e)
        import traceback
        traceback.print_exc()
        return {"reply": f"Something went wrong: {str(e)}", "context": None}
