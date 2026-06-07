#!/bin/bash
set -e

REGION="ca-central-1"
INGESTION_FUNCTION="jobhunter-ingestion"
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
  httpx supabase pandas

pip install \
  --target lambdas/layer/python \
  --no-deps \
  "jobhive-py @ git+https://github.com/kalil0321/ats-scrapers.git"

cd lambdas/layer
zip -r ../layer.zip python/
cd ../..
echo "Layer built: lambdas/layer.zip"

echo "Publishing Lambda layer..."
LAYER_ARN=$(aws lambda publish-layer-version \
  --layer-name $LAYER_NAME \
  --zip-file fileb://lambdas/layer.zip \
  --compatible-runtimes python3.14 \
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
  --no-cli-pager
aws lambda update-function-configuration \
  --function-name $INGESTION_FUNCTION \
  --handler handler.lambda_handler \
  --layers "$LAYER_ARN" \
  --region $REGION \
  --no-cli-pager
echo "Ingestion deployed."

echo "Deploying scoring Lambda..."
cd lambdas/scoring
zip -r ../scoring.zip handler.py
cd ../..
aws lambda update-function-code \
  --function-name $SCORING_FUNCTION \
  --zip-file fileb://lambdas/scoring.zip \
  --region $REGION \
  --no-cli-pager
aws lambda update-function-configuration \
  --function-name $SCORING_FUNCTION \
  --handler handler.lambda_handler \
  --layers "$LAYER_ARN" \
  --region $REGION \
  --no-cli-pager
echo "Scoring deployed."

echo "Done."
