# Deployment

Project: `so-smart-2025-26`

This repository is prepared for two Cloud Build triggers:

- `develop` -> `.cloudbuild/staging.yaml` -> Cloud Run service `sosmart-api-staging`
- `main` -> `.cloudbuild/production.yaml` -> Cloud Run service `sosmart-api`

Database setup already provisioned:

- Cloud SQL instance: `so-smart-2025-26:europe-west1:sosmart-postgres`
- staging database secret: `sosmart-database-url-staging`
- production database secret: `sosmart-database-url-prod`
- staging JWT secret: `sosmart-jwt-secret-staging`
- production JWT secret: `sosmart-jwt-secret-prod`
- runtime service account: `sosmart-api-runtime@so-smart-2025-26.iam.gserviceaccount.com`

Recommended setup in GCP:

1. Create one Artifact Registry Docker repository named `sosmart` in `europe-west1`.
2. In Cloud Run, connect this GitHub repository.
3. Create one trigger for `develop` using `.cloudbuild/staging.yaml`.
4. Create one trigger for `main` using `.cloudbuild/production.yaml`.

These build files expect the application code and `Dockerfile` at repository root.
