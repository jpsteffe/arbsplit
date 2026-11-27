# Deployment

Cloud Run service `arbsplit` in `jpsteffe` (`us-central1`) is created by Terraform and released through Cloud Deploy pipeline `arbsplit`

## How it fits together

- `infra/runtime.tf` creates the runtime service account the Cloud Run service runs as, and names the platform's Cloud Deploy execution service account. It also lets the deployer `app-deployer@jpsteffe.iam.gserviceaccount.com` act as the runtime service account, because Terraform creates the service as the deployer. That grant can take a minute to propagate, so the first apply may fail with a 403 on `iam.serviceaccounts.actAs`. Re-run the failed apply job in GitHub Actions.
- `infra/service.tf` creates the service with a public placeholder image and Identity-Aware Proxy on. Terraform ignores the service after creation.
- `infra/access.tf` lets the IAP service agent invoke the service and lets the access group through IAP, in the same apply, so no step after the release grants access.
- `infra/clouddeploy.tf` creates the Cloud Deploy target and the canary pipeline. The target renders and deploys as `clouddeploy-exec@jpsteffe.iam.gserviceaccount.com` and stores artifacts in `gs://jpsteffe-clouddeploy/artifacts`.
- `infra/clouddeploy_iam.tf` lets the execution service account act as the runtime service account, and gives it the operator role on the pipeline so the canary automation can advance rollouts. The platform grants that account `roles/iam.serviceAccountUser` on itself. The grant is shared by every application, so this repository does not manage it.
- `clouddeploy/service.yaml` and `clouddeploy/skaffold.yaml` are what each release applies. Cloud Deploy replaces the whole service from `service.yaml`, so change environment variables, the port, resources, and the service account there, not in Terraform. Keep the `run.googleapis.com/iap-enabled` annotation or a release turns IAP off.

## First release

The service exists with the placeholder before the first release, so the first release canaries at 0%, 5%, 10%, 25%, and 50%, and then goes stable. A Cloud Deploy automation advances each phase as soon as the previous one finishes, with no soak period. Until it succeeds, the service serves the placeholder.

A failed rollout shows in the Cloud Deploy console. The release stage exits after it creates the release.

## Who can call the service

Identity-Aware Proxy signs people in with their Google account. Only accounts in the organization that owns `jpsteffe` can sign in. A request that does not come through IAP does not reach the service, so a script needs an identity that IAP accepts.

- People in `group:app-access@jpsteffe.com` can open every application. Add or remove a person by changing that group's membership.
- To let one more member into this application only, add a `user:`, `group:`, or `serviceAccount:` to `accessors` in `infra/access.tf`. The next apply updates the binding.

An IAP policy change can take 5 to 10 minutes to take effect. A 403 right after a grant is not a failed grant.

## Hostname

After the first release succeeds, map a hostname to Cloud Run service `arbsplit` in the platform repository. This repository does not change DNS.

## Names other templates rely on

`google_service_account.runtime` and `local.clouddeploy_exec` are defined in `infra/runtime.tf`. The build template grants that member `roles/artifactregistry.reader` on this application's Artifact Registry repository, and the platform grants it no project-wide read. Cloud Run requires the account that deploys a revision to read the image's repository. An application from the image template has no repository of its own. It deploys a public image, or a private image from a repository that already grants that member read access. The pipeline is named `arbsplit`, the release source directory is `clouddeploy`, and the release stage stages source in `gs://jpsteffe-clouddeploy/source`.
