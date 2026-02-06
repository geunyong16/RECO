# 설계 문서 (Design Document)

## 1. 개요

이 문서는 계근지(차량 계량 영수증) OCR 텍스트 파서의 설계 결정 사항과 아키텍처를 설명합니다.

## 2. 아키텍처

### 2.1 전체 구조

```
┌─────────────────────────────────────────────────────────────┐
│                        CLI (main.py)                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Parser (parser.py)                       │
│  - 전체 파싱 프로세스 조율                                  │
│  - 추출기, 검증기 호출                                      │
└─────────────────────────────────────────────────────────────┘
         │              │              │              │
         ▼              ▼              ▼              ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  Extractors  │ │ Normalizers  │ │  Validators  │ │   Output     │
│              │ │              │ │              │ │              │
│ - document   │ │ - text       │ │ - weights    │ │ - json       │
│ - date       │ │ - numbers    │ │ - confidence │ │ - csv        │
│ - vehicle    │ │ - datetime   │ │              │ │              │
│ - weights    │ │              │ │              │ │              │
│ - company    │ │              │ │              │ │              │
│ - location   │ │              │ │              │ │              │
│ - contact    │ │              │ │              │ │              │
└──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘
         │              │              │              │
         ▼              ▼              ▼              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Models (Pydantic)                        │
│  - OCRDocument (입력)                                       │
│  - WeighingReceipt (출력)                                   │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 데이터 흐름

```
OCR JSON 파일
    │
    ▼
OCRDocument 모델로 파싱
    │
    ▼
각 Extractor가 필드별 추출
    │
    ├─→ Normalizer로 텍스트/숫자 정규화
    │
    ▼
Validator로 데이터 검증
    │
    ▼
WeighingReceipt 모델 생성
    │
    ▼
JSON/CSV 출력
```

## 3. 모듈 설계

### 3.1 Models

#### OCRDocument (입력 모델)
Google Cloud Vision API 출력 형식을 그대로 모델링합니다.

```python
class OCRDocument:
    apiVersion: str
    confidence: float
    text: str
    pages: list[Page]
        └── lines: list[Line]
            └── words: list[Word]
                └── text, confidence, boundingBox
```

#### WeighingReceipt (출력 모델)
파싱된 계근지 데이터의 구조화된 표현입니다.

```python
class WeighingReceipt:
    document_type: str        # 문서 유형
    date: date               # 계량 날짜
    vehicle_number: str      # 차량 번호
    total_weight: WeightMeasurement  # 총중량
    tare_weight: WeightMeasurement   # 공차중량
    net_weight: WeightMeasurement    # 실중량
    ...
    confidence_scores: list  # 신뢰도 점수
    validation_errors: list  # 검증 오류
```

### 3.2 Extractors

각 추출기는 BaseExtractor를 상속하고 extract() 메서드를 구현합니다.

```python
class BaseExtractor(ABC):
    @abstractmethod
    def extract(self, document: OCRDocument) -> Tuple[Any, float]:
        """
        Returns:
            (추출된 값, 신뢰도 점수)
        """
        pass
```

#### 추출기 목록

| 추출기 | 책임 | 검색 패턴 |
|--------|------|-----------|
| DocumentTypeExtractor | 문서 유형 식별 | "계량증명서", "계량확인서", "계표" |
| DateExtractor | 날짜/일련번호 추출 | "계량일자:", "날짜:" |
| VehicleExtractor | 차량번호 추출 | "차량번호:", "차번호:" |
| WeightsExtractor | 중량 3종 추출 | "총중량:", "공차:", "실중량:" |
| CompanyExtractor | 거래처명 추출 | "거래처:", "상호:" |
| IssuerExtractor | 발급회사 추출 | "(주)", "C&S" 패턴 |
| LocationExtractor | GPS/주소 추출 | 좌표 패턴, 주소 패턴 |
| ContactExtractor | 연락처 추출 | "Tel)", 전화번호 패턴 |

### 3.3 Normalizers

#### TextNormalizer
```python
class TextNormalizer:
    @staticmethod
    def remove_spaces(text: str) -> str:
        """'계 량 증 명 서' → '계량증명서'"""

    @staticmethod
    def fix_ocr_errors(text: str) -> str:
        """'계 그 표' → '계표'"""
```

#### NumberNormalizer
```python
class NumberNormalizer:
    @staticmethod
    def parse_weight(text: str) -> int:
        """'12,480', '5 900' → 12480, 5900"""
```

#### DateTimeNormalizer
```python
class DateTimeNormalizer:
    @classmethod
    def parse_time(cls, text: str) -> time:
        """'05:26:18', '11시 33분', '(09:09)' → time 객체"""
```

### 3.4 Validators

#### WeightValidator
```python
class WeightValidator:
    def validate_weight_equation(
        self, total: int, tare: int, net: int
    ) -> Tuple[bool, Optional[str]]:
        """
        검증: net == total - tare (허용 오차 내)
        """
```

#### ConfidenceValidator
```python
class ConfidenceValidator:
    LOW_THRESHOLD = 0.7
    CRITICAL_THRESHOLD = 0.5

    def check_confidence(self, field: str, conf: float):
        """신뢰도에 따른 경고 생성"""
```

## 4. 설계 결정 사항

### 4.1 정규식 vs NLP 라이브러리

**결정**: 정규식 직접 구현

**이유**:
- 샘플 데이터 분석 결과, 필드 패턴이 명확하고 일관됨
- 외부 의존성 최소화 (pydantic만 사용)
- 코드 동작 원리를 100% 설명 가능
- spaCy 등 NLP 라이브러리는 오버헤드가 큼

### 4.2 모듈화 전략

**결정**: 기능별 분리 (extractors, normalizers, validators, output)

**이유**:
- 단일 책임 원칙 (SRP) 준수
- 각 모듈을 독립적으로 테스트 가능
- 새로운 필드 추가 시 기존 코드 변경 최소화
- 유지보수 용이

### 4.3 에러 처리 전략

**결정**: Graceful Degradation (부분 실패 허용)

**이유**:
- OCR 결과는 항상 완벽하지 않음
- 일부 필드 추출 실패해도 나머지 필드는 반환
- 실패/경고 내용은 `validation_errors`에 기록

```python
# 추출 실패 시 None 반환, 에러는 validation_errors에 기록
try:
    value, conf = extractor.extract(document)
except Exception as e:
    logger.warning(f"Failed to extract {field}: {e}")
    receipt.validation_errors.append(f"Extraction failed: {field}")
```

## 4.4 에러 처리 흐름 (Error Handling Flow)

### 4.4.1 예외 계층 구조

```
ParserException (base)
│
├─ InvalidOCRFormatError ─────────────────────────────────┐
│   ├─ EmptyDocumentError     # 빈 문서                    │
│   ├─ JSONParseError         # JSON 파싱 실패             │ Input Layer
│   └─ MissingRequiredFieldError  # 필수 필드 누락        │
│                                                          ┘
├─ ExtractionError ───────────────────────────────────────┐
│   ├─ FieldNotFoundError     # 필드 못찾음                │
│   ├─ InvalidFieldValueError # 잘못된 값                  │ Extraction Layer
│   └─ LowConfidenceError     # 신뢰도 부족               │
│                                                          ┘
├─ ValidationError ───────────────────────────────────────┐
│   └─ WeightValidationError                               │
│       ├─ WeightEquationError  # 수식 불일치             │ Validation Layer
│       ├─ NegativeWeightError  # 음수 중량               │
│       └─ WeightOrderError     # 순서 오류               │
│                                                          ┘
├─ NormalizationError ────────────────────────────────────┐
│   ├─ DateParseError         # 날짜 파싱 실패            │ Normalization Layer
│   ├─ WeightParseError       # 중량 파싱 실패            │
│   └─ TimeParseError         # 시간 파싱 실패            │
│                                                          ┘
└─ OutputError ───────────────────────────────────────────┐
    ├─ FileWriteError         # 파일 쓰기 실패            │ Output Layer
    └─ UnsupportedFormatError # 지원되지 않는 형식        │
                                                           ┘
```

### 4.4.2 에러 처리 흐름 다이어그램

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           parse_file(filepath)                           │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │ 파일 존재 여부 확인            │
                    └───────────────────────────────┘
                         │                    │
                    [존재함]              [존재안함]
                         │                    │
                         ▼                    ▼
                         │         ┌──────────────────────┐
                         │         │ FileNotFoundError    │───▶ 즉시 종료
                         │         └──────────────────────┘
                         ▼
                    ┌───────────────────────────────┐
                    │ JSON 파싱                     │
                    └───────────────────────────────┘
                         │                    │
                    [성공]               [실패]
                         │                    │
                         ▼                    ▼
                         │         ┌──────────────────────┐
                         │         │ JSONParseError       │───▶ 즉시 종료
                         │         └──────────────────────┘
                         ▼
                    ┌───────────────────────────────┐
                    │ 필수 필드 검증                 │
                    │ (apiVersion, confidence, etc) │
                    └───────────────────────────────┘
                         │                    │
                    [모두 있음]           [누락됨]
                         │                    │
                         ▼                    ▼
                         │         ┌──────────────────────┐
                         │         │ MissingRequiredFieldError │───▶ 즉시 종료
                         │         └──────────────────────┘
                         ▼
                    ┌───────────────────────────────┐
                    │ Pydantic 모델 검증            │
                    └───────────────────────────────┘
                         │                    │
                    [성공]               [실패]
                         │                    │
                         ▼                    ▼
                         │         ┌──────────────────────┐
                         │         │ InvalidOCRFormatError │───▶ 즉시 종료
                         │         └──────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                              parse(document)                             │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │ 빈 문서 체크                   │
                    └───────────────────────────────┘
                         │                    │
                    [내용 있음]           [비어있음]
                         │                    │
                         ▼                    ▼
                         │         ┌──────────────────────┐
                         │         │ EmptyDocumentError   │───▶ 즉시 종료
                         │         └──────────────────────┘
                         ▼
        ┌────────────────────────────────────────────────────┐
        │           _extract_field() 헬퍼 메서드 호출         │
        │                                                     │
        │  ┌─────────────────────────────────────────────┐   │
        │  │  try:                                        │   │
        │  │      result = extractor.extract(document)   │   │
        │  │      return ExtractionResult(success=True)  │   │
        │  │                                              │   │
        │  │  except DateParseError, WeightParseError:   │   │
        │  │      ─▶ validation_errors에 추가            │   │
        │  │      return ExtractionResult(success=False) │   │
        │  │                                              │   │
        │  │  except ExtractionError, NormalizationError: │   │
        │  │      ─▶ validation_errors에 추가            │   │
        │  │      return ExtractionResult(success=False) │   │
        │  │                                              │   │
        │  │  except ValueError, TypeError, AttributeError: │ │
        │  │      ─▶ validation_errors에 추가            │   │
        │  │      return ExtractionResult(success=False) │   │
        │  └─────────────────────────────────────────────┘   │
        │                                                     │
        │  ※ 개별 필드 실패 시에도 파싱 계속 진행!            │
        └────────────────────────────────────────────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │ 신뢰도 검증                    │
                    │ - 문서 전체 신뢰도             │
                    │ - 필드별 신뢰도               │
                    └───────────────────────────────┘
                         │
                         ▼ (경고만 추가, 중단하지 않음)
                    ┌───────────────────────────────┐
                    │ WeighingReceipt 생성          │
                    │ - model_validator에서         │
                    │   중량 수식 검증              │
                    └───────────────────────────────┘
                         │
                         ▼
            ┌───────────────────────────────────────┐
            │ WeighingReceipt 반환                  │
            │                                        │
            │ - 추출 성공 필드: 값 포함             │
            │ - 추출 실패 필드: None                │
            │ - 모든 에러/경고: validation_errors  │
            └───────────────────────────────────────┘
```

### 4.4.3 에러 처리 원칙

| 에러 유형 | 처리 방식 | 이유 |
|----------|----------|------|
| 파일 없음 | 즉시 예외 발생 | 복구 불가능 |
| JSON 파싱 실패 | 즉시 예외 발생 | 복구 불가능 |
| 필수 필드 누락 | 즉시 예외 발생 | 문서 구조 손상 |
| 빈 문서 | 즉시 예외 발생 | 추출할 내용 없음 |
| 필드 추출 실패 | validation_errors에 추가 | 다른 필드는 추출 가능 |
| 신뢰도 부족 | validation_errors에 경고 추가 | 사용자가 판단 |
| 중량 수식 불일치 | validation_errors에 추가 | 데이터 품질 경고 |

### 4.4.4 에러 메시지 예시

```python
# 성공 케이스
{
    "document_type": "계량증명서",
    "total_weight": {"value_kg": 12480},
    "validation_errors": []  # 에러 없음
}

# 부분 실패 케이스
{
    "document_type": "계량증명서",
    "total_weight": {"value_kg": 12480},
    "vehicle_number": None,  # 추출 실패
    "validation_errors": [
        "vehicle_number extraction failed: pattern not found",
        "Low confidence for document_type: 45.00%"
    ]
}

# 중량 검증 실패 케이스
{
    "total_weight": {"value_kg": 12480},
    "tare_weight": {"value_kg": 7470},
    "net_weight": {"value_kg": 5100},  # 5010이어야 함
    "validation_errors": [
        "Weight equation mismatch: expected 5010, got 5100 (tolerance: 10kg)"
    ]
}
```

### 4.4 신뢰도 처리

**결정**: OCR 신뢰도를 결과에 포함하고 경고 생성

**이유**:
- 사용자가 수동 검증이 필요한 필드를 알 수 있음
- 임계값: 70% 미만 경고, 50% 미만 심각 경고
- `confidence_scores` 필드에 모든 신뢰도 기록

## 5. OCR 노이즈 패턴 분석

### 5.1 샘플 데이터 분석 결과

| 패턴 | 샘플 예시 | 해결 방법 |
|------|-----------|-----------|
| 띄어쓰기 | "계 량 증 명 서" | `remove_spaces()` |
| 오탈자 | "계 그 표" (근→그) | 패턴 대체 목록 |
| 숫자 공백 | "13 460 kg" | 정규식으로 공백 제거 |
| 숫자 쉼표 | "12,480" | 쉼표 제거 후 파싱 |
| 시간 다양성 | "11시 33분", "(09:09)" | 다중 패턴 매칭 |

### 5.2 필드별 레이블 변형

```python
# 총중량 레이블 변형
TOTAL_LABELS = ["총중량", "총 중 량", "품종명랑"]  # OCR 노이즈 포함

# 공차중량 레이블 변형
TARE_LABELS = ["공차중량", "공차 중량", "차중량", "차 중 량", "중 량"]
```

## 6. 테스트 전략

### 6.1 단위 테스트

각 모듈별 독립적인 테스트:

```python
# normalizers 테스트
def test_parse_weight():
    assert NumberNormalizer.parse_weight("12,480") == 12480
    assert NumberNormalizer.parse_weight("5 900") == 5900

# validators 테스트
def test_weight_equation():
    validator = WeightValidator()
    is_valid, _ = validator.validate_weight_equation(12480, 7470, 5010)
    assert is_valid
```

### 6.2 통합 테스트

실제 샘플 데이터로 전체 파이프라인 테스트:

```python
def test_parse_sample_01(parser, sample_data_dir):
    receipt = parser.parse_file(sample_data_dir / "receipt_01.json")

    assert receipt.document_type == "계량증명서"
    assert receipt.total_weight.value_kg == 12480
    assert receipt.net_weight.value_kg == 5010
```

## 7. 확장 포인트

### 7.1 새로운 필드 추가

1. `models/receipt.py`에 필드 추가
2. `extractors/`에 새 추출기 생성
3. `parser.py`에 추출기 등록
4. 테스트 추가

### 7.2 새로운 출력 형식 추가

1. `output/`에 새 Writer 클래스 생성
2. `main.py`에 출력 형식 옵션 추가

### 7.3 새로운 문서 유형 지원

1. `extractors/document_type.py`에 패턴 추가
2. 필요시 새로운 추출 로직 추가

## 8. 성능 고려사항

- 파일 I/O: 각 파일 개별 읽기 (배치 처리 시 병렬화 가능)
- 정규식: 컴파일된 패턴 재사용
- 메모리: Pydantic 모델 사용으로 타입 검증 + 직렬화 효율

## 9. 향후 개선 방향

1. **병렬 처리**: 대량 파일 처리 시 multiprocessing 적용
2. **캐싱**: 컴파일된 정규식 패턴 캐싱
3. **학습 기반**: 패턴 자동 학습/업데이트 기능
4. **GUI**: 웹 인터페이스 추가
