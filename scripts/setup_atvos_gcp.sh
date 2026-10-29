#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-ageless-venture-509715-t8}"
LOCATION="${GOOGLE_CLOUD_LOCATION:-us-central1}"
ACCOUNT="${GOOGLE_CLOUD_ACCOUNT:-$(gcloud auth list --filter=status:ACTIVE --format='value(account)' | head -1)}"

usage() {
    cat <<'EOF'
Uso: bash scripts/setup_atvos_gcp.sh [--project PROJECT_ID] [--location REGION] [--account EMAIL] [--check-only]

Prepara las dependencias locales y los recursos necesarios para ejecutar
Atvos MCP con Vertex AI. No concede roles ni elimina recursos.
EOF
}

CHECK_ONLY=false
while (($#)); do
    case "$1" in
        --project) PROJECT_ID="$2"; shift 2 ;;
        --location) LOCATION="$2"; shift 2 ;;
        --account) ACCOUNT="$2"; shift 2 ;;
        --check-only) CHECK_ONLY=true; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Argumento desconocido: $1" >&2; usage >&2; exit 2 ;;
    esac
done

require_command() {
    command -v "$1" >/dev/null 2>&1 || {
        echo "ERROR: Falta el comando '$1'." >&2
        exit 1
    }
}

step() {
    printf '\n==> %s\n' "$1"
}

require_command gcloud
require_command python3


step "Cuenta y proyecto"
echo "Cuenta: $ACCOUNT"
echo "Proyecto: $PROJECT_ID"
echo "Region: $LOCATION"
gcloud config set project --quiet "$PROJECT_ID" >/dev/null || true

gcloud auth list --filter=status:ACTIVE --format='value(account)' | grep -Fxq "$ACCOUNT" || {
    echo "ERROR: activa la cuenta $ACCOUNT con: gcloud auth login --account=$ACCOUNT" >&2
    exit 1
}

step "Permisos necesarios"
cat <<EOF
El administrador del proyecto debe ejecutar:

  gcloud projects add-iam-policy-binding $PROJECT_ID \\
    --member="user:$ACCOUNT" \\
    --role="roles/aiplatform.user"

  gcloud projects add-iam-policy-binding $PROJECT_ID \\
    --member="user:$ACCOUNT" \\
    --role="roles/serviceusage.serviceUsageConsumer"
EOF

if $CHECK_ONLY; then
    if gcloud projects get-iam-policy "$PROJECT_ID" \
        --flatten='bindings[].members' \
        --filter="bindings.members:user:$ACCOUNT" \
        --format='table(bindings.role)' 2>/dev/null; then
        :
    else
        echo "INFO: La cuenta no tiene permiso resourcemanager.projects.getIamPolicy; pide al administrador que compruebe los roles."
    fi
    exit 0
fi

step "APIs requeridas"
for api in aiplatform.googleapis.com serviceusage.googleapis.com iam.googleapis.com; do
    if gcloud services enable "$api" --project="$PROJECT_ID" --quiet; then
        echo "API habilitada/verificada: $api"
    else
        echo "ERROR: no se pudo habilitar $api. Solicita serviceusage.services.enable al administrador." >&2
        exit 1
    fi
done

step "Credenciales ADC"
gcloud auth application-default login --account="$ACCOUNT"
gcloud auth application-default set-quota-project "$PROJECT_ID" || true

step "Entorno Python"
if [[ ! -d .venv ]]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt

step "Verificacion"
export GOOGLE_GENAI_USE_VERTEXAI=true
export GOOGLE_CLOUD_PROJECT="$PROJECT_ID"
export GOOGLE_CLOUD_LOCATION="$LOCATION"
make validate

cat <<EOF

Configuracion completada.

Ejecuta MCP HTTP:
  export GOOGLE_GENAI_USE_VERTEXAI=true
  export GOOGLE_CLOUD_PROJECT=$PROJECT_ID
  export GOOGLE_CLOUD_LOCATION=$LOCATION
  MCP_TRANSPORT=streamable-http python mcp_server.py

Endpoint:
  http://127.0.0.1:8001/mcp
EOF
