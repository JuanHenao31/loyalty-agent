# PMV — Microservicio de Agente IA para Techapoli Loyalty

**Asistente de producto:** **Lumi** — asistente inteligente de fidelización. Lumi es la voz y la persona del sistema en canales conversacionales (Telegram, WhatsApp y, más adelante, web). Promesa de marca: *Lumi hace simple la fidelización*; narrativa: claridad (nieve / *lumi*) y guía (luz / *lúmen*).

## 1. Visión del producto

**Techapoli Loyalty Agent** (motor del asistente **Lumi**) será un microservicio en **Python** encargado de actuar como un **usuario inteligente del sistema de loyalty**, orientado exclusivamente a **usuarios internos del negocio**. Su propósito es reducir la necesidad de que el humano entre al frontend para tareas operativas y consultas del programa de fidelización.

El agente podrá:

- responder preguntas sobre clientes, puntos, recompensas y estado del programa;
- ejecutar acciones sobre el microservicio de loyalty;
- solicitar confirmación humana antes de ejecutar operaciones sensibles;
- mantener contexto conversacional por usuario interno;
- operar por múltiples canales, iniciando en **WhatsApp** y **Telegram**, con posibilidad de extenderse a web UI.

El agente será **single-agent with tools**. Esta decisión encaja con el PMV porque LangChain Agents está pensado para sistemas donde el modelo razona, decide qué tools usar y ejecuta un loop de acción hasta llegar a una salida. Además, LangChain Agents está construido sobre LangGraph, por lo que hereda capacidades como durable execution, streaming, human-in-the-loop y persistence sin obligar a bajar a un nivel más complejo desde el primer día. citeturn753761search8turn753761search26turn753761search1

---

## 2. Objetivo del PMV

Construir un microservicio agéntico que permita a un usuario interno del negocio interactuar por chat con el sistema de loyalty para:

- consultar puntos de clientes;
- consultar recompensas disponibles;
- crear clientes;
- asignar puntos;
- redimir recompensas;
- consultar historial básico;
- consultar analytics básicas;
- ejecutar cualquier endpoint relevante del microservicio de loyalty, siempre bajo reglas y validaciones.

El agente debe funcionar como una **capa conversacional e inteligente sobre el microservicio de loyalty**, no como una fuente de verdad independiente.

---

## 3. Alcance del PMV

### 3.1 Incluido

- microservicio en Python;
- integración con **OpenAI** como modelo;
- uso de **LangChain Agents**;
- memoria conversacional en **PostgreSQL**;
- integración con el **microservicio de loyalty** mediante puertos/adaptadores;
- entrada por **WhatsApp** y **Telegram**;
- respuesta síncrona o asíncrona según caso de uso;
- soporte de streaming para UI cuando aplique;
- auditoría completa de conversaciones, decisiones y tool calls;
- confirmación humana obligatoria para acciones sensibles;
- guardrails de dominio para restringir al agente al contexto loyalty.

### 3.2 Fuera de alcance

- multiagentes;
- RAG complejo;
- fine-tuning;
- voz;
- campañas automáticas complejas;
- decisiones sin confirmación humana en acciones sensibles;
- integración directa con PassKit, Passcreator u otros desde el agente;
- memoria semántica/vectorial avanzada;
- temas fuera del dominio loyalty.

---

## 4. Actores

### 4.1 Usuario interno del negocio
Recepcionista, administrador o dueño del negocio que conversa con el agente desde WhatsApp, Telegram o UI.

### 4.2 Agente IA
Entidad conversacional que interpreta intención, consulta contexto, usa tools y responde.

### 4.3 Microservicio Loyalty
Sistema core donde viven clientes, puntos, recompensas, tarjetas, redenciones y reglas de negocio.

### 4.4 OpenAI
Proveedor del modelo que interpreta, decide herramientas, redacta respuestas y resume contexto.

---

## 5. Principios de diseño

El microservicio debe construirse con:

- **arquitectura limpia**;
- **puertos y adaptadores**;
- principios **SOLID**;
- principio **DRY**;
- separación estricta entre dominio, aplicación e infraestructura;
- nula dependencia del agente con la base de datos del loyalty core;
- nula lógica de negocio sensible directamente embebida en el canal.

### Regla central
El agente **nunca** debe manipular directamente la base de datos del loyalty core. Toda interacción con loyalty se hará mediante **puertos/casos de uso** expuestos por el microservicio de loyalty.

---

## 6. Decisión tecnológica principal

### 6.1 Framework agéntico
**LangChain Agents**

#### Justificación
LangChain Agents permite construir un agente con tools, razonamiento iterativo y orquestación rápida. LangChain documenta que un agent corre tools en loop hasta cumplir un objetivo o llegar a una condición de parada. También recomienda usar sus agents como la opción de más alto nivel para empezar rápido, mientras que LangGraph da más control cuando el problema necesita durable execution, streaming y human-in-the-loop más complejos. citeturn753761search8turn753761search1turn753761search26

#### Diferencia con LangGraph
- **LangChain Agents**: más alto nivel, ideal para empezar rápido con tools y loop agéntico. citeturn753761search8turn753761search26
- **LangGraph**: más control, más explícito para state machines, durable execution, streaming y human-in-the-loop complejos. citeturn753761search1turn753761search5

#### Decisión PMV
Usar **LangChain Agents** para el PMV. Dejar la puerta abierta a migrar ciertos flujos a LangGraph si luego aparecen necesidades más complejas de orquestación.

### 6.2 Modelo
**Modelo de OpenAI configurable por variable de entorno**.

El modelo será responsable de:
- interpretación de intención;
- selección de tools;
- composición de respuestas;
- confirmación de acciones;
- resúmenes de contexto;
- manejo conversacional.

### 6.3 Persistencia
**PostgreSQL** como almacenamiento de memoria conversacional, sesiones, mensajes, tool calls y auditoría.

### 6.4 Comunicación con clientes/canales
- **Webhook-based ingestion** para WhatsApp y Telegram;
- respuesta síncrona o asíncrona según caso de uso;
- soporte de streaming hacia UI cuando aplique.

Telegram soporta dos formas de recibir actualizaciones: `getUpdates` y **webhooks**; para producción, webhook es la opción natural cuando se quiere que Telegram empuje mensajes al servidor. WhatsApp Cloud API usa **webhooks** para recibir mensajes/eventos y su API para enviar respuestas. citeturn753761search2turn753761search6turn753761search7turn753761search11

---

## 7. Arquitectura propuesta

### 7.1 Estilo arquitectónico
**Microservicio hexagonal / ports and adapters**

### 7.2 Capas
- **Domain**
- **Application**
- **Infrastructure**
- **Entrypoints / Adapters**

### 7.3 Flujo lógico de alto nivel

1. Llega un mensaje desde WhatsApp, Telegram o UI.
2. El adapter del canal transforma el mensaje a un comando interno uniforme.
3. La capa de aplicación carga la sesión y la memoria del usuario.
4. El agente LangChain recibe:
   - mensaje actual,
   - contexto reciente,
   - perfil del usuario,
   - tools disponibles,
   - guardrails del dominio loyalty.
5. El modelo decide:
   - responder directamente,
   - o invocar una o varias tools.
6. Si la acción es sensible, el agente primero pide confirmación humana.
7. Una vez confirmada, la tool llama al puerto del loyalty core.
8. Se persiste:
   - mensaje,
   - decisión,
   - tool calls,
   - resultado,
   - auditoría.
9. La respuesta sale por el mismo canal de entrada.

---

## 8. Módulos principales

### 8.1 `conversation`
Maneja sesiones, mensajes, contexto y recuperación de memoria.

### 8.2 `agent_runtime`
Contiene la configuración del agente LangChain, tools registry, prompt base, middleware y guardrails.

### 8.3 `loyalty_tools`
Define herramientas para hablar con el microservicio de loyalty.

### 8.4 `channel_adapters`
Adapters para WhatsApp, Telegram y UI.

### 8.5 `memory`
Maneja persistencia del historial conversacional y resumen de contexto en PostgreSQL.

### 8.6 `audit`
Registra prompts, respuestas, tool calls, confirmaciones, errores y acciones sensibles.

### 8.7 `orchestration`
Gestiona flujos síncronos, asíncronos y streaming.

### 8.8 `security`
Autenticación del usuario del negocio, autorización, correlación por empresa y validación de alcance.

---

## 9. Casos de uso del PMV

### 9.1 Consultar puntos de un cliente
Ejemplo:
> “¿Cuántos puntos tiene Juan David?”

### 9.2 Consultar recompensas disponibles
Ejemplo:
> “¿Qué recompensas tiene disponibles este cliente?”

### 9.3 Crear cliente
Ejemplo:
> “Créame un cliente llamado Laura Pérez, correo X y teléfono Y.”

#### Regla
Debe pedir confirmación antes de ejecutar.

### 9.4 Asignar puntos
Ejemplo:
> “Súmale 3 puntos a Laura por combo corte + barba.”

#### Regla
Debe:
- validar que el cliente exista;
- validar campos mínimos;
- resumir la operación;
- pedir confirmación;
- ejecutar la tool solo tras confirmación.

### 9.5 Redimir recompensa
Ejemplo:
> “Canjéale la recompensa de 7 puntos.”

#### Regla
Debe:
- validar saldo;
- explicar qué va a hacer;
- pedir confirmación;
- ejecutar;
- informar resultado final.

### 9.6 Consultar historial
Ejemplo:
> “Muéstrame los últimos movimientos de este cliente.”

### 9.7 Consultar analytics básicas
Ejemplo:
> “¿Cuántas tarjetas activas tiene la empresa?”
> “¿Cuántos puntos se redimieron este mes?”

### 9.8 Responder FAQs del programa
Ejemplo:
> “¿Los puntos vencen?”
> “¿Cómo funciona el canje?”

### 9.9 Resumen operativo
Ejemplo:
> “Resúmeme la actividad loyalty de hoy.”

---

## 10. Confirmación humana

Toda acción sensible debe requerir **confirmación explícita**.

### 10.1 Acciones sensibles
- crear cliente;
- asignar puntos;
- redimir recompensa;
- revocar tarjeta;
- cualquier modificación de estado;
- cualquier operación que altere datos de negocio.

### 10.2 Patrón de interacción
1. El usuario pide la acción.
2. El agente valida y arma una propuesta.
3. El agente responde algo como:
   > “Voy a crear el cliente Laura Pérez con correo X y teléfono Y. ¿Confirmas?”
4. Solo si el usuario confirma, la tool se ejecuta.

LangChain documenta un middleware de **human-in-the-loop** que permite pausar tool calls para revisión humana antes de ejecutar acciones sensibles. citeturn753761search0turn753761search16

---

## 11. Memoria del agente

### 11.1 Alcance de memoria
La memoria será **por usuario interno**.

#### Llave sugerida
- `company_id`
- `internal_user_id`
- `channel`
- `conversation_id` opcional

### 11.2 Qué se guarda
- historial de mensajes;
- contexto reciente;
- últimas entidades referidas;
- últimas confirmaciones pendientes;
- resultados de tool calls;
- resumen corto de conversación.

### 11.3 Qué no se guarda por ahora
- vector embeddings;
- memoria semántica avanzada;
- conocimiento corporativo fuera del historial;
- preferencias complejas.

### 11.4 Expiración
Configurable por variable de entorno o política.

Ejemplo:
- 24 horas
- 7 días
- 30 días

### 11.5 Fuente de verdad
La memoria del agente **no reemplaza** el estado oficial del loyalty core. Sirve solo para continuidad conversacional.

---

## 12. Modelo de datos sugerido en PostgreSQL

### `agent_sessions`
- id
- company_id
- internal_user_id
- channel
- status
- last_activity_at
- expires_at
- created_at

### `agent_messages`
- id
- session_id
- role
- message_text
- raw_payload_json
- created_at

### `agent_runs`
- id
- session_id
- input_message_id
- model_name
- status
- started_at
- finished_at
- latency_ms

### `tool_execution_logs`
- id
- run_id
- tool_name
- input_json
- output_json
- success
- error_message
- created_at

### `confirmation_requests`
- id
- session_id
- action_type
- payload_json
- status
- expires_at
- created_at
- confirmed_at

### `conversation_summaries`
- id
- session_id
- summary_text
- generated_at

### `guardrail_events`
- id
- session_id
- event_type
- message
- metadata_json
- created_at

### `agent_audit_logs`
- id
- company_id
- internal_user_id
- session_id
- action
- entity_type
- entity_id
- metadata_json
- created_at

---

## 13. Puertos y adaptadores

### 13.1 Puertos de entrada
Interfaces abstractas para recibir mensajes desde:
- WhatsApp
- Telegram
- Web UI

Ejemplo conceptual:
- `InboundMessagePort`

### 13.2 Puertos de salida
Interfaces abstractas para:
- responder mensajes;
- invocar microservicio loyalty;
- persistir memoria;
- registrar auditoría;
- llamar a OpenAI.

Ejemplo conceptual:
- `OutboundMessagePort`
- `LoyaltyServicePort`
- `MemoryRepositoryPort`
- `AuditRepositoryPort`
- `LLMPort`

### 13.3 Adaptadores de entrada
- `WhatsAppWebhookAdapter`
- `TelegramWebhookAdapter`
- `UiChatAdapter`

### 13.4 Adaptadores de salida
- `WhatsAppSenderAdapter`
- `TelegramSenderAdapter`
- `OpenAIAdapter`
- `PostgresMemoryAdapter`
- `PostgresAuditAdapter`
- `HttpLoyaltyApiAdapter`

---

## 14. Integración con canales

### 14.1 WhatsApp
Recomendación:
- recibir mensajes por webhook;
- enviar respuestas por la API del canal;
- normalizar payload al modelo interno del agente.

Meta documenta que WhatsApp Cloud API permite enviar mensajes y recibir webhooks, y que el messages webhook describe mensajes entrantes y estados de entrega. citeturn753761search7turn753761search11turn753761search15

### 14.2 Telegram
Recomendación:
- usar webhook en producción;
- transformar `Update` a un `InboundMessageCommand` interno.

Telegram documenta que existen dos formas mutuamente excluyentes de recibir updates: `getUpdates` y webhooks. citeturn753761search2turn753761search6turn753761search10

### 14.3 UI Web
Para UI propia:
- endpoint HTTP o WebSocket/SSE para enviar mensajes;
- streaming opcional de respuesta.

LangChain documenta streaming para mostrar progreso y actualizaciones en tiempo real durante runs de agentes. citeturn753761search12turn753761search16

---

## 15. Modo de ejecución

### 15.1 Híbrido con sesgo asíncrono
El microservicio debe soportar:

#### Síncrono
Para consultas rápidas:
- consultar puntos;
- consultar recompensas;
- responder FAQ.

#### Asíncrono
Para acciones que pueden tardar o requerir confirmación:
- crear cliente;
- asignar puntos;
- redimir;
- generar resúmenes;
- procesos de varias etapas.

#### Patrón recomendado
- respuesta inmediata: “Estoy creando el cliente…”
- ejecución en background;
- respuesta final cuando termine.

LangGraph y LangChain resaltan durable execution, streaming y human-in-the-loop como capacidades clave para agentes de larga duración o con pasos múltiples. citeturn753761search1turn753761search5turn753761search16

---

## 16. Streaming

### 16.1 Necesidad
Sí, debe soportarse en el PMV para UI.

### 16.2 Recomendación
- streaming hacia UI web;
- no obligatorio para WhatsApp/Telegram;
- usar SSE o WebSocket en la capa web.

LangChain documenta streaming de updates en tiempo real durante agent runs para mejorar la experiencia de usuario. citeturn753761search12turn753761search16

---

## 17. Tools del agente

El agente debe exponer tools que representen casos de uso del loyalty core, no endpoints crudos.

### 17.1 Tools sugeridas
- `find_customer`
- `get_customer_points`
- `get_customer_rewards`
- `create_customer`
- `add_points`
- `redeem_reward`
- `get_customer_history`
- `get_company_analytics`
- `explain_loyalty_policy`

LangChain define tools como funciones invocables con inputs y outputs claros que el modelo puede decidir usar según el contexto. citeturn753761search23turn753761search8

### 17.2 Regla de diseño
Cada tool debe:
- validar entrada;
- no contener lógica de canal;
- no tocar directamente la base de loyalty;
- depender de un puerto de aplicación.

---

## 18. Guardrails

El agente debe estar restringido al dominio loyalty.

### 18.1 Restricciones de alcance
No debe:
- responder sobre política;
- responder sobre religión;
- responder sobre finanzas personales fuera del loyalty;
- ejecutar acciones fuera del sistema;
- inventar saldos, puntos o estados;
- hablar de entidades fuera de la empresa autenticada.

### 18.2 Validaciones obligatorias
- validar `company_id`;
- validar `internal_user_id`;
- validar permisos;
- validar datos mínimos antes de proponer acciones;
- validar confirmación humana;
- validar que el resultado venga del loyalty core.

LangChain documenta guardrails como mecanismos para validar y filtrar contenido y comportamiento en puntos clave de ejecución del agente. citeturn753761search4turn753761search20

---

## 19. Auditoría

Debe existir **auditoría completa**.

### 19.1 Se debe registrar
- mensaje de entrada;
- respuesta del agente;
- tool seleccionada;
- input y output de la tool;
- confirmación humana;
- errores;
- bloqueos por guardrails;
- acción final ejecutada.

### 19.2 Objetivo
- trazabilidad;
- soporte;
- debugging;
- revisión operativa;
- evaluación futura del agente.

---

## 20. Patrones de diseño recomendados

### 20.1 Ports and Adapters
Para desacoplar canales, OpenAI, PostgreSQL y loyalty core.

### 20.2 Strategy
Para elegir comportamiento por canal o por modo de respuesta.

Ejemplo:
- estrategia de salida WhatsApp
- estrategia de salida Telegram
- estrategia de salida UI stream

### 20.3 Repository
Para memoria, mensajes, auditoría y confirmaciones.

### 20.4 Factory
Para construir el agente con:
- modelo,
- tools,
- prompt base,
- middlewares,
- guardrails.

### 20.5 Application Service / Use Case
Para encapsular operaciones del dominio conversacional.

### 20.6 Adapter
Para integrar providers externos.

### 20.7 Template Method opcional
Para un flujo uniforme:
1. recibir mensaje
2. cargar contexto
3. ejecutar agente
4. validar guardrails
5. responder
6. auditar

---

## 21. Estructura lógica sugerida

```text
src/
  domain/
    entities/
    value_objects/
    services/
    ports/

  application/
    use_cases/
    dto/
    orchestrators/
    policies/

  infrastructure/
    llm/
    persistence/
    loyalty_api/
    messaging/
    audit/
    config/

  entrypoints/
    http/
    webhooks/
    streaming/

  agent/
    prompts/
    tools/
    runtime/
    guardrails/

  shared/
    exceptions/
    utils/
    logging/
```

---

## 22. Seguridad

### 22.1 Identidad
El agente debe operar siempre en nombre de un **usuario interno autenticado**.

### 22.2 Autorización
Las tools deben validar:
- empresa;
- rol;
- permisos del usuario.

### 22.3 No acceso cross-tenant
Nunca debe acceder a datos de otra empresa.

### 22.4 Secretos
- OpenAI API key
- URL/token de loyalty core
- credenciales de WhatsApp
- credenciales de Telegram
- credenciales Postgres

Todo por variables de entorno o secret manager.

---

## 23. Configuración por variables de entorno

Ejemplos mínimos:
- `OPENAI_MODEL`
- `OPENAI_API_KEY`
- `POSTGRES_URL`
- `LOYALTY_API_BASE_URL`
- `LOYALTY_API_TOKEN`
- `WHATSAPP_VERIFY_TOKEN`
- `WHATSAPP_ACCESS_TOKEN`
- `TELEGRAM_BOT_TOKEN`
- `AGENT_MEMORY_TTL_HOURS`
- `AGENT_MAX_TOOL_ITERATIONS`
- `ENABLE_STREAMING`
- `ENABLE_BACKGROUND_JOBS`

---

## 24. Jobs opcionales del PMV

Como plus, el microservicio puede incluir jobs para:
- resumir conversaciones largas;
- cerrar confirmaciones expiradas;
- limpiar memoria vencida;
- generar resúmenes operativos diarios.

---

## 25. Requisitos no funcionales

### 25.1 Rendimiento
- respuesta rápida en consultas simples;
- capacidad de procesamiento asíncrono para acciones largas.

### 25.2 Mantenibilidad
- código desacoplado;
- testing por capas;
- tools testeables sin canales.

### 25.3 Observabilidad
- logs estructurados;
- trazabilidad por `session_id`, `company_id`, `internal_user_id`, `run_id`.

### 25.4 Escalabilidad
- nuevos canales sin tocar dominio;
- nuevos modelos sin tocar aplicación;
- cambio de PostgreSQL por otro storage mediante repositorios/puertos.

---

## 26. Decisiones explícitas del PMV

- Python
- LangChain Agents
- OpenAI configurable
- PostgreSQL para memoria
- single-agent with tools
- arquitectura limpia
- puertos y adaptadores
- interacción solo con usuarios internos
- canales iniciales: WhatsApp y Telegram
- salida por el mismo canal de entrada
- confirmación humana obligatoria para acciones sensibles
- memoria por usuario interno
- expiración configurable
- streaming soportado para UI
- full audit
- foco exclusivo en loyalty

---

## 27. Riesgos principales

- tool overreach: que el agente intente ejecutar algo sin validación;
- ambigüedad del usuario al pedir acciones;
- latencia de canales externos;
- mala gestión de memoria conversacional;
- fuga cross-tenant si no se valida empresa en cada tool;
- dependencia excesiva de prompts sin guardrails suficientes.

---

## 28. Roadmap posterior

- migrar flujos críticos a LangGraph si hace falta más control;
- memoria semántica o RAG;
- campañas automáticas;
- multiagente;
- voice channels;
- analytics del agente;
- scoring de conversaciones;
- recomendador de campañas loyalty.

---

## 29. Recomendación final de implementación

Para este PMV, la mejor decisión es:

- **LangChain Agents** como runtime principal;
- **microservicio loyalty** como único backend de negocio;
- **PostgreSQL** solo para memoria y auditoría del agente;
- **webhooks** para WhatsApp y Telegram;
- **HTTP/SSE** para UI;
- **confirmación humana** para todo lo sensible;
- **tools orientadas a casos de uso**, no a endpoints crudos.

Eso deja un sistema:
- simple para arrancar,
- robusto en diseño,
- desacoplado,
- extensible,
- y alineado con la visión de Techapoli como ecosistema de microservicios.
