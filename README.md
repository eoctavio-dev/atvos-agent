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

Copia `.env.example` como `.env` y reemplaza los valores de ejemplo por los datos reales del proyecto.
