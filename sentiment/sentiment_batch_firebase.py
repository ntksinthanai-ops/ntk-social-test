import os
import sys
import time
import json
from google.cloud import firestore
from dotenv import load_dotenv

# Load local environment configuration
load_dotenv()

# Make sure we use the shared client
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "connectors"))
from firebase_client import get_firestore_client

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

def get_db():
    try:
        return get_firestore_client()
    except Exception as e:
        print(f"Firestore Client Connection failed: {e}")
        sys.exit(1)

# Fallback/Dummy MuRIL sentiment scorer
def query_muril_local(text):
    """
    MuRIL (Multilingual Representations for Indian Languages) local fallback.
    In a full production environment, this imports transformers and torch to classify.
    For this prototype/lightweight setup, we use an rule-based fallback check.
    """
    try:
        from transformers import pipeline
        # Lazy load pipeline if transformers is available
        classifier = pipeline("sentiment-analysis", model="google/muril-base-cased")
        res = classifier(text)
        label = res[0]["label"].lower()
        score = res[0]["score"]
        # Map label to positive/negative/neutral
        sentiment = "neutral"
        if "pos" in label:
            sentiment = "positive"
        elif "neg" in label:
            sentiment = "negative"
        return sentiment, score
    except ImportError:
        # Simple heuristic fallback
        text_lower = text.lower()
        positive_words = ["வாழ்த்துகள்", "வெற்றி", "சிறப்பு", "நன்று", "great", "good", "super", "proud"]
        negative_words = ["worst", "bad", "தவறு", "மோசம்", "எதிர்ப்பு", "fail"]
        
        pos_count = sum(1 for w in positive_words if w in text_lower)
        neg_count = sum(1 for w in negative_words if w in text_lower)
        
        if pos_count > neg_count:
            return "positive", 0.75
        elif neg_count > pos_count:
            return "negative", 0.75
        return "neutral", 0.5

def query_groq_api(text):
    """
    Queries Groq Cloud API for Tamil/Tanglish stance & sentiment analysis.
    If GROQ_API_KEY is not set, returns mock response.
    """
    if not GROQ_API_KEY:
        # Generate mock classification based on basic rules
        time.sleep(0.1) # Simulate network delay
        text_lower = text.lower()
        if "வாழ்த்துகள்" in text_lower or "proud" in text_lower:
            return {"sentiment": "positive", "stance": "pro", "target": "NTK", "score": 0.9}
        elif "worst" in text_lower or "மோசம்" in text_lower:
            return {"sentiment": "negative", "stance": "anti", "target": "NTK", "score": 0.85}
        return {"sentiment": "neutral", "stance": "neutral", "target": None, "score": 0.6}

    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)
        
        prompt = f"Analyze this Tamil/Tanglish social media comment and return ONLY a JSON block: '{text}'"
        
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a Tamil political comment classifier. Given a comment in Tamil, Tanglish, "
                        "or mixed Tamil-English, classify it. "
                        "Return JSON only: {\"sentiment\": \"positive|neutral|negative\", "
                        "\"stance\": \"pro|anti|neutral\", \"target\": \"<entity name or null>\", \"score\": 0.0-1.0}"
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            model="llama-3.1-8b-instant",
            temperature=0.2,
            response_format={"type": "json_object"}
        )
        
        result_text = chat_completion.choices[0].message.content
        return json.loads(result_text)
    except Exception as e:
        print(f"Error calling Groq API: {e}")
        return {"sentiment": "neutral", "stance": "neutral", "target": None, "score": 0.0}

def process_sentiment_batch():
    db = get_db()
    print("Starting Sentiment Analysis Batch Job...")
    
    # 1. Fetch comments that don't have matching sentiment records
    comments_ref = db.collection("comments")
    comments = comments_ref.limit(50).stream() # Small batch for prototype limits
    
    processed_count = 0
    flagged_count = 0
    batch = db.batch()

    for comment_doc in comments:
        comment_id = comment_doc.id
        comment_data = comment_doc.to_dict()
        comment_text = comment_data.get("text", "")
        
        # Check if already processed
        sent_ref = db.collection("comment_sentiment").document(comment_id)
        if sent_ref.get().exists:
            continue
            
        # Safely print text in case of terminal encoding issues
        try:
            print(f"Processing comment '{comment_id}': '{comment_text[:30]}...'")
        except UnicodeEncodeError:
            print(f"Processing comment '{comment_id}': [Non-ASCII Text]")
        
        # Get Groq Analysis (Primary Model)
        groq_res = query_groq_api(comment_text)
        
        # Get Local MuRIL Fallback Analysis (Cross-check Model)
        muril_sentiment, muril_score = query_muril_local(comment_text)
        
        # Compare and set reviewed flag if they disagree
        groq_sentiment = groq_res.get("sentiment", "neutral")
        reviewed = True
        if groq_sentiment != muril_sentiment:
            reviewed = False
            flagged_count += 1
            print(f" -> Disagreement: Groq={groq_sentiment} vs MuRIL={muril_sentiment}. Setting reviewed=False")
            
        # Write results
        sentiment_data = {
            "sentiment": groq_sentiment,
            "stance": groq_res.get("stance", "neutral"),
            "target": groq_res.get("target"),
            "score": groq_res.get("score", 0.0),
            "model_version": "groq-llama-3.1-8b + muril-fallback",
            "reviewed": reviewed
        }
        
        batch.set(sent_ref, sentiment_data)
        processed_count += 1
        
        # Rate limit protection for Groq API free tier
        if GROQ_API_KEY:
            time.sleep(2)

    if processed_count > 0:
        batch.commit()
        print(f"Successfully processed {processed_count} comments. Flagged {flagged_count} for review.")
    else:
        print("No new comments to process.")

if __name__ == "__main__":
    process_sentiment_batch()
