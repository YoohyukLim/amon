# ADR: Single command + flag (subcommand 미채택)

- Date: 2026-05-18
- Status: Accepted

## Context

amon 은 세 가지 동작 모드를 제공한다.
1. Mode A tail — 특정 session 의 실시간 이벤트 스트림
2. Mode A snapshot — 특정 session 의 1줄 status (CI/script 용)
3. Mode B — 모든 활성 agent 세션을 발견하고 xpanes 로 모니터를 분배

CLI 표면을 어떻게 노출할지 두 가지 안이 가능했다.

## Options considered

- **(A) 단일 명령 + flag** — `amon`, `amon --session-id X`, `amon --session-id X --once`
- **(B) 서브커맨드 분리** — `amon watch`, `amon tail X`, `amon snapshot X`

## Decision

**(A) 단일 명령 + flag** 채택.

## Rationale

- 세 모드의 핵심 동작은 모두 *"jsonl tail + event → line format"* 의 변형이다. 코어 로직이 단일 함수 (tail loop) 이고, snapshot 은 그 로프의 1회 호출 + 종료, Mode B 는 그 로프의 N개 spawn 일 뿐이다.
- 명령이 3개뿐이어서 서브커맨드 분리는 과한 indirection — 사용자가 `--help` 한 번에 전체 인터페이스를 본다.
- argparse 만으로 구현 가능 → click/typer 의존성 회피 (Python stdlib only 제약).
- 단축 호출이 짧다: `amon` 한 단어가 Mode B 진입점.

## Consequences

- 새 모드가 늘면 flag 가 비대해질 수 있다. 4개 모드 이상이 되면 서브커맨드로 재구조화 검토.
- snapshot 과 tail 의 분기가 `--once` 한 flag 에 묶여 있어서 모르는 사용자가 발견하기 어려움. `--help` 출력에 예시 3개를 박아 보완.
- Mode B 가 인자 0개로 동작 = "그냥 `amon` 만 치면 다 알아서" 라는 멘탈 모델. 의도에 부합.
