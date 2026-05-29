import os
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
from dotenv import load_dotenv

# Load local environment configuration
load_dotenv()

_db = None

def get_firestore_client():
    global _db
    if _db is None:
        cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if not cred_path:
            # Fallback to service-account.json in the parent directory of connectors
            fallback_path = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "service-account.json")
            )
            if os.path.exists(fallback_path):
                cred_path = fallback_path
            else:
                raise FileNotFoundError(
                    "Service account key not found. Please set GOOGLE_APPLICATION_CREDENTIALS environment variable "
                    "or place 'service-account.json' in the project root folder."
                )

        cred = credentials.Certificate(cred_path)
        # Check if default app is already initialized to prevent duplicate initialization error
        try:
            firebase_admin.get_app()
        except ValueError:
            firebase_admin.initialize_app(cred)
            
        _db = firestore.client()
    return _db
