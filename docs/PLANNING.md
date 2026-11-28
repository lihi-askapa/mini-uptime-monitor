# Pulse project planning

Last updated: 2026-11-28

Pulse is a small uptime-monitoring application used to learn DevOps through a working project. The aim is to build, operate, investigate and explain the system, and to share a public demonstration with interviewers and portfolio visitors.

This plan distinguishes completed work from preparation and future work. The completed-stage descriptions reconstruct the approach followed during the project; they are not a claim that this entire roadmap was written before implementation.

For current configuration, file responsibilities and continuation instructions, read [CONTEXT.md](CONTEXT.md). Use [learning-notes.md](learning-notes.md) for the chronological learning record.

## Version 1 completion boundary

The application, public HTTPS deployment, CI publication, manually triggered CD,
compatible-image rollback, scheduler-health exercise, daily S3 backup configuration,
isolated S3 restore and versioned Terraform state with locking are implemented and
verified within the limits recorded in the operational guides. The architecture
is summarized in [architecture.md](architecture.md). A future calendar-triggered
backup firing is distinct from the immediate service execution already verified.

Alerting, stable addressing, history retention, Terraform modules/adoption of the
existing server, ECS and schema-migration recovery are follow-up improvements,
not unfinished acceptance criteria for this first version.

## Goals and boundaries

- Understand the path from a browser request to application code, an external HTTP request and persistent storage.
- Package and run the application with Docker, then operate it on AWS.
- Verify changes with tests and CI, and learn to investigate failures.
- Add infrastructure as code, an image registry and controlled deployment automation.
- Learn when a managed container service is useful.
- Keep the application small enough for Lihi to explain each component herself.

This is a learning demo. High availability, enterprise authentication, arbitrary user-supplied URLs and a production service-level commitment are outside the current scope.

## Progress overview

| Stage | Status | Result or completion criterion |
|---|---|---|
| Local application | Complete | Manual checks, SQLite history and a health endpoint work. |
| Docker packaging | Complete | Image runs with Gunicorn, a non-root application user and a persistent volume. |
| Continuous integration | Complete | GitHub runs tests, builds the image and runs tests inside it. |
| CI failure exercise | Complete | An intentionally wrong expectation caused a red run; correcting it restored green. |
| Scheduled checks | Complete | Separate worker checks configured targets and saves into shared SQLite storage. |
| Manual AWS deployment | Complete | Application and scheduler run on a personal EC2 instance. |
| Public HTTPS demo | Complete | User verified page loading, manual checks and repeated-check blocking. |
| Terraform foundations | Complete for current scope | ECR, IAM/SSM, backup and state buckets managed; versioned encrypted S3 state migrated and locking verified. Existing EC2 resources are not adopted. |
| ECR image registry | In progress | CI publication, EC2 pull and manual deployment verified; registry retention remains planned. |
| Controlled CD | Verified for compatible image versions | Manual GitHub workflow deployed cda4c66 and returned to b13144f; both runs passed health verification. Database migration rollback remains outside this exercise. |
| ECS learning and evaluation | Deferred | Explain the concepts and record whether a separate migration exercise is worthwhile. |

## Completed stages and decisions

### 1. Build the smallest useful monitor

Use Python and Flask with server-rendered HTML and CSS. Start with a fixed list of three targets and a manual check button. Store the target, UTC time, status, HTTP code, response duration and error in SQLite.

SQLite keeps the learning scope small: one local database file, accessed through Python's `sqlite3` module. The page displays the latest 50 checks while older rows remain stored. `/health` reports database readability independently of target availability.

The original five tests cover successful persistence, HTTP errors, connection errors, unknown targets and database health failure.

### 2. Package the application and separate code from data

Build a Python 3.12 image from a Dockerfile. Run the application with Gunicorn. Configure ports, environment variables, resource limits and the named volume with Compose.

Practice the distinction between rebuilding an image, recreating a container and retaining a volume. Container replacement was exercised with existing history preserved.

A local TLS download problem required an offline dependency-wheel cache on the Mac. The server and CI use ordinary online installation. The dependency lists were later consolidated into one `requirements.txt`.

### 3. Add CI and investigate a failure

GitHub Actions runs on pushes, pull requests and manual requests. It prepares Python, installs dependencies, runs tests, builds the Docker image and runs tests in that image.

An exercise changed the database-failure test's expected code from 503 to 200. The workflow failed with `AssertionError: 503 != 200`; restoring the correct expectation produced a green run. This demonstrated that a failed test can expose an incorrect test expectation as well as an application defect.

### 4. Schedule checks in a separate process

Extract the check-and-save operation into one function shared by the web route and a CLI command. Run the CLI command in a separate `scheduler` container using the same application image and data volume.

The worker checks targets sequentially, then waits 60 seconds after the round. It is enabled with the `monitoring` Compose profile. Two tests were added, bringing the total to seven.

### 5. Deploy manually before automating deployment

Launch a personal EC2 instance, configure restricted SSH access, install Docker and Compose, transfer a Git archive, build an image and start the services. First inspect the page through an SSH tunnel.

This makes the manual deployment steps understandable before converting them into a CD workflow. No automated deployment has been configured yet.

### 6. Publish a small HTTPS demonstration

Add Caddy as a third container and configure a hostname through an IP-based DNS service. Keep the application port bound to server loopback; public traffic enters through Caddy.

Enable form-token validation and a shared 30-second per-target cooldown for manual checks. The scheduler remains independent of this cooldown. Three tests were added, bringing the total to ten. Public page loading, a successful manual check and cooldown rejection were confirmed by the user.

## Next stages

### 7. Introduce Terraform safely

Terraform 1.17.2 is installed and initialized on the Mac with AWS provider 6.74.0. The user validated and applied the ECR repository, GitHub OIDC provider and publishing IAM role/policy in the personal account. A follow-up plan confirmed no changes after ECR creation. State was subsequently migrated to private versioned S3 storage with native locking; it remains excluded from Git. The existing EC2 server remains unmanaged by Terraform.

Next actions:

1. Read the initial configuration together and initialize the working directory.
2. Explain provider installation, the dependency lock file and the distinction between `init`, `validate`, `plan` and `apply`.
3. Establish a named personal AWS authentication path and verify the account identity before planning cloud changes. Keep work-account credentials separate.
4. Decide which resources Terraform will own first. A proposed small first resource is the ECR repository needed for CD.
5. Completed: dedicated encrypted, versioned S3 backend and native S3 locking, with local recovery snapshots. Migration retained 24 resource records/outputs, a plan reported no changes and a concurrent plan was blocked. Never commit state or credentials.
6. For the existing server and security group, write a deliberate import/adoption plan. Review the resulting plan before applying; resolve replacement or deletion proposals before proceeding.
7. Introduce modules and environment inputs when they clarify a real separation in the project.

Completion: configuration validates, a reviewed plan matches the intended scope, the selected resource is managed successfully, and a follow-up plan shows no unintended changes. Existing resources must not be duplicated accidentally.

### 8. Add ECR

Create a private image repository through Terraform. Define image tagging, repository permissions and an image-retention policy. Publish a tested image from CI and verify that the EC2 host can pull it.

Current progress: the private repository exists with immutable tags and deletion protection in Terraform. GitHub's publishing role is restricted to this repository's immutable OIDC identity on main, with ECR image permissions scoped to the project repository. The workflow now prepares an explicit linux/amd64 build, tests it and publishes it under the commit SHA. The user confirmed green CI, an image in ECR, pull-only EC2 role authentication, ten tests passing from the pulled image, and manual deployment of that image to web and scheduler. Public health returned 200 and scheduler logs showed completed rounds. Registry retention remains future work; deployment automation is not implemented.

Use commit-based tags or image digests so deployment identifies a specific version. Plan for the Mac's ARM architecture and the server's x86 architecture: the deployment image must support the server.

Completion: a tested image is present in ECR and the server can retrieve the exact version intended for deployment.

### 9. Build controlled CD

SSM prerequisite completed on 2026-11-28: Terraform attached the managed SSM core policy to the EC2 role; the user confirmed Online status and a successful remote whoami returning root. The separate GitHub deployment role and bounded SSM document were applied. A manual SSM invocation verified the existing image and a fresh scheduled round. The manual GitHub workflow subsequently deployed cda4c66 successfully and returned to compatible version b13144f. Both runs passed web and scheduler verification; this did not test a database schema rollback.

Proposed approach: GitHub authenticates to AWS through OIDC and receives temporary permissions. Systems Manager sends a bounded deployment operation to the intended EC2 host. Keep the initial trigger manual; do not assume GitHub environment approval features are available for the repository's plan and visibility.

Define the EC2 instance role, GitHub trust restrictions, deployment permissions and image-pull permissions separately. Restrict the intended repository, branch or environment, account and target server. Do not store the personal SSH private key in the repository.

Deploy a specific image version, avoid overlapping deployments, preserve volumes and check application health after the update. Include evidence that the scheduler continues to save results; `/health` alone cannot establish this. Retain the previous version and rehearse rollback, including the effect of future database-schema changes.

Completion: a controlled run deploys the requested tested version, reports its checks and demonstrates a recoverable failure path. Do not claim zero downtime or automatic rollback before testing them.

### 10. Learn ECS and decide whether to migrate (deferred)

The user chose to continue CD on the current EC2/Compose stack first. Revisit this stage later.

Explain clusters, task definitions, tasks and services, and compare EC2-backed capacity with Fargate. Relate each concept to the Compose setup already understood.

A migration needs a storage design: the two current services share one host-local SQLite file. Do not assume this volume can simply be shared across independent ECS tasks. Evaluate an external database or another explicitly supported storage arrangement, networking, ingress, permissions and cost before implementation.

Completion: Lihi can explain the tradeoffs. An actual migration is a separate decision, not a prerequisite for completing the EC2-based project.

## Operational improvements to consider

| Item | Why it matters | Completion evidence |
|---|---|---|
| History retention | SQLite grows with every scheduled and manual check. | A documented policy and a tested cleanup path. |
| Backup and restore | Daily S3 backups enabled; first service execution and isolated restore verified. | Private encrypted bucket, 30-day lifecycle, daily 03:00 UTC timer and 15-minute failure retry. First S3 snapshot: 6,175 checks; checksum, integrity, contents and Flask checks passed. Future timer firing has not yet been observed. |
| Scheduler monitoring | Deployed and verified on EC2. | Fifteen tests passed; user stopped the worker, observed 503 after the 180-second limit, restarted it and confirmed recovery to 200 on 2026-11-28. No automatic alerts yet. |
| Stable address | The current demo hostname embeds a public IP that may change. | A chosen address/domain strategy with its cost understood. |
| Integration checks | Unit tests do not boot the entire Compose stack together. | A repeatable check of web, scheduler and shared storage. |
| Cost tracking | EC2, storage and networking consume account credits. | Review actual usage and know how to stop and clean up resources. |

## Plan maintenance

Update this plan when a stage changes status or scope. Mark a stage complete only after its completion evidence exists. Update the context document when configuration or the continuation point changes. Neither document should contain passwords, access tokens or private-key contents.
