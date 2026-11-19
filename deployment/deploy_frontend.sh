#!/usr/bin/env bash
# deploy_frontend.sh - upload the built React app to S3 and refresh CloudFront. Run on YOUR computer.
#   BUCKET=my-absenteeism-site DISTRIBUTION_ID=E123ABC456 bash deployment/deploy_frontend.sh
# Needs the AWS CLI configured with `aws configure` (credentials stay on your machine; nothing is stored in this repo).
set -euo pipefail
: "${BUCKET:?Set BUCKET to your S3 bucket name}"
: "${DISTRIBUTION_ID:?Set DISTRIBUTION_ID to your CloudFront distribution ID}"
DIST="$(cd "$(dirname "${BASH_SOURCE[0]}")/../frontend" && pwd)/dist"
[ -f "$DIST/index.html" ] || { echo "Build first: (cd frontend && npm ci && npm run build)"; exit 1; }
# Hashed assets can be cached for a year; index.html must always be revalidated.
aws s3 sync "$DIST" "s3://$BUCKET" --delete --exclude index.html --cache-control "public,max-age=31536000,immutable"
aws s3 cp "$DIST/index.html" "s3://$BUCKET/index.html" --cache-control "no-cache" --content-type "text/html"
aws cloudfront create-invalidation --distribution-id "$DISTRIBUTION_ID" --paths "/index.html" >/dev/null
echo "Frontend deployed."
