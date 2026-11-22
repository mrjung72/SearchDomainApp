"""정규식 패턴에 매칭되는 .com 도메인의 DNS 등록 여부를 확인합니다.

사용 예:
    python com_regex_domain_checker.py "^[a-z]{3}\\.com$"
    python com_regex_domain_checker.py "^a.*b\\.com$" --max-length 5 --workers 50
"""
import argparse
import itertools
import re

from domain_checker_utils import (
    DEFAULT_MAX_LENGTH, MAX_WORKERS, candidate_charset,
    build_domains_by_pattern, required_length_hint, run_scan,
)


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
    parser.add_argument(
        "--delay",
        type=float,
        default=0.0,
        help="워커당 조회 전 대기 시간(초) - 속도 제한용. 기본값: 0",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if args.max_length <= 0:
        raise ValueError("최대 문자 개수는 1 이상이어야 합니다.")

    # 패턴 앞뒤를 제외한 중간에 ^ 또는 $가 있으면 전형적인 오타 가능성 경고
    body = args.pattern
    inner = body[1:] if body.startswith("^") else body
    inner = inner[:-1] if inner.endswith("$") else inner
    if "^" in inner or "$" in inner:
        print("[경고] 패턴 중간에 ^ 또는 $가 있습니다 - "
              "도메인 전체 패턴은 보통 ^[a-z]{3}\\.com$ 형태입니다.", flush=True)
        print("   패턴을 확인하세요. (예: ^[a-z]{5}\\.com$)", flush=True)

    # 패턴의 {n}/{n,m} 수량자가 요구하는 길이가 max-length보다 크면 자동 보정
    hint = required_length_hint(args.pattern)
    if hint and args.max_length < hint:
        print(f"참고: 패턴이 최소 {hint}글자를 요구하여 "
              f"--max-length를 {hint}로 자동 조정합니다.", flush=True)
        args.max_length = hint

    safe_pattern_name = re.sub(r"[^a-zA-Z0-9]+", "_", args.pattern).strip("_")
    output_file = f"com_regex_{safe_pattern_name}_check.csv"

    # 생성 전에 규모를 추정해 경고 (charset^max_length는 상한 추정치)
    charset = candidate_charset(args.pattern)
    estimate = len(charset) ** args.max_length
    if estimate > 100_000:
        print(f"[경고] 패턴이 최대 약 {estimate:,}개 이상의 후보를 만들 수 있습니다 "
              f"(문자셋 {len(charset)}자 × 최대 {args.max_length}글자).", flush=True)
        print("   실제 매칭 수는 패턴에 따라 줄어들 수 있지만, "
              "규모가 크면 완료까지 상당 시간이 걸립니다.", flush=True)
        print("   패턴을 더 좁히거나 --workers/--delay로 속도를 조절하세요.", flush=True)

    domains = build_domains_by_pattern(args.pattern, args.max_length)
    first = next(domains, None)  # 지연 생성기 - 첫 후보 존재 여부만 확인
    if first is None:
        print("정규식 패턴에 매칭되는 도메인이 없습니다.", flush=True)
        return
    domains = itertools.chain([first], domains)

    run_scan(
        domains,
        output_file,
        workers=args.workers,
        delay=args.delay,
        desc=f"정규식 {args.pattern} (최대 {args.max_length}글자)",
    )


if __name__ == "__main__":
    main()
