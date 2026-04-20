"""Agent runtime factory.

Wraps LangGraph's prebuilt ReAct agent with:
- OpenAI chat model configured from settings,
- the loyalty tools registry,
- a PostgresSaver checkpointer for durable conversational state.

Human-in-the-loop for sensitive actions is handled conversationally: the
system prompt instructs the agent to summarise the proposed action and ask
for explicit confirmation before calling any sensitive tool. The user's next
"sí / confirmo" message triggers the actual tool call in the following turn.
This is simpler than graph-level interrupt_before (which only supports node
names like "tools", not individual tool names) and works naturally over
WhatsApp/Telegram where each message is a separate HTTP call.

Each tool entrypoint calls `require_tool_access` so disallowed roles cannot
execute owner-only tools even if the model requests them.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from langchain_openai import ChatOpenAI
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.prebuilt import create_react_agent

from app.agent.prompts.system import POLICY_KNOWLEDGE, format_system_prompt_core
from app.agent.tools import ALL_TOOLS
from app.core.config import settings

logger = logging.getLogger(__name__)


def _build_llm() -> ChatOpenAI:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    return ChatOpenAI(
        model=settings.openai_model,
        temperature=settings.openai_temperature,
        api_key=settings.openai_api_key,
    )


def render_system_prompt(
    *, company_id: str, internal_user_id: str, role: str, user_display_name: str
) -> str:
    return (
        format_system_prompt_core(
            company_id=company_id,
            internal_user_id=internal_user_id,
            role=role,
            user_display_name=user_display_name or "(sin nombre)",
        )
        + "\n\n"
        + POLICY_KNOWLEDGE
    )


@asynccontextmanager
async def agent_runtime() -> AsyncIterator["AgentRuntime"]:
    """Async context manager that owns the checkpointer connection pool."""
    checkpointer_cm = AsyncPostgresSaver.from_conn_string(
        _to_psycopg_url(settings.agent_database_url)
    )
    async with checkpointer_cm as checkpointer:
        await checkpointer.setup()
        runtime = AgentRuntime(checkpointer)
        yield runtime


class AgentRuntime:
    def __init__(self, checkpointer: AsyncPostgresSaver):
        self._checkpointer = checkpointer
        self._graph = create_react_agent(
            model=_build_llm(),
            tools=ALL_TOOLS,
            checkpointer=checkpointer,
        )

    @property
    def graph(self):
        return self._graph


def _to_psycopg_url(async_url: str) -> str:
    """AsyncPostgresSaver uses psycopg (sync driver dsn form), not +asyncpg."""
    return async_url.replace("+asyncpg", "").replace("postgresql+psycopg", "postgresql")
