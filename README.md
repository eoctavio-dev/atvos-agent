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
gcloud config set project ageless-venture-509715-t8
gcloud services enable aiplatform.googleapis.com run.googleapis.com
adk deploy cloud_run \
  --project=ageless-venture-509715-t8 \
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

## Preparar permisos y recursos de GCP

Comprueba primero el proyecto, la cuenta activa y los permisos sin modificar recursos:

```bash
bash scripts/setup_atvos_gcp.sh --check-only
```

La cuenta administradora debe conceder primero los roles indicados por el script.
Después puedes preparar API, ADC y dependencias completas:

```bash
bash scripts/setup_atvos_gcp.sh \
  --project ageless-venture-509715-t8 \
  --location us-central1 \
  --account octavio@luisalcantara.altostrat.com
```

El script no elimina recursos ni concede roles automáticamente. Para comprobar IAM después de asignarlos:

```bash
gcloud projects get-iam-policy ageless-venture-509715-t8 \
  --flatten='bindings[].members' \
  --filter='bindings.members:octavio@luisalcantara.altostrat.com'
```

Copia `.env.example` como `.env` y reemplaza los valores de ejemplo por los datos reales del proyecto.
