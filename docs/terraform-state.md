# Terraform remote state

## Current configuration

The project state was migrated from the Mac to a dedicated S3 backend on
2026-11-28. AWS account: `944464821297`; region: `eu-north-1`.

| Setting | Value |
|---|---|
| Bucket | `pulse-944464821297-tfstate-eu-north-1` |
| State object | `pulse/terraform.tfstate` |
| Lock object | `pulse/terraform.tfstate.tflock` |
| Versioning | Enabled |
| Encryption | AES256 server-side encryption |
| Public access | All four S3 public-access blocks enabled; ACLs disabled |
| Transport | Bucket policy denies requests without TLS |
| Expiration | None; this bucket does not use SQLite's 30-day retention rule |
| Terraform version | At least 1.10, below 2.0; installed and exercised with 1.17.2 |

`backend.tf` selects the storage location and enables `use_lockfile`.
`state-storage.tf` manages the bucket and its protections. The bucket was created
with the original local backend before adding the S3 backend configuration, then
its own resources were included in the migration. Terraform deletion protection
and `force_destroy=false` protect against routine destruction through this code.

The state is Terraform's mapping of configuration to AWS resources. The S3 object
is now the authoritative state, not just a scheduled backup of a local file.
Successful state writes create versions automatically. The Mac need not remain
running to retain the stored state. State is not application data or source code.
The SQLite backups use a different bucket and timer.

## Verification performed

1. Verified the personal AWS account and saved a private local recovery snapshot.
2. Reviewed a plan containing six state-storage creations only; applied it without
   changing or deleting existing resources.
3. Saved a second complete snapshot after bucket creation and verified the target
   S3 prefix was empty with versioning enabled.
4. Ran `terraform init -migrate-state -force-copy -input=false` for this deliberate
   one-time migration. All 24 resource records and all outputs matched the local
   snapshot. The newly initialized backend uses a new lineage/serial; resource
   contents and identities were preserved.
5. Verified the S3 object has a version ID, AES256 encryption, public access blocks
   and no lifecycle expiration configuration.
6. Ran a full plan: **No changes**. Observed its real S3 lock object, attempted a
   concurrent plan and confirmed it failed to acquire the lock. The first plan
   completed normally and released the lock.

Recovery copies and the verification report are owner-only files outside Git in
`/Users/lihias/Documents/Codex/pulse-private/terraform-state/`. The original snapshot
contains 18 resources; the snapshot immediately before migration contains 24,
including the six new state-storage resources. Neither state nor plan files should
be committed. `.terraform/` contains local backend/provider metadata, not a public
copy to distribute.

## Normal use on the Mac

Use the personal profile for both backend and provider authentication:

```bash
AWS_PROFILE=pulse-personal terraform -chdir=infra/terraform init
AWS_PROFILE=pulse-personal terraform -chdir=infra/terraform plan
```

These examples run from the repository root. A fresh clone uses ordinary `init`
to connect to the existing backend. Do not repeat migration or force-copy flags
for normal initialization. If authentication has expired, sign in again using
`aws login --profile pulse-personal --region eu-north-1`.

No credentials are stored in backend.tf. The existing EC2 and GitHub roles were
not granted access to the state bucket. Operators need S3 list access to the
bucket, get/put for the state, and get/put/delete for the lock object. The personal
operator role currently supplies these permissions.

## Recovery boundaries

S3 versions can be retrieved to a private file for inspection before any recovery.
Recovering Terraform state does not itself revert infrastructure, application
versions or database contents. Stop concurrent operations and establish the
correct version before any state replacement. Do not delete an active lock or
force-unlock merely because another operation is running.

The state bucket itself is managed by this configuration; if the bucket is lost,
ordinary backend initialization cannot recreate it. Recovery requires recreating
the protected bucket and restoring verified state before normal Terraform use.
The local pre-migration snapshots provide an additional recovery reference.

[HashiCorp S3 backend and locking documentation](https://developer.hashicorp.com/terraform/language/backend/s3)
