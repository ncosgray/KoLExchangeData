#!/bin/bash

# AWS docs: https://docs.aws.amazon.com/lambda/latest/dg/python-image.html

# Build and tag the Docker image
docker buildx build --platform linux/amd64 --provenance=false -t kol-exchange-upload:latest ../kol-exchange-upload
docker tag kol-exchange-upload:latest $KOL_ECR_REPO:latest

# Deploy to ECR
aws ecr get-login-password --region $AWS_DEFAULT_REGION | docker login --username AWS --password-stdin $KOL_ECR
docker push $KOL_ECR_REPO:latest

# Update Lambda function code
aws lambda update-function-code \
  --function-name kol-exchange-get-data \
  --image-uri $KOL_ECR_REPO:latest \
  --publish

# Invoke the function once to test
#aws lambda invoke --function-name kol-exchange-get-data response.json
