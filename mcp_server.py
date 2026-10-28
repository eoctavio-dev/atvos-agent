import uuid

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from mcp.server.fastmcp import FastMCP

from agents.atvos_agent import root_agent

mcp = FastMCP("Atvos Agent MCP")
sessions = InMemorySessionService()
runner = Runner(
    app_name="atvos_agent_mcp",
    agent=root_agent,
    session_service=sessions,
)


async def run_agent(message: str, session_id: str | None = None) -> dict[str, str]:
    user_id = "mcp-user"
    current_session_id = session_id or uuid.uuid4().hex
    session = await sessions.get_session(
        app_name=runner.app_name,
        user_id=user_id,
        session_id=current_session_id,
    )
    if session is None:
        await sessions.create_session(
            app_name=runner.app_name,
            user_id=user_id,
            session_id=current_session_id,
        )

    response_parts: list[str] = []
    async for event in runner.run_async(
        user_id=user_id,
        session_id=current_session_id,
        new_message=types.Content(
            role="user",
            parts=[types.Part(text=message)],
        ),
    ):
        if event.is_final_response() and event.content:
            response_parts.extend(
                part.text for part in (event.content.parts or []) if part.text
            )

    return {
        "session_id": current_session_id,
        "response": "\n".join(response_parts),
    }


@mcp.tool()
async def ask_atvos_agent(
    message: str, session_id: str | None = None
) -> dict[str, str]:
    """Send a prompt to the Atvos Google Cloud ADK agent."""
    return await run_agent(message, session_id)


if __name__ == "__main__":
    mcp.run(transport="stdio")
