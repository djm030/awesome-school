# AWS 배포 구성

## 지금 구성 (과제 데모)

서울 리전(`ap-northeast-2`) 기본 VPC에 EC2 한 대와 RDS 한 대를 둡니다. 도메인은 사지 않았습니다. Elastic IP를 이름에 담는 무료 와일드카드 DNS(`3-35-123-81.sslip.io`)를 씁니다. Caddy가 Let's Encrypt 인증서를 자동으로 받습니다.

```mermaid
flowchart LR
  user[신청자·관리자 브라우저] -- HTTPS 443 --> caddy
  subgraph EC2 t4g.small · Ubuntu 24.04 arm64 · Elastic IP
    caddy[Caddy<br/>HTTPS 종료, 인증서 자동 갱신] --> web[Django + gunicorn<br/>WhiteNoise 정적 파일]
    caddy -. /media/ .-> media[(Docker 볼륨 media<br/>업로드 이미지)]
    web --> media
    cron[cron<br/>1분마다 send_mails<br/>매일 08:00 export_sheets] -. docker compose exec .-> web
  end
  web -- 5432 --> rds[(RDS PostgreSQL 17<br/>db.t4g.micro, 외부 비공개)]
  web -- SMTP 587 --> gmail[Gmail SMTP]
  web -- HTTPS --> sheets[Google Sheets API]
```

| 리소스 | 사양 | 이유 |
|---|---|---|
| EC2 | t4g.small(2 vCPU, 2GB), gp3 20GB, 스왑 2GB | 컨테이너 2개를 돌리고 서버에서 이미지를 빌드하기에 충분한 최소 사양. Graviton이라 같은 사양의 x86보다 쌈 |
| Elastic IP | 1개 | 인스턴스를 재시작해도 주소와 sslip.io 도메인이 바뀌지 않게 함 |
| RDS PostgreSQL 17 | db.t4g.micro, gp3 20GB, 단일 AZ, 백업 1일, 외부 비공개 | DB를 서버와 분리해 EC2를 다시 만들어도 데이터가 남음. 데모라 Multi-AZ는 뺌 |
| 보안 그룹 `awesome-school-web` | 80과 443은 모두에게, 22는 생성한 사람의 IP에만 엶 | SSH 노출을 줄임 |
| 보안 그룹 `awesome-school-db` | web 보안 그룹에서 오는 5432만 받음 | 인터넷에서 DB에 닿지 않음 |

### 예상 비용 (온디맨드, 프리 티어 미적용 추정)

| 항목 | 월 |
|---|---|
| EC2 t4g.small | 약 $15 |
| EBS gp3 20GB | 약 $2 |
| RDS db.t4g.micro와 스토리지 20GB | 약 $21 |
| 퍼블릭 IPv4 (Elastic IP) | 약 $4 |
| 합계 | 약 $42 |

서울 리전 시간당 단가로 계산한 근삿값입니다. 정확한 금액은 [AWS Pricing Calculator](https://calculator.aws/)로 확인합니다. 면접이 끝나면 `deploy/teardown.sh`로 모두 삭제합니다.

## 생성, 배포, 삭제

| 스크립트 | 하는 일 |
|---|---|
| `deploy/aws.sh` | 보안 그룹, RDS, 키 페어, EC2(user-data로 Docker 설치), Elastic IP를 만든다. 리소스 ID는 `secrets/aws.env`에, 서버 환경변수는 `secrets/prod.env`에 남긴다. DB 비밀번호와 `SECRET_KEY`는 무작위로 만든다. 처음 한 번만 실행한다. |
| `deploy/deploy.sh [--seed]` | git이 추적하는 파일을 서버로 복사하고 `.env`를 올린다. 그다음 `docker compose up -d --build`, 마이그레이션, crontab 등록을 한다. `--seed`를 붙이면 교육 시드 데이터와 이미지도 넣는다. |
| `deploy/teardown.sh` | EC2, Elastic IP, RDS(스냅샷 없이), 보안 그룹, 키 페어를 삭제한다. |

관리자가 올린 교육 이미지는 Docker 볼륨 `media`에 저장합니다. Caddy가 `/media/` 요청을 Django를 거치지 않고 바로 서빙합니다. 비밀값(`secrets/`, `.env`)은 git에 올리지 않고 `scp`로만 서버에 보냅니다. 컨테이너는 `restart: unless-stopped`라서 서버를 재부팅하면 다시 뜹니다.

## 운영 서비스로 키운다면

지금 구성은 EC2 한 대가 멈추면 서비스 전체가 멈춥니다. 실제로 운영한다면 아래 표 순서로 바꿉니다.

| 지금 | 운영 | 바꾸는 이유 |
|---|---|---|
| EC2 한 대와 docker compose | ECR 이미지로 띄운 ECS Fargate 서비스 2개 이상과 ALB | 무중단 배포, 인스턴스 장애 자동 복구, 서버 패치 불필요 |
| Caddy와 sslip.io | Route 53 도메인과 ALB에 연결한 ACM 인증서 | 실제 도메인을 쓰고 인증서 관리를 AWS에 맡김 |
| 서버 cron | EventBridge Scheduler가 ECS 단발 태스크(`send_mails`, `export_sheets`)를 실행 | 웹 서버 수와 상관없이 작업이 정확히 한 번 돎. 웹 서버를 늘려도 메일이 중복으로 나가지 않음 |
| Gmail SMTP | Amazon SES (도메인 인증, 샌드박스 해제) | 발송량 한도, 도달률, 반송 처리. 코드는 그대로 두고 `EMAIL_HOST`만 바꿈 |
| RDS 단일 AZ, 백업 1일 | RDS Multi-AZ, 백업 7일 이상, 삭제 보호 | DB 장애 조치와 실수 복구 |
| `.env` 파일 | Secrets Manager나 SSM Parameter Store 값을 ECS 태스크 환경변수로 주입 | 비밀값 교체와 접근 기록 |
| 업로드 이미지를 EC2의 Docker 볼륨에 저장 | S3와 CloudFront (`django-storages`) | 서버를 다시 만들어도 이미지가 남고 CDN이 캐시함 |
| 컨테이너 로그 | CloudWatch Logs, 메일 발송 실패와 5xx 알람 | 장애를 바로 알아챔 |
| 수동 `deploy.sh` | GitHub Actions에서 테스트, ECR 푸시, ECS 배포를 차례로 실행 | 배포 실수 방지 |

`send_mails`는 DB에서 발송할 때가 된 메일을 찾아 보내고 발송 시각을 기록합니다. 그래서 스케줄러를 cron에서 EventBridge로 바꿔도 애플리케이션 코드는 그대로입니다. 다만 여러 태스크가 동시에 돌 수 있게 되면 `select_for_update(skip_locked=True)`로 행을 잠가야 합니다. 지금은 `flock`이 서버 한 대 안의 중복 실행만 막습니다.
