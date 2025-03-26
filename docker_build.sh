#!/bin/bash

# AWS docs: https://docs.aws.amazon.com/lambda/latest/dg/python-image.html

# Call with container name as argument, e.g.: docker_build.sh kol-exchange-upload
[ "$#" -eq 1 ] || exit 1

# Build and tag the Docker image
docker buildx build --platform linux/amd64 --provenance=false -t $1:latest $1
docker tag $1:latest $KOL_ECR/$1/repo:latest

# Deploy to ECR
aws ecr get-login-password --region $AWS_DEFAULT_REGION \
  | docker login --username AWS --password-stdin $KOL_ECR
docker push $KOL_ECR/$1/repo:latest

# Update Lambda function code
aws lambda update-function-code \
  --function-name $1 \
  --image-uri $KOL_ECR/$1/repo:latest \
  --publish

# Invoke the function once to test
#aws lambda invoke --function-name $1 response.json
