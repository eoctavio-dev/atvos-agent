import asyncio
from types import SimpleNamespace

from pytest import MonkeyPatch

from mcp_server import ask_atvos_agent, sessions


class FinalEvent:
    content = SimpleNamespace(parts=[SimpleNamespace(text="respuesta de prueba")])

    def is_final_response(self) -> bool:
        return True


def test_mcp_tool_returns_agent_response(monkeypatch: MonkeyPatch) -> None:
    async def fake_run_async(**_: object):
        yield FinalEvent()

    monkeypatch.setattr("mcp_server.runner.run_async", fake_run_async)
    result = asyncio.run(ask_atvos_agent("Hola", "test-session"))

    assert result["session_id"] == "test-session"
    assert result["response"] == "respuesta de prueba"
    asyncio.run(
        sessions.delete_session(
            app_name="atvos_agent_mcp",
            user_id="mcp-user",
            session_id="test-session",
        )
    )
