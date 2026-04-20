# Apoli · Techapoli Loyalty

**Apoli** es el asistente de fidelización de Techapoli: capa conversacional en **Python / FastAPI** sobre el API de loyalty. Usuarios internos (dueño, admin, staff) operan el programa por **Telegram** y **WhatsApp**, con LangGraph contra el core vía HTTP y confirmación explícita en acciones sensibles.

![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)

## Índice

- [Arquitectura](#arquitectura)
- [Requisitos](#requisitos)
- [Inicio rápido](#inicio-rápido)
- [Variables de entorno](#variables-de-entorno)
- [Base de datos](#base-de-datos)
- [Service account (loyalty)](#service-account-loyalty)
- [Onboarding de canales](#onboarding-de-canales)
- [Webhooks](#webhooks)
- [Probar en desarrollo](#probar-en-desarrollo)
- [Tests](#tests)
- [Estructura del repo](#estructura-del-repo)
- [Tools del agente](#tools-del-agente)
- [Documentación](#documentación)
- [Roadmap](#roadmap)

## Arquitectura

1. Mensaje entrante (Telegram / WhatsApp) → webhook valida firma / secreto.
2. Se resuelve `channel_identity_binding` → usuario interno del loyalty.
3. LangGraph ejecuta tools HTTP; acciones sensibles piden confirmación antes de aplicar.
4. Respuesta por el mismo canal (Bot API / Graph API).

```text
Usuario (Telegram / WhatsApp)
            │
            ▼
   [Webhook FastAPI] ──► 200 OK inmediato
            │
     BackgroundTask
            ▼
   ProcessInboundMessage
     ├── binding → internal_user + JWT
     ├── sesión + mensajes (Postgres)
     └── LangGraph ReAct + tools
            │
            ▼
   OutboundAdapter → Telegram / WhatsApp
```

## Requisitos

| Componente | Notas |
|------------|--------|
| **Python** | 3.11+ |
| **PostgreSQL** | 12+ (base propia del agente) |
| **Loyalty API** | Instancia del core (ej. `http://localhost:8000`) |
| **OpenAI** | API key para el modelo configurado |

## Inicio rápido

```bash
git clone https://github.com/JuanHenao31/loyalty-agent.git
cd loyalty-agent

python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
# Edita .env (ver tabla siguiente + comentarios en .env.example)

# Crear DB y migrar
createdb loyalty_agent   # o CREATE DATABASE desde psql
alembic upgrade head

uvicorn main:app --host 0.0.0.0 --port 9000 --reload
```

Comprobar salud: `curl http://localhost:9000/health` → `{"status":"ok"}`  
Swagger: [http://localhost:9000/docs](http://localhost:9000/docs)

## Variables de entorno

Valores de ejemplo y descripciones cortas están en [`.env.example`](./.env.example).

### Núcleo (PMV)

| Variable | Uso |
|----------|-----|
| `OPENAI_API_KEY` | Llamadas al modelo |
| `OPENAI_MODEL` | Por defecto `gpt-4o-mini` |
| `LOYALTY_API_BASE_URL` | URL base del loyalty |
| `LOYALTY_AGENT_SERVICE_EMAIL` / `LOYALTY_AGENT_SERVICE_PASSWORD` | Service account (`business_owner`) para lecturas |
| `AGENT_DATABASE_URL` | Postgres async (SQLAlchemy + asyncpg) |
| `REFRESH_TOKEN_ENCRYPTION_KEY` | Fernet para cifrar refresh tokens en bindings |

Generar Fernet:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Telegram

| Variable | Uso |
|----------|-----|
| `TELEGRAM_BOT_TOKEN` | Envío de respuestas (`sendMessage`) |
| `TELEGRAM_WEBHOOK_SECRET` | Opcional: si está definido, debe coincidir con `secret_token` en `setWebhook` y con la cabecera `X-Telegram-Bot-Api-Secret-Token` |

### WhatsApp (Cloud API)

| Variable | Uso |
|----------|-----|
| `WHATSAPP_VERIFY_TOKEN` | Verificación GET del webhook |
| `WHATSAPP_ACCESS_TOKEN` / `WHATSAPP_PHONE_NUMBER_ID` | Envío de mensajes |
| `WHATSAPP_APP_SECRET` | Validación `X-Hub-Signature-256` |

Para **solo Telegram** en local puedes dejar las variables de WhatsApp vacías; el servidor arranca igual.

## Base de datos

La base del **agente** es independiente del loyalty: sesiones, mensajes, auditoría, confirmaciones, bindings.

```bash
alembic upgrade head
```

## Service account (loyalty)

El agente usa un usuario de servicio en el loyalty para operaciones de lectura. Creación típica (ajusta host, admin y `COMPANY_ID`):

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@techapoli.com", "password": "tu-password"}'

curl -s -X POST "http://localhost:8000/api/v1/companies/COMPANY_ID/users" \
  -H "Authorization: Bearer ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "full_name": "Loyalty Agent",
    "email": "agent@techapoli.com",
    "password": "contraseña-segura",
    "role": "business_owner"
  }'
```

Esas credenciales van en `LOYALTY_AGENT_SERVICE_*`.

## Onboarding de canales

Cada chat debe mapearse a un `internal_user` mediante la tabla `channel_identity_bindings` (inserción manual en el PMV; UI prevista en v2). Sin fila válida, el bot responde que el chat no está vinculado.

Pseudoflujo: login del usuario en loyalty → cifrar `refresh_token` con `encrypt_token` → insertar fila con `channel`, `channel_user_id` (teléfono o `chat.id` de Telegram), `company_id`, `internal_user_id`, rol, etc.

## Webhooks

Los endpoints viven bajo el mismo host que la app (por defecto puerto **9000**).

| Canal | Método | Ruta |
|-------|--------|------|
| Telegram | `POST` | `/webhooks/telegram` |
| WhatsApp | `GET` + `POST` | `/webhooks/whatsapp` |

**HTTPS público:** Telegram y Meta requieren URL accesible; en local suele usarse [ngrok](https://ngrok.com) (`ngrok http 9000`).

### Telegram — `setWebhook`

```bash
curl "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook" \
  -d "url=https://TU-DOMINIO/webhooks/telegram" \
  -d "secret_token=${TELEGRAM_WEBHOOK_SECRET}"
```

> Un mismo bot solo puede tener **un** webhook activo. Si otro sistema (p. ej. n8n) ya registró el bot, hay que decidir qué URL queda en Telegram.

### WhatsApp — Meta

En Meta for Developers → WhatsApp → Configuración:

- **Callback URL:** `https://TU-DOMINIO/webhooks/whatsapp`
- **Verify token:** valor de `WHATSAPP_VERIFY_TOKEN`
- Suscripción al campo `messages`

## Probar en desarrollo

### Chat por consola (sin Telegram/WhatsApp)

Útil con el loyalty corriendo y variables en `.env`:

```bash
pip install python-dotenv   # si no está ya en tu entorno

python scripts/dev_chat.py \
  --company-id <UUID-empresa> \
  --role business_owner \
  --name "Tu nombre"
```

| Comando | Efecto |
|---------|--------|
| `/reset` | Nueva conversación |
| `/tools` | Lista tools (lectura / sensible) |
| `/confirm` | Confirma la última propuesta |
| `/exit` | Sale |

### Simular webhook Telegram (`curl`)

Si `TELEGRAM_WEBHOOK_SECRET` está vacío, no hace falta la cabecera.

```bash
curl -X POST http://localhost:9000/webhooks/telegram \
  -H "Content-Type: application/json" \
  -H "X-Telegram-Bot-Api-Secret-Token: ${TELEGRAM_WEBHOOK_SECRET}" \
  -d '{
    "update_id": 1,
    "message": {
      "message_id": 1,
      "chat": {"id": 123456789, "first_name": "Juan", "type": "private"},
      "text": "¿cuántos puntos tiene Laura?"
    }
  }'
```

La API responde al instante; el procesamiento sigue en background.

## Tests

```bash
pytest tests/unit -q
pytest tests/unit --cov=app --cov-report=term-missing
```

Cubren utilidades de idempotencia, Fernet, auth manager, cliente HTTP, guardrails RBAC, etc.

## Estructura del repo

<details>
<summary><strong>Árbol principal</strong> (clic para expandir)</summary>

```text
loyalty_agent/
├── main.py                 # FastAPI + lifespan
├── alembic/                # Migraciones Postgres
├── app/
│   ├── core/               # Settings, DB, logging, seguridad
│   ├── domain/             # Entidades + puertos
│   ├── application/        # DTOs, políticas, casos de uso
│   ├── agent/              # LangGraph, prompts, tools
│   ├── infrastructure/     # HTTP loyalty, mensajería, modelos SQLAlchemy, auditoría
│   ├── entrypoints/        # health + webhooks
│   └── shared/
├── scripts/dev_chat.py
└── tests/unit/
```

</details>

## Tools del agente

| Tool | Tipo | Descripción |
|------|------|-------------|
| `find_customer` | Lectura | Búsqueda por nombre / email / teléfono |
| `get_customer_loyalty_status` | Lectura | Puntos y estado de tarjeta |
| `get_customer_rewards` | Lectura | Recompensas y elegibilidad |
| `get_customer_history` | Lectura | Movimientos recientes |
| `get_company_analytics` | Lectura | Métricas del programa |
| `explain_loyalty_policy` | Lectura | Política del programa |
| `create_customer_with_card` | Sensible | Alta + tarjeta (confirmación) |
| `add_points` | Sensible | Suma puntos (confirmación) |
| `redeem_reward` | Sensible | Canje (confirmación) |
| `revoke_card` | Sensible | Revoca tarjeta — owner+ (confirmación) |

## Documentación

Especificación ampliada del PMV: [`techapoli_loyalty_agent_pmv.md`](./techapoli_loyalty_agent_pmv.md).

### Identidad del asistente

El nombre público es **Apoli** (asistente de fidelización Techapoli). Nombre, mensajes fijos de onboarding/errores y título por defecto de la API viven en `app/core/branding.py`; el tono y reglas conversacionales del modelo están en `app/agent/prompts/system.py`.

## Roadmap

- Onboarding conversacional (vincular identidad desde el chat)
- Web UI con streaming (SSE)
- Resúmenes de conversación larga
- Memoria semántica / RAG
- Multiagente
- Canales de voz
