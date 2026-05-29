# NTK Social Media Data & Sentiment Pipeline (Firebase/GCP Version)

This pipeline extracts metrics, posts, and comments from social platforms (Meta, YouTube, X), stores raw and normalized document payloads in **Firebase Firestore**, exports them to **Google Cloud BigQuery** for analytics, and visualizes them on a **Grafana Dashboard**.

## Project Folder Structure
- `connectors/`: Scripts for calling Meta, YouTube, and X APIs and saving response payloads.
- `firebase/`: Firestore database rules, collection initialization scripts, and BigQuery views.
- `sentiment/`: Batch sentiment classification scripts integrating Groq (Llama 3.1) and local MuRIL models.
- `ml/`: K-Means clustering script for audience segmentation.
- `grafana/`: Dashboard layout JSON configurations.

## Local Setup

### 1. Prerequisites
- Python 3.11+
- A Google Cloud Platform (GCP) project with **Firebase** enabled.
- A service account key file generated from Firebase Console (Project Settings -> Service accounts).

### 2. Dependency Installation
Install the necessary packages:
```bash
pip install -r requirements.txt
```

### 3. Database Initialization
1. Place your Firebase service account JSON key file in the root directory and rename it to `service-account.json`.
2. Run the collection setup script:
   ```bash
   python firebase/firestore_init.py
   ```
