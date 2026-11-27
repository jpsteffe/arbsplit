resource "google_clouddeploy_target" "prod" {
  name        = "arbsplit"
  location    = "us-central1"
  description = "Cloud Run service arbsplit"

  run {
    location = "projects/jpsteffe/locations/us-central1"
  }

  # Render and deploy as the platform's execution service account. Without
  # this, Cloud Deploy falls back to the Compute Engine default service account.
  execution_configs {
    usages           = ["RENDER", "DEPLOY"]
    service_account  = "clouddeploy-exec@jpsteffe.iam.gserviceaccount.com"
    artifact_storage = "gs://jpsteffe-clouddeploy/artifacts"
  }
}

resource "google_clouddeploy_delivery_pipeline" "app" {
  name        = "arbsplit"
  location    = "us-central1"
  description = "Deploy arbsplit"

  serial_pipeline {
    stages {
      target_id = google_clouddeploy_target.prod.name

      strategy {
        canary {
          runtime_config {
            cloud_run {
              automatic_traffic_control = true
            }
          }

          canary_deployment {
            percentages = [0, 5, 10, 25, 50]
            verify      = false
          }
        }
      }
    }
  }
}

# Advance each canary phase as soon as the previous one finishes. There is no
# wait, so there is no soak period between phases.
resource "google_clouddeploy_automation" "advance_canary" {
  name              = "advance-canary"
  location          = "us-central1"
  delivery_pipeline = google_clouddeploy_delivery_pipeline.app.name
  description       = "Advance arbsplit canary phases without waiting"
  service_account   = "clouddeploy-exec@jpsteffe.iam.gserviceaccount.com"

  selector {
    targets {
      id = google_clouddeploy_target.prod.name
    }
  }

  rules {
    advance_rollout_rule {
      id = "advance-canary"
    }
  }

  # The platform grants clouddeploy-exec permission to act as itself. This
  # automation fails to create until that grant exists.
  depends_on = [google_clouddeploy_delivery_pipeline_iam_member.exec_operator]
}
