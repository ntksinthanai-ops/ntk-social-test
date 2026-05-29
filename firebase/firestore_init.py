import os
import sys
from datetime import datetime
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

def init_firestore():
    # Attempt to load credentials
    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not cred_path:
        # Fallback to local service-account.json if present
        local_cred = os.path.join(os.path.dirname(__file__), "..", "service-account.json")
        if os.path.exists(local_cred):
            cred_path = local_cred
        else:
            print("ERROR: GOOGLE_APPLICATION_CREDENTIALS environment variable is not set,")
            print("and 'service-account.json' was not found in the root directory.")
            print("Please download your service account JSON file from Firebase Console and place it in the root folder.")
            sys.exit(1)

    print(f"Loading credentials from: {cred_path}")
    cred = credentials.Certificate(cred_path)
    
    # Initialize the app (default app)
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    return db

def verify_and_setup_collections(db):
    collections = [
        "raw_payloads",
        "accounts",
        "content_items",
        "content_metrics_daily",
        "audience_dimensions",
        "events",
        "comments",
        "comment_sentiment"
    ]
    
    print("\nVerifying Firestore write access by inserting verification test documents...")
    
    for coll in collections:
        doc_ref = db.collection(coll).document("_verification_test_")
        test_data = {
            "verified_at": datetime.utcnow(),
            "status": "active",
            "info": f"Initialization verification doc for {coll}"
        }
        # Write/Update the document
        doc_ref.set(test_data)
        print(f" -> Verified collection access for: '{coll}'")
        
    print("\nFirestore initialization successfully completed!")

if __name__ == "__main__":
    try:
        db = init_firestore()
        verify_and_setup_collections(db)
    except Exception as e:
        print(f"\nFailed to initialize or verify Firestore connection: {e}")
        sys.exit(1)
