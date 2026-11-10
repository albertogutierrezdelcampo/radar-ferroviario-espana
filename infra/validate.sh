#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(
  cd "$(dirname "${BASH_SOURCE[0]}")/.." &&
  pwd
)"

echo "Repository: $ROOT_DIR"

terraform \
  -chdir="$ROOT_DIR/infra/bootstrap" \
  fmt \
  -check \
  -recursive

terraform \
  -chdir="$ROOT_DIR/infra/production" \
  fmt \
  -check \
  -recursive

terraform \
  -chdir="$ROOT_DIR/infra/bootstrap" \
  init \
  -backend=false

terraform \
  -chdir="$ROOT_DIR/infra/bootstrap" \
  validate

terraform \
  -chdir="$ROOT_DIR/infra/production" \
  init \
  -backend=false

terraform \
  -chdir="$ROOT_DIR/infra/production" \
  validate

echo "Terraform validation completed successfully."
