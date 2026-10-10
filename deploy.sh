#!/usr/bin/env bash
# usage: ./deploy.sh <function-name> <dist/zip> <s3-bucket>   (needs an existing Lambda execution role ARN in $ROLE_ARN)
set -e
F=$1; Z=$2; B=$3
aws s3 cp $Z s3://$B/$(basename $Z)
if aws lambda get-function --function-name $F >/dev/null 2>&1; then
  aws lambda update-function-code --function-name $F --s3-bucket $B --s3-key $(basename $Z) >/dev/null
else
  aws lambda create-function --function-name $F --runtime python3.12 --handler handler.handler \
    --role $ROLE_ARN --memory-size 512 --timeout 30 --code S3Bucket=$B,S3Key=$(basename $Z) >/dev/null
fi
aws lambda wait function-updated --function-name $F && echo "deployed $F"
