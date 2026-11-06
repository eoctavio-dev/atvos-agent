# Atvos Agent

## Instalacion

En Debian/Ubuntu o Google Cloud Shell ejecuta:

```bash
bash install.txt
source .venv/bin/activate
```

El entorno tambien puedes crear y actualizar manualmente con:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Google Cloud

Inicia sesion en tu cuenta y crea las credenciales de aplicacion predeterminadas:

```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project TU_PROJECT_ID
```

Consulta los recursos disponibles:

```bash
gcloud projects list
gcloud config list
gcloud compute instances list
```

Activa tambien las APIs necesarias para Vertex AI y Cloud Storage:

```bash
gcloud services enable aiplatform.googleapis.com storage.googleapis.com
```

Verifica la configuracion:

```bash
python check_setup.py
```

## Ejecutar el agente ADK en local

```bash
adk web agents --host 0.0.0.0 --port 8000
```

Abre `http://localhost:8000` y selecciona `atvos_agent`.

## Ejecutar el agente en Google Cloud

Configura y habilita las APIs necesarias:

```bash
gcloud config set project gsd-appmod
gcloud services enable aiplatform.googleapis.com run.googleapis.com
adk deploy cloud_run \
  --project=gsd-appmod \
  --region=us-central1 \
  --with_ui \
  agents/atvos_agent
```

El comando publica el agente y devuelve la URL del servicio. El servicio necesita permisos para llamar a Vertex AI.

## Consumir el agente desde MCP

La configuración de VS Code está en `.vscode/mcp.json`. El servidor MCP usa
Python del entorno virtual y expone la herramienta `ask_atvos_agent`.

Para iniciarlo manualmente:

```bash
source .venv/bin/activate
python mcp_server.py
```

La herramienta acepta un mensaje y, opcionalmente, un `session_id` para continuar una conversación anterior.

## Configuración paso a paso de GCP, Vertex AI y observabilidad

`scripts/setup_atvos_gcp.sh` no ejecuta acciones: contiene solamente comentarios. Ejecuta manualmente cada paso para mantener control sobre autenticación, IAM y recursos.

### 1. Autenticación

```bash
gcloud auth login octavio@luisalcantara.altostrat.com
gcloud auth application-default login
gcloud config set project gsd-appmod
gcloud auth application-default set-quota-project gsd-appmod
```

### 2. APIs

```bash
gcloud services enable aiplatform.googleapis.com \
  serviceusage.googleapis.com iam.googleapis.com \
  cloudtrace.googleapis.com monitoring.googleapis.com logging.googleapis.com \
  --project=gsd-appmod
```

### 3. Roles IAM

Ejecuta como administrador del proyecto. Sustituye el grupo si corresponde.

```bash
gcloud projects add-iam-policy-binding gsd-appmod \
  --member='group:gsd-appmod@luisalcantara.altostrat.com' \
  --role='roles/aiplatform.user'

for role in roles/serviceusage.serviceUsageConsumer roles/cloudtrace.agent roles/monitoring.metricWriter roles/logging.logWriter; do
  gcloud projects add-iam-policy-binding gsd-appmod \
    --member='group:gsd-appmod@luisalcantara.altostrat.com' \
    --role="$role"
done
```

Verificación:

```bash
gcloud projects get-iam-policy gsd-appmod \
  --flatten='bindings[].members' \
  --filter='bindings.members:gsd-appmod@luisalcantara.altostrat.com'
```

### 4. Entorno Python

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
```

### 5. Variables del agente

```bash
cp .env.example .env
```

El archivo `agents/atvos_agent/.env` debe contener:

```dotenv
GOOGLE_GENAI_USE_VERTEXAI=true
GOOGLE_CLOUD_PROJECT=gsd-appmod
GOOGLE_CLOUD_LOCATION=us-central1
ATVOS_TELEMETRY_ENABLED=true
OTEL_SERVICE_NAME=atvos-agent-mcp
OTEL_RESOURCE_ATTRIBUTES=service.namespace=atvos,service.version=1.0.0
```

### 6. Dashboard

```bash
gcloud monitoring dashboards create \
  --project=gsd-appmod \
  --config-from-file=dashboards/atvos-agent.json
```

Guarda el ID devuelto por el comando y abre:

```text
https://console.cloud.google.com/monitoring/dashboards?project=gsd-appmod
```

### 7. MCP y prueba de carga

```bash
source .venv/bin/activate
MCP_TRANSPORT=streamable-http python mcp_server.py
```

En otra terminal, ejecuta pruebas MCP reales para generar logs y métricas. También puedes usar el flujo de VS Code MCP configurado en `.vscode/mcp.json`.

### 8. Verificación de observabilidad

Logs de GenAI:

```text
https://console.cloud.google.com/logs/query?project=gsd-appmod
```

Filtro:

```text
logName:"gen_ai"
```

Traces:

```text
https://console.cloud.google.com/traces/list?project=gsd-appmod
```

Dashboards y métricas:

```text
https://console.cloud.google.com/monitoring/dashboards?project=gsd-appmod
```
