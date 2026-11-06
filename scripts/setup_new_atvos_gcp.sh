#!/usr/bin/env bash
set -euo pipefail

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

PROJECT_ID="${GCP_PROJECT_ID:-atvos-agent-poc}"
REGION="${GCP_REGION:-us-central1}"
ACCOUNT="${GOOGLE_CLOUD_ACCOUNT:-}"
GEMINI_MODEL="${GEMINI_MODEL:-gemini-2.5-flash}"
SA_NAME="${SA_NAME:-sa-atvos-agent}"
PRINCIPAL_USER="${PRINCIPAL_USER:-}"
ORG_ID="${ORG_ID:-}"
FOLDER_ID="${FOLDER_ID:-}"
BUCKET_NAME=""
DRY_RUN=false

usage() {
  cat <<EOF
Uso: bash scripts/setup_new_atvos_gcp.sh [opciones]
  --project-id ID       ID del nuevo proyecto
  --region REGION       Región de Vertex AI
  --org-id ID           Organización del proyecto nuevo
  --folder-id ID        Carpeta del proyecto nuevo
  --gcp-account EMAIL   Cuenta activa de Google Cloud
  --gemini-model MODEL  Modelo Gemini
  --sa-name NAME        Nombre de la cuenta de servicio
  --principal-user ID   Principal IAM (user:email, group:email o serviceAccount:email)
  --bucket-name NAME    Bucket de la POC (predeterminado: proyecto-atvos-poc)
  --dry-run             Comprobar sin modificar recursos
EOF
}

while (($#)); do
  case "$1" in
    --project-id) PROJECT_ID="$2"; shift 2 ;;
    --region) REGION="$2"; shift 2 ;;
    --org-id) ORG_ID="$2"; shift 2 ;;
    --folder-id) FOLDER_ID="$2"; shift 2 ;;
    --gcp-account) ACCOUNT="$2"; shift 2 ;;
    --gemini-model) GEMINI_MODEL="$2"; shift 2 ;;
    --sa-name) SA_NAME="$2"; shift 2 ;;
    --principal-user) PRINCIPAL_USER="$2"; shift 2 ;;
    --bucket-name) BUCKET_NAME="$2"; shift 2 ;;
    --dry-run) DRY_RUN=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Argumento desconocido: $1" >&2; usage >&2; exit 2 ;;
  esac
done

BUCKET_NAME="${BUCKET_NAME:-${GCS_BUCKET_NAME:-${PROJECT_ID}-atvos-poc}}"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
SA_MEMBER="serviceAccount:$SA_EMAIL"
if [[ -z "$ACCOUNT" ]]; then
  ACCOUNT="$(gcloud auth list --filter=status:ACTIVE --format='value(account)' 2>/dev/null | head -n 1 || true)"
fi
if [[ -z "$PRINCIPAL_USER" ]]; then
  PRINCIPAL_USER="${ACCOUNT:+user:$ACCOUNT}"
fi

step() { printf '\n==> %s\n' "$1"; }
confirm() {
  $DRY_RUN && return
  read -r -p "$1 [y/N] " answer
  [[ "$answer" == "y" || "$answer" == "Y" ]] || exit 1
}
run() {
  if $DRY_RUN; then
    printf '[DRY-RUN]'; printf ' %q' "$@"; printf '\n'
  else
    "$@"
  fi
}

for tool in gcloud python3; do
  command -v "$tool" >/dev/null || { echo "Falta $tool" >&2; exit 1; }
done
[[ -n "$ACCOUNT" ]] || { echo "Indica --gcp-account o ejecuta gcloud auth login" >&2; exit 1; }
[[ -n "$PRINCIPAL_USER" ]] || { echo "Indica --principal-user" >&2; exit 1; }

APIS=(
  aiplatform.googleapis.com
  storage.googleapis.com
  run.googleapis.com
  iam.googleapis.com
)

step "Cuenta y proyecto"
echo "Cuenta: $ACCOUNT"
echo "Proyecto: $PROJECT_ID"
echo "Región: $REGION"
echo "Modelo: $GEMINI_MODEL"
echo "Bucket: gs://$BUCKET_NAME"
run gcloud auth login "$ACCOUNT" || run gcloud config set account "$ACCOUNT"
if ! gcloud projects describe "$PROJECT_ID" >/dev/null 2>&1; then
  confirm "¿Crear el proyecto $PROJECT_ID?"
  create_args=(projects create "$PROJECT_ID")
  [[ -z "$ORG_ID" ]] || create_args+=(--organization="$ORG_ID")
  [[ -z "$FOLDER_ID" ]] || create_args+=(--folder="$FOLDER_ID")
  run gcloud "${create_args[@]}" --name="$PROJECT_ID"
fi
run gcloud config set project "$PROJECT_ID"

step "Facturación"
BILLING_ACCOUNT="$(gcloud billing projects describe "$PROJECT_ID" --format='value(billingAccountName)' 2>/dev/null || true)"
if [[ -z "$BILLING_ACCOUNT" && ! $DRY_RUN ]]; then
  echo "El proyecto no tiene facturación vinculada. Vincula una cuenta manualmente:"
  echo "  gcloud billing accounts list"
  echo "  gcloud billing projects link $PROJECT_ID --billing-account=CUENTA"
fi

step "APIs"
run gcloud services enable "${APIS[@]}" --project="$PROJECT_ID"

step "Cuenta de servicio y IAM"
if ! gcloud iam service-accounts describe "$SA_EMAIL" --project="$PROJECT_ID" >/dev/null 2>&1; then
  confirm "¿Crear la cuenta de servicio $SA_EMAIL?"
  run gcloud iam service-accounts create "$SA_NAME" --project="$PROJECT_ID" --display-name="Atvos Content Agent"
fi
PROJECT_ROLES=(
  roles/aiplatform.user
)
for role in "${PROJECT_ROLES[@]}"; do
  if [[ ! "${PRINCIPAL_USER}" == serviceAccount:* ]] && ! gcloud projects get-iam-policy "$PROJECT_ID" --flatten='bindings[].members' --filter="bindings.role:$role AND bindings.members:$SA_MEMBER" --format='value(bindings.role)' 2>/dev/null | grep -q .; then
    confirm "¿Asignar $role a $SA_EMAIL?"
    run gcloud projects add-iam-policy-binding "$PROJECT_ID" --member="$SA_MEMBER" --role="$role"
  fi
  if [[ "${PRINCIPAL_USER}" == user:* || "${PRINCIPAL_USER}" == group:* || "${PRINCIPAL_USER}" == serviceAccount:* ]]; then
    if ! gcloud projects get-iam-policy "$PROJECT_ID" --flatten='bindings[].members' --filter="bindings.role:$role AND bindings.members:$PRINCIPAL_USER" --format='value(bindings.role)' 2>/dev/null | grep -q .; then
      confirm "¿Asignar $role a $PRINCIPAL_USER?"
      run gcloud projects add-iam-policy-binding "$PROJECT_ID" --member="$PRINCIPAL_USER" --role="$role"
    fi
  fi
done

step "Bucket de la POC"
if ! gcloud storage buckets describe "gs://$BUCKET_NAME" >/dev/null 2>&1; then
  confirm "¿Crear el bucket gs://$BUCKET_NAME?"
  run gcloud storage buckets create "gs://$BUCKET_NAME" --project="$PROJECT_ID" --location="$REGION" --uniform-bucket-level-access
fi
run gcloud storage buckets add-iam-policy-binding "gs://$BUCKET_NAME" --member="$SA_MEMBER" --role="roles/storage.objectAdmin"

step "ADC"
if ! $DRY_RUN; then
  gcloud auth application-default set-quota-project "$PROJECT_ID" || true
  if ! gcloud auth application-default print-access-token >/dev/null 2>&1; then
    echo "Ejecuta: gcloud auth application-default login --account=$ACCOUNT"
    exit 1
  fi
fi

step "Variables locales"
if ! $DRY_RUN && [[ -f .env ]] && ! cmp -s .env /dev/stdin <<<""; then
  confirm "¿Reemplazar el archivo .env existente con la configuración de este proyecto?"
fi
if ! $DRY_RUN; then
  cat > .env <<EOF
GCP_PROJECT_ID=$PROJECT_ID
GCP_REGION=$REGION
GEMINI_MODEL=$GEMINI_MODEL
GCS_BUCKET_NAME=$BUCKET_NAME
PORT=8080
GOOGLE_SERVICE_ACCOUNT_EMAIL=$SA_EMAIL
EOF
fi

step "Entorno Python"
if ! $DRY_RUN; then
  [[ -d .venv ]] || python3 -m venv .venv
  .venv/bin/python -m pip install --upgrade pip
  .venv/bin/python -m pip install -r requirements.txt
  .venv/bin/python -m pip install -r requirements-dev.txt
fi

step "Validaciones"
if ! $DRY_RUN; then
  gcloud auth application-default print-access-token >/dev/null
  .venv/bin/python check_setup.py
  export GCP_PROJECT_ID="$PROJECT_ID" GCP_REGION="$REGION" GEMINI_MODEL="$GEMINI_MODEL"
  .venv/bin/python - <<'PY'
import os
import vertexai
from vertexai.generative_models import GenerativeModel

vertexai.init(project=os.environ["GCP_PROJECT_ID"], location=os.environ["GCP_REGION"])
response = GenerativeModel(os.environ["GEMINI_MODEL"]).generate_content("Responde: ok")
assert response.text
print("Vertex AI Gemini: ok")
PY
fi

step "Completado"
if $DRY_RUN; then
  echo "Comprobación finalizada; no se modificaron recursos."
else
  echo "Proyecto configurado: $PROJECT_ID"
  echo "ADC: gcloud auth application-default login --account=$ACCOUNT"
  echo "API: uvicorn api_server:app --host 0.0.0.0 --port 8080"
fi
