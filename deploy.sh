#!/bin/bash
set -e

REGION="ca-central-1"
INGESTION_FUNCTION="jobhunter-ingestion"
ORCHESTRATOR_FUNCTION="jobhunter-orchestrator"
SCORING_FUNCTION="jobhunter-scoring"
LAYER_NAME="jobhunter-deps"

echo "Building Lambda layer..."
rm -rf lambdas/layer
pip install \
  --platform manylinux2014_x86_64 \
  --implementation cp \
  --python-version 3.12 \
  --only-binary=:all: \
  --target lambdas/layer/python \
  httpx supabase pandas beautifulsoup4

pip install \
  --target lambdas/layer/python \
  --no-deps \
  "jobhive-py @ git+https://github.com/kalil0321/ats-scrapers.git@d825caefc8e97c3533efe1707b4daddfeed58706"

# Strip bytecode caches and bundled test suites — pandas/numpy tests alone are
# tens of MB and push the zip past Lambda's 70MB direct-upload limit.
find lambdas/layer/python -type d -name "__pycache__" -prune -exec rm -rf {} +
rm -rf lambdas/layer/python/pandas/tests \
       lambdas/layer/python/numpy/tests \
       lambdas/layer/python/numpy/_core/tests \
       lambdas/layer/python/numpy/*/tests

cd lambdas/layer
zip -rq ../layer.zip python/
cd ../..
echo "Layer built: lambdas/layer.zip ($(du -h lambdas/layer.zip | cut -f1))"

# Publish via S3: the zip exceeds the ~52MB effective direct-upload limit
# (the API base64-encodes the payload against a 70MB request cap).
DEPLOY_BUCKET="jobhunter-deploy-ca"
echo "Uploading layer to s3://$DEPLOY_BUCKET/layer.zip..."
aws s3 cp lambdas/layer.zip "s3://$DEPLOY_BUCKET/layer.zip" --region $REGION --no-cli-pager

echo "Publishing Lambda layer..."
LAYER_ARN=$(aws lambda publish-layer-version \
  --layer-name $LAYER_NAME \
  --content S3Bucket=$DEPLOY_BUCKET,S3Key=layer.zip \
  --compatible-runtimes python3.12 \
  --region $REGION \
  --query 'LayerVersionArn' \
  --output text \
  --no-cli-pager)
echo "Layer published: $LAYER_ARN"

echo "Deploying ingestion Lambda..."
cd lambdas/ingestion
zip -r ../ingestion.zip handler.py location_filter.py data/
cd ../..
aws lambda update-function-code \
  --function-name $INGESTION_FUNCTION \
  --zip-file fileb://lambdas/ingestion.zip \
  --region $REGION \
  --query '{FunctionName:FunctionName,LastUpdateStatus:LastUpdateStatus}' \
  --no-cli-pager
aws lambda wait function-updated \
  --function-name $INGESTION_FUNCTION \
  --region $REGION
aws lambda update-function-configuration \
  --function-name $INGESTION_FUNCTION \
  --handler handler.lambda_handler \
  --layers "$LAYER_ARN" \
  --region $REGION \
  --query '{FunctionName:FunctionName,LastUpdateStatus:LastUpdateStatus}' \
  --no-cli-pager
echo "Ingestion deployed."

echo "Deploying orchestrator Lambda..."
cd lambdas/ingestion
zip -r ../orchestrator.zip orchestrator.py data/
cd ../..
aws lambda update-function-code \
  --function-name $ORCHESTRATOR_FUNCTION \
  --zip-file fileb://lambdas/orchestrator.zip \
  --region $REGION \
  --query '{FunctionName:FunctionName,LastUpdateStatus:LastUpdateStatus}' \
  --no-cli-pager
aws lambda wait function-updated \
  --function-name $ORCHESTRATOR_FUNCTION \
  --region $REGION
# Max Lambda timeout (900s) — the orchestrator self-chains in ~15-minute
# waves to stay under the account's Lambda concurrency ceiling, and each
# wave's own sleep-then-self-invoke needs the full budget.
aws lambda update-function-configuration \
  --function-name $ORCHESTRATOR_FUNCTION \
  --handler orchestrator.lambda_handler \
  --timeout 900 \
  --region $REGION \
  --query '{FunctionName:FunctionName,LastUpdateStatus:LastUpdateStatus}' \
  --no-cli-pager
echo "Orchestrator deployed."

echo "Deploying scoring Lambda..."
cd lambdas/scoring
zip -r ../scoring.zip handler.py
cd ../..
aws lambda update-function-code \
  --function-name $SCORING_FUNCTION \
  --zip-file fileb://lambdas/scoring.zip \
  --region $REGION \
  --query '{FunctionName:FunctionName,LastUpdateStatus:LastUpdateStatus}' \
  --no-cli-pager
aws lambda wait function-updated \
  --function-name $SCORING_FUNCTION \
  --region $REGION
aws lambda update-function-configuration \
  --function-name $SCORING_FUNCTION \
  --handler handler.lambda_handler \
  --layers "$LAYER_ARN" \
  --region $REGION \
  --query '{FunctionName:FunctionName,LastUpdateStatus:LastUpdateStatus}' \
  --no-cli-pager
echo "Scoring deployed."

echo "Done."
