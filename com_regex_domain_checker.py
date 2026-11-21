def parse_args():
    parser = argparse.ArgumentParser(
        description="정규식 패턴에 매칭되는 .com 도메인의 DNS 등록 여부를 확인합니다."
    )
    parser.add_argument(
        "pattern",
        help=r"검색할 전체 도메인명 정규식 패턴입니다. 예: ^[a-z]{3}\.com$",
    )
    parser.add_argument(
        "--max-length",
        type=int,
        default=DEFAULT_MAX_LENGTH,
        help=f"생성할 도메인 이름의 최대 문자 개수입니다. 기본값: {DEFAULT_MAX_LENGTH}",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=MAX_WORKERS,
        help=f"동시 조회 스레드 수입니다. 기본값: {MAX_WORKERS}",
    )
    return parser.parse_args()


def build_domains(pattern: str, max_length: int) -> list[str]:
    compiled_pattern = re.compile(pattern)
    domains = []

    for length in range(1, max_length + 1):
        for chars in itertools.product(string.ascii_lowercase, repeat=length):
            domain = f"{''.join(chars)}.com"
            if compiled_pattern.fullmatch(domain):
                domains.append(domain)

    return domains


def main():
    args = parse_args()

    if args.max_length <= 0:
        raise ValueError("최대 문자 개수는 1 이상이어야 합니다.")

    safe_pattern_name = re.sub(r"[^a-zA-Z0-9]+", "_", args.pattern).strip("_")
    output_file = f"com_regex_{safe_pattern_name}_check.csv"

    domains = build_domains(args.pattern, args.max_length)

    if not domains:
        print("정규식 패턴에 매칭되는 도메인이 없습니다.")
        return

    start_time = time.time()
    results = []

    print("정규식 기반 .com 도메인 검사 시작")
    print(f"검색 패턴: {args.pattern}")
    print(f"최대 문자 개수: {args.max_length}")
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
