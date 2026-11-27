# Identity-Aware Proxy fronts the service. Enabling IAP needs two grants: the
# IAP service agent invokes the service, and people get
# roles/iap.httpsResourceAccessor.
resource "google_cloud_run_v2_service_iam_member" "iap_invoker" {
  project  = google_cloud_run_v2_service.app.project
  location = google_cloud_run_v2_service.app.location
  name     = google_cloud_run_v2_service.app.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:service-1008138599778@gcp-sa-iap.iam.gserviceaccount.com"
}

# Add a member for this app only. The default group is shared by every app;
# add or remove people by changing that group's membership, not this list.
variable "accessors" {
  description = "Members granted roles/iap.httpsResourceAccessor on the service."
  type        = list(string)
  default     = ["group:app-access@jpsteffe.com"]
}

resource "google_iap_web_cloud_run_service_iam_member" "accessor" {
  for_each = toset(var.accessors)

  project                = google_cloud_run_v2_service.app.project
  location               = google_cloud_run_v2_service.app.location
  cloud_run_service_name = google_cloud_run_v2_service.app.name
  role                   = "roles/iap.httpsResourceAccessor"
  member                 = each.value
}
