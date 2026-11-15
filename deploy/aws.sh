#!/usr/bin/env bash
# 서울 리전 기본 VPC에 AWS 리소스를 만든다. 처음 한 번만 실행한다.
# 리소스 ID와 IP는 secrets/aws.env에, DB 접속 정보를 포함한 서버 환경변수는 secrets/prod.env에 남긴다.
set -euo pipefail
export AWS_REGION=ap-northeast-2 MSYS_NO_PATHCONV=1
NAME=awesome-school
mkdir -p secrets

VPC=$(aws ec2 describe-vpcs --filters Name=is-default,Values=true --query 'Vpcs[0].VpcId' --output text)
MYIP=$(curl -s https://checkip.amazonaws.com)

# web 보안 그룹은 80과 443을 모두에게 열고 22는 실행한 사람의 IP에만 연다. db 보안 그룹은 web에서 오는 5432만 받는다.
WEB_SG=$(aws ec2 create-security-group --group-name $NAME-web --description "$NAME web" --vpc-id "$VPC" --query GroupId --output text)
aws ec2 authorize-security-group-ingress --group-id "$WEB_SG" --ip-permissions \
  'IpProtocol=tcp,FromPort=80,ToPort=80,IpRanges=[{CidrIp=0.0.0.0/0}]' \
  'IpProtocol=tcp,FromPort=443,ToPort=443,IpRanges=[{CidrIp=0.0.0.0/0}]' \
  "IpProtocol=tcp,FromPort=22,ToPort=22,IpRanges=[{CidrIp=$MYIP/32}]" >/dev/null
DB_SG=$(aws ec2 create-security-group --group-name $NAME-db --description "$NAME db" --vpc-id "$VPC" --query GroupId --output text)
aws ec2 authorize-security-group-ingress --group-id "$DB_SG" --protocol tcp --port 5432 --source-group "$WEB_SG" >/dev/null

# RDS PostgreSQL 17은 외부에서 접근할 수 없고 단일 AZ에 있으며 백업을 1일 보관한다.
DB_PASSWORD=$(openssl rand -hex 16)
aws rds create-db-instance --db-instance-identifier $NAME-db --engine postgres --engine-version 17 \
  --db-instance-class db.t4g.micro --allocated-storage 20 --storage-type gp3 \
  --master-username app --master-user-password "$DB_PASSWORD" --db-name awesome_school \
  --vpc-security-group-ids "$DB_SG" --no-publicly-accessible --backup-retention-period 1 >/dev/null

# EC2는 Ubuntu 24.04 arm64 t4g.small이고 Elastic IP로 주소를 고정한다.
aws ec2 create-key-pair --key-name $NAME --query KeyMaterial --output text > secrets/$NAME.pem
chmod 600 secrets/$NAME.pem
AMI=$(aws ssm get-parameter --name /aws/service/canonical/ubuntu/server/24.04/stable/current/arm64/hvm/ebs-gp3/ami-id --query Parameter.Value --output text)
INSTANCE=$(aws ec2 run-instances --image-id "$AMI" --instance-type t4g.small --key-name $NAME \
  --security-group-ids "$WEB_SG" --user-data file://deploy/user-data.sh \
  --block-device-mappings 'DeviceName=/dev/sda1,Ebs={VolumeSize=20,VolumeType=gp3}' \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$NAME}]" \
  --query 'Instances[0].InstanceId' --output text)
aws ec2 wait instance-running --instance-ids "$INSTANCE"
ALLOC=$(aws ec2 allocate-address --query AllocationId --output text)
aws ec2 associate-address --instance-id "$INSTANCE" --allocation-id "$ALLOC" >/dev/null
IP=$(aws ec2 describe-addresses --allocation-ids "$ALLOC" --query 'Addresses[0].PublicIp' --output text)
DOMAIN=${IP//./-}.sslip.io

echo "RDS 생성 대기 (10분 안팎)..."
aws rds wait db-instance-available --db-instance-identifier $NAME-db
DB_HOST=$(aws rds describe-db-instances --db-instance-identifier $NAME-db --query 'DBInstances[0].Endpoint.Address' --output text)

cat > secrets/aws.env <<OUT
INSTANCE=$INSTANCE
ALLOC=$ALLOC
WEB_SG=$WEB_SG
DB_SG=$DB_SG
IP=$IP
OUT
cat > secrets/prod.env <<OUT
DOMAIN=$DOMAIN
DJANGO_DEBUG=0
DJANGO_SECRET_KEY=$(openssl rand -hex 32)
DJANGO_ALLOWED_HOSTS=$DOMAIN
DJANGO_CSRF_TRUSTED_ORIGINS=https://$DOMAIN
DB_HOST=$DB_HOST
DB_NAME=awesome_school
DB_USER=app
DB_PASSWORD=$DB_PASSWORD
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
GOOGLE_SERVICE_ACCOUNT_FILE=/app/secrets/google.json
GOOGLE_SHEET_ID=
OUT
echo "완료: https://$DOMAIN"
