#!/usr/bin/env bash
# Run ON the EC2 instance (Amazon Linux 2023) from the project folder:
#   cd ~/protein-prediction-cloud && bash deploy/setup_ec2.sh
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> Installing system packages"
sudo dnf install -y python3.11 python3.11-pip

echo "==> Creating Python virtual environment"
cd backend
python3.11 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

if [ ! -f .env ]; then
  cp .env.example .env
  echo "==> Created backend/.env from the example. EDIT IT NOW: nano backend/.env"
  echo "    Set S3_BUCKET_NAME, AWS_REGION and CORS_ORIGINS. Do NOT add access keys."
fi

echo "==> Checking the IAM role (should print an 'assumed-role' ARN)"
aws sts get-caller-identity || echo "!! No IAM role credentials found. Attach ProteinAppEC2Role to this instance."

echo "==> Done. Next: sudo cp ../deploy/protein-api.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable --now protein-api"
