#!/bin/bash
set -e

REGION="ca-central-1"
INGESTION_FUNCTION="jobhunter-ingestion"
SCORING_FUNCTION="jobhunter-scoring"

echo "Building Lambda layer..."
pip install \
  --platform manylinux2014_aarch64 \
  --only-binary=:all: \
  --target lambdas/layer/python \
  httpx supabase jobhive rapidfuzz

cd lambdas/layer
zip -r ../layer.zip python/
cd ../..
echo "Layer built: lambdas/layer.zip"

echo "Deploying ingestion Lambda..."
cd lambdas/ingestion
zip -r ../ingestion.zip handler.py
cd ../..
aws lambda update-function-code \
  --function-name $INGESTION_FUNCTION \
  --zip-file fileb://lambdas/ingestion.zip \
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
echo "Scoring deployed."

echo "Done."
