#!/usr/bin/env bash
# aws.sh로 만든 리소스를 모두 삭제한다. DB 스냅샷을 남기지 않으므로 되돌릴 수 없다.
set -euo pipefail
export AWS_REGION=ap-northeast-2
source secrets/aws.env
NAME=awesome-school
aws ec2 terminate-instances --instance-ids "$INSTANCE" >/dev/null
aws rds delete-db-instance --db-instance-identifier $NAME-db --skip-final-snapshot --delete-automated-backups >/dev/null
aws ec2 wait instance-terminated --instance-ids "$INSTANCE"
aws ec2 release-address --allocation-id "$ALLOC"
aws rds wait db-instance-deleted --db-instance-identifier $NAME-db
aws ec2 delete-security-group --group-id "$DB_SG"
aws ec2 delete-security-group --group-id "$WEB_SG"
aws ec2 delete-key-pair --key-name $NAME
echo "삭제 완료"
