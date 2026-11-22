"""지정한 글자 수의 .com 도메인 DNS 등록 여부를 확인합니다.

사용 예:
    python com_domain_dns_checker.py 3          # 3글자 .com 17,576개
    python com_domain_dns_checker.py 4 --workers 50 --delay 0.05
"""
import argparse

from domain_checker_utils import (
    DEFAULT_MAX_LENGTH, MAX_WORKERS, iter_domains_by_length, run_scan,
)


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
    parser.add_argument(
        "--delay",
        type=float,
        default=0.0,
        help="워커당 조회 전 대기 시간(초) - 속도 제한용. 기본값: 0",
    )
    parser.add_argument(
        "--digits",
        action="store_true",
        help="후보에 숫자 0-9를 포함합니다 (기본: 영문 a-z만). "
             "포함 시 조회 수가 약 2배(3글자)~3.6배(4글자)로 증가합니다.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if args.length <= 0:
        raise ValueError("문자 개수는 1 이상이어야 합니다.")

    output_file = f"com_{args.length}letter_check.csv"
    run_scan(
        iter_domains_by_length(args.length, with_digits=args.digits),
        output_file,
        workers=args.workers,
        delay=args.delay,
        desc=f"{args.length}글자 .com 도메인",
    )


if __name__ == "__main__":
    main()
