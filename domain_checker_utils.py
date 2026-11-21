"""공용 .com 도메인 DNS 스캔 유틸리티.

- NS 레코드 조회로 등록 여부 판정 (NXDOMAIN ≈ 미등록)
- 스레드별 Resolver 재사용, 타임아웃 재시도, 증분 CSV 저장
"""
import csv
import itertools
import re
import string
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
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
    delay:   조회 전 대기 시간(초) — 워커당 속도 제한용
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
            # 도메인은 존재하나 NS 레코드 없음 — 등록됐으나 위임 정보 없음
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


def build_domains_by_pattern(pattern: str, max_length: int,
                             charset: str = None) -> list:
    """정규식 패턴에 fullmatch 되는 .com 도메인 목록을 만든다.

    charset을 생략하면 패턴에서 숫자 허용 여부를 자동 판별한다.
    """
    compiled = re.compile(pattern)
    if charset is None:
        charset = candidate_charset(pattern)
    domains = []
    for length in range(1, max_length + 1):
        for chars in itertools.product(charset, repeat=length):
            domain = f"{''.join(chars)}.com"
            if compiled.fullmatch(domain):
                domains.append(domain)
    return domains


def run_scan(domains, output_file: str, workers: int = MAX_WORKERS,
             delay: float = 0.0, retries: int = 2, desc: str = "도메인"):
    """도메인 iterable을 스캔해 결과를 CSV에 증분 저장한다.

    완료 순서대로 기록되므로 파일은 알파벳순이 아니다.
    """
    domains = list(domains)
    total = len(domains)
    start_time = time.time()
    done = 0

    print(f"{desc} 검사 시작")
    print(f"총 검사 대상: {total:,}개")
    print(f"출력 파일: {output_file}")

    with open(output_file, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [
                executor.submit(check_domain, d, retries, delay)
                for d in domains
            ]
            for future in as_completed(futures):
                writer.writerow(future.result())
                done += 1
                if done % 1000 == 0 or done == total:
                    f.flush()  # 중간 저장 — 중단돼도 진행분 유지
                    elapsed = time.time() - start_time
                    print(f"[{done}/{total:,}] 완료 ({elapsed:.1f}초 경과)")

    print(f"저장 완료: {output_file} (총 {time.time() - start_time:.1f}초)")
