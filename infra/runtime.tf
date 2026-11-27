# Identity the Cloud Run service runs as. Cloud Deploy acts as this account
# when it creates a revision, so the Cloud Deploy execution service account
# needs roles/iam.serviceAccountUser on it.
resource "google_service_account" "runtime" {
  account_id   = "arbsplit"
  display_name = "arbsplit runtime"
}

# Terraform creates the Cloud Run service in service.tf, so the deployer that
# runs `terraform apply` must be able to act as the runtime account too. The
# platform gives the deployer no project-wide actAs.
resource "google_service_account_iam_member" "deployer_runtime" {
  service_account_id = google_service_account.runtime.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:app-deployer@jpsteffe.iam.gserviceaccount.com"
}

locals {
  # The platform's Cloud Deploy execution service account. The target in
  # clouddeploy.tf runs as it. build_template grants this member
  # roles/artifactregistry.reader on the app's Artifact Registry repository.
  # The platform grants it no project-wide read. Rename it only together with
  # that template.
  clouddeploy_exec = "serviceAccount:clouddeploy-exec@jpsteffe.iam.gserviceaccount.com"
}
