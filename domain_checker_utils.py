"""공용 .com 도메인 DNS 스캔 유틸리티.

- NS 레코드 조회로 등록 여부 판정 (NXDOMAIN ≈ 미등록)
- 스레드별 Resolver 재사용, 타임아웃 재시도, 증분 CSV 저장
"""
import csv
import itertools
import json
import os
import re
import string
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from threading import local

import dns.resolver

MAX_WORKERS = 30          # 동시 조회 스레드 수 (네트워크 상태에 맞게 조절)
DEFAULT_MAX_LENGTH = 3    # 정규식 스캔 기본 최대 도메인 길이
FIELDNAMES = ["domain", "status", "ns"]

_tls = local()            # 스레드별 Resolver 보관


def create_resolver() -> dns.resolver.Resolver:
    resolver = dns.resolver.Resolver()
    resolver.nameservers = ["8.8.8.8", "1.1.1.1", "9.9.9.9"]
    resolver.lifetime = 2.0
    resolver.timeout = 2.0
    return resolver


def get_resolver() -> dns.resolver.Resolver:
    """스레드별 Resolver를 재사용한다 (매 조회마다 생성하지 않음)."""
    resolver = getattr(_tls, "resolver", None)
    if resolver is None:
        resolver = create_resolver()
        _tls.resolver = resolver
    return resolver


def check_domain(domain: str, retries: int = 2, delay: float = 0.0) -> dict:
    """단일 도메인의 NS 레코드를 조회해 등록 여부를 판정한다.

    retries: LifetimeTimeout/NoNameservers 등 일시 오류 재시도 횟수
    delay:   조회 전 대기 시간(초) - 워커당 속도 제한용
    """
    if delay:
        time.sleep(delay)
    resolver = get_resolver()
    for attempt in range(retries + 1):
        try:
            answers = resolver.resolve(domain, "NS")
            ns_list = sorted({str(rdata.target).rstrip(".") for rdata in answers})
            return {
                "domain": domain,
                "status": "REGISTERED_DNS",
                "ns": ";".join(ns_list),
            }
        except dns.resolver.NXDOMAIN:
            # DNS상 존재하지 않는 도메인(미등록 또는 미설정 가능성 높음)
            return {"domain": domain, "status": "NO_DNS_NXDOMAIN", "ns": ""}
        except dns.resolver.NoAnswer:
            # 도메인은 존재하나 NS 레코드 없음 - 등록됐으나 위임 정보 없음
            return {"domain": domain, "status": "NO_NS_ANSWER", "ns": ""}
        except (dns.resolver.LifetimeTimeout, dns.resolver.NoNameservers):
            if attempt < retries:
                time.sleep(0.5 * (attempt + 1))  # 점증 백오프
                continue
            return {"domain": domain, "status": "CHECK_NEEDED_TIMEOUT", "ns": ""}
        except dns.exception.DNSException as e:
            return {
                "domain": domain,
                "status": f"CHECK_NEEDED_{type(e).__name__}",
                "ns": "",
            }
    return {"domain": domain, "status": "CHECK_NEEDED_TIMEOUT", "ns": ""}


def candidate_charset(pattern: str) -> str:
    """정규식 패턴이 숫자를 허용하면 후보 문자셋에 숫자를 포함한다.

    {n} 수량자 안의 숫자는 도메인 문자가 아니므로 제외하고 판별한다.
    """
    stripped = re.sub(r"\{\d+(,\d*)?\}", "", pattern)
    if re.search(r"\\[dw]|0-9|\d", stripped):
        return string.ascii_lowercase + string.digits
    return string.ascii_lowercase


def iter_domains_by_length(length: int, with_digits: bool = False):
    """length글자 .com 도메인 전체를 생성한다 (itertools.product 지연 생성).

    with_digits=True면 a-z0-9 전체(36^N)를 생성한다.
    """
    letters = string.ascii_lowercase + (string.digits if with_digits else "")
    for chars in itertools.product(letters, repeat=length):
        yield f"{''.join(chars)}.com"


def _quantifier_repeat(s: str, i: int):
    """i 위치의 수량자(없으면 1, *=0, ?=0, +=1)를 파싱해 (반복수, 다음위치) 반환."""
    if i >= len(s):
        return 1, i
    c = s[i]
    if c == "{":
        m = re.match(r"\{(\d+)(?:,(\d*)?)?\}", s[i:])
        if m:
            upper = m.group(2)
            rep = int(upper) if upper else int(m.group(1))
            return rep, i + m.end()
        return 1, i
    if c == "+":
        return 1, i + 1
    if c == "?":
        return 1, i + 1
    if c == "*":
        return 0, i + 1
    return 1, i


def _unit_length(s: str, i: int):
    """i 위치의 정규식 단위(원자/그룹) 길이와 다음 위치를 반환한다."""
    c = s[i]
    if c == "\\":
        return 1, min(i + 2, len(s))          # \d, \w, \. 등
    if c == "[":
        j = s.find("]", i + 1)
        return 1, (j + 1 if j != -1 else i + 1)
    if c == "(":
        depth, j = 1, i + 1
        while j < len(s) and depth:
            if s[j] == "\\":
                j += 2
                continue
            if s[j] == "(":
                depth += 1
            elif s[j] == ")":
                depth -= 1
            j += 1
        return _pattern_length(s[i + 1:j - 1]), j
    return 1, i + 1


def _pattern_length(s: str) -> int:
    """정규식 조각이 표현하는 최대 고정 길이를 추정한다."""
    i, total = 0, 0
    while i < len(s):
        if s[i] in "^$" and (i == 0 or i == len(s) - 1):
            i += 1
            continue
        w, j = _unit_length(s, i)
        r, k = _quantifier_repeat(s, j)
        total += w * r
        i = k
    return total


def required_length_hint(pattern: str):
    """패턴이 요구하는 도메인명 길이를 추정한다 (.com 접미사 앞부분 기준).

    수량자뿐 아니라 리터럴·문자클래스·그룹의 길이도 합산한다.
    예: ^a[a-z]{4}\\.com$ -> 1+4 = 5
    """
    body = pattern.strip()
    if body.startswith("^"):
        body = body[1:]
    if body.endswith("$"):
        body = body[:-1]
    m = re.search(r"\\\.com|\.com", body)
    if m:
        body = body[:m.start()]
    length = _pattern_length(body)
    return length if length > 0 else None


def build_domains_by_pattern(pattern: str, max_length: int,
                             charset: str = None) -> list:
    """정규식 패턴에 fullmatch 되는 .com 도메인 목록을 만든다.

    charset을 생략하면 패턴에서 숫자 허용 여부를 자동 판별한다.
    """
    compiled = re.compile(pattern)
    if charset is None:
        charset = candidate_charset(pattern)
    for length in range(1, max_length + 1):
        for chars in itertools.product(charset, repeat=length):
            domain = f"{''.join(chars)}.com"
            if compiled.fullmatch(domain):
                yield domain


RDAP_ENDPOINT = "https://rdap.verisign.com/com/v1/domain/"
RDAP_FIELDS = ["domain", "rdap_status", "registrar", "expires"]


def rdap_check(domain: str, retries: int = 2, delay: float = 0.0) -> dict:
    """RDAP(레지스트리 공식 프로토콜)로 .com 도메인 등록 여부를 확정한다.

    - 404 -> NOT_REGISTERED (레지스트리에 없음 = 등록 가능)
    - 200 -> REGISTERED (registrar·만료일 추출)
    DNS NXDOMAIN과 달리 레지스트리 DB 기준의 정확한 판정이다.
    """
    if delay:
        time.sleep(delay)
    url = RDAP_ENDPOINT + domain
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "SearchDomainApp/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            registrar = ""
            expires = ""
            for ent in data.get("entities", []):
                if "registrar" in ent.get("roles", []):
                    vcard = ent.get("vcardArray", [None, []])[1]
                    for item in vcard:
                        if item and item[0] == "fn":
                            registrar = item[3]
                            break
                    break
            for ev in data.get("events", []):
                if ev.get("eventAction") == "expiration":
                    expires = (ev.get("eventDate") or "")[:10]
            return {"domain": domain, "rdap_status": "REGISTERED",
                    "registrar": registrar, "expires": expires}
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return {"domain": domain, "rdap_status": "NOT_REGISTERED",
                        "registrar": "", "expires": ""}
            if attempt < retries:
                time.sleep(0.5 * (attempt + 1))
                continue
            return {"domain": domain,
                    "rdap_status": f"CHECK_NEEDED_HTTP{e.code}",
                    "registrar": "", "expires": ""}
        except Exception as e:
            if attempt < retries:
                time.sleep(0.5 * (attempt + 1))
                continue
            return {"domain": domain,
                    "rdap_status": f"CHECK_NEEDED_{type(e).__name__}",
                    "registrar": "", "expires": ""}
    return {"domain": domain, "rdap_status": "CHECK_NEEDED_TIMEOUT",
            "registrar": "", "expires": ""}


RESULT_DIR = "result"   # 결과 CSV 출력 디렉토리


def output_path(base_name: str) -> str:
    """result/ 디렉토리 아래에 타임스탬프가 붙은 CSV 경로를 만든다."""
    stem, _ = os.path.splitext(base_name)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    return os.path.join(RESULT_DIR, f"{stem}_{stamp}.csv")


def run_scan(domains, output_file: str, workers: int = MAX_WORKERS,
             delay: float = 0.0, retries: int = 2, desc: str = "도메인",
             check_fn=None, fieldnames=None):
    """도메인 iterable을 스캔해 결과를 result/<이름>_<시각>.csv에 증분 저장한다.

    완료 순서대로 기록되므로 파일은 알파벳순이 아니다.
    check_fn/fieldnames를 생략하면 DNS NS 스캔(check_domain)으로 동작한다.
    domains는 지연 생성 iterable도 가능 - 전체를 메모리에 올리지 않고
    창(window) 단위로 제출해 대량 스캔 시 메모리를 절약한다.
    """
    check_fn = check_fn or check_domain
    fieldnames = fieldnames or FIELDNAMES
    start_time = time.time()
    done = 0
    path = output_path(output_file)
    os.makedirs(RESULT_DIR, exist_ok=True)
    window = max(workers * 20, 1000)   # 동시 대기 future 상한

    print(f"{desc} 검사 시작", flush=True)
    print(f"출력 파일: {path}", flush=True)

    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        pending = set()
        exhausted = False
        it = iter(domains)
        with ThreadPoolExecutor(max_workers=workers) as executor:
            while True:
                while not exhausted and len(pending) < window:
                    try:
                        d = next(it)
                    except StopIteration:
                        exhausted = True
                        break
                    pending.add(executor.submit(check_fn, d, retries, delay))
                if not pending:
                    break
                finished, pending = wait(pending, return_when=FIRST_COMPLETED)
                for future in finished:
                    writer.writerow(future.result())
                done += len(finished)
                if done % 1000 < len(finished) or (exhausted and not pending):
                    f.flush()  # 중간 저장 - 중단돼도 진행분 유지
                    elapsed = time.time() - start_time
                    rate = done / elapsed if elapsed else 0
                    print(f"[{done:,} 완료] ({elapsed:.0f}초 경과, {rate:.0f}건/초)", flush=True)

    print(f"저장 완료: {path} (총 {time.time() - start_time:.1f}초, {done:,}개)", flush=True)
