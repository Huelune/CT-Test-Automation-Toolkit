# 커밋 규칙

Git 커밋을 생성하거나 제안할 때 따르는 규칙입니다. 사람과 에이전트 모두에게
적용됩니다.

## 가장 중요한 기준

**커밋 로그만 읽어도 프로젝트가 어떤 이유로 어떻게 변화했는지 파악할 수 있어야
합니다.**

커밋 수를 최소화하는 것보다 다음을 우선합니다.

- 변경 목적의 명확성
- 독립적인 롤백 가능성
- 변경 이력 추적 가능성

## 기본 원칙

**하나의 커밋에는 하나의 논리적 변경만 포함합니다.**

- 파일 개수가 아니라 변경 목적을 기준으로 나눕니다.
- 서로 독립적으로 롤백할 수 있는 변경은 별도 커밋으로 분리합니다.
- 기능 추가 + 관련 없는 리팩터링 + 문서 수정을 한 커밋에 섞지 않습니다.

메시지는 **Conventional Commits 형식**을 기본으로 합니다.

```text
<type>: <summary>
```

필요한 경우에만 scope를 붙입니다.

```text
<type>(<scope>): <summary>
```

`summary`는 변경한 파일이 아니라 **무엇을 왜 변경했는지**가 드러나게 씁니다.

| | 예 |
| --- | --- |
| 좋음 | `fix: prevent duplicate test IDs for same function names` |
| 좋음 | `feat: add coverage summary export from CT report` |
| 좋음 | `refactor: separate CLI.ini generation from UtCLI execution` |
| 좋음 | `test: add report parsing cases for empty coverage rows` |
| 나쁨 | `fix: update code` |
| 나쁨 | `chore: modify files` |
| 나쁨 | `feat: add function` |
| 나쁨 | `fix: bug fix` |

## Type

| type | 쓰는 경우 |
| --- | --- |
| `feat` | 새로운 기능 또는 기존 기능의 의미 있는 확장 |
| `fix` | 실제 오류나 잘못된 동작 수정 |
| `refactor` | 동작 변경 없이 구조 개선 |
| `test` | 테스트 코드, 테스트 케이스, 검증 로직 변경 |
| `docs` | 문서만 변경 |
| `chore` | 설정, 빌드, 환경, 의존성, 기타 유지보수 |
| `perf` | 성능 개선 |
| `style` | 포맷팅처럼 동작에 영향을 주지 않는 변경 |
| `revert` | 기존 커밋 되돌리기 |

`chore`를 의미 없이 남발하지 않습니다. 기능이나 버그 수정이면 각각 `feat`, `fix`를
우선합니다.

## Scope

scope는 **명확하게 도움이 될 때만** 씁니다.

```text
feat(cli): support target function filter in CLI.ini
fix(report): read MC/DC column when branch column is empty
refactor(report): separate sheet reading and summary logic
```

프로젝트 구조가 자주 바뀔 수 있으므로 폴더 경로나 지나치게 세부적인 모듈명을
scope로 고정하지 않습니다.

## 커밋 분리 기준

다음은 가능하면 별도 커밋으로 분리합니다.

- 새로운 기능 구현
- 기존 버그 수정
- 대규모 리팩터링
- 테스트 추가·수정
- 설정 또는 dependency 변경
- 생성 파일이나 결과물 변경

단, 어떤 기능을 구현하려면 반드시 함께 바뀌어야 하고 따로 떼면 의미가 없는
변경은 하나의 커밋으로 유지합니다.

**커밋 개수를 억지로 늘리지 않습니다.** 작은 변경 여러 개가 하나의 목적을
이루면 하나로 묶습니다.

### CHANGELOG는 해당 커밋에 포함합니다

`CHANGELOG.md` 항목은 그 변경을 만든 커밋에 함께 넣습니다. 별도 `docs` 커밋으로
빼면 기능 커밋만 되돌렸을 때 CHANGELOG에 없는 기능이 적힌 채로 남습니다.

같은 이유로, 변경과 분리하면 이력이 어긋나는 다른 파일도 함께 넣습니다.

### 리팩터링이 함께 일어날 때

기능 변경과 리팩터링이 동시에 발생하면 가능하면 순서대로 분리합니다.

```text
refactor: ...
feat: ...
```

```text
refactor: ...
fix: ...
```

기능 구현 과정에서 필요한 작은 구조 변경이라면 불필요하게 분리하지 않습니다.

## 메시지 작성 방식

- 한 줄 summary는 짧고 명확하게 씁니다.
- 구현 방법보다 결과와 의도를 우선합니다.
- `updated`, `changed`, `modified`처럼 정보량이 적은 표현은 피합니다.
- 같은 내용의 커밋 메시지를 반복하지 않습니다.
- `WIP`, `temp`, `test123`, `final`, `final2` 같은 메시지는 쓰지 않습니다.
- 코드 내용을 확인하지 않고 커밋 메시지를 추측하지 않습니다.

### Body

변경 이유가 summary만으로 부족할 때에만 body를 씁니다.

```text
fix(report): handle duplicate function names across source files

Use a stable identifier instead of the function name alone because
different source files can contain functions with identical names.

This prevents unrelated verification results from being merged.
```

body에는 다음 중 필요한 것만 담습니다.

- 왜 변경했는지
- 기존 방식의 문제
- 중요한 설계 결정
- 호환성 또는 영향 범위

코드를 그대로 설명하는 장황한 body는 쓰지 않습니다.

## Breaking Change

기존 사용 방법이나 API가 깨지면 반드시 명시합니다.

```text
feat!: change summary output structure
```

필요하면 body 하단에 추가합니다.

```text
BREAKING CHANGE: summary rows now use stable function identifiers.
```

## 에이전트 작업 시 추가 규칙

코드 수정이 끝나도 바로 커밋하지 않고 먼저 변경 내용을 분석합니다.

1. `git diff`와 변경 파일을 확인합니다.
2. 변경사항을 논리적인 단위로 분류합니다.
3. 커밋별 포함 파일·변경 영역을 결정합니다.
4. 서로 다른 목적의 변경이 섞였으면 분리합니다.
5. 각 커밋 메시지를 위 규칙으로 작성합니다.
6. 테스트 실패나 미완성 코드가 있으면 커밋 전에 사용자에게 알립니다.

사용자가 명시적으로 요청하지 않는 한 기존 history를 rewrite하거나 squash,
force push하지 않습니다.

여러 커밋이 필요하면 먼저 계획을 제시합니다.

```text
1. refactor(cli): separate CLI.ini generation
2. feat(report): add coverage summary from CT report
3. test(report): add empty coverage row cases
4. docs: document report summary workflow
```

그 후 각 변경을 해당 커밋에만 포함합니다.

## 에이전트 커밋 꼬리말

에이전트가 만든 커밋은 끝에 `Co-Authored-By:` 줄을 붙인다. 사람 혼자 만든 커밋에는
붙이지 않는다.
