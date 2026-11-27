# Build

`src/` is the FastAPI application and the optimizer it calls. See [app.md](app.md) and [optimizer.md](optimizer.md). The `Dockerfile` installs `src/requirements.txt` into a `python:3.12-slim` image, copies `src/`, and runs `uvicorn app:app` as a non-root user on the port Cloud Run sets.

`tests/run.sh` runs the `unittest` suite in `tests/` with `src/` on `PYTHONPATH`. It is what the `test` workflow runs on a pull request, after it installs `tests/requirements.txt`. Run it locally the same way. `examples/` holds a runnable usage script. Neither `tests/` nor `examples/` goes into the image.

On a push to `main`, `pipeline.yaml` runs the `apply` stage first, then `release.yaml`. The release stage skips its jobs unless the push changes `src/`, `Dockerfile`, `clouddeploy/`, or `release.yaml`. Otherwise it builds the image, pushes it to Artifact Registry as `us-central1-docker.pkg.dev/jpsteffe/arbsplit/arbsplit:<sha>`, and creates a Cloud Deploy release, staging the source in `gs://jpsteffe-clouddeploy/source`. It exits after the release is created. Check the rollout in the Cloud Deploy console.

`release.yaml` replaces the placeholder that `infra_template` ships.

`infra/registry.tf` creates the Artifact Registry repository and lets the Cloud Deploy execution service account read it. This is the only Artifact Registry read grant that account has. The platform gives it no project-wide read. Cloud Run requires the account that deploys a revision to read the image's repository, so removing `google_artifact_registry_repository_iam_member.clouddeploy_reader` makes releases fail.

The repository deletes old images. It keeps the 10 newest versions and every version less than 30 days old, and Artifact Registry deletes the rest. A rollback target or the live Cloud Run revision must fall inside that window, or its image can be deleted. Change `keep_count` or `newer_than` in `infra/registry.tf` to change the window. To log what would be deleted without deleting it, set `cleanup_policy_dry_run = true`.
