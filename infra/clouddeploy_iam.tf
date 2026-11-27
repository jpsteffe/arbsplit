resource "google_service_account_iam_member" "clouddeploy_runtime" {
  service_account_id = google_service_account.runtime.name
  role               = "roles/iam.serviceAccountUser"
  member             = local.clouddeploy_exec
}

# The automation in clouddeploy.tf runs as the execution service account and
# advances rollouts on this pipeline, which needs the operator role.
resource "google_clouddeploy_delivery_pipeline_iam_member" "exec_operator" {
  location = google_clouddeploy_delivery_pipeline.app.location
  name     = google_clouddeploy_delivery_pipeline.app.name
  role     = "roles/clouddeploy.operator"
  member   = local.clouddeploy_exec
}
