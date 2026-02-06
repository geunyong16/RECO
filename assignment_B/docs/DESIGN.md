# 누리장터 입찰공고 크롤러 설계 문서

## 1. 개요

### 1.1 프로젝트 목적

나라장터(G2B) 입찰공고 페이지에서 입찰 정보를 자동으로 수집하여 구조화된 형태로 저장하는 크롤러 개발

### 1.2 핵심 요구사항

| 요구사항 | 설명 | 구현 방식 |
|---------|------|----------|
| 동적 페이지 크롤링 | JavaScript 렌더링 페이지 처리 | Playwright 브라우저 자동화 |
| 목록/상세 탐색 | 목록에서 상세 페이지로 이동 | 자동 링크 추적 |
| 중단점 재시작 | 오류 시 마지막 지점부터 계속 | 상태 파일 영속화 |
| 중복 방지 | 이미 수집된 항목 스킵 | ID 기반 중복 체크 |
| 재시도 로직 | 일시적 오류 복구 | 지수 백오프 |
| 스케줄링 | 정기 실행 | interval/cron 지원 |

### 1.3 기술 스택

- **언어**: Python 3.9+
- **브라우저 자동화**: Playwright
- **데이터 모델링**: Pydantic
- **스케줄링**: APScheduler
- **CLI**: Click + Rich
- **테스트**: pytest + pytest-asyncio

## 2. 아키텍처

### 2.1 시스템 구성도

```
┌─────────────────────────────────────────────────────────────┐
│                         CLI (main.py)                        │
├─────────────────────────────────────────────────────────────┤
│                    Crawler Orchestrator                      │
│                       (crawler.py)                           │
├───────────┬───────────┬───────────┬────────────┬────────────┤
│  Browser  │ Scrapers  │  Storage  │ Scheduler  │   Utils    │
│  Manager  │           │           │            │            │
├───────────┼───────────┼───────────┼────────────┼────────────┤
│Playwright │  List     │  State    │   Cron     │   Retry    │
│           │  Detail   │  JSON     │            │   Logger   │
│           │           │  CSV      │            │   Browser  │
└───────────┴───────────┴───────────┴────────────┴────────────┘
```

### 2.2 데이터 흐름

```
                    ┌──────────────┐
                    │   시작/재시작  │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │  상태 로드    │
                    │ (재시작 지점)  │
                    └──────┬───────┘
                           │
              ┌────────────▼────────────┐
              │     목록 페이지 크롤링     │
              │  (ListScraper.scrape)   │
              └────────────┬────────────┘
                           │
                    ┌──────▼───────┐
                    │  공고 목록    │
                    │   추출       │
                    └──────┬───────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
    ┌────▼────┐      ┌─────▼────┐      ┌─────▼────┐
    │ 중복?   │      │  상세    │      │ 다음     │
    │ 스킵    │      │ 크롤링   │      │ 페이지   │
    └─────────┘      └────┬─────┘      └──────────┘
                          │
                   ┌──────▼───────┐
                   │   데이터     │
                   │   저장       │
                   └──────┬───────┘
                          │
                   ┌──────▼───────┐
                   │   상태 저장   │
                   └──────────────┘
```

### 2.3 모듈 책임

| 모듈 | 책임 | 의존성 |
|-----|------|-------|
| `config.py` | 설정 관리, 검증 | Pydantic |
| `crawler.py` | 워크플로우 오케스트레이션 | 모든 모듈 |
| `models/` | 데이터 구조 정의 | Pydantic |
| `scrapers/` | HTML 파싱, 데이터 추출 | Playwright |
| `storage/` | 데이터 영속화 | JSON, CSV |
| `scheduler/` | 정기 실행 관리 | APScheduler |
| `utils/` | 공통 유틸리티 | - |

## 3. 핵심 컴포넌트 설계

### 3.1 데이터 모델

#### BidNotice (목록 항목)

```python
class BidNotice(BaseModel):
    # 필수
    bid_notice_id: str      # 공고번호 (PK)
    title: str              # 공고명

    # 선택
    bid_type: BidType       # 입찰유형 (물품/용역/공사)
    status: BidStatus       # 상태 (공고중/마감)
    organization: str       # 공고기관
    deadline: datetime      # 마감일시
    estimated_price: int    # 추정가격
    detail_url: str         # 상세 URL
    crawled_at: datetime    # 수집일시
```

#### BidNoticeDetail (상세 정보)

```python
class BidNoticeDetail(BidNotice):
    # 추가 필드
    bid_method: str         # 입찰방식
    contract_method: str    # 계약방법
    qualification: str      # 참가자격
    region: str             # 지역
    contact_person: str     # 담당자
    contact_phone: str      # 연락처
    attachments: List[str]  # 첨부파일
    detail_crawled_at: datetime
    crawl_success: bool
    crawl_error: str
```

#### CrawlState (크롤링 상태)

```python
class CrawlState(BaseModel):
    run_id: str             # 실행 ID
    started_at: datetime    # 시작 시간
    is_running: bool        # 실행 중 여부
    is_completed: bool      # 완료 여부

    progress: CrawlProgress # 진행 상황
    statistics: CrawlStatistics  # 통계
    collected_ids: Set[str] # 수집된 ID (중복 방지)
    failed_items: List[dict] # 실패 항목 (재시도용)
```

### 3.2 스크래퍼 설계

#### 추상 기본 클래스 (BaseScraper)

```python
class BaseScraper(ABC):
    """모든 스크래퍼의 기본 인터페이스"""

    @abstractmethod
    async def scrape(self) -> Any:
        pass

    # 공통 유틸리티
    async def get_text(self, selector: str) -> str
    async def get_attribute(self, selector: str, attr: str) -> str
    def parse_price(self, text: str) -> int
    def parse_datetime(self, text: str) -> datetime
```

#### ListScraper

```
목록 페이지 처리 흐름:
1. 테이블 로드 대기
2. 행(row) 순회
3. 각 행에서 필드 추출
4. BidNotice 객체 생성
5. 페이지네이션 정보 추출
```

#### DetailScraper

```
상세 페이지 처리 흐름:
1. 상세 컨테이너 로드 대기
2. 정보 테이블 파싱
3. 필드 매핑 및 정규화
4. BidNoticeDetail 객체 생성
```

### 3.3 상태 관리

#### 상태 파일 구조

```json
{
  "run_id": "20240115_103000",
  "started_at": "2024-01-15T10:30:00",
  "last_updated_at": "2024-01-15T11:45:30",
  "is_running": true,
  "is_completed": false,
  "progress": {
    "current_page": 5,
    "current_index": 3,
    "total_pages": 20,
    "last_completed_page": 4
  },
  "statistics": {
    "total_collected": 43,
    "errors": 2,
    "retries": 5,
    "skipped_duplicates": 3
  },
  "collected_ids": ["id1", "id2", "id3", ...],
  "failed_items": [
    {"info": {"bid_id": "xxx"}, "error": "timeout"}
  ]
}
```

#### 재시작 로직

```python
def initialize(run_id: str, resume: bool) -> CrawlState:
    if resume and state_file.exists():
        loaded = load()
        if not loaded.is_completed:
            # 이전 상태에서 재시작
            return loaded
    # 새로 시작
    return CrawlState(run_id=run_id)
```

### 3.4 재시도 전략

#### 지수 백오프

```python
delay = min(base_delay * (2 ** attempt), max_delay)
# 1초 → 2초 → 4초 → 8초 → ... → 60초(최대)
```

#### 지터 (Jitter)

```python
delay = delay * (0.5 + random.random())
# 0.5x ~ 1.5x 랜덤화로 동시 재시도 방지
```

#### 재시도 대상 예외

```python
retry_exceptions = (
    TimeoutError,
    ConnectionError,
    PlaywrightTimeout,
)
```

### 3.5 스케줄러

#### Interval 모드

```python
scheduler.add_job(
    crawl_job,
    IntervalTrigger(minutes=60),  # 1시간마다
)
```

#### Cron 모드

```python
scheduler.add_job(
    crawl_job,
    CronTrigger.from_crontab("0 */6 * * *"),  # 6시간마다
)
```

## 4. 설계 결정 및 트레이드오프

### 4.1 Playwright vs Selenium

| 항목 | Playwright | Selenium |
|-----|-----------|----------|
| 속도 | 빠름 | 보통 |
| 설치 | 간편 (pip) | 복잡 (드라이버 필요) |
| API | 현대적, async | 레거시 |
| 지원 | Microsoft | 커뮤니티 |

**결정**: Playwright 선택 - 더 나은 성능과 현대적인 API

### 4.2 동기 vs 비동기

| 항목 | 동기 | 비동기 |
|-----|-----|-------|
| 복잡도 | 낮음 | 높음 |
| 성능 | I/O 대기 중 블로킹 | I/O 동시 처리 |
| 디버깅 | 쉬움 | 어려움 |

**결정**: 비동기 선택 - 네트워크 I/O가 많아 비동기가 효율적

### 4.3 상태 저장 주기

| 전략 | 장점 | 단점 |
|-----|-----|-----|
| 매 항목 | 정밀한 재시작 | I/O 오버헤드 |
| 매 페이지 | 적절한 균형 | 페이지 내 손실 가능 |
| 종료 시만 | 빠름 | 많은 데이터 손실 가능 |

**결정**: 매 페이지 + 일정 간격 - 성능과 안정성 균형

### 4.4 데이터 저장 형식

| 형식 | 장점 | 단점 |
|-----|-----|-----|
| JSON | 구조화, 타입 보존 | 증분 저장 어려움 |
| CSV | 엑셀 호환, 증분 쉬움 | 중첩 데이터 어려움 |
| SQLite | 쿼리 가능, 트랜잭션 | 복잡도 증가 |

**결정**: JSON + CSV 동시 지원 - 용도에 따라 선택 가능

## 5. 확장 포인트

### 5.1 다른 사이트 지원

```python
class NewSiteScraper(BaseScraper):
    SELECTORS = {
        "table": ".custom-table",
        "rows": "tr.item-row",
        ...
    }

    async def scrape(self) -> BidNoticeList:
        # 사이트별 커스텀 로직
```

### 5.2 알림 기능

```python
crawler.on_item_collected(send_notification)

def send_notification(item: BidNoticeDetail):
    if "관심키워드" in item.title:
        send_email(item)
```

### 5.3 데이터베이스 저장

```python
class DatabaseStorage:
    def save(self, notices: List[BidNotice]):
        session.bulk_save_objects(notices)
        session.commit()
```

## 6. 테스트 전략

### 6.1 단위 테스트

| 대상 | 테스트 내용 |
|-----|-----------|
| 모델 | 생성, 직렬화, 메서드 |
| 파서 | 텍스트 파싱, 날짜 변환 |
| 저장소 | 저장, 로드, 중복 처리 |
| 재시도 | 성공, 실패, 백오프 |

### 6.2 통합 테스트

| 시나리오 | 테스트 내용 |
|---------|-----------|
| 정상 크롤링 | 전체 파이프라인 |
| 재시작 | 상태 복원 및 계속 |
| 오류 복구 | 재시도 및 기록 |

### 6.3 E2E 테스트

```python
@pytest.mark.e2e
async def test_full_crawl():
    config = CrawlerConfig(max_pages=1)
    crawler = BidCrawler(config)
    state = await crawler.run()
    assert state.statistics.total_collected > 0
```

## 7. 성능 고려사항

### 7.1 메모리 관리

- 대량 ID 저장 시 Set 사용 (O(1) 조회)
- 저장 버퍼 일정 크기 유지
- 페이지 완료 후 GC 힌트

### 7.2 네트워크 최적화

- 불필요한 리소스 차단 (이미지, 폰트)
- 적절한 타임아웃 설정
- 연결 재사용

### 7.3 브라우저 리소스

- 단일 브라우저 인스턴스 재사용
- 페이지 종료 시 명시적 close
- 헤드리스 모드 사용

## 8. 보안 고려사항

### 8.1 크롤링 윤리

- robots.txt 준수
- 적절한 요청 간격 (slow_mo)
- User-Agent 명시

### 8.2 데이터 보호

- 민감 정보 로깅 제외
- 상태 파일 접근 권한
- 설정 파일 암호화 (필요시)

## 9. 배포

### 9.1 Docker

```dockerfile
FROM mcr.microsoft.com/playwright/python:v1.40.0
WORKDIR /app
COPY . .
RUN pip install -e .
CMD ["bid-crawler", "schedule"]
```

### 9.2 Cron (Linux)

```cron
0 */6 * * * /path/to/venv/bin/bid-crawler crawl >> /var/log/crawler.log 2>&1
```

### 9.3 Windows Task Scheduler

```xml
<Task>
  <Triggers>
    <CalendarTrigger>
      <Repetition>
        <Interval>PT6H</Interval>
      </Repetition>
    </CalendarTrigger>
  </Triggers>
  <Actions>
    <Exec>
      <Command>python</Command>
      <Arguments>-m bid_crawler crawl</Arguments>
    </Exec>
  </Actions>
</Task>
```
