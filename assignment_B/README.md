# 누리장터 입찰공고 크롤러 (Bid Crawler)

동적으로 렌더링되는 나라장터(G2B) 입찰공고 페이지에서 목록 및 상세 정보를 수집하여 표준 스키마로 저장하는 크롤러입니다.

## 주요 기능

- **동적 웹페이지 크롤링**: Playwright 기반 브라우저 자동화
- **목록/상세 페이지 자동 탐색**: 목록에서 상세 페이지로 자동 이동하여 모든 필드 추출
- **중단점 저장 및 재시작**: 오류 발생 시 마지막 지점부터 이어서 수집
- **중복 방지**: 이미 수집된 공고 자동 스킵
- **재시도 로직**: 지수 백오프를 적용한 안정적인 재시도
- **스케줄링**: interval/cron 모드로 정기 실행 지원
- **다중 출력 형식**: JSON, CSV 동시 지원

## 프로젝트 구조

```
assignment_B/
├── src/bid_crawler/           # 소스 코드
│   ├── __init__.py           # 패키지 초기화
│   ├── __main__.py           # 모듈 실행 진입점
│   ├── main.py               # CLI 진입점
│   ├── config.py             # 설정 관리
│   ├── crawler.py            # 메인 크롤러 오케스트레이터
│   │
│   ├── models/               # 데이터 모델 (Pydantic)
│   │   ├── bid_notice.py     # 입찰공고 모델
│   │   └── crawl_state.py    # 크롤링 상태 모델
│   │
│   ├── scrapers/             # 스크래퍼 모듈
│   │   ├── base.py           # 기본 스크래퍼 (추상)
│   │   ├── list_scraper.py   # 목록 페이지 스크래퍼
│   │   └── detail_scraper.py # 상세 페이지 스크래퍼
│   │
│   ├── storage/              # 저장소 모듈
│   │   ├── state_manager.py  # 상태 관리 (재시작 지원)
│   │   ├── json_storage.py   # JSON 저장소
│   │   └── csv_storage.py    # CSV 저장소
│   │
│   ├── scheduler/            # 스케줄러 모듈
│   │   └── cron.py           # interval/cron 스케줄러
│   │
│   └── utils/                # 유틸리티
│       ├── browser.py        # 브라우저 관리
│       ├── retry.py          # 재시도 로직
│       └── logger.py         # 로깅
│
├── tests/                    # 테스트 코드
│   ├── conftest.py           # pytest 설정
│   ├── unit/                 # 단위 테스트
│   └── integration/          # 통합 테스트
│
├── docs/                     # 문서
│   └── DESIGN.md             # 설계 문서
│
├── data/                     # 수집 데이터 (gitignore)
├── logs/                     # 로그 파일 (gitignore)
├── requirements.txt          # 의존성
├── setup.py                  # 패키지 설정
└── README.md                 # 이 문서
```

## 설치

### 1. 의존성 설치

```bash
cd assignment_B
pip install -r requirements.txt
```

### 2. Playwright 브라우저 설치

```bash
playwright install chromium
```

### 3. 패키지 설치 (개발 모드)

```bash
pip install -e .
```

## 사용법

### 기본 크롤링

```bash
# CLI로 실행
bid-crawler crawl

# 또는 모듈로 실행
python -m bid_crawler crawl
```

### 옵션

```bash
# 최대 5페이지, 50개 항목만 수집
bid-crawler crawl --max-pages 5 --max-items 50

# 브라우저 창 표시 (디버깅용)
bid-crawler crawl --no-headless

# JSON + CSV 동시 출력
bid-crawler crawl --format both

# 키워드 검색
bid-crawler crawl --keyword "IT서비스"

# 새로 시작 (이전 상태 무시)
bid-crawler crawl --no-resume
```

### 스케줄 실행

```bash
# 1시간 간격으로 실행
bid-crawler schedule --mode interval --interval 60

# cron 표현식으로 실행 (매일 9시, 15시, 21시)
bid-crawler schedule --mode cron --cron "0 9,15,21 * * *"
```

### 상태 확인

```bash
# 현재 크롤링 상태 확인
bid-crawler status

# 상태 초기화
bid-crawler reset
```

## Python API

```python
import asyncio
from bid_crawler import BidCrawler, CrawlerConfig

async def main():
    # 설정 생성
    config = CrawlerConfig(
        max_pages=10,
        max_items=100,
    )

    # 크롤러 생성 및 실행
    crawler = BidCrawler(config)

    # 콜백 등록 (선택)
    crawler.on_item_collected(lambda item: print(f"수집: {item.title}"))

    # 크롤링 실행
    state = await crawler.run(resume=True)

    print(f"수집 완료: {state.statistics.total_collected}건")

asyncio.run(main())
```

## 출력 형식

### JSON

```json
{
  "bid_notice_id": "20240115-001",
  "title": "IT 장비 구매 입찰",
  "bid_type": "물품",
  "status": "공고중",
  "organization": "조달청",
  "deadline": "2024-01-31T17:00:00",
  "estimated_price": 100000000,
  "bid_method": "일반경쟁입찰",
  "contact_person": "홍길동",
  "contact_phone": "02-1234-5678",
  "crawled_at": "2024-01-15T10:30:00"
}
```

### CSV

| 공고번호 | 공고명 | 입찰유형 | 상태 | 공고기관 | 마감일시 | 추정가격 |
|---------|--------|---------|------|---------|---------|---------|
| 20240115-001 | IT 장비 구매 입찰 | 물품 | 공고중 | 조달청 | 2024-01-31 17:00 | 100000000 |

## 핵심 설계

### 1. 중단점 저장 및 재시작

```
상태 파일 (crawl_state.json):
- 현재 페이지/인덱스
- 수집된 공고 ID 목록
- 통계 정보

오류 발생 시:
1. 상태 자동 저장
2. 재실행 시 상태 로드
3. 마지막 지점부터 계속
```

### 2. 재시도 전략

```
지수 백오프 (Exponential Backoff):
- 1차 실패: 2초 대기
- 2차 실패: 4초 대기
- 3차 실패: 8초 대기
- 최대 60초 대기

지터 (Jitter):
- 0.5 ~ 1.5배 랜덤화
- Thundering herd 방지
```

### 3. 중복 방지

```
수집된 ID를 Set으로 관리:
- O(1) 조회
- 상태 파일에 영속화
- 재시작 시 복원
```

## 테스트

```bash
# 전체 테스트
pytest

# 커버리지 포함
pytest --cov=bid_crawler

# 단위 테스트만
pytest tests/unit/

# 특정 테스트
pytest tests/unit/test_models.py -v
```

## 설정 옵션

| 옵션 | 기본값 | 설명 |
|-----|-------|------|
| `max_pages` | None | 최대 크롤링 페이지 수 |
| `max_items` | None | 최대 수집 항목 수 |
| `headless` | True | 브라우저 숨김 모드 |
| `timeout` | 30000 | 페이지 로드 타임아웃 (ms) |
| `output_format` | json | 출력 형식 (json/csv/both) |
| `max_retries` | 3 | 최대 재시도 횟수 |
| `retry_delay` | 2.0 | 재시도 기본 대기 (초) |

## 환경 변수

```bash
CRAWLER_BASE_URL=https://www.g2b.go.kr
CRAWLER_HEADLESS=true
CRAWLER_TIMEOUT=30000
CRAWLER_LOG_LEVEL=INFO
CRAWLER_MAX_PAGES=10
CRAWLER_MAX_ITEMS=100
```

## 트러블슈팅

### 브라우저 설치 오류

```bash
# 시스템 의존성 설치 (Ubuntu)
sudo apt-get install libnss3 libnspr4 libatk1.0-0

# Playwright 재설치
playwright install --with-deps chromium
```

### 타임아웃 오류

```bash
# 타임아웃 증가
bid-crawler crawl --timeout 60000
```

### 메모리 부족

```bash
# 페이지 제한
bid-crawler crawl --max-pages 10
```

## 라이선스

MIT License
