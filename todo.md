# 서버 PC 실행 요청

작성: 2026-10-27. 결과를 붙여 주면 해당 절은 지운다.

명령은 서버 PC의 `cmd`에서 저장소 루트로 이동한 뒤 그대로 붙여 넣는다. 화면에는 개수, CT
플러그인 폴더 이름(버전), 정해 둔 안내 문구만 찍는다. 고객 소스의 함수·파일 이름, 경로,
계정은 찍지 않는다(회사 내부 정보).

## 1. 서버 PC 환경 점검

**왜:** CT를 부르는 기능을 만들기 전에 서버 PC에서 Python이 도는지, `UtCLI.exe`를 찾을 수
있는지, 실행 로그를 쓸 수 있는지 확인한다. CT 버전도 여기서 알 수 있다. 1분.

처음 한 번만 클론한다(이미 있으면 `git pull`).

```bat
git clone https://github.com/Huelune/CT-Test-Automation-Toolkit.git
cd CT-Test-Automation-Toolkit
```

`<CT 설치 폴더>`를 실제 위치로 바꿔 붙여 넣는다. `UtCLI.exe` 위치를 알면 `CT_HOME` 대신
`set CT_UTCLI=<UtCLI.exe 전체 경로>`도 된다.

```bat
cls
set CT_HOME=<CT 설치 폴더>
ct.bat selfcheck
echo exit=%ERRORLEVEL%
```

**확인할 것:** 마지막 줄 근처 `필수 통과 3 / 3`, `exit=0`. `UtCLI.exe` 줄의 괄호 안에 CT 플러그인
폴더 이름(버전)이 찍힌다. FAIL 줄에는 이유가 같이 찍힌다.

**돌려줄 것:** 화면 캡처 한 장. 그리고 CT 메뉴 Help > About의 CT 버전(예: 2026.06).
