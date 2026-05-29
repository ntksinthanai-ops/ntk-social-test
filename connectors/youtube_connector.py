import os
import sys
import hashlib
import time
from datetime import datetime, date
import requests
from dotenv import load_dotenv
from firebase_client import get_firestore_client

# Load environment configuration
load_dotenv()

# Load environment configs
YOUTUBE_CHANNEL_ID = os.environ.get("YOUTUBE_CHANNEL_ID", "UC_x5XG1OV2P6uYZ5FGPQbGQ") # Mock NTK Channel ID if empty
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")

def get_db():
    try:
        return get_firestore_client()
    except Exception as e:
        print(f"Firestore Client Connection failed: {e}")
        sys.exit(1)

def hash_id(input_id):
    """Hashes sensitive identifiers (e.g., author IDs) for privacy."""
    if not input_id:
        return None
    return hashlib.sha256(input_id.encode('utf-8')).hexdigest()

def save_raw_payload(db, source, object_id, object_type, payload):
    """Saves the raw JSON payload to Firestore /raw_payloads/ collection."""
    doc_ref = db.collection("raw_payloads").document()
    doc_ref.set({
        "source": source,
        "account_id": YOUTUBE_CHANNEL_ID,
        "object_id": object_id,
        "object_type": object_type,
        "fetched_at": datetime.utcnow(),
        "payload": payload
    })
    print(f" -> Saved raw payload for {object_type} (ID: {object_id})")

def fetch_youtube_videos():
    """Fetches list of videos for the channel from YouTube Data API v3."""
    if not YOUTUBE_API_KEY:
        print("WARNING: YOUTUBE_API_KEY not set. Using mock API response.")
        return get_mock_videos_response()

    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "key": YOUTUBE_API_KEY,
        "channelId": YOUTUBE_CHANNEL_ID,
        "part": "snippet",
        "order": "date",
        "maxResults": 10,
        "type": "video"
    }
    
    response = requests.get(url, params=params)
    if response.status_code != 200:
        print(f"Failed to fetch videos from API: {response.text}")
        return []
    
    data = response.json()
    return data.get("items", [])

def process_youtube_pipeline():
    db = get_db()
    print(f"Starting YouTube Ingestion Pipeline for Channel: {YOUTUBE_CHANNEL_ID}...")
    
    # 1. Fetch channel videos
    videos = fetch_youtube_videos()
    if not videos:
        print("No videos found or failed to retrieve.")
        return

    # Save search payload
    save_raw_payload(db, "youtube", YOUTUBE_CHANNEL_ID, "video_list", {"items": videos})

    # Process individual videos
    batch = db.batch()
    batch_count = 0

    for video in videos:
        video_id = video["id"].get("videoId")
        if not video_id:
            continue
            
        snippet = video["snippet"]
        published_at_str = snippet.get("publishedAt")
        published_at = datetime.strptime(published_at_str, "%Y-%m-%dT%H:%M:%SZ") if published_at_str else datetime.utcnow()
        
        # Save each normalized content item to Firestore
        content_ref = db.collection("content_items").document(video_id)
        content_data = {
            "account_id": YOUTUBE_CHANNEL_ID,
            "platform": "youtube",
            "content_type": "video",
            "published_at": published_at,
            "caption": snippet.get("title", ""),
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "event_id": None,
            "source_tier": "owned",
            "collection_method": "youtube_data_api"
        }
        batch.set(content_ref, content_data)
        batch_count += 1

        # Save mock / placeholder daily metrics for prototype
        metrics_ref = db.collection("content_metrics_daily").document(f"{video_id}_{date.today()}")
        metrics_data = {
            "impressions": 1250, # Mock/Estimated reach values
            "reach": 980,
            "follower_reach": 600,
            "nonfollower_reach": 380,
            "engagement": 45,
            "saves": 4,
            "shares": 8,
            "video_views": 105,
            "avg_watch_time": "00:03:15",
            "completion_rate": 0.42
        }
        batch.set(metrics_ref, metrics_data)
        batch_count += 1

        # Commit batch if close to limit
        if batch_count >= 400:
            batch.commit()
            batch = db.batch()
            batch_count = 0

    if batch_count > 0:
        batch.commit()
    
    print("YouTube Connector pipeline processed successfully!")

def get_mock_videos_response():
    """Mock fallback data for testing/prototyping."""
    return [
        {
            "id": {"videoId": "mock_vid_001"},
            "snippet": {
                "publishedAt": "2026-05-28T10:00:00Z",
                "title": "NTK Public Meeting Live Address in Chennai",
                "description": "Mock description for NTK video."
            }
        },
        {
            "id": {"videoId": "mock_vid_002"},
            "snippet": {
                "publishedAt": "2026-05-27T15:30:00Z",
                "title": "Interview: Infrastructure development plans in Tamil Nadu",
                "description": "Mock interview."
            }
        }
    ]

if __name__ == "__main__":
    process_youtube_pipeline()
