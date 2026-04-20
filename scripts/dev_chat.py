"""
CLI interactivo para probar el agente localmente sin Telegram/WhatsApp.

Usa MemorySaver (sin Postgres) y el loyalty core real (si está corriendo).

Uso:
    # Desde la raíz de loyalty_agent con el .env cargado:
    python scripts/dev_chat.py

    # Con un company_id específico:
    python scripts/dev_chat.py --company-id 687930e8-9cc2-4a4f-97ba-6e916eb3a4c6 --role business_owner

    # Apuntando a un loyalty diferente:
    LOYALTY_API_BASE_URL=http://staging:8000 python scripts/dev_chat.py

Comandos especiales en el chat:
    /reset    → borra el hilo de conversación actual y empieza uno nuevo
    /exit     → salir
    /tools    → lista las tools disponibles
    /confirm  → simula confirmación afirmativa de la última acción propuesta
"""

import argparse
import asyncio
import os
import sys
import uuid
from pathlib import Path

# Añadir raíz del proyecto al path para que los imports de `app.*` funcionen.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Cargar .env antes de importar cualquier módulo de app.
from dotenv import load_dotenv  # type: ignore  # pip install python-dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def _parse_args():
    p = argparse.ArgumentParser(description="Dev chat para Apoli (Techapoli Loyalty)")
    p.add_argument(
        "--company-id",
        default=os.getenv("DEV_COMPANY_ID", str(uuid.uuid4())),
        help="UUID de la empresa (default: genera uno nuevo o DEV_COMPANY_ID)",
    )
    p.add_argument(
        "--user-id",
        default=os.getenv("DEV_USER_ID", str(uuid.uuid4())),
        help="UUID del internal_user (default: genera uno nuevo o DEV_USER_ID)",
    )
    p.add_argument(
        "--role",
        default=os.getenv("DEV_ROLE", "business_owner"),
        choices=["platform_admin", "business_owner", "staff"],
        help="Rol del usuario (default: business_owner)",
    )
    p.add_argument(
        "--name",
        default=os.getenv("DEV_USER_NAME", "Dev User"),
        help="Nombre a mostrar",
    )
    return p.parse_args()


async def main():
    args = _parse_args()

    # Importaciones tardías para que los settings ya tengan el .env cargado.
    from langchain_core.messages import HumanMessage
    from langchain_openai import ChatOpenAI
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.prebuilt import create_react_agent

    from app.agent.guardrails import SENSITIVE_TOOLS
    from app.agent.runtime import render_system_prompt
    from app.agent.tools import ALL_TOOLS
    from app.agent.tools._context import AgentTurnContext
    from app.core.config import settings
    from app.infrastructure.loyalty_api.auth_manager import LoyaltyAuthManager
    from app.infrastructure.loyalty_api.http_client import (
        HttpLoyaltyServiceAdapter,
        build_http_client,
    )

    company_id = uuid.UUID(args.company_id)
    user_id = uuid.UUID(args.user_id)
    session_id = uuid.uuid4()

    print(f"\n{'='*60}")
    print("  Apoli — Dev Chat (Techapoli Loyalty)")
    print(f"{'='*60}")
    print(f"  Loyalty URL : {settings.loyalty_api_base_url}")
    print(f"  Modelo      : {settings.openai_model}")
    print(f"  company_id  : {company_id}")
    print(f"  user_id     : {user_id}")
    print(f"  rol         : {args.role}")
    print(f"  session_id  : {session_id}")
    print(f"{'='*60}")
    print("  Comandos: /reset  /tools  /exit")
    print(f"{'='*60}\n")

    if not settings.openai_api_key:
        print("[ERROR] OPENAI_API_KEY no está configurado en .env")
        sys.exit(1)

    # Auth manager con service account (solo para lecturas en dev).
    # Para mutaciones el user_access_token será el del service account también.
    auth = LoyaltyAuthManager(client_factory=build_http_client)
    loyalty = HttpLoyaltyServiceAdapter(auth)

    llm = ChatOpenAI(
        model=settings.openai_model,
        temperature=settings.openai_temperature,
        api_key=settings.openai_api_key,
    )
    checkpointer = MemorySaver()
    graph = create_react_agent(
        model=llm,
        tools=ALL_TOOLS,
        checkpointer=checkpointer,
    )

    system_prompt = render_system_prompt(
        company_id=str(company_id),
        internal_user_id=str(user_id),
        role=args.role,
        user_display_name=args.name,
    )

    thread_id = str(session_id)

    async def _get_service_token() -> str:
        try:
            return await auth.get_service_token()
        except Exception:
            return "dev-token-no-loyalty"

    while True:
        try:
            user_input = input("Tú: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nHasta luego.")
            break

        if not user_input:
            continue

        if user_input == "/exit":
            print("Hasta luego.")
            break

        if user_input == "/reset":
            thread_id = str(uuid.uuid4())
            print(f"[nuevo hilo: {thread_id}]\n")
            continue

        if user_input == "/tools":
            print("\nTools disponibles:")
            for t in ALL_TOOLS:
                marker = "⚠️  SENSIBLE" if t.name in SENSITIVE_TOOLS else "   lectura "
                print(f"  {marker}  {t.name}")
            print()
            continue

        if user_input == "/confirm":
            user_input = "sí, confirmo"

        user_token = await _get_service_token()
        turn_ctx = AgentTurnContext(
            company_id=company_id,
            internal_user_id=user_id,
            role=args.role,  # type: ignore[arg-type]
            session_id=session_id,
            loyalty=loyalty,
            user_access_token=user_token,
            idempotency_seed=thread_id,
        )

        config = {
            "configurable": {
                "thread_id": thread_id,
                "turn_context": turn_ctx,
            },
            "recursion_limit": settings.agent_max_tool_iterations * 2,
        }

        messages_input = {
            "messages": [
                {"role": "system", "content": system_prompt},
                HumanMessage(content=user_input),
            ]
        }

        try:
            result = await graph.ainvoke(messages_input, config)
        except Exception as exc:
            print(f"[ERROR del agente] {exc}\n")
            continue

        # Extraer respuesta final.
        msgs = result.get("messages", [])
        reply = "(sin respuesta)"
        for msg in reversed(msgs):
            content = getattr(msg, "content", None)
            if isinstance(content, str) and content.strip():
                # Mostrar tool calls intermedios si los hay.
                break
        else:
            content = None

        # Mostrar tool calls que ocurrieron en este turno.
        from langchain_core.messages import AIMessage, ToolMessage

        for msg in msgs:
            if isinstance(msg, AIMessage) and msg.tool_calls:
                for tc in msg.tool_calls:
                    marker = "⚠️ " if tc["name"] in SENSITIVE_TOOLS else "→ "
                    print(f"  [tool {marker}{tc['name']}] args: {tc['args']}")
            elif isinstance(msg, ToolMessage):
                snippet = str(msg.content)[:120]
                print(f"  [tool result] {snippet}{'...' if len(str(msg.content)) > 120 else ''}")

        reply = content or "(sin respuesta)"
        print(f"\nAgente: {reply}\n")


if __name__ == "__main__":
    asyncio.run(main())
