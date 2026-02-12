"""
Action module — parses FUNCTION_CALL strings and executes tools via MCP session.

This is the fourth step in the agent loop:
  perception → memory → decision → action
"""

import json
import logging
from typing import Dict, Any, Optional, Union
from pydantic import BaseModel
from mcp import ClientSession

log = logging.getLogger("email-assistant.action")


class ToolCallResult(BaseModel):
    """Result of executing a tool via MCP."""
    tool_name: str
    arguments: Dict[str, Any]
    result: Union[str, list, dict]

    class Config:
        arbitrary_types_allowed = True


def parse_function_call(
    response: str,
    tools: list,
    tool_results: Optional[Dict] = None,
) -> tuple[str, Dict[str, Any]]:
    """
    Parse a FUNCTION_CALL string into tool name and arguments.
    Uses positional parameter matching against the tool's input schema.

    Format: FUNCTION_CALL: tool_name|param1|param2|...
    """
    if not response.startswith("FUNCTION_CALL:"):
        raise ValueError("Not a valid FUNCTION_CALL")

    _, function_info = response.split(":", 1)
    parts = [p.strip() for p in function_info.split("|")]
    func_name = parts[0]
    params = parts[1:]

    # Find matching tool schema
    tool = next((t for t in tools if t.name == func_name), None)
    if not tool:
        available = [t.name for t in tools]
        raise ValueError(f"Unknown tool: {func_name}. Available: {available}")

    schema_properties = tool.inputSchema.get("properties", {})
    arguments = {}

    for param_name, param_info in schema_properties.items():
        param_type = param_info.get("type", "string")

        if not params and param_type in ("array", "object"):
            # Try to inject complex data from previous tool results
            if tool_results:
                for prev_tool, prev_result in tool_results.items():
                    raw = prev_result
                    if isinstance(raw, list):
                        parsed = json.loads(raw[0])
                    else:
                        parsed = json.loads(raw)
                    if isinstance(parsed, dict) and param_name in parsed:
                        arguments[param_name] = parsed[param_name]
                        break
        elif not params:
            # No more params — skip optional parameters
            continue
        else:
            value = params.pop(0)

            if param_type == "integer":
                arguments[param_name] = int(value)
            elif param_type == "number":
                arguments[param_name] = float(value)
            elif param_type in ("array", "object"):
                if isinstance(value, str):
                    try:
                        arguments[param_name] = json.loads(value)
                    except (json.JSONDecodeError, ValueError):
                        arguments[param_name] = value.strip("[]").split(",")
                else:
                    arguments[param_name] = value
            else:
                arguments[param_name] = str(value)

    log.info("Parsed: %s(%s)", func_name, arguments)
    return func_name, arguments


async def execute_tool(
    session: ClientSession,
    tools: list,
    response: str,
    tool_results: Optional[Dict] = None,
) -> ToolCallResult:
    """Execute a FUNCTION_CALL via the MCP session."""

    tool_name, arguments = parse_function_call(response, tools, tool_results)
    log.info("Executing tool: %s with %s", tool_name, arguments)

    result = await session.call_tool(tool_name, arguments=arguments)

    # Extract result content
    if hasattr(result, "content"):
        if isinstance(result.content, list):
            out = [
                getattr(item, "text", str(item))
                for item in result.content
            ]
        else:
            out = getattr(result.content, "text", str(result.content))
    else:
        out = str(result)

    log.info("Tool %s returned: %s", tool_name, str(out)[:200])

    return ToolCallResult(
        tool_name=tool_name,
        arguments=arguments,
        result=out,
    )
