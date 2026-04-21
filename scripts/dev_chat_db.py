"""
CLI interactivo para probar el agente con el mismo checkpointer que producción (Postgres).

A diferencia de dev_chat.py (MemorySaver), este script persiste el hilo LangGraph
en AGENT_DATABASE_URL. Útil para reproducir comportamiento con checkpoint real.

Uso (desde la raíz de loyalty_agent, con .env):
    python scripts/dev_chat_db.py

Identidad por defecto (recomendado):
    Con LOYALTY_AGENT_SERVICE_EMAIL / LOYALTY_AGENT_SERVICE_PASSWORD el script hace
    login al loyalty y resuelve internal_user_id + rol + nombre vía
    GET /api/v1/companies/{company_id}/users buscando tu email (mismo company_id).

    Si el service account es platform_admin (sin fila en esa empresa), define
    DEV_USER_ID o pasa --user-id con el UUID del usuario en el core.

Identidad manual:
    python scripts/dev_chat_db.py --user-id <uuid> --role staff --name "QA"

Variables:
    AGENT_DATABASE_URL  (requerida; asyncpg en app, aquí se convierte a DSN psycopg)
    LOYALTY_AGENT_SERVICE_EMAIL / LOYALTY_AGENT_SERVICE_PASSWORD (resolución automática)
    OPENAI_API_KEY, LOYALTY_API_BASE_URL, etc.  igual que dev_chat.py

En Windows, psycopg async exige SelectorEventLoop; el script fuerza la política adecuada.

Comandos en el chat: /reset  /tools  /exit  /confirm  (igual que dev_chat.py)
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # type: ignore

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Compañía por defecto solicitada para entorno TechApoli.
DEFAULT_COMPANY_ID = uuid.UUID("687930e8-9cc2-4a4f-97ba-6e916eb3a4c6")


def _to_psycopg_url(async_url: str) -> str:
    """Misma conversión que AgentRuntime (psycopg sync, sin +asyncpg)."""
    return async_url.replace("+asyncpg", "").replace("postgresql+psycopg", "postgresql")


def _parse_args():
    p = argparse.ArgumentParser(description="Dev chat Lumi con Postgres checkpointer")
    p.add_argument(
        "--company-id",
        default=os.getenv("DEV_COMPANY_ID", str(DEFAULT_COMPANY_ID)),
        help=f"UUID empresa (default: {DEFAULT_COMPANY_ID} o DEV_COMPANY_ID)",
    )
    p.add_argument(
        "--user-id",
        default="",
        help="UUID internal_user; vacío = resolver por API con LOYALTY_AGENT_SERVICE_EMAIL",
    )
    p.add_argument(
        "--role",
        default=os.getenv("DEV_ROLE", "business_owner"),
        choices=["platform_admin", "business_owner", "staff"],
        help="Solo identidad manual: rol (con --user-id o DEV_USER_ID)",
    )
    p.add_argument(
        "--name",
        default=os.getenv("DEV_USER_NAME", "Dev User"),
        help="Solo identidad manual: nombre en system prompt",
    )
    return p.parse_args()


async def _resolve_identity_from_service_account(
    auth, company_id: uuid.UUID
) -> tuple[uuid.UUID, str, str]:
    """Login con service account y localiza fila internal_user por email en la empresa."""
    from app.core.config import settings
    from app.infrastructure.loyalty_api.http_client import build_http_client

    email = (settings.loyalty_agent_service_email or "").strip().lower()
    if not email or not (settings.loyalty_agent_service_password or "").strip():
        print(
            "[ERROR] Para resolver el usuario hace falta LOYALTY_AGENT_SERVICE_EMAIL "
            "y LOYALTY_AGENT_SERVICE_PASSWORD en .env"
        )
        sys.exit(1)

    token = await auth.get_service_token()
    async with build_http_client() as client:
        resp = await client.get(
            f"/api/v1/companies/{company_id}/users",
            headers={"Authorization": f"Bearer {token}"},
        )
    if resp.status_code >= 400:
        print(f"[ERROR] loyalty GET .../users → {resp.status_code}: {resp.text[:500]}")
        sys.exit(1)

    users = resp.json()
    if not isinstance(users, list):
        print("[ERROR] Respuesta inesperada del loyalty (no es lista de usuarios)")
        sys.exit(1)

    for u in users:
        if str(u.get("email", "")).strip().lower() == email:
            uid = uuid.UUID(str(u["id"]))
            role = u.get("role") or "staff"
            if role not in ("platform_admin", "business_owner", "staff"):
                role = "staff"
            name = str(u.get("full_name") or email)
            return uid, role, name

    sample = ", ".join(str(u.get("email")) for u in users[:5])
    print(
        f"[ERROR] Ningún usuario de la empresa {company_id} tiene el email {email!r}.\n"
        f"  Primeros emails en la lista: {sample or '(vacío)'}\n"
        "  Si eres platform_admin, usa --user-id o DEV_USER_ID con tu UUID del core."
    )
    sys.exit(1)


async def main():
    args = _parse_args()

    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
    from langchain_openai import ChatOpenAI
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
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

    if not settings.agent_database_url.strip():
        print("[ERROR] AGENT_DATABASE_URL no está definida en .env")
        sys.exit(1)

    if not settings.openai_api_key:
        print("[ERROR] OPENAI_API_KEY no está configurado en .env")
        sys.exit(1)

    dsn = _to_psycopg_url(settings.agent_database_url)
    if not dsn.startswith("postgresql"):
        print("[ERROR] AGENT_DATABASE_URL debe ser una URL postgresql válida")
        sys.exit(1)

    company_id = uuid.UUID(args.company_id)
    auth = LoyaltyAuthManager(client_factory=build_http_client)

    manual_uid = (args.user_id or "").strip() or (os.getenv("DEV_USER_ID") or "").strip()
    if manual_uid:
        user_id = uuid.UUID(manual_uid)
        role: str = args.role
        display_name = args.name
        identity_note = "manual (--user-id o DEV_USER_ID)"
    else:
        user_id, role, display_name = await _resolve_identity_from_service_account(auth, company_id)
        identity_note = "API (email en LOYALTY_AGENT_SERVICE_EMAIL)"

    session_id = uuid.uuid4()

    print(f"\n{'='*60}")
    print("  Lumi — Dev Chat + Postgres checkpointer")
    print(f"{'='*60}")
    print(f"  Loyalty URL : {settings.loyalty_api_base_url}")
    print(f"  Postgres    : {_to_psycopg_url(settings.agent_database_url).split('@')[-1]}")
    print(f"  Modelo      : {settings.openai_model}")
    print(f"  company_id  : {company_id}")
    print(f"  user_id     : {user_id}")
    print(f"  rol         : {role}")
    print(f"  nombre      : {display_name}")
    print(f"  identidad   : {identity_note}")
    print(f"  session_ctx : {session_id}  (AgentTurnContext; thread_id vía /reset)")
    print(f"{'='*60}")
    print("  Comandos: /reset  /tools  /exit  /confirm")
    print(f"{'='*60}\n")

    loyalty = HttpLoyaltyServiceAdapter(auth)

    llm = ChatOpenAI(
        model=settings.openai_model,
        temperature=settings.openai_temperature,
        api_key=settings.openai_api_key,
    )

    checkpointer_cm = AsyncPostgresSaver.from_conn_string(dsn)
    async with checkpointer_cm as checkpointer:
        await checkpointer.setup()
        graph = create_react_agent(
            model=llm,
            tools=ALL_TOOLS,
            checkpointer=checkpointer,
        )

        system_prompt = render_system_prompt(
            company_id=str(company_id),
            internal_user_id=str(user_id),
            role=role,
            user_display_name=display_name,
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
                print(f"[nuevo thread_id (checkpoint): {thread_id}]\n")
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
                role=role,  # type: ignore[arg-type]
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
                ],
            }

            try:
                result = await graph.ainvoke(messages_input, config)
            except Exception as exc:
                print(f"[ERROR del agente] {exc}\n")
                continue

            msgs = result.get("messages", [])
            content = None
            for msg in reversed(msgs):
                c = getattr(msg, "content", None)
                if isinstance(c, str) and c.strip():
                    content = c
                    break

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
    # ProactorEventLoop (default en Windows) no es compatible con psycopg async.
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
