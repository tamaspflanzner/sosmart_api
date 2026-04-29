# Deployment

Project: `so-smart-2025-26`

This repository is prepared for two Cloud Build triggers:

- `develop` -> `.cloudbuild/staging.yaml` -> Cloud Run service `sosmart-api-staging`
- `main` -> `.cloudbuild/production.yaml` -> Cloud Run service `sosmart-api`

Recommended setup in GCP:

1. Create one Artifact Registry Docker repository named `sosmart` in `europe-west1`.
2. In Cloud Run, connect this GitHub repository.
3. Create one trigger for `develop` using `.cloudbuild/staging.yaml`.
4. Create one trigger for `main` using `.cloudbuild/production.yaml`.

These build files expect the application code and `Dockerfile` at repository root.
