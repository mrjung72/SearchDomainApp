import csv
import itertools
import string
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import dns.resolver

OUTPUT_FILE = "com_3letter_check.csv"
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


def main():
    domains = [
        f"{''.join(chars)}.com"
        for chars in itertools.product(string.ascii_lowercase, repeat=3)
    ]

    start_time = time.time()
    results = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(check_domain, d): d for d in domains}
        for idx, future in enumerate(as_completed(futures), start=1):
            results.append(future.result())
            if idx % 1000 == 0 or idx == len(domains):
                elapsed = time.time() - start_time
                print(f"[{idx}/{len(domains)}] 완료 ({elapsed:.1f}초 경과)")

    # 알파벳순 정렬 후 CSV 저장
    results.sort(key=lambda x: x["domain"])
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["domain", "status", "ns"])
        writer.writeheader()
        writer.writerows(results)

    print(f"저장 완료: {OUTPUT_FILE} (총 {time.time() - start_time:.1f}초)")


if __name__ == "__main__":
    main()