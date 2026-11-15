# AWS 배포 구성

## 지금 구성 (과제 데모)

서울 리전(`ap-northeast-2`) 기본 VPC에 EC2 한 대와 RDS 한 대를 둡니다. 도메인은 사지 않고 Elastic IP를 이름에 담는 무료 와일드카드 DNS(`3-35-123-81.sslip.io`)를 쓰며, Caddy가 Let's Encrypt 인증서를 자동으로 받습니다.

```mermaid
flowchart LR
  user[신청자·관리자 브라우저] -- HTTPS 443 --> caddy
  subgraph EC2 t4g.small · Ubuntu 24.04 arm64 · Elastic IP
    caddy[Caddy<br/>HTTPS 종료·인증서 자동 갱신] --> web[Django + gunicorn<br/>WhiteNoise 정적 파일]
    cron[cron<br/>1분마다 send_mails<br/>매일 08:00 export_sheets] -. docker compose exec .-> web
  end
  web -- 5432 --> rds[(RDS PostgreSQL 17<br/>db.t4g.micro · 비공개)]
  web -- SMTP 587 --> gmail[Gmail SMTP]
  web -- HTTPS --> sheets[Google Sheets API]
```

| 리소스 | 사양 | 이유 |
|---|---|---|
| EC2 | t4g.small (2 vCPU, 2GB), gp3 20GB, 스왑 2GB | 컨테이너 2개와 서버 안에서의 이미지 빌드에 충분한 최소 사양. Graviton이라 같은 사양 x86보다 저렴 |
| Elastic IP | 1개 | 인스턴스를 재시작해도 주소·도메인(sslip.io)이 바뀌지 않게 |
| RDS PostgreSQL 17 | db.t4g.micro, gp3 20GB, 단일 AZ, 백업 1일, 외부 비공개 | DB를 서버와 분리해 EC2를 다시 만들어도 데이터가 남게. 데모라 Multi-AZ는 생략 |
| 보안 그룹 `awesome-school-web` | 80·443 전체 허용, 22는 생성한 사람의 IP만 | SSH 노출 최소화 |
| 보안 그룹 `awesome-school-db` | 5432를 web 보안 그룹에서만 허용 | DB는 인터넷에서 닿지 않음 |

### 예상 비용 (온디맨드, 프리 티어 미적용 추정)

| 항목 | 월 |
|---|---|
| EC2 t4g.small | 약 $15 |
| EBS gp3 20GB | 약 $2 |
| RDS db.t4g.micro + 스토리지 20GB | 약 $21 |
| 퍼블릭 IPv4 (Elastic IP) | 약 $4 |
| **합계** | **약 $42** |

서울 리전 시간당 단가로 계산한 근삿값입니다. 정확한 금액은 [AWS Pricing Calculator](https://calculator.aws/)로 확인합니다. 면접이 끝나면 `deploy/teardown.sh`로 모두 삭제합니다.

## 생성·배포·삭제

| 스크립트 | 하는 일 |
|---|---|
| `deploy/aws.sh` | 보안 그룹, RDS, 키 페어, EC2(user-data로 Docker 설치), Elastic IP를 만들고 `secrets/aws.env`(리소스 ID)와 `secrets/prod.env`(서버 환경변수, DB 비밀번호·SECRET_KEY 무작위 생성)를 남깁니다. 처음 한 번만 실행합니다. |
| `deploy/deploy.sh [--seed]` | git이 추적하는 파일을 서버로 복사하고 `.env`를 올린 뒤 `docker compose up -d --build`, 마이그레이션, crontab 등록. `--seed`는 교육 시드 데이터를 넣습니다. |
| `deploy/teardown.sh` | EC2, Elastic IP, RDS(스냅샷 없이), 보안 그룹, 키 페어를 삭제합니다. |

비밀값(`secrets/`, `.env`)은 git에 올리지 않고 `scp`로만 서버에 전달합니다. 서버에서 컨테이너는 `restart: unless-stopped`라 재부팅 후 자동으로 다시 뜹니다.

## 운영 서비스로 키운다면

데모 구성은 "한 대가 죽으면 서비스가 멈춘다"는 한계가 있습니다. 실제 운영에서는 다음 순서로 바꿉니다.

| 지금 | 운영 | 바꾸는 이유 |
|---|---|---|
| EC2 한 대 + docker compose | ECR 이미지 → **ECS Fargate** 서비스 2개 이상 + **ALB** | 무중단 배포, 인스턴스 장애 자동 복구, 서버 패치 불필요 |
| Caddy + sslip.io | **Route 53** 도메인 + **ACM** 인증서(ALB에 연결) | 실제 도메인, 인증서 관리 자동화 |
| 서버 cron | **EventBridge Scheduler** → ECS 단발 태스크(`send_mails`, `export_sheets`) | 웹 서버 수와 무관하게 정확히 한 번 실행. 웹을 여러 대로 늘려도 메일이 중복 발송되지 않음 |
| Gmail SMTP | **Amazon SES** (도메인 인증, 샌드박스 해제) | 발송량 한도·도달률·반송 처리. 코드 변경 없이 `EMAIL_HOST`만 교체 |
| RDS 단일 AZ, 백업 1일 | RDS **Multi-AZ**, 백업 7일 이상, 삭제 보호 | DB 장애 조치, 실수 복구 |
| `.env` 파일 | **Secrets Manager** / SSM Parameter Store → ECS 태스크 환경변수 | 비밀값 회전·접근 기록 |
| WhiteNoise, 정적 이미지 경로 | **S3 + CloudFront** (`django-storages`) | 관리자가 교육 이미지를 업로드, 캐시 |
| 컨테이너 로그 | **CloudWatch Logs** + 메일 발송 실패·5xx 알람 | 장애 인지 |
| 수동 `deploy.sh` | **GitHub Actions**: 테스트 → ECR 푸시 → ECS 배포 | 배포 실수 방지 |

메일 발송을 "DB에서 보낼 차례인 메일을 찾아 보내고 발송 시각을 기록"하는 방식으로 만든 덕분에, 스케줄러를 cron에서 EventBridge로 바꿔도 애플리케이션 코드는 그대로입니다. 다만 여러 태스크가 동시에 돌 수 있게 되면 `select_for_update(skip_locked=True)`로 행 잠금을 추가해야 합니다(지금은 `flock`이 한 서버 안의 중복 실행만 막습니다).
