# NTK Analytics Pipeline Walkthrough & Status Report

This document outlines the detailed architecture, technology stack, integration steps, testing phase trials and successes, and future steps for the NTK Social Media Analytics and Sentiment Pipeline.

---

## 1. Complete Technology Stack

The pipeline is built using a modern, serverless, and completely free-tier compatible stack:

* **Core Runtime**: Python 3.11+
* **Primary Database (NoSQL)**: **Google Firebase Firestore** (Stores live & mock content items, daily metrics, comments, sentiment, and user segmentation metadata).
* **Analytics Data Warehouse**: **Google Cloud BigQuery** (Receives aggregated and structured data synced from Firestore for querying and dashboard reporting).
* **Data Visualization**: **Grafana Dashboard** (Integrated with BigQuery data source to display executive KPIs, sentiment distributions, and platform breakdowns).
* **Generative AI & NLP Models**:
  * **Groq Cloud API (Llama 3.1 8B Instant)**: Primary model for low-latency classification of sentiment (positive/neutral/negative) and political stance (pro/anti/neutral) in English, Tamil, and Tanglish comments.
  * **Hugging Face / Google MuRIL (Multilingual Representations for Indian Languages)**: Secondary local model fallback for validating sentiment tags and highlighting classification mismatches.
* **Orchestration & Libraries**:
  * `google-cloud-firestore` & `google-cloud-bigquery`: GCP python SDKs.
  * `requests`: Meta, X, and YouTube API calls.
  * `transformers` & `torch`: MuRIL evaluation.
  * `python-dotenv`: Environment configuration.

---

## 2. In-Depth Details of the Testing Phase

The pipeline went through rigorous testing to validate permission flows, sandbox limits, and API integration paths:

### A. Database Connection & Verification
* **Firestore Verification**: Executed [`firestore_init.py`](file:///d:/CS/Projects/Ongoing/NTK_Socialmediaanalytics/firebase/firestore_init.py) which created an active verification document (`_verification_test_`) in all collections to confirm that read/write roles are set correctly under the Firestore security rules.
* **Dynamic Service Accounts**: Validated parsing of credentials dynamically from the root [`service-account.json`](file:///d:/CS/Projects/Ongoing/NTK_Socialmediaanalytics/service-account.json) key to avoid hardcoding project names, allowing seamless switching of target Firebase apps (e.g. from `ntk-socialmediaalalytics` to `ntk-social`).

### B. Overcoming BigQuery Sandbox Restrictions
* **The Problem**: Initial tests using BigQuery streaming insert APIs (`insert_rows_json`) failed with a `403 Forbidden` error because streaming inserts are blocked on the BigQuery free tier sandbox.
* **The Solution**: Redesigned the sync mechanism in [`firestore_to_bigquery.py`](file:///d:/CS/Projects/Ongoing/NTK_Socialmediaanalytics/firebase/firestore_to_bigquery.py) to write the Firestore data to an in-memory JSON file and load it using BigQuery **Load Jobs** (`load_table_from_file` with `WriteDisposition.WRITE_TRUNCATE`). Load Jobs are 100% free and bypass the streaming billing restriction.

### C. Region and Dataset Location Validation
* **The Problem**: Attempts to create SQL dashboard views in the default `US` region failed because the source tables in Firestore/BigQuery were created in the `asia-south1` (Mumbai) region.
* **The Solution**: Modified [`create_views.py`](file:///d:/CS/Projects/Ongoing/NTK_Socialmediaanalytics/firebase/create_views.py) to dynamically query the location of the source dataset first, and then create the target dashboard dataset (`ntk_dashboard`) and views in the exact same region (`asia-south1`).

### D. Meta Graph API & OAuth Token Lifecycle Testing
* **Token Expiration Tests**: Validated error-handling mechanisms by simulating API calls with expired User Tokens, catching `OAuthException (code 190, subcode 463)` and printing explicit user instructions to refresh the token.
* **Account Mismatch Debugging**:
  * Tested requests to previous Page ID `61590246280179` and caught `Unsupported get request (code 100, subcode 33)`. 
  * Tested requests against `/me/accounts` and verified the active token was limited to the Page **Sinthanai Selvan** (ID: `1131753156689723`).
* **Live Content Ingestion**: Once the user published posts on the active Facebook page, we verified that the connector retrieved **2 live posts** and **5 live comments** containing Tamil text.

### E. Sentiment Pipeline & Multilingual Heuristics
* **MuRIL Load Validation**: Verified the local loading of `google/muril-base-cased` using Hugging Face pipelines on CPU.
* **Groq Rate-Limiting**: Added a `time.sleep(2)` delay between batch classifications to remain within free-tier Rate Limits (RPM/TPM) of the Groq API.
* **Unicode Support**: Resolved Windows terminal encoding problems (`UnicodeEncodeError`) when logging Tamil output logs to console by safely encoding and checking counts.

### F. Audience Clustering Testing
* Tested the pure-python heuristic clustering in [`audience_segmentation_firebase.py`](file:///d:/CS/Projects/Ongoing/NTK_Socialmediaanalytics/ml/audience_segmentation_firebase.py), successfully clustering **11 records** into *highly_active*, *moderate*, and *passive* user lists based on engagement scores.

---

## 3. Recommended Next Steps

### Step 1: Configure X (Twitter) API
* **Action Required**: Generate a new Bearer Token from the [X Developer Portal](https://developer.x.com/en/portal/dashboard).
* **Reason**: The current token in `.env` is returning `CreditsDepleted` (limit reached or tier restricted).
* **Setup**: Paste the new values in `.env`:
  ```ini
  X_BEARER_TOKEN=your_new_bearer_token
  X_ACCOUNT_ID=699216790816075776
  ```

### Step 2: Configure Instagram Integration
* **Action Required**: Link your Instagram Business/Creator account to the Facebook Page **Sinthanai Selvan** via Facebook Page Settings -> **Linked Accounts**.
* **Setup**: Re-generate the Page Access Token on the Meta Graph API Explorer, checking the `instagram_basic`, `instagram_manage_comments`, and `instagram_manage_insights` permissions.
* **Pipeline Integration**: Once linked, we can update the connectors to dynamically query Instagram media and comments.

### Step 3: Configure YouTube Integration
* **Action Required**: Add a Google Developer project API Key to `.env` to pull live video views and stats instead of mock indicators.
  ```ini
  YOUTUBE_API_KEY=your_google_api_key
  YOUTUBE_CHANNEL_ID=your_channel_id
  ```
