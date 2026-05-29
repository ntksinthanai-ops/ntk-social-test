import os
import sys
import io
import json
from google.cloud import bigquery
from google.api_core.exceptions import NotFound

# Include connectors path for shared client
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "connectors"))
from firebase_client import get_firestore_client

DATASET_ID = "firestore_export"

def get_bq_client():
    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not cred_path:
        fallback_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "service-account.json")
        )
        if os.path.exists(fallback_path):
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = fallback_path
            cred_path = fallback_path
        else:
            raise FileNotFoundError("service-account.json not found.")
            
    # Client will automatically read project_id from service account credentials JSON
    return bigquery.Client()

def create_dataset_if_not_exists(client, project_id):
    dataset_ref = bigquery.DatasetReference(project_id, DATASET_ID)
    try:
        client.get_dataset(dataset_ref)
        print(f"Dataset '{DATASET_ID}' already exists.")
    except NotFound:
        dataset = bigquery.Dataset(dataset_ref)
        dataset.location = "US"
        client.create_dataset(dataset)
        print(f"Created new dataset '{DATASET_ID}'.")

def create_table_if_not_exists(client, project_id, table_name, schema):
    table_ref = bigquery.TableReference(
        bigquery.DatasetReference(project_id, DATASET_ID), table_name
    )
    try:
        client.get_table(table_ref)
        print(f"Table '{table_name}' already exists.")
    except NotFound:
        table = bigquery.Table(table_ref, schema=schema)
        client.create_table(table)
        print(f"Created new table '{table_name}'.")

def sync_collections_to_bigquery():
    db = get_firestore_client()
    bq_client = get_bq_client()
    project_id = bq_client.project
    print(f"Ingesting into BigQuery Project: '{project_id}'...")
    
    create_dataset_if_not_exists(bq_client, project_id)
    
    # Define schemas to match Firestore collections
    schemas = {
        "content_items": [
            bigquery.SchemaField("content_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("account_id", "STRING"),
            bigquery.SchemaField("platform", "STRING"),
            bigquery.SchemaField("content_type", "STRING"),
            bigquery.SchemaField("caption", "STRING"),
            bigquery.SchemaField("url", "STRING"),
            bigquery.SchemaField("source_tier", "STRING"),
            bigquery.SchemaField("published_at", "TIMESTAMP"),
        ],
        "content_metrics_daily": [
            bigquery.SchemaField("content_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("impressions", "INTEGER"),
            bigquery.SchemaField("reach", "INTEGER"),
            bigquery.SchemaField("engagement", "INTEGER"),
            bigquery.SchemaField("shares", "INTEGER"),
            bigquery.SchemaField("video_views", "INTEGER"),
            bigquery.SchemaField("completion_rate", "FLOAT"),
        ],
        "comments": [
            bigquery.SchemaField("comment_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("content_id", "STRING"),
            bigquery.SchemaField("author_hash", "STRING"),
            bigquery.SchemaField("text", "STRING"),
            bigquery.SchemaField("lang", "STRING"),
        ],
        "comment_sentiment": [
            bigquery.SchemaField("comment_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("sentiment", "STRING"),
            bigquery.SchemaField("stance", "STRING"),
            bigquery.SchemaField("target", "STRING"),
            bigquery.SchemaField("score", "FLOAT"),
            bigquery.SchemaField("reviewed", "BOOLEAN"),
        ],
        "audience_dimensions": [
            bigquery.SchemaField("account_id", "STRING"),
            bigquery.SchemaField("dim_type", "STRING"),
            bigquery.SchemaField("dim_value", "STRING"),
            bigquery.SchemaField("metric", "STRING"),
            bigquery.SchemaField("value", "FLOAT"),
        ]
    }
    
    for table_name, schema in schemas.items():
        create_table_if_not_exists(bq_client, project_id, table_name, schema)
        
        # Read from Firestore
        print(f"Syncing Firestore collection '{table_name}' to BigQuery...")
        docs = db.collection(table_name).stream()
        rows_to_insert = []
        
        for doc in docs:
            # Skip verification test documents
            if doc.id == "_verification_test_":
                continue
            
            data = doc.to_dict()
            # Convert datetime properties to ISO strings for JSON serialization
            for key, val in data.items():
                if hasattr(val, "isoformat"):
                    data[key] = val.isoformat()
            # Map Firestore ID into schema fields
            if table_name == "content_items":
                data["content_id"] = doc.id
            elif table_name == "content_metrics_daily":
                data["content_id"] = doc.id.rsplit("_", 1)[0]
            elif table_name == "comments":
                data["comment_id"] = doc.id
            elif table_name == "comment_sentiment":
                data["comment_id"] = doc.id
                
            # Filter only keys matching the schema
            clean_row = {}
            for field in schema:
                clean_row[field.name] = data.get(field.name)
            rows_to_insert.append(clean_row)
            
        if rows_to_insert:
            table_ref = bq_client.dataset(DATASET_ID).table(table_name)
            
            # Use LoadJob (free tier compatible) instead of streaming inserts
            job_config = bigquery.LoadJobConfig(
                source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
                schema=schema,
                write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE
            )
            
            json_data = "\n".join(json.dumps(row) for row in rows_to_insert)
            file_obj = io.StringIO(json_data)
            
            # Upload the file object
            load_job = bq_client.load_table_from_file(
                file_obj, table_ref, job_config=job_config
            )
            load_job.result() # Wait for job to complete
            print(f" -> Successfully loaded/synced {len(rows_to_insert)} rows to table '{table_name}'.")
        else:
            print(f" -> No documents to sync for collection '{table_name}'.")

if __name__ == "__main__":
    try:
        sync_collections_to_bigquery()
    except Exception as e:
        print(f"Sync job failed: {e}")
        sys.exit(1)
