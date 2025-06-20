# 🔍 Photo Timeline 모니터링 스크립트 가이드

## 📋 개요

Photo Timeline 클러스터링 시스템을 실시간으로 모니터링하고 디버깅하기 위한 두 가지 스크립트입니다.

## 🛠️ 스크립트 종류

### 1. 🔍 `check_redis.sh` - Redis 모니터링

**용도**: Redis 키 상태와 debounce 메커니즘 실시간 추적

**핵심 기능**:

- 클러스터링 키 상태 확인 (`cluster:pending:*`, `cluster:job:*`, `cluster:count:*`)
- TTL 값과 활성 상태 실시간 표시
- 그룹별 클러스터링 상태 세부 분석
- 고아 키 자동 정리

### 2. 📊 `check_clustering.sh` - 시스템 전체 상태

**용도**: 데이터베이스, 워커, API 전체 시스템 헬스 체크

**핵심 기능**:

- 전체 시스템 건강 상태 확인
- 데이터베이스 통계 (미팅, 사진, 그룹 수)
- 워커 상태 및 작업 큐 모니터링
- 클러스터링 효율성 분석

## 🚀 빠른 시작

### 기본 사용법

```bash
# Redis 상태 한 번 확인
./scripts/check_redis.sh

# 특정 그룹 모니터링
GROUP_ID=your-group-id ./scripts/check_redis.sh

# 시스템 전체 상태 확인
./scripts/check_clustering.sh
```

### 실시간 모니터링

```bash
# Redis 실시간 감시 (2초마다 자동 새로고침)
./scripts/check_redis.sh --watch

# 대화형 모드 (명령어로 제어)
./scripts/check_redis.sh --interactive

# 클러스터링 시스템 실시간 모니터링
./scripts/check_clustering.sh --watch
```

## 📊 실제 사용 시나리오

### 🔥 **시나리오 1: 대량 업로드 모니터링**

```bash
# 터미널 1: Redis 실시간 감시
GROUP_ID=your-group-id ./scripts/check_redis.sh --watch

# 터미널 2: 업로드 테스트 실행
./test_burst_upload.sh

# 관찰 포인트:
# - pending 키 TTL 변화
# - job 키 생성/소멸
# - count 값 증가
```

**예상 동작**:

1. 업로드 시작 → `cluster:pending:group-id` 생성 (TTL: 5초)
2. 첫 업로드 → `cluster:job:group-id` 스케줄링
3. 추가 업로드 → pending TTL 연장, count 증가
4. 업로드 종료 → TTL 만료 후 클러스터링 실행
5. 완료 → 모든 키 정리

### 🔍 **시나리오 2: 시스템 헬스 체크**

```bash
# 전체 시스템 상태 확인
./scripts/check_clustering.sh --health

# 특정 그룹 상세 분석
GROUP_ID=your-group-id ./scripts/check_clustering.sh -g your-group-id
```

**확인 항목**:

- ✅ Docker 서비스 실행 상태
- ✅ 데이터베이스 연결
- ✅ Redis 연결
- ✅ API 응답
- 📊 클러스터링 효율성 (몇 % 사진이 적절히 클러스터링되었는지)

### 🧹 **시나리오 3: 문제 해결**

```bash
# 고아 키 정리
./scripts/check_redis.sh --clean

# 대화형 모드로 세밀한 분석
./scripts/check_redis.sh --interactive
# 명령어: g <group-id>, c (정리), q (종료)
```

## ⚙️ 고급 설정

### 환경 변수 커스터마이징

```bash
# Redis 설정
export REDIS_HOST=localhost
export REDIS_PORT=6379
export REDIS_DB=0

# 데이터베이스 설정
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
export POSTGRES_DB=phototimeline
export POSTGRES_USER=user
export POSTGRES_PASSWORD=password

# API 설정
export API_BASE_URL=http://localhost:3067/api/v1
export JWT_TOKEN=your-jwt-token

# 모니터링 설정
export WATCH_INTERVAL=2  # 새로고침 간격 (초)
export GROUP_ID=default-group-to-monitor
```

### Docker 환경에서 사용

```bash
# Docker 내부 Redis 접근
REDIS_HOST=localhost REDIS_PORT=6379 ./scripts/check_redis.sh

# 특정 포트로 포워딩된 경우
REDIS_PORT=16379 ./scripts/check_redis.sh
```

## 🎯 모니터링 해석 가이드

### Redis 키 상태 해석

```
Pending Keys (1):
  b94c0a4a-...: 1 (TTL: 3s)    # 업로드 진행 중, 3초 후 조용해짐

Job Keys (1):
  b94c0a4a-...: 1 (TTL: 38s)   # 클러스터링 작업 스케줄됨

Count Keys (1):
  b94c0a4a-...: 15 (no TTL)    # 15장 사진 업로드됨
```

**상태 해석**:

- ⏳ **업로드 진행 중**: Pending ✅, Job ✅
- 🔄 **클러스터링 실행 중**: Pending ❌, Job ✅
- ✅ **완료**: 모든 키 삭제됨
- ⚠️ **문제 발생**: Pending ✅, Job ❌ (작업 스케줄링 실패)

### 클러스터링 효율성 해석

```
Photos: 100 (Default: 20, Clustered: 80)
Clustering Efficiency: 80.0%
```

- **80% 효율성** = 잘 작동 중
- **20% 미만** = 설정 문제 가능성 (MEETING_GAP_HOURS 너무 작음)
- **90% 이상** = 매우 좋음

## 🛠️ 트러블슈팅

### 자주 발생하는 문제

1. **"redis-cli not found"**

   ```bash
   sudo apt install redis-tools  # Ubuntu/Debian
   sudo yum install redis        # CentOS/RHEL
   ```

2. **"Cannot connect to Redis"**

   ```bash
   # Docker Redis 포트 확인
   docker compose ps redis

   # 직접 연결 테스트
   redis-cli -h localhost -p 6379 ping
   ```

3. **"Database connection failed"**

   ```bash
   # Docker 데이터베이스 접근
   docker compose exec postgres psql -U user -d phototimeline
   ```

4. **"API not responding"**

   ```bash
   # API 엔드포인트 확인
   curl -s http://localhost:3067/health

   # Docker 서비스 상태 확인
   docker compose ps
   ```

### 고급 디버깅

```bash
# 특정 그룹의 Redis 키만 모니터링
redis-cli --scan --pattern "cluster:*:your-group-id"

# 워커 로그 실시간 확인
docker compose logs -f worker

# 데이터베이스 직접 쿼리
docker compose exec postgres psql -U user -d phototimeline -c "
  SELECT title, photo_count, created_at
  FROM meetings
  WHERE group_id = 'your-group-id'
  ORDER BY created_at DESC;
"
```

## 📈 성능 지표

### 정상 동작 기준값

- **클러스터링 효율성**: 70% 이상
- **Redis TTL**: 2-8초 범위
- **작업 처리 시간**: 5-15초 내
- **실패한 작업**: 0개

### 경고 신호

- 🔴 **고아 키 다수 발견**: 워커 크래시 가능성
- 🔴 **효율성 20% 미만**: 설정 문제
- 🔴 **TTL 60초 이상**: 무한 대기 상태
- 🔴 **실패 작업 누적**: 시스템 문제

---

## 🎉 활용 팁

1. **개발 중**: `--watch` 모드로 실시간 모니터링
2. **테스트 중**: 두 스크립트를 별도 터미널에서 동시 실행
3. **운영 중**: 주기적으로 `--health` 체크 및 로그 수집
4. **문제 해결**: `--interactive` 모드로 세밀한 분석

이 스크립트들을 통해 Photo Timeline의 클러스터링 시스템을 완전히 투명하게 모니터링할 수 있습니다! 🚀
