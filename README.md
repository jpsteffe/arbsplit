# arbsplit

Terraform for `arbsplit` in `jpsteffe` (`us-central1`). State lives in `gs://jpsteffe-tf-state` under `apps/arbsplit`. This repository must live under `jpsteffe` so the Workload Identity pool accepts it.

## Terraform

A pull request that changes `infra/` runs format, validate, and plan. Every push to `main` runs `pipeline.yaml`. Its `apply` stage runs `terraform apply` only when the push changes `infra/`. Its `release` stage runs `.github/workflows/release.yaml`. The infra template ships a release stage that does nothing. The build or image template replaces it, so read that file to see what your release stage does. `infra/main.tf` holds the backend and the provider.

Other templates add more `.tf` files to `infra/`. See the `infra_template` README for the names they rely on.

## Guides

Each template applied to this repository adds its own guide under `docs/`, and none of them edits this README. Only the guides for the templates you applied exist:

- `docs/deployment.md` from the deployment template: the Cloud Run service, Cloud Deploy, and who can call the service.
- `docs/build.md` from the build template: how the repository builds and releases `src/`.
- `docs/image.md` from the image template: how the repository releases a prebuilt image.

## Delete

Follow "Delete an application" in the `infra_template` README. Delete this repository only after that procedure finishes.
