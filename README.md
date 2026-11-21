# SearchDomainApp

`.com` 도메인의 **DNS 등록 여부를 대량으로 스캔**하는 도구입니다.
짧은 도메인(3~5글자 등)이나 특정 패턴의 도메인이 등록되어 있는지 NS 레코드 조회로 확인하고, 결과를 CSV로 저장합니다.

## 요구사항

- Python 3.8+
- `dnspython` — `pip install -r requirements.txt`

## 사용법

### 1) 글자 수 지정 스캔 (가장 일반적)

```bash
python com_domain_dns_checker.py <글자수> [--workers N] [--delay 초]
```

| 예시 | 설명 |
|------|------|
| `python com_domain_dns_checker.py 3` | 3글자 `.com` 전체 17,576개 스캔 |
| `python com_domain_dns_checker.py 4` | 4글자 `.com` 전체 456,976개 스캔 |
| `python com_domain_dns_checker.py 3 --workers 50` | 동시 조회 스레드 50개로 증가 |
| `python com_domain_dns_checker.py 3 --delay 0.05` | 워커당 0.05초 간격으로 속도 제한 |
| `python com_domain_dns_checker.py 3 --digits` | 숫자 포함 도메인까지 스캔 (a-z0-9, 46,656개) |

> ⚠️ 5글자 이상(1,180만 개)은 조회량이 매우 크므로 비추천 — 공용 DNS 서버의
> rate limit에 걸리거나 차단될 수 있습니다.

### 2) 정규식 패턴 스캔

```bash
python com_regex_domain_checker.py "<정규식>" [--max-length N] [--workers N] [--delay 초]
```

- 패턴은 **도메인 전체명(`xxx.com`)에 fullmatch** 됩니다.
- `--max-length`(기본 3) 이하의 모든 길이 조합을 생성해 패턴과 비교합니다.
- **후보 문자셋은 패턴에서 자동 판별**됩니다 — 패턴에 `0-9`, `\d`, `\w`,
  또는 숫자가 포함되어 있으면 후보에 숫자가 포함됩니다
  (예: `^[a-z0-9]{3}\.com$` → a-z0-9 전체, `^[a-z]{3}\.com$` → a-z만).
  `{n}` 수량자 안의 숫자는 도메인 문자로 보지 않습니다.

| 예시 | 설명 |
|------|------|
| `python com_regex_domain_checker.py "^[a-z]{3}\.com$"` | 3글자 영문 `.com` 전체 |
| `python com_regex_domain_checker.py "^a.*b\.com$" --max-length 4` | a로 시작하고 b로 끝나는 최대 4글자 도메인 |
| `python com_regex_domain_checker.py "^(job\|work)\w*\.com$"` | job/work로 시작하는 도메인 |

## 결과 파일

스크립트 실행 위치에 CSV로 저장됩니다 (UTF-8 BOM — 엑셀 바로 열기 가능).

- 글자수 스캔: `com_<N>letter_check.csv`
- 정규식 스캔: `com_regex_<패턴>_check.csv`

### 상태 값

| status | 의미 |
|--------|------|
| `REGISTERED_DNS` | NS 레코드 존재 — **등록된 도메인** (ns 컬럼에 네임서버 목록) |
| `NO_DNS_NXDOMAIN` | DNS에 존재하지 않음 — **미등록일 가능성이 높음** |
| `NO_NS_ANSWER` | 도메인은 존재하나 NS 레코드 없음 — 등록됐으나 위임 정보 없는 특수 케이스 |
| `CHECK_NEEDED_TIMEOUT` | 재시도 후에도 타임아웃 — **수동 확인 필요** |
| `CHECK_NEEDED_<오류명>` | 기타 DNS 오류 — **수동 확인 필요** |

> NXDOMAIN은 "미등록"의 강한 신호이지만 100% 보장은 아닙니다.
> 실제 등록 가능 여부는 registrar(가비아 등)에서 최종 확인하세요.
> `CHECK_NEEDED_*` 상태는 네트워크 일시 장애일 수 있으니 재스캔을 권장합니다.

## 동작 방식

- 공용 리졸버(`8.8.8.8`, `1.1.1.1`, `9.9.9.9`)에 도메인별 `NS` 쿼리를 병렬 전송
- 스레드별 Resolver를 재사용하고, 일시 오류는 점증 백오프로 최대 2회 재시도
- 결과는 **완료 순서대로 증분 저장**되므로 중단돼도 진행분이 유지됩니다
  (알파벳 정렬은 되지 않습니다 — 필요하면 스캔 후 정렬하세요)
- `--workers`(기본 30)가 동시성, `--delay`가 속도 제한 역할을 합니다

## 파일 구성

| 파일 | 역할 |
|------|------|
| `domain_checker_utils.py` | 공용 로직 — Resolver, `check_domain`, 도메인 생성, `run_scan` |
| `com_domain_dns_checker.py` | 글자 수 지정 스캔 진입점 |
| `com_regex_domain_checker.py` | 정규식 패턴 스캔 진입점 |
| `requirements.txt` | 의존성 (`dnspython`) |

## 주의사항

- 공용 DNS 서버에 대한 **대량 쿼리**이므로 `--workers`/`--delay`를 조절해
  과도한 부하를 피하세요. 차단당하면 값이 낮을수록 안전합니다.
- 이 도구는 등록 *가능성*을 판별할 뿐, registrar의 실제 등록 가능 여부
  (프리미엄 가격, 예약어 등)는 별도로 확인해야 합니다.
