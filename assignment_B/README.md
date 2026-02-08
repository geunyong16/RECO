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

## 환경 요구사항

- **Python**: >= 3.9
- **주요 의존성**: playwright >= 1.40.0, pydantic >= 2.0, aiohttp >= 3.9.0, click >= 8.1.0
- **브라우저**: Chromium (Playwright가 자동 관리)
- **OS**: Windows, macOS, Linux

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

> 전체 결과물 예시 파일은 `examples/output/` 디렉토리에서 확인할 수 있습니다.

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

## 주요 가정

- **대상 사이트**: 나라장터(G2B, g2b.go.kr) 입찰공고 페이지만 대상
- **렌더링 방식**: JavaScript로 동적 렌더링되는 페이지를 Playwright로 처리
- **브라우저**: Chromium 브라우저 사용 (Playwright 관리)
- **네트워크**: 안정적인 인터넷 연결 환경 가정 (타임아웃 기본 30초)
- **페이지 구조**: 나라장터 페이지의 HTML 구조가 `config/selectors.yaml`에 정의된 셀렉터와 일치한다고 가정 (사이트 구조 변경 시 셀렉터 업데이트 필요)
- **robots.txt**: 크롤링 대상 페이지가 robots.txt에 의해 차단되지 않는다고 가정

## 한계 및 개선 아이디어

### 현재 한계

- **단일 사이트 전용**: 나라장터(G2B)만 지원하며, 다른 입찰 사이트(조달청 직접입찰 등)는 미지원
- **사이트 구조 변경 취약**: 나라장터 페이지 구조가 변경되면 `selectors.yaml` 수동 업데이트 필요
- **단일 브라우저 인스턴스**: 동시에 여러 페이지를 병렬 크롤링하지 않으므로 대량 수집 시 속도 제한
- **로그인 미지원**: 로그인이 필요한 상세 정보(첨부파일 다운로드 등)는 수집 불가
- **캡차/봇 차단**: 사이트의 봇 차단 메커니즘에 대한 우회 기능 없음

### 개선 아이디어

- **다중 사이트 지원**: BaseScraper를 확장하여 다른 입찰 사이트 크롤러 추가
- **알림 기능**: 특정 키워드 공고 등록 시 이메일/슬랙 알림
- **데이터베이스 저장**: SQLite/PostgreSQL 연동으로 쿼리 및 분석 기능 강화
- **병렬 크롤링**: 여러 브라우저 컨텍스트를 활용한 동시 수집
- **대시보드**: 수집 현황을 실시간 모니터링할 수 있는 웹 대시보드

## 라이선스

MIT License
