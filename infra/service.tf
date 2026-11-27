# Terraform creates this service so it exists with its IAM from the first apply.
# Cloud Run needs an image to create it, so it starts with a public placeholder.
# Cloud Deploy replaces the whole service from clouddeploy/service.yaml on every
# release, so that manifest controls runtime config. Terraform ignores the
# service after creation. IAP is on from the start, and clouddeploy/service.yaml
# keeps it on across releases.
resource "google_cloud_run_v2_service" "app" {
  name                = "arbsplit"
  location            = "us-central1"
  deletion_protection = true
  ingress             = "INGRESS_TRAFFIC_ALL"
  iap_enabled         = true

  template {
    service_account = google_service_account.runtime.email

    containers {
      image = "us-docker.pkg.dev/cloudrun/container/hello"
    }
  }

  # The grant can take a minute to propagate. If the first apply fails with a
  # 403 on iam.serviceaccounts.actAs, re-run the apply job.
  depends_on = [google_service_account_iam_member.deployer_runtime]

  lifecycle {
    ignore_changes = all
  }
}
