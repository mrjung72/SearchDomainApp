import argparse
import csv
import itertools
import string
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import dns.resolver

MAX_WORKERS = 30  # 동시 조회 스레드 수 (네트워크 상태에 맞게 조절)


def create_resolver() -> dns.resolver.Resolver:
    resolver = dns.resolver.Resolver()
    resolver.nameservers = ["8.8.8.8", "1.1.1.1", "9.9.9.9"]
    resolver.lifetime = 2.0
    resolver.timeout = 2.0
    return resolver


def check_domain(domain: str) -> dict:
    resolver = create_resolver()
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
        return {
            "domain": domain,
            "status": "NO_DNS_NXDOMAIN",
            "ns": "",
        }
    except (dns.resolver.NoAnswer, dns.resolver.LifetimeTimeout, dns.exception.DNSException) as e:
        return {
            "domain": domain,
            "status": f"CHECK_NEEDED_{type(e).__name__}",
            "ns": "",
        }


def parse_args():
    parser = argparse.ArgumentParser(
        description="지정한 글자 수의 .com 도메인 DNS 등록 여부를 확인합니다."
    )
    parser.add_argument(
        "length",
        type=int,
        help="검사할 도메인 이름의 문자 개수입니다. 예: 3",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=MAX_WORKERS,
        help=f"동시 조회 스레드 수입니다. 기본값: {MAX_WORKERS}",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if args.length <= 0:
        raise ValueError("문자 개수는 1 이상이어야 합니다.")

    output_file = f"com_{args.length}letter_check.csv"

    domains = [
        f"{''.join(chars)}.com"
        for chars in itertools.product(string.ascii_lowercase, repeat=args.length)
    ]

    start_time = time.time()
    results = []

    print(f"{args.length}글자 .com 도메인 검사 시작")
    print(f"총 검사 대상: {len(domains):,}개")
    print(f"출력 파일: {output_file}")

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(check_domain, d): d for d in domains}
        for idx, future in enumerate(as_completed(futures), start=1):
            results.append(future.result())
            if idx % 1000 == 0 or idx == len(domains):
                elapsed = time.time() - start_time
                print(f"[{idx}/{len(domains)}] 완료 ({elapsed:.1f}초 경과)")

    # 알파벳순 정렬 후 CSV 저장
    results.sort(key=lambda x: x["domain"])
    with open(output_file, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["domain", "status", "ns"])
        writer.writeheader()
        writer.writerows(results)

    print(f"저장 완료: {output_file} (총 {time.time() - start_time:.1f}초)")


if __name__ == "__main__":
    main()
