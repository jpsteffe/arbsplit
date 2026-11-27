# Every release pushes an image tagged with the git SHA, so versions build up.
# Artifact Registry applies a KEEP policy over a DELETE policy. A version is
# kept when it is one of the 10 newest or is less than 30 days old, and
# deleted otherwise. The count keeps the live image of an app that rarely
# releases. The age keeps the images of recent releases when many releases
# in a row fail to go live, and keeps rollback targets.
resource "google_artifact_registry_repository" "app" {
  location      = "us-central1"
  repository_id = "arbsplit"
  format        = "DOCKER"
  description   = "Images for arbsplit"

  # Deletion is intentional. Set true to log what would be deleted without
  # deleting it.
  cleanup_policy_dry_run = false

  cleanup_policies {
    id     = "keep-recent-versions"
    action = "KEEP"

    most_recent_versions {
      keep_count = 10
    }
  }

  cleanup_policies {
    id     = "keep-recent-days"
    action = "KEEP"

    condition {
      newer_than = "2592000s" # 30 days
    }
  }

  cleanup_policies {
    id     = "delete-old"
    action = "DELETE"

    condition {
      tag_state = "ANY"
    }
  }
}

# The Cloud Deploy execution service account deploys the Cloud Run revision,
# and Cloud Run requires the deploying account to read the image's repository.
# This is the only Artifact Registry read grant for that account. The platform
# gives it no project-wide read.
resource "google_artifact_registry_repository_iam_member" "clouddeploy_reader" {
  project    = "jpsteffe"
  location   = google_artifact_registry_repository.app.location
  repository = google_artifact_registry_repository.app.repository_id
  role       = "roles/artifactregistry.reader"
  member     = local.clouddeploy_exec
}
