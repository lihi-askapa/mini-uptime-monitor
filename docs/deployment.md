# Controlled deployment to EC2

## Current evidence

On 2026-11-28, SSM document `mini-uptime-monitor-deploy` version 1 successfully
processed the already running image `b13144f3ef327628849a377f409dfef02ce77a5d`.
It verified web and scheduler image IDs, public health endpoints and a scheduled
round completed after the deployment request. This did not exercise a version
change or rollback in that initial run. Subsequent GitHub run
[46098753552](https://github.com/lihi-askapa/mini-uptime-monitor/actions/runs/46098753552)
successfully deployed cda4c6634b67d22827a4e10a7df68ba18c2a2aa2, and run
[46098856078](https://github.com/lihi-askapa/mini-uptime-monitor/actions/runs/46098856078)
successfully returned to b13144f3ef327628849a377f409dfef02ce77a5d. Both runs
passed deployment verification. These tags share application/schema code;
this is an image-version rollback exercise, not a database migration rollback.

## What each change needs

- Application changes: commit, push, successful publishing CI, then manually deploy
  that commit's image when ready to update the public application.
- Documentation-only changes: commit and push; no application deployment required.
- Terraform changes: review `plan`, then `apply` for the intended infrastructure.
- Host Compose/Caddy configuration changes: explicitly synchronize and validate
  the host files. Pulling an application image does not update those files.

The publishing workflow still runs on pushes, including documentation changes.
Publishing an image does not deploy it. No push automatically updates EC2.

## Run the GitHub deployment

After this workflow is committed and pushed to the default branch:

1. Wait for the selected commit's **Test, build and publish image** run to succeed
   on `main`. The image must already be in the private ECR repository.
2. Open GitHub Actions and select **Deploy Pulse to EC2**.
3. Choose **Run workflow**, keep branch `main`, and enter the full 40-character
   commit SHA in `image_tag`. For the first orchestration check, use the verified
   image `b13144f3ef327628849a377f409dfef02ce77a5d`.
4. The workflow verifies successful publishing CI, authenticates using the separate
   deployment OIDC role and requests SSM document **version 1** on the fixed EC2 host.
5. Inspect the run logs and summary for the SSM command ID and terminal result.
   Green requires SSM Success and exit code zero, after the script's checks pass.
6. Open the public dashboard and inspect its results. Application health does not
   establish that every UI interaction or monitored target is working.

The workflow does not build an image. It serializes deployment runs; the host also
has a deployment lock. It handles initially missing SSM invocation results and
polls for up to 20 minutes. The SSM step itself has a 15-minute execution limit.
Application tests remain fifteen; local workflow validation included six mocked
polling scenarios, not additional application test methods.

## Boundaries and recovery

- The GitHub role may send only the custom deployment document to the project
  instance. It cannot use arbitrary `AWS-RunShellScript` or edit the document.
- The document runs as root. It accepts only a validated commit SHA, uses a fixed
  registry and host directory, and consumes the existing three Compose files.
- The script updates web and scheduler with `--no-build --pull never`, preserves
  volumes, and checks actual image IDs. This is not a zero-downtime deployment.
- `/health` checks database readability. `/health/monitoring` checks scheduled-round
  freshness; the script additionally requires a round newer than deployment start.
- Root-only `/var/lib/mini-uptime-monitor/previous-image` records the image before
  a version change. `current-image` records the last verified deployment. These
  are recovery references, not backups or an automatic rollback mechanism.
- A failed update can leave the requested image running. Inspect the recorded
  SSM command and service logs before another attempt. There is no automatic rollback.
- Cancelling GitHub does not necessarily stop a command already accepted by SSM.
  Use the recorded command ID to inspect it before requesting another deployment.
- Version 1 is pinned deliberately. Future script changes require Terraform apply
  to publish a new document version and an explicit workflow version update after review.
- Image-version rollback was rehearsed between compatible versions. Future incompatible database changes require
  a separate recovery plan; switching an image alone cannot undo data changes.

## References

- [GitHub manual workflow triggers](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_dispatch)
- [SSM invocation results and eventual consistency](https://docs.aws.amazon.com/systems-manager/latest/APIReference/API_GetCommandInvocation.html)
