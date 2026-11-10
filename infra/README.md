# Radar Ferroviario Infrastructure as Code

Terraform manages the persistent AWS infrastructure for Radar Ferroviario.

## Architecture

```text
GitHub tag
    |
    v
GitHub Actions
    |
    +--> Build and test linux/amd64 image
    |
    +--> Publish immutable version to Amazon ECR
    |
    +--> Resolve ECR digest
    |
    +--> Update ECS Express Gateway Service
    |
    +--> Monitor canary deployment and rollback alarm
    |
    +--> Validate public endpoints
```

## Terraform scope

Terraform manages:

- S3 remote state bucket
- Amazon ECR repository
- ECR lifecycle policy
- GitHub OIDC IAM role
- GitHub ECR permissions
- GitHub ECS deployment permissions
- Restricted iam:PassRole permission
- ECS task execution role
- ECS Express infrastructure role
- ECS cluster
- CloudWatch log group retention
- ECS Express Gateway Service
- AWS monthly budget

Terraform does not manage:

- Application source
- Docker builds
- ECR release tags
- The active container image digest
- Per-release ECS updates
- Express Mode internal ALB and target-group resources

The active image is deliberately ignored by Terraform because releases are
managed by the tag workflow.

## Directories

```text
infra/
├── bootstrap/
│   ├── main.tf
│   ├── variables.tf
│   └── versions.tf
├── production/
│   ├── budget.tf
│   ├── data.tf
│   ├── ecr.tf
│   ├── ecs.tf
│   ├── iam.tf
│   ├── import-existing.sh
│   ├── outputs.tf
│   ├── terraform.tfvars.example
│   ├── variables.tf
│   └── versions.tf
├── README.md
└── validate.sh
```

## Prerequisites

- Terraform 1.9 or newer
- AWS CLI v2
- AWS profile named `personal`
- AWS region `eu-west-1`
- Access to AWS account `778427063899`

Verify:

```bash
terraform version
aws sts get-caller-identity --profile personal
```

## Bootstrap the remote state

The bootstrap stack uses local Terraform state initially.

```bash
terraform -chdir=infra/bootstrap init
terraform -chdir=infra/bootstrap plan
terraform -chdir=infra/bootstrap apply
```

Expected bucket:

```text
radar-ferroviario-tfstate-778427063899
```

The bucket has:

- Versioning enabled
- AES-256 server-side encryption
- Public access blocked
- `prevent_destroy` protection

## Configure production

Create the local variables file:

```bash
cp \
  infra/production/terraform.tfvars.example \
  infra/production/terraform.tfvars
```

Set the budget email:

```hcl
budget_email = "your-personal-email@example.com"
```

Never commit `terraform.tfvars`.

## Initialize the production backend

```bash
terraform \
  -chdir=infra/production \
  init \
  -reconfigure
```

## Import existing AWS resources

The current infrastructure was created before Terraform and must be imported.

Do not run `terraform apply` before import.

```bash
cd infra/production
./import-existing.sh
cd ../..
```

The ECS Express Gateway Service is imported using:

```text
arn:aws:ecs:eu-west-1:778427063899:service/default/radar-ferroviario
```

## Review drift

Run:

```bash
terraform \
  -chdir=infra/production \
  plan \
  -out=tfplan
```

Review the human-readable plan:

```bash
terraform \
  -chdir=infra/production \
  show \
  tfplan
```

Required safety criteria:

```text
0 to destroy
```

Do not apply if Terraform proposes replacing:

- The ECS Express Gateway Service
- The ECR repository
- The ECS cluster
- The CloudWatch log group
- IAM production roles

Resolve drift before applying.

## Apply

Only after the plan reports zero destructive operations:

```bash
terraform \
  -chdir=infra/production \
  apply \
  tfplan
```

## Normal workflow

```bash
terraform -chdir=infra/production fmt -recursive
terraform -chdir=infra/production validate
terraform -chdir=infra/production plan
```

## Release workflow

Terraform does not change the active application image.

A production release uses:

```text
Git tag
    -> GitHub Actions
    -> Amazon ECR immutable tag
    -> ECR digest
    -> ECS Express Gateway Service update
    -> Canary deployment
    -> Automatic rollback alarm
    -> Public smoke tests
```

## Drift caused by releases

The ECS resource ignores:

```hcl
primary_container[0].image
```

This prevents Terraform from reverting a production release to the bootstrap
image.

## Disaster recovery

The current stable production baseline is:

```text
Tag:
v74.0.5

Digest:
sha256:8c7cb7ff01f265a6b28ac6227bccb82043d72c053e3cf095aee9e985aa744b1b
```

A rollback can redeploy this immutable digest through the release workflow or
the ECS Express Gateway Service update operation.

## State recovery

The state bucket uses S3 versioning. If a state file is damaged:

1. Stop all Terraform operations.
2. Inspect S3 object versions.
3. Restore the last known valid state object version.
4. Run `terraform plan`.
5. Confirm that the plan matches the actual infrastructure.

## Destruction policy

Production resources have `prevent_destroy` where accidental deletion would
cause data loss or service disruption.

Do not bypass `prevent_destroy` without:

- A reviewed maintenance plan
- A verified rollback plan
- A current ECR digest
- A state backup
- An approved outage window
