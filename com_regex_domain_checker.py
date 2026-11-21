"""정규식 패턴에 매칭되는 .com 도메인의 DNS 등록 여부를 확인합니다.

사용 예:
    python com_regex_domain_checker.py "^[a-z]{3}\\.com$"
    python com_regex_domain_checker.py "^a.*b\\.com$" --max-length 5 --workers 50
"""
import argparse
import re

from domain_checker_utils import (
    DEFAULT_MAX_LENGTH, MAX_WORKERS,
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
        help="워커당 조회 전 대기 시간(초) — 속도 제한용. 기본값: 0",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if args.max_length <= 0:
        raise ValueError("최대 문자 개수는 1 이상이어야 합니다.")

    # 패턴의 {n}/{n,m} 수량자가 요구하는 길이가 max-length보다 크면 자동 보정
    hint = required_length_hint(args.pattern)
    if hint and args.max_length < hint:
        print(f"참고: 패턴이 최소 {hint}글자를 요구하여 "
              f"--max-length를 {hint}로 자동 조정합니다.")
        args.max_length = hint

    safe_pattern_name = re.sub(r"[^a-zA-Z0-9]+", "_", args.pattern).strip("_")
    output_file = f"com_regex_{safe_pattern_name}_check.csv"

    domains = build_domains_by_pattern(args.pattern, args.max_length)

    if not domains:
        print("정규식 패턴에 매칭되는 도메인이 없습니다.")
        return

    if len(domains) > 100_000:
        print(f"⚠️  검사 대상이 {len(domains):,}개로 매우 많습니다 — "
              "완료까지 상당 시간이 걸릴 수 있습니다.")
        print("   패턴을 더 좁히거나 --workers/--delay로 속도를 조절하세요.")

    run_scan(
        domains,
        output_file,
        workers=args.workers,
        delay=args.delay,
        desc=f"정규식 {args.pattern} (최대 {args.max_length}글자)",
    )


if __name__ == "__main__":
    main()
