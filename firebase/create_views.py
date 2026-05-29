import os
import sys
from google.cloud import bigquery
from google.api_core.exceptions import NotFound

# Include connectors path for shared client
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "connectors"))
from firebase_client import get_firestore_client
from firestore_to_bigquery import get_bq_client

def create_views():
    bq_client = get_bq_client()
    project_id = bq_client.project
    print(f"Creating SQL views dynamically in BigQuery project: '{project_id}'...")
    
    # Get the location of the firestore_export dataset to match locations
    try:
        export_dataset = bq_client.get_dataset(f"{project_id}.firestore_export")
        dataset_location = export_dataset.location
        print(f"Detected 'firestore_export' dataset location: '{dataset_location}'")
    except Exception as e:
        print(f"Could not check 'firestore_export' dataset: {e}")
        dataset_location = "US" # Fallback

    # Ensure ntk_dashboard dataset exists and matches location
    dataset_id = "ntk_dashboard"
    dataset_ref = bigquery.DatasetReference(project_id, dataset_id)
    
    try:
        existing_dataset = bq_client.get_dataset(dataset_ref)
        if existing_dataset.location != dataset_location:
            print(f"Dataset '{dataset_id}' exists but in a different location ('{existing_dataset.location}'). Deleting and recreating in '{dataset_location}'...")
            bq_client.delete_dataset(dataset_ref, delete_contents=True, not_found_ok=True)
            raise NotFound("Forcing recreation of dataset in matching location")
        else:
            print(f"Dataset '{dataset_id}' already exists and matches location '{dataset_location}'.")
    except NotFound:
        dataset = bigquery.Dataset(dataset_ref)
        dataset.location = dataset_location
        bq_client.create_dataset(dataset)
        print(f"Created new dataset '{dataset_id}' in location '{dataset_location}'.")

    # Read SQL view templates
    views_file = os.path.join(os.path.dirname(__file__), "bigquery_views.sql")
    with open(views_file, "r", encoding="utf-8") as f:
        sql_content = f.read()
        
    # Dynamically replace old/placeholder project IDs with the active one
    sql_content = sql_content.replace("ntk-socialmediaalalytics", project_id)
    sql_content = sql_content.replace("ntk-analytics", project_id)
    
    # Split queries by semicolon to execute one by one
    queries = [q.strip() for q in sql_content.split(";") if q.strip()]
    
    for idx, query in enumerate(queries, 1):
        # Remove comments/empty lines to check start word
        normalized_query = "\n".join([line for line in query.splitlines() if not line.strip().startswith("--")]).strip()
        if not normalized_query.lower().startswith("create"):
            continue
        print(f"Executing Query {idx}...")
        
        # Configure job to run in matching dataset location
        job_config = bigquery.QueryJobConfig()
        query_job = bq_client.query(query, location=dataset_location, job_config=job_config)
        query_job.result() # Wait for job to finish
        print(f" -> Query {idx} executed successfully.")
        
    print("\nAll BigQuery views created successfully!")

if __name__ == "__main__":
    try:
        create_views()
    except Exception as e:
        print(f"Failed to create views: {e}")
        sys.exit(1)
