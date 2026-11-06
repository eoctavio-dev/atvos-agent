#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-gsd-appmod}"
LOCATION="${GOOGLE_CLOUD_LOCATION:-us-central1}"
ACCOUNT="${GOOGLE_CLOUD_ACCOUNT:-$(gcloud auth list --filter=status:ACTIVE --format='value(account)' | head -1)}"
MEMBER=""
GRANT_ROLES=true
CHECK_ONLY=false
CREATE_DASHBOARD=true

usage() {
  cat <<EOF
Uso: bash scripts/setup_atvos_gcp.sh [opciones]

  --project PROJECT_ID   Proyecto GCP (predeterminado: gsd-appmod)
  --location REGION      Región Vertex AI (predeterminado: us-central1)
  --account EMAIL        Cuenta activa de GCP
  --member PRINCIPAL     Identidad IAM; ejemplo: group:grupo@empresa.com o user:correo@empresa.com
  --no-grant-roles       Solo verificar roles, sin asignarlos
  --check-only           Verificar proyecto, APIs y roles sin modificar recursos
  --no-dashboard         No crear el dashboard
EOF
}

while (($#)); do
  case "$1" in
    --project=*) PROJECT_ID="${1#*=}"; shift ;;
    --location=*) LOCATION="${1#*=}"; shift ;;
    --account=*) ACCOUNT="${1#*=}"; shift ;;
    --member=*) MEMBER="${1#*=}"; shift ;;
    --project) PROJECT_ID="$2"; shift 2 ;;
    --location) LOCATION="$2"; shift 2 ;;
    --account) ACCOUNT="$2"; shift 2 ;;
    --member) MEMBER="$2"; shift 2 ;;
    --no-grant-roles) GRANT_ROLES=false; shift ;;
    --check-only) CHECK_ONLY=true; shift ;;
    --no-dashboard) CREATE_DASHBOARD=false; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Argumento desconocido: $1" >&2; usage >&2; exit 2 ;;
  esac
done

for command_name in gcloud python3; do
  command -v "$command_name" >/dev/null || { echo "ERROR: falta '$command_name'" >&2; exit 1; }
done

if [[ -z "$ACCOUNT" ]]; then
  echo "ERROR: autentica una cuenta con: gcloud auth login" >&2
  exit 1
fi
if [[ -z "$MEMBER" ]]; then
  MEMBER="user:$ACCOUNT"
fi

step() { printf '
==> %s
' "$1"; }

verify_role() {
  local role="$1"
  local assigned
  assigned=$(gcloud projects get-iam-policy "$PROJECT_ID" \
    --flatten='bindings[].members' \
    --filter="bindings.role:$role AND bindings.members:$MEMBER" \
    --format='value(bindings.role)' 2>/dev/null)
  [[ -n "$assigned" ]]
}

step "Cuenta y proyecto"
echo "Cuenta: $ACCOUNT"
echo "Proyecto: $PROJECT_ID"
echo "Región: $LOCATION"
echo "Identidad IAM: $MEMBER"
gcloud config set account "$ACCOUNT" >/dev/null
gcloud config set project "$PROJECT_ID" >/dev/null

gcloud auth list --filter="account:$ACCOUNT AND status:ACTIVE" --format='value(account)' | grep -Fxq "$ACCOUNT" || {
  echo "ERROR: ejecuta: gcloud auth login --account=$ACCOUNT" >&2
  exit 1
}

step "Roles IAM requeridos"
roles=(
  roles/aiplatform.user
  roles/serviceusage.serviceUsageConsumer
  roles/cloudtrace.agent
  roles/monitoring.metricWriter
  roles/logging.logWriter
)

for role in "${roles[@]}"; do
  if $GRANT_ROLES && ! $CHECK_ONLY; then
    echo "Asignando $role..."
    if ! gcloud projects add-iam-policy-binding "$PROJECT_ID" --member="$MEMBER" --role="$role"; then
      echo "ERROR: no tienes permiso para asignar $role. Solicítalo al administrador." >&2
      exit 1
    fi
  else
    if verify_role "$role"; then
      echo "OK $role"
    else
      echo "FALTA $role"
    fi
  fi
done

if $CHECK_ONLY; then
  exit 0
fi

step "APIs requeridas"
for api in aiplatform.googleapis.com serviceusage.googleapis.com iam.googleapis.com cloudtrace.googleapis.com monitoring.googleapis.com logging.googleapis.com; do
  echo "Habilitando $api..."
  gcloud services enable "$api" --project="$PROJECT_ID"
done

step "Credenciales ADC"
gcloud auth application-default set-quota-project "$PROJECT_ID" || true
gcloud auth application-default print-access-token >/dev/null || {
  echo "ERROR: configura ADC con: gcloud auth application-default login --account=$ACCOUNT" >&2
  exit 1
}

step "Entorno Python"
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
. .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt

step "Variables del agente"
cat > agents/atvos_agent/.env <<EOF
GOOGLE_GENAI_USE_VERTEXAI=true
GOOGLE_CLOUD_PROJECT=$PROJECT_ID
GOOGLE_CLOUD_LOCATION=$LOCATION
ATVOS_TELEMETRY_ENABLED=true
OTEL_SERVICE_NAME=atvos-agent-mcp
OTEL_RESOURCE_ATTRIBUTES=service.namespace=atvos,service.version=1.0.0
EOF

step "Dashboard"
if $CREATE_DASHBOARD && [[ -f dashboards/atvos-agent.json ]]; then
  gcloud monitoring dashboards create --project="$PROJECT_ID" --config-from-file=dashboards/atvos-agent.json
elif $CREATE_DASHBOARD; then
  echo "ADVERTENCIA: no existe dashboards/atvos-agent.json"
fi

step "Verificación"
gcloud config get-value project
gcloud services list --enabled --project="$PROJECT_ID" --filter="config.name:aiplatform.googleapis.com OR config.name:cloudtrace.googleapis.com OR config.name:monitoring.googleapis.com OR config.name:logging.googleapis.com"

cat <<EOF

Configuración completada.

Iniciar MCP:
  MCP_TRANSPORT=streamable-http python mcp_server.py

Endpoint:
  http://127.0.0.1:8001/mcp
EOF
