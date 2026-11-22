@echo off
rem 5글자 .com 도메인을 첫 글자(a~z)별로 나눠 스캔하는 배치 파일
rem 결과는 result/com_regex_<첫글자>_a_z_4_com_check_YYYYMMDD_HHMMSS.csv 로 자동 저장됨
cd /d %~dp0

for %%L in (a b c d e f g h i j k l m n o p q r s t u v w x y z) do (
    echo.
    echo ===== %%L =====
    python com_regex_domain_checker.py "^%%L[a-z]{4}\.com$"
    if errorlevel 1 (
        echo [오류] %%L 스캔 실패 - 계속 진행합니다.
    )
)

echo.
echo 전체 스캔 완료. 결과는 result/ 폴더를 확인하세요.
pause
