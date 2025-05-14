# Streamlit Task Manager on Cloud Run with Cloud SQL and IAP

## Overview

This project demonstrates how to deploy a Python Streamlit application on Google Cloud Run, using Cloud SQL (PostgreSQL) as a persistent database backend, and securing access with Google's Identity-Aware Proxy (IAP). The application is a simple task manager allowing users to add, view, and delete tasks.

## Architecture

* **Frontend:** Streamlit (Python web framework)
* **Backend Logic:** Python
* **Hosting:** Google Cloud Run (Serverless container platform)
* **Database:** Google Cloud SQL (Managed PostgreSQL)
* **Authentication:** Google Identity-Aware Proxy (IAP)
* **Container Registry:** Google Artifact Registry
* **Secrets Management:** Google Secret Manager

## Prerequisites

### Google Cloud Platform (GCP)
* A Google Cloud Project with billing enabled.
* `gcloud` command-line tool installed and configured ([Install Guide](https://cloud.google.com/sdk/docs/install)). Authenticate with:
    ```bash
    gcloud auth login
    gcloud auth application-default login
    gcloud config set project YOUR_PROJECT_ID
    ```
* Permissions to enable APIs, create Cloud SQL instances, Cloud Run services, Artifact Registry repositories, Secret Manager secrets, and manage IAP and IAM settings.

### Local Development (Optional, for testing before deployment)
* Python 3.8+
* Docker Desktop (if building images locally)
* The application files: `app.py`, `requirements.txt`, `Dockerfile`.

## Project Files

* **`app.py`**: The main Streamlit application code using SQLAlchemy for database interaction and the Google Cloud SQL Connector.
* **`requirements.txt`**: Lists Python dependencies for the application.
* **`Dockerfile`**: Defines the container image for deploying the application.

## Local Development (Summary)

1.  **Clone/Download Files**: Get `app.py`, `requirements.txt`, and `Dockerfile`.
2.  **Install Dependencies**: `pip install -r requirements.txt`
3.  **Set up Cloud SQL Auth Proxy**: (Recommended for secure local connection)
    * [Download and install the proxy](https://cloud.google.com/sql/docs/postgres/connect-auth-proxy#install).
    * Run it in a separate terminal: `./cloud-sql-proxy YOUR_INSTANCE_CONNECTION_NAME --port 5432`
4.  **Set Environment Variables** (for `app.py`):
    ```bash
    export DB_USER="your_db_user"
    export DB_PASS="your_db_password"
    export DB_NAME="tasks_db"
    # For Cloud SQL Connector (if not using proxy directly for app config)
    export INSTANCE_CONNECTION_NAME="YOUR_PROJECT_ID:YOUR_REGION:YOUR_INSTANCE_ID"
    # If using proxy and app connects to localhost:
    export DB_HOST="127.0.0.1"
    export DB_PORT="5432"
    export DB_IAM_AUTH="false" # Or "true" if configured
    ```
5.  **Run Streamlit App**: `streamlit run app.py`

## Deployment to Google Cloud

Follow these steps to deploy the application:

### Step 1: Google Cloud Project Setup

1.  **Select or Create Project**:
    Ensure you have a Google Cloud project selected.
    ```bash
    gcloud config set project YOUR_PROJECT_ID
    ```

2.  **Enable APIs**:
    Enable all necessary APIs for your project:
    ```bash
    gcloud services enable \
        [run.googleapis.com](https://www.google.com/search?q=run.googleapis.com) \
        [sqladmin.googleapis.com](https://www.google.com/search?q=sqladmin.googleapis.com) \
        [artifactregistry.googleapis.com](https://www.google.com/search?q=artifactregistry.googleapis.com) \
        [cloudbuild.googleapis.com](https://www.google.com/search?q=cloudbuild.googleapis.com) \
        [secretmanager.googleapis.com](https://www.google.com/search?q=secretmanager.googleapis.com) \
        [iap.googleapis.com](https://www.google.com/search?q=iap.googleapis.com)
    ```

3.  **Configure OAuth Consent Screen (for IAP)**:
    * In the Google Cloud Console, navigate to "APIs & Services" > "OAuth consent screen."
    * Choose "Internal" if all users are within your Google Workspace organization, or "External."
    * Fill in the application name, user support email, and developer contact information.
    * Save and continue. You generally don't need to add scopes for IAP itself.

### Step 2: Set up Cloud SQL (PostgreSQL)

1.  **Choose a Region**:
    Define your preferred GCP region (e.g., `us-central1`).
    ```bash
    export REGION="us-central1" # Or your preferred region
    ```

2.  **Create Cloud SQL Instance**:
    Create a PostgreSQL instance. Adjust machine type and storage as needed.
    ```bash
    export SQL_INSTANCE_NAME="streamlit-tasks-db-instance"
    gcloud sql instances create ${SQL_INSTANCE_NAME} \
        --database-version=POSTGRES_15 \
        --cpu=1 \
        --memory=4GiB \
        --region=${REGION} \
        --root-password="CHOOSE_A_STRONG_ROOT_PASSWORD" # Set and remember this
    ```
    Wait for the instance to be created.

3.  **Get Instance Connection Name**:
    This is crucial for connecting your application.
    ```bash
    export INSTANCE_CONNECTION_NAME=$(gcloud sql instances describe ${SQL_INSTANCE_NAME} --format='value(connectionName)')
    echo "Instance Connection Name: ${INSTANCE_CONNECTION_NAME}"
    ```

4.  **Create a Database**:
    ```bash
    export DB_NAME="tasks_db"
    gcloud sql databases create ${DB_NAME} --instance=${SQL_INSTANCE_NAME}
    ```

5.  **Create a Database User**:
    It's best practice to create a dedicated user for your application.
    ```bash
    export DB_USER="streamlit_app_user"
    export DB_PASS="CHOOSE_A_STRONG_DB_USER_PASSWORD" # Set and remember this
    gcloud sql users create ${DB_USER} \
        --instance=${SQL_INSTANCE_NAME} \
        --password=${DB_PASS}
    ```

### Step 3: Store Secrets in Secret Manager

Store your database credentials securely.

1.  **Create Secrets**:
    ```bash
    echo -n "${DB_USER}" | gcloud secrets create streamlit-db-user --data-file=- --replication-policy=automatic
    echo -n "${DB_PASS}" | gcloud secrets create streamlit-db-pass --data-file=- --replication-policy=automatic
    echo -n "${DB_NAME}" | gcloud secrets create streamlit-db-name --data-file=- --replication-policy=automatic
    echo -n "${INSTANCE_CONNECTION_NAME}" | gcloud secrets create streamlit-instance-connection-name --data-file=- --replication-policy=automatic
    ```

### Step 4: Build and Push Docker Image to Artifact Registry

1.  **Create an Artifact Registry Repository**:
    ```bash
    export AR_REPO_NAME="streamlit-apps-repo"
    gcloud artifacts repositories create ${AR_REPO_NAME} \
        --repository-format=docker \
        --location=${REGION} \
        --description="Docker repository for Streamlit apps"
    ```

2.  **Build and Push the Image (Using Cloud Build - Recommended)**:
    Ensure your `Dockerfile`, `app.py`, and `requirements.txt` are in the current directory.
    ```bash
    export IMAGE_NAME="streamlit-task-manager"
    export IMAGE_TAG="latest"
    export IMAGE_URI="${REGION}-docker.pkg.dev/$(gcloud config get-value project)/${AR_REPO_NAME}/${IMAGE_NAME}:${IMAGE_TAG}"

    gcloud builds submit --tag ${IMAGE_URI} .
    ```
    *(Alternatively, you can build and push with local Docker commands after configuring Docker authentication for Artifact Registry: `gcloud auth configure-docker ${REGION}-docker.pkg.dev`)*

### Step 5: Deploy to Cloud Run

1.  **Create a Dedicated Service Account for Cloud Run**:
    This service account will be used by your Cloud Run service.
    ```bash
    export CLOUDRUN_SA_NAME="sa-streamlit-task-app"
    gcloud iam service-accounts create ${CLOUDRUN_SA_NAME} \
        --display-name="Streamlit Task App Service Account"
    
    export CLOUDRUN_SA_EMAIL="${CLOUDRUN_SA_NAME}@$(gcloud config get-value project)[.iam.gserviceaccount.com](https://www.google.com/search?q=.iam.gserviceaccount.com)"
    ```

2.  **Grant Permissions to the Service Account**:
    * Allow it to connect to Cloud SQL:
        ```bash
        gcloud projects add-iam-policy-binding $(gcloud config get-value project) \
            --member="serviceAccount:${CLOUDRUN_SA_EMAIL}" \
            --role="roles/cloudsql.client"
        ```
    * Allow it to access secrets from Secret Manager:
        ```bash
        gcloud secrets add-iam-policy-binding streamlit-db-user \
            --member="serviceAccount:${CLOUDRUN_SA_EMAIL}" \
            --role="roles/secretmanager.secretAccessor"
        gcloud secrets add-iam-policy-binding streamlit-db-pass \
            --member="serviceAccount:${CLOUDRUN_SA_EMAIL}" \
            --role="roles/secretmanager.secretAccessor"
        gcloud secrets add-iam-policy-binding streamlit-db-name \
            --member="serviceAccount:${CLOUDRUN_SA_EMAIL}" \
            --role="roles/secretmanager.secretAccessor"
        gcloud secrets add-iam-policy-binding streamlit-instance-connection-name \
            --member="serviceAccount:${CLOUDRUN_SA_EMAIL}" \
            --role="roles/secretmanager.secretAccessor"
        ```

3.  **Deploy the Cloud Run Service**:
    Replace `YOUR_PROJECT_NUMBER` with your actual project number (you can find it with `gcloud projects describe YOUR_PROJECT_ID --format='value(projectNumber)'`).
    ```bash
    export CLOUD_RUN_SERVICE_NAME="streamlit-task-manager"
    export PROJECT_NUMBER=$(gcloud projects describe $(gcloud config get-value project) --format='value(projectNumber)')

    gcloud run deploy ${CLOUD_RUN_SERVICE_NAME} \
        --image=${IMAGE_URI} \
        --platform=managed \
        --region=${REGION} \
        --service-account=${CLOUDRUN_SA_EMAIL} \
        --port=8501 \
        --add-cloudsql-instances=${INSTANCE_CONNECTION_NAME} \
        --update-secrets=DB_USER=streamlit-db-user:latest \
        --update-secrets=DB_PASS=streamlit-db-pass:latest \
        --update-secrets=DB_NAME=streamlit-db-name:latest \
        --update-secrets=INSTANCE_CONNECTION_NAME=streamlit-instance-connection-name:latest \
        --set-env-vars=DB_IAM_AUTH="false" \
        --allow-unauthenticated # Temporarily for initial testing before IAP setup
    ```
    * **`--port=8501`**: Streamlit's default port. Your Dockerfile also sets `ENV PORT 8501` and runs Streamlit on `${PORT}`.
    * **`--add-cloudsql-instances`**: This automatically configures the Cloud SQL connection (proxy).
    * **`--update-secrets`**: Maps Secret Manager secrets to environment variables.
    * **`--allow-unauthenticated`**: We use this for initial deployment testing. **This will be changed after configuring IAP.**

4.  **Test Initial Deployment**:
    After deployment, Cloud Run will provide a URL. Try accessing it. The app should load and connect to the database. If not, check the logs in Cloud Run.

### Step 6: Secure with Identity-Aware Proxy (IAP)

1.  **Enable IAP for the Cloud Run service**:
    * Go to "Security" > "Identity-Aware Proxy" in the Cloud Console.
    * If prompted, configure your OAuth consent screen.
    * Find your Cloud Run service in the list. It might take a few minutes to appear after the first access, or it might be listed under "Backend Services" if a load balancer was implicitly created.
    * Toggle the IAP switch ON for your service.

2.  **Add Authorized Users/Groups (Principals)**:
    * The IAP permissions panel will appear (or click the service name, then "Add Principal" in the info panel on the right).
    * Click "Add Principal."
    * Enter the Google email addresses of users or Google Groups who should have access.
    * In "Select a role," choose **Cloud IAP > IAP-secured Web App User**.
    * Click "Save."

3.  **Update Cloud Run to Require Authentication**:
    Now that IAP is configured, restrict direct access to Cloud Run.
    ```bash
    gcloud run services update ${CLOUD_RUN_SERVICE_NAME} \
        --region=${REGION} \
        --no-allow-unauthenticated
    ```
    This ensures that only IAP can invoke your Cloud Run service. IAP handles the user authentication. The IAP service account (`service-{PROJECT_NUMBER}@gcp-sa-iap.iam.gserviceaccount.com`) is automatically granted the `roles/run.invoker` role on your Cloud Run service by the console when you enable IAP.

## Accessing the Application

* Once deployed and IAP is enabled, use the URL provided by Cloud Run.
* You (or other authorized users) will be prompted to sign in with your Google account.
* Only users/groups granted the "IAP-secured Web App User" role will be able to access the application.
* The application sidebar should attempt to display your email if the IAP information is passed as query parameters (note: IAP usually passes this via headers; a custom setup might be needed if you strictly want them as query params for Streamlit).
