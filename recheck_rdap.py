"""스캔 결과 CSV에서 NXDOMAIN 등 미등록 후보를 RDAP로 정확히 재검증합니다.

사용 예:
    python recheck_rdap.py result/com_3letter_check_20261121_120000.csv
    python recheck_rdap.py result/                      # result/ 내 전체 CSV
    python recheck_rdap.py result/a.csv result/b.csv --status NO_NS_ANSWER
"""
import argparse
import csv
import glob
import os

from domain_checker_utils import (
    MAX_WORKERS, RDAP_FIELDS, rdap_check, run_scan,
)

DEFAULT_STATUS = "NO_DNS_NXDOMAIN"   # 재검증 대상 기본 상태


def collect_domains(paths: list, statuses: set) -> list:
    """CSV 파일들에서 지정 상태의 도메인을 중복 제거해 수집한다."""
    domains = []
    seen = set()
    files = []
    for p in paths:
        if os.path.isdir(p):
            files.extend(sorted(glob.glob(os.path.join(p, "*.csv"))))
        else:
            files.append(p)
    for path in files:
        # Excel(.xlsx) 등 바이너리 파일이 .csv로 저장된 경우 명확히 안내
        with open(path, "rb") as bf:
            if bf.read(4) == b"PK\x03\x04":
                raise SystemExit(
                    f"오류: {path} 는 CSV가 아니라 Excel(.xlsx) 파일입니다.\n"
                    "Excel에서 '다른 이름으로 저장 → CSV UTF-8'로 저장 후 다시 시도하세요.")
        rows = read_csv_rows(path)
        for row in rows:
            if row.get("status") in statuses and row.get("domain"):
                d = row["domain"].strip().lower()
                if d not in seen:
                    seen.add(d)
                    domains.append(d)
        print(f"읽음: {path}")
    return domains


def read_csv_rows(path: str):
    """CSV/TSV를 읽는다 — 구분자 자동 감지, 인코딩은 UTF-8(BOM)→CP949 폴백."""
    for enc in ("utf-8-sig", "cp949", "euc-kr", "utf-8", "latin-1"):
        try:
            with open(path, newline="", encoding=enc) as f:
                sample = f.read(8192)
                f.seek(0)
                try:
                    dialect = csv.Sniffer().sniff(
                        sample, delimiters=",\t;|")
                except csv.Error:
                    dialect = csv.excel
                return list(csv.DictReader(f, dialect=dialect))
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("utf-8", b"", 0, 1, f"{path}: 읽을 수 없는 인코딩")


def main():
    parser = argparse.ArgumentParser(
        description="NXDOMAIN 등 미등록 후보를 RDAP로 재검증합니다.")
    parser.add_argument(
        "paths", nargs="+",
        help="결과 CSV 파일 또는 result/ 디렉토리 (복수 지정 가능)")
    parser.add_argument(
        "--status", default=DEFAULT_STATUS,
        help=f"재검증할 상태 (쉼표 구분). 기본값: {DEFAULT_STATUS}")
    parser.add_argument(
        "--workers", type=int, default=MAX_WORKERS,
        help=f"동시 조회 수. 기본값: {MAX_WORKERS}")
    parser.add_argument(
        "--delay", type=float, default=0.0,
        help="워커당 조회 전 대기 시간(초). 기본값: 0")
    args = parser.parse_args()

    statuses = {s.strip() for s in args.status.split(",") if s.strip()}
    domains = collect_domains(args.paths, statuses)

    if not domains:
        print("재검증 대상 도메인이 없습니다.")
        return

    run_scan(
        domains,
        "rdap_recheck.csv",
        workers=args.workers,
        delay=args.delay,
        desc=f"RDAP 재검증 ({'/'.join(sorted(statuses))})",
        check_fn=rdap_check,
        fieldnames=RDAP_FIELDS,
    )


if __name__ == "__main__":
    main()
