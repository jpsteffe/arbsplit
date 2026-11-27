# arbsplit

Race Arbitrage Studio: a FastAPI service and static web UI that find worst-case-profit and fewest-bet arbitrage portfolios for a single horse race. See `docs/app.md`.

Terraform for `arbsplit` in `jpsteffe` (`us-central1`). State lives in `gs://jpsteffe-tf-state` under `apps/arbsplit`. This repository must live under `jpsteffe` so the Workload Identity pool accepts it.

## Terraform

A pull request that changes `infra/` runs format, validate, and plan. Every push to `main` runs `pipeline.yaml`. Its `apply` stage runs `terraform apply` only when the push changes `infra/`. Its `release` stage runs `.github/workflows/release.yaml`. The infra template ships a release stage that does nothing. The build or image template replaces it, so read that file to see what your release stage does. `infra/main.tf` holds the backend and the provider.

Other templates add more `.tf` files to `infra/`. See the `infra_template` README for the names they rely on.

## Guides

Each template applied to this repository adds its own guide under `docs/`. The application guides `app.md` and `optimizer.md` are not from a template. Only the guides for the templates you applied exist:

- `docs/deployment.md` from the deployment template: the Cloud Run service, Cloud Deploy, and who can call the service.
- `docs/build.md` from the build template: how the repository builds and releases `src/`.
- `docs/app.md`: the Race Arbitrage Studio web app, its single `POST /api/calculate` endpoint, and its limits.
- `docs/optimizer.md`: the input schema, payout math, and limits of `src/arbitrage_optimizer.py`.
- `docs/image.md` from the image template: how the repository releases a prebuilt image.

## Delete

Follow "Delete an application" in the `infra_template` README. Delete this repository only after that procedure finishes.
