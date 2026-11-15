#!/bin/bash
# EC2 first boot: install Docker + Compose, add 2GB swap for builds
set -e
apt-get update
apt-get install -y docker.io docker-compose-v2 docker-buildx
usermod -aG docker ubuntu
fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
