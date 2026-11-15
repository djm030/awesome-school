#!/bin/bash
# Runs on the first EC2 boot. Installs Docker and Compose and adds 2 GB of swap for image builds.
set -e
apt-get update
apt-get install -y docker.io docker-compose-v2 docker-buildx
usermod -aG docker ubuntu
fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
