import shutil

from google.auth import default

print("Python environment ready")
print(f"gcloud: {shutil.which('gcloud') or 'not found'}")

try:
    credentials, project = default()
    print(f"Application Default Credentials: {credentials.__class__.__name__}")
    print(f"Project: {project or 'not configured'}")
except Exception as exc:
    print(f"Application Default Credentials: not configured ({exc})")
