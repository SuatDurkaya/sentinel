#!/bin/bash
set -e

echo "Building checker..."
docker build -f Dockerfile.checker -t sentinel-checker:local .

echo "Building api..."
docker build -f Dockerfile.api -t sentinel-api:local .

echo "Building notifier..."
docker build -f Dockerfile.notifier -t sentinel-notifier:local .

echo "Loading images into kind..."
kind load docker-image sentinel-checker:local
kind load docker-image sentinel-api:local
kind load docker-image sentinel-notifier:local

echo "Restarting deployments..."
kubectl rollout restart deployment sentinel-checker sentinel-api sentinel-notifier

echo "Done!"