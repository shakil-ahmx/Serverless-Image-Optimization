#!/bin/bash
set -e

echo "🗑️  Destroying Image Processor Application..."

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"

if ! command -v terraform &> /dev/null; then
    echo "❌ Terraform is not installed."
    exit 1
fi

cd "$PROJECT_DIR/terraform"

# Buckets use force_destroy = true, so Terraform empties them (all versions) itself.
terraform destroy -auto-approve

echo "✅ All resources destroyed successfully!"
