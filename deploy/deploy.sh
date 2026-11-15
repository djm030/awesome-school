#!/usr/bin/env bash
# .gitignore 대상을 뺀 작업 트리를 서버에 복사한 뒤 이미지를 다시 빌드하고 마이그레이션한다.
# 처음 배포할 때는 --seed를 붙여 교육 시드 데이터도 넣는다.
set -euo pipefail
source secrets/aws.env
KEY=secrets/awesome-school.pem
SSH="ssh -i $KEY -o StrictHostKeyChecking=accept-new ubuntu@$IP"

git ls-files -co --exclude-standard | tar -czf - -T - | $SSH "mkdir -p app/secrets && tar -xzf - -C app"
scp -i $KEY secrets/prod.env ubuntu@$IP:app/.env
[ -f secrets/google.json ] && scp -i $KEY secrets/google.json ubuntu@$IP:app/secrets/google.json
$SSH "cd app && docker compose up -d --build web caddy && docker compose exec -T web python manage.py migrate --noinput"
[ "${1:-}" = "--seed" ] && $SSH "cd app && docker compose exec -T web python manage.py loaddata ai_hero"
$SSH "crontab app/deploy/crontab"
echo "배포 완료"
