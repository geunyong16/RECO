# 계근지 OCR 텍스트 파서 (Weighing Receipt Parser)

차량 계량 영수증(계근지) OCR 결과를 파싱하여 구조화된 데이터로 변환하는 Python 라이브러리입니다.

## 주요 기능

- Google Cloud Vision OCR JSON 출력 파싱
- 다양한 문서 유형 지원 (계량증명서, 계량확인서, 계량증명표, 계표)
- OCR 노이즈 자동 처리 (띄어쓰기, 오탈자, 숫자 포맷)
- 중량 계산 검증 (실중량 = 총중량 - 공차중량)
- JSON/CSV 출력 지원
- CLI 명령줄 도구 제공

## 환경 요구사항

- **Python**: >= 3.9
- **주요 의존성**: pydantic >= 2.0, structlog >= 23.0.0
- **개발 의존성**: pytest >= 7.0, pytest-asyncio >= 0.21.0, pytest-cov >= 4.0
- **OS**: Windows, macOS, Linux

## 설치

```bash
# 개발 환경 설치
pip install -e ".[dev]"

# 또는 의존성만 설치
pip install -r requirements.txt
```

## 빠른 시작

### Python 코드

```python
from weighing_parser import WeighingReceiptParser

# 파서 생성
parser = WeighingReceiptParser()

# 단일 파일 파싱
receipt = parser.parse_file("receipt_01.json")

# 결과 출력
print(f"문서 유형: {receipt.document_type}")
print(f"날짜: {receipt.date}")
print(f"차량번호: {receipt.vehicle_number}")
print(f"총중량: {receipt.total_weight.value_kg} kg")
print(f"공차중량: {receipt.tare_weight.value_kg} kg")
print(f"실중량: {receipt.net_weight.value_kg} kg")
```

### CLI 사용

```bash
# 단일 파일 파싱 (JSON 출력)
python -m weighing_parser receipt_01.json

# 결과를 파일로 저장
python -m weighing_parser receipt_01.json -o result.json

# 여러 파일을 CSV로 저장
python -m weighing_parser *.json -o results.csv

# 상세 로그 출력
python -m weighing_parser receipt_01.json -v
```

## 추출 필드

| 필드 | 설명 | 예시 |
|------|------|------|
| document_type | 문서 유형 | 계량증명서, 계량확인서 |
| date | 계량 날짜 | 2026-02-02 |
| sequence_number | 일련번호 | 0016 |
| vehicle_number | 차량 번호 | 80구8713 |
| company_name | 거래처명 | 고요환경 |
| product_name | 품목명 | 식물, 국판 |
| category | 입출고 구분 | 입고/출고 |
| total_weight | 총중량 (kg) | 12,480 |
| tare_weight | 공차중량 (kg) | 7,470 |
| net_weight | 실중량 (kg) | 5,010 |
| issuing_company | 발급 회사 | 동우바이오(주) |
| timestamp | 발급 시간 | 2026-02-02 05:37:55 |
| gps_coordinates | GPS 좌표 | 37.105317, 127.375673 |
| address | 주소 | 경기도 화성시... |
| phone | 연락처 | 031-354-7778 |

## OCR 노이즈 처리

라이브러리는 다음과 같은 OCR 노이즈를 자동으로 처리합니다:

### 띄어쓰기
```
입력: "계 량 증 명 서"
출력: "계량증명서"
```

### 숫자 포맷
```
입력: "12,480", "5 900", "13 460"
출력: 12480, 5900, 13460
```

### 시간 포맷
```
입력: "05:26:18", "11시 33분", "(09:09)"
출력: 05:26:18 (표준화)
```

### OCR 오탈자
```
입력: "계 그 표" (그 ← 근 오인식)
출력: "계표"
```

## 프로젝트 구조

```
assignment_A/
├── src/weighing_parser/
│   ├── models/          # 데이터 모델 (Pydantic)
│   ├── extractors/      # 필드 추출기
│   ├── normalizers/     # 텍스트/숫자 정규화
│   ├── validators/      # 데이터 검증
│   ├── output/          # JSON/CSV 출력
│   ├── parser.py        # 메인 파서
│   └── main.py          # CLI
├── tests/
│   ├── unit/            # 단위 테스트
│   └── integration/     # 통합 테스트
└── docs/
    └── DESIGN.md        # 설계 문서
```

## 테스트 실행

```bash
# 전체 테스트
pytest

# 단위 테스트만
pytest tests/unit/

# 통합 테스트만
pytest tests/integration/

# 커버리지 포함
pytest --cov=weighing_parser
```

## 출력 예시

### JSON 출력
```json
{
  "document_type": "계량증명서",
  "date": "2026-02-02",
  "vehicle_number": "8713",
  "company_name": "곰욕환경폐기물",
  "total_weight": {
    "value_kg": 12480,
    "timestamp": "05:26:18"
  },
  "tare_weight": {
    "value_kg": 7470,
    "timestamp": "05:36:01"
  },
  "net_weight": {
    "value_kg": 5010
  },
  "issuing_company": "동우바이오(주)",
  "gps_coordinates": {
    "latitude": 37.105317,
    "longitude": 127.375673
  }
}
```

### CSV 출력
```csv
document_type,date,vehicle_number,total_weight_kg,tare_weight_kg,net_weight_kg,...
계량증명서,2026-02-02,8713,12480,7470,5010,...
```

> 전체 결과물 예시 파일은 `examples/output/` 디렉토리에서 확인할 수 있습니다.

## 검증 기능

### 중량 계산 검증
- 실중량 = 총중량 - 공차중량 검증
- 허용 오차: 10kg (설정 가능)

### 신뢰도 검증
- OCR 신뢰도 70% 미만: 경고 표시
- OCR 신뢰도 50% 미만: 심각 경고

## API 참조

### WeighingReceiptParser

```python
parser = WeighingReceiptParser(
    min_confidence=0.5,      # 최소 신뢰도 임계값
    validate_weights=True,   # 중량 검증 활성화
    weight_tolerance_kg=10   # 중량 검증 허용 오차
)

# 단일 파일 파싱
receipt = parser.parse_file("input.json")

# 여러 파일 파싱
receipts = parser.parse_batch(["file1.json", "file2.json"])
```

### 출력 작성

```python
from weighing_parser.output import JSONWriter, CSVWriter

# JSON 출력
JSONWriter.write(receipt, "output.json", pretty=True)

# CSV 출력 (배치)
CSVWriter.write_batch(receipts, "output.csv")
```

## 주요 가정

- **입력 형식**: Google Cloud Vision OCR API의 JSON 출력 형식만 지원
- **문서 언어**: 한국어 계근지(차량 계량 영수증) 문서만 대상
- **문서 유형**: 계량증명서, 계량확인서, 계량증명표, 계표 4가지 유형 지원
- **OCR 신뢰도**: 최소 50% 이상의 OCR 신뢰도를 가진 입력 데이터 가정
- **중량 단위**: 모든 중량 값은 kg 단위로 기록되어 있다고 가정
- **중량 관계**: 실중량 = 총중량 - 공차중량 수식이 항상 성립 (허용 오차 10kg)

## 한계 및 개선 아이디어

### 현재 한계

- **OCR 엔진 종속**: Google Cloud Vision 출력 형식에만 대응하며, 다른 OCR 엔진(Tesseract, Naver Clova 등)의 출력은 지원하지 않음
- **정규식 기반 추출**: 패턴 매칭에 의존하므로, 예상하지 못한 레이아웃이나 새로운 노이즈 패턴에 취약
- **단일 언어**: 한국어 계근지만 지원하며, 다국어 문서 처리 불가
- **배치 처리 성능**: 대량 파일 처리 시 순차 처리로 인한 속도 제한

### 개선 아이디어

- **병렬 처리**: multiprocessing 적용으로 대량 파일 배치 처리 성능 개선
- **다중 OCR 엔진 지원**: Tesseract, Naver Clova OCR 등 다양한 입력 형식 어댑터 추가
- **학습 기반 추출**: OCR 노이즈 패턴 자동 학습/업데이트 기능
- **웹 인터페이스**: 파싱 결과를 시각적으로 확인할 수 있는 GUI 추가
- **정규식 패턴 캐싱**: 컴파일된 정규식 재사용으로 성능 최적화

## 라이선스

이 프로젝트는 과제 제출용으로 작성되었습니다.
