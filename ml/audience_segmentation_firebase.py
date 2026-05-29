import os
import sys
from datetime import date

# Make sure we use the shared client
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "connectors"))
from firebase_client import get_firestore_client

def get_db():
    try:
        return get_firestore_client()
    except Exception as e:
        print(f"Firestore Client Connection failed: {e}")
        sys.exit(1)

def run_audience_segmentation():
    db = get_db()
    print("Starting Audience Segmentation batch job (Heuristic Engine for Prototype)...")
    
    # 1. Fetch metrics from Firestore
    metrics_ref = db.collection("content_metrics_daily")
    docs = metrics_ref.stream()
    
    processed = 0
    batch = db.batch()
    
    for doc in docs:
        data = doc.to_dict()
        doc_id = doc.id
        
        # Calculate engagement score
        engagement = data.get("engagement", 0)
        shares = data.get("shares", 0)
        score = engagement + (shares * 2)
        
        if score > 200:
            segment = "highly_active"
            cluster_id = 2
        elif score > 20:
            segment = "moderate"
            cluster_id = 1
        else:
            segment = "passive"
            cluster_id = 0
            
        segment_ref = db.collection("audience_segments").document(f"seg_{doc_id}")
        segment_data = {
            "account_id": "UC_x5XG1OV2P6uYZ5FGPQbGQ", # Mock account ID
            "date": date.today().isoformat(),
            "segment": segment,
            "cluster_id": cluster_id
        }
        batch.set(segment_ref, segment_data)
        processed += 1
        
    if processed == 0:
        print("No metric data found in database. Inserting fallback segments...")
        # Fallbacks
        fallbacks = [
            {"account_id": "UC_x5XG1OV2P6uYZ5FGPQbGQ", "segment": "highly_active", "cluster_id": 2},
            {"account_id": "mock_meta_page_id_123", "segment": "moderate", "cluster_id": 1},
            {"account_id": "mock_x_account_id_789", "segment": "passive", "cluster_id": 0}
        ]
        for i, data in enumerate(fallbacks):
            ref = db.collection("audience_segments").document(f"fallback_seg_{i}")
            segment_data = {
                "account_id": data["account_id"],
                "date": date.today().isoformat(),
                "segment": data["segment"],
                "cluster_id": data["cluster_id"]
            }
            batch.set(ref, segment_data)
            processed += 1
            
    batch.commit()
    print(f"Segmentation job successfully processed {processed} records!")

if __name__ == "__main__":
    run_audience_segmentation()
