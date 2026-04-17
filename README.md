# Techapoli Loyalty Agent

Microservicio agéntico en Python que actúa como capa conversacional sobre el microservicio de loyalty de Techapoli. Permite a usuarios internos del negocio (dueños, administradores, staff) operar el programa de fidelización por chat desde **Telegram** y **WhatsApp**.

---

## Cómo funciona

1. El usuario manda un mensaje desde Telegram o WhatsApp.
2. El webhook del agente valida la firma del canal y normaliza el mensaje.
3. Se busca el binding `(canal, usuario)` → `internal_user` del loyalty.
4. El agente LangGraph elige qué herramienta invocar, la ejecuta contra el loyalty core vía HTTP y construye la respuesta.
5. Para acciones sensibles (crear cliente, sumar puntos, redimir, revocar tarjeta) el agente **propone primero y espera confirmación explícita** antes de ejecutar.
6. La respuesta sale por el mismo canal de entrada.

```
Usuario WhatsApp/Telegram
        │
        ▼
[Webhook FastAPI]  ──valida firma──► 200 OK inmediato
        │
  BackgroundTask
        │
        ▼
[ProcessInboundMessage]
  ├── lookup channel_identity_binding
  ├── get/create agent_session
  ├── fetch user JWT (refresh_token cifrado)
  └── LangGraph ReAct Agent
        ├── tool: find_customer
        ├── tool: get_customer_loyalty_status
        ├── tool: add_points  ◄── interrupt_before (pide confirmación)
        └── ...
        │
        ▼
[OutboundAdapter]  ──► Telegram Bot API / WhatsApp Graph API
```

---

## Requisitos previos

| Herramienta | Versión mínima |
|---|---|
| Python | 3.11+ |
| PostgreSQL | 12+ |
| [loyalty core](../loyalty) | corriendo en `http://localhost:8000` |

---

## Instalación

```bash
# 1. Clonar / navegar al directorio
cd loyalty_agent

# 2. Crear y activar entorno virtual
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
.venv\Scripts\activate           # Windows

# 3. Instalar dependencias
pip install -r requirements.txt
```

---

## Configuración

```bash
cp .env.example .env
```

Edita `.env` con tus valores. Las variables obligatorias para el PMV son:

| Variable | Descripción |
|---|---|
| `OPENAI_API_KEY` | API key de OpenAI |
| `OPENAI_MODEL` | Modelo a usar (default: `gpt-4o-mini`) |
| `LOYALTY_API_BASE_URL` | URL base del loyalty core (ej. `http://localhost:8000`) |
| `LOYALTY_AGENT_SERVICE_EMAIL` | Email del service account en el loyalty (rol `business_owner`) |
| `LOYALTY_AGENT_SERVICE_PASSWORD` | Password del service account |
| `AGENT_DATABASE_URL` | URL de la base Postgres del agente (ej. `postgresql+asyncpg://postgres:postgres@localhost:5432/loyalty_agent`) |
| `REFRESH_TOKEN_ENCRYPTION_KEY` | Clave Fernet para cifrar refresh tokens (ver abajo) |
| `TELEGRAM_BOT_TOKEN` | Token del bot de Telegram |
| `TELEGRAM_WEBHOOK_SECRET` | Secret configurado al registrar el webhook en Telegram |
| `WHATSAPP_VERIFY_TOKEN` | Token de verificación del webhook de Meta |
| `WHATSAPP_ACCESS_TOKEN` | Token de acceso de WhatsApp Cloud API |
| `WHATSAPP_PHONE_NUMBER_ID` | ID del número de WhatsApp en Meta |
| `WHATSAPP_APP_SECRET` | App secret de Meta para validar firmas HMAC |

### Generar la clave Fernet

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Pega el resultado en `REFRESH_TOKEN_ENCRYPTION_KEY`.

---

## Base de datos del agente

La base de datos del agente es **independiente** de la del loyalty core. Almacena sesiones conversacionales, mensajes, logs de tools, confirmaciones pendientes y auditoría.

```bash
# Crear la base (si no existe)
createdb loyalty_agent   # o desde psql: CREATE DATABASE loyalty_agent;

# Aplicar migraciones
alembic upgrade head
```

---

## Service account en el loyalty core

El agente necesita un usuario interno en el loyalty para hacer llamadas de lectura. Créalo con la API del loyalty:

```bash
# 1. Login como platform_admin
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@techapoli.com", "password": "tu-password"}'

# Guarda el access_token como ADMIN_TOKEN

# 2. Crear el service account
curl -X POST http://localhost:8000/api/v1/companies/{COMPANY_ID}/users \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "full_name": "Loyalty Agent",
    "email": "agent@techapoli.com",
    "password": "contraseña-segura",
    "role": "business_owner"
  }'
```

Luego pon ese email y password en `LOYALTY_AGENT_SERVICE_EMAIL` / `LOYALTY_AGENT_SERVICE_PASSWORD`.

---

## Vincular usuarios de chat al loyalty (onboarding)

Cada usuario interno que quiera usar el bot debe tener su identidad de chat vinculada a su `internal_user` del loyalty. Esto se hace una sola vez insertando directamente en `channel_identity_bindings` (flujo de UI de onboarding pendiente en v2):

```python
from app.core.security import encrypt_token
# Obtener el refresh_token del loyalty haciendo login con las credenciales del usuario
# Luego insertar en la tabla:
# channel="telegram", channel_user_id="<chat_id>", company_id=..., internal_user_id=...,
# internal_user_email=..., internal_user_role="staff",
# encrypted_refresh_token=encrypt_token("<refresh_token_del_loyalty>")
```

---

## Levantar el servidor

```bash
# Desarrollo (con hot reload)
python main.py

# O directamente con uvicorn
uvicorn main:app --host 0.0.0.0 --port 9000 --reload
```

El servidor queda disponible en `http://localhost:9000`.

**Health check:**
```bash
curl http://localhost:9000/health
# {"status": "ok"}
```

---

## Registrar webhooks

### Telegram

```bash
curl "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook" \
  -d "url=https://TU-DOMINIO/webhooks/telegram" \
  -d "secret_token=${TELEGRAM_WEBHOOK_SECRET}"
```

### WhatsApp

En el panel de Meta for Developers → tu app → WhatsApp → Configuración:
- **Callback URL**: `https://TU-DOMINIO/webhooks/whatsapp`
- **Verify Token**: el valor de `WHATSAPP_VERIFY_TOKEN`
- Suscribirse al campo `messages`

> Para pruebas locales usá [ngrok](https://ngrok.com): `ngrok http 9000` y registrá la URL pública.

---

## Probar la app

### Opción 1 — FastAPI `/docs` (Swagger UI)

Levantá el server y abrí `http://localhost:9000/docs`.  
Verás los endpoints disponibles: `/health`, `/webhooks/telegram`, `/webhooks/whatsapp`.  
Útil para probar el health check o simular un payload de webhook manualmente.

### Opción 2 — Chat interactivo por consola (recomendado en dev)

Habla con el agente directamente desde la terminal, sin necesitar Telegram ni WhatsApp.  
Usa `MemorySaver` (sin Postgres) y el loyalty core real si está corriendo.

```bash
# Instalar dependencia extra del script
pip install python-dotenv

# Levantar el loyalty core primero (en otra terminal)
# cd ../loyalty && uvicorn main:app --port 8000

# Correr el chat
python scripts/dev_chat.py

# Con parámetros explícitos
python scripts/dev_chat.py \
  --company-id <UUID-de-tu-empresa> \
  --role business_owner \
  --name "Juan David"
```

**Comandos disponibles en el chat:**

| Comando | Qué hace |
|---|---|
| `/reset` | Borra el contexto y empieza una conversación nueva |
| `/tools` | Lista todas las tools con su tipo (lectura / sensible) |
| `/confirm` | Atajo para responder "sí, confirmo" a una propuesta del agente |
| `/exit` | Salir |

**Ejemplo de sesión:**

```
Tú: ¿cuántos puntos tiene Laura?
  [tool → find_customer] args: {'query': 'Laura'}
  [tool result] [{"id": "...", "first_name": "Laura", ...}]
  [tool → get_customer_loyalty_status] args: {'customer_id': '...'}
  [tool result] {"has_card": true, "current_points_balance": 12, ...}

Agente: Laura tiene 12 puntos en su tarjeta activa, con vencimiento el 17/04/2027.

Tú: súmale 5 puntos por corte
  [tool ⚠️ add_points] args: {'customer_id': '...', 'points': 5, 'reason': 'corte'}

Agente: Voy a sumarle 5 puntos a Laura por "corte". ¿Confirmas?

Tú: /confirm
Agente: Listo. Laura ahora tiene 17 puntos.
```

> **Nota:** Las variables de entorno del `.env` se cargan automáticamente.  
> Si el loyalty core no está corriendo, las tools de lectura fallarán con un error de conexión pero el agente seguirá respondiendo.

### Opción 3 — `curl` para webhooks

```bash
# Health check
curl http://localhost:9000/health

# Simular un mensaje de Telegram (sin validación de firma en dev)
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
# Responde 200 inmediatamente; el agente procesa en background
```

### Opción 4 — ngrok para canales reales

```bash
# En una terminal: levantar el agente
uvicorn main:app --port 9000

# En otra: exponer con ngrok
ngrok http 9000

# Registrar la URL en Telegram
curl "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook" \
  -d "url=https://XXXX.ngrok.io/webhooks/telegram" \
  -d "secret_token=${TELEGRAM_WEBHOOK_SECRET}"
```

---

## Tests

```bash
# Solo unitarios (sin Postgres ni loyalty core)
pytest tests/unit -q

# Con cobertura
pytest tests/unit --cov=app --cov-report=term-missing
```

Los tests unitarios cubren:
- Idempotency key derivation (determinista y sensible a entradas)
- Cifrado/descifrado Fernet de refresh tokens
- Auth manager: login, cache, expiración y refresh por usuario
- HTTP client: inyección de `Authorization` + `Idempotency-Key`, mapeo de errores
- Guardrails RBAC por rol

---

## Estructura del proyecto

```
loyalty_agent/
├── main.py                          # FastAPI app + lifespan (agent runtime)
├── alembic/                         # Migraciones Postgres del agente
│   └── versions/001_initial.py
├── app/
│   ├── core/                        # Config (Pydantic Settings), logging, Fernet, DB engine
│   ├── domain/
│   │   ├── entities/loyalty.py      # DTOs que espejean la API del loyalty core
│   │   └── ports/                   # Interfaces abstractas (LoyaltyServicePort, etc.)
│   ├── application/
│   │   ├── dto/inbound.py           # InboundMessageCommand (canal-agnóstico)
│   │   ├── policies/guardrails.py   # Detección off-topic, RBAC pre-checks
│   │   └── use_cases/
│   │       └── process_inbound_message.py  # Orquestación principal
│   ├── agent/
│   │   ├── runtime.py               # create_react_agent + PostgresSaver
│   │   ├── guardrails.py            # SENSITIVE_TOOLS, tool_allowed_for_role
│   │   ├── prompts/system.py        # System prompt + política del programa
│   │   └── tools/                   # 10 tools (una por archivo)
│   ├── infrastructure/
│   │   ├── loyalty_api/
│   │   │   ├── auth_manager.py      # Service account + refresh por usuario
│   │   │   └── http_client.py       # HttpLoyaltyServiceAdapter (httpx)
│   │   ├── messaging/               # TelegramOutboundAdapter, WhatsAppOutboundAdapter
│   │   ├── persistence/models/      # 9 modelos SQLAlchemy
│   │   └── audit/postgres_audit.py
│   ├── entrypoints/
│   │   ├── http/health.py
│   │   └── webhooks/
│   │       ├── telegram.py          # POST /webhooks/telegram
│   │       └── whatsapp.py          # GET + POST /webhooks/whatsapp
│   └── shared/
│       ├── exceptions.py
│       └── ids.py                   # derive_idempotency_key
└── tests/
    └── unit/                        # 18 tests, sin dependencias externas
```

---

## Tools disponibles

| Tool | Tipo | Descripción |
|---|---|---|
| `find_customer` | Lectura | Busca clientes por nombre/email/teléfono |
| `get_customer_loyalty_status` | Lectura | Saldo de puntos y estado de tarjeta |
| `get_customer_rewards` | Lectura | Recompensas activas, marcadas como alcanzables o no |
| `get_customer_history` | Lectura | Últimos movimientos de earn/redeem |
| `get_company_analytics` | Lectura | Métricas del programa (clientes, puntos, redenciones) |
| `explain_loyalty_policy` | Lectura | Política del programa (expiración, canje, tarjetas) |
| `create_customer_with_card` | **Sensible** | Crea cliente + inscribe tarjeta (pide confirmación) |
| `add_points` | **Sensible** | Suma puntos a la tarjeta activa (pide confirmación) |
| `redeem_reward` | **Sensible** | Canjea una recompensa (pide confirmación) |
| `revoke_card` | **Sensible** | Revoca tarjeta — solo `business_owner`+ (pide confirmación) |

---

## Variables de entorno completas

Ver `.env.example` para la lista completa con descripciones.

---

## Roadmap v2

- Flujo de onboarding conversacional (vincular chat identity desde el propio chat)
- Web UI con streaming SSE
- Resúmenes automáticos de conversaciones largas
- Memoria semántica / RAG
- Multiagente
- Canales de voz
#   l o y a l t y - a g e n t  
 