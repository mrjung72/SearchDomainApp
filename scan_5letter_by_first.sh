#!/usr/bin/env bash
# 5글자 .com 도메인을 첫 글자(a~z)별로 나눠 스캔하는 쉘 스크립트
# 결과는 result/com_regex_<첫글자>_a_z_4_com_check_YYYYMMDD_HHMMSS.csv 로 자동 저장됨
# 사용법: bash scan_5letter_by_first.sh  (또는 ./scan_5letter_by_first.sh)

cd "$(dirname "$0")" || exit 1

for L in {a..z}; do
    echo
    echo "===== $L ====="
    python com_regex_domain_checker.py "^${L}[a-z]{4}\.com$"
    if [ $? -ne 0 ]; then
        echo "[오류] $L 스캔 실패 - 계속 진행합니다."
    fi
done

echo
echo "전체 스캔 완료. 결과는 result/ 폴더를 확인하세요."
