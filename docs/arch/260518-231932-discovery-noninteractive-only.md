# ADR: Discovery 는 non-interactive 세션만 대상

- Date: 2026-05-18
- Status: Superseded by [260520-093830-discovery-all-agents-inline-filter.md](./260520-093830-discovery-all-agents-inline-filter.md)

## Context

`pgrep claude` 또는 `pgrep codex` 는 인터랙티브 TUI 세션과 non-interactive (`-p` / `exec`) 세션을 구분하지 않는다. amon 의 Mode B discovery 가 어디까지 포함할지 결정해야 한다.

## Options considered

- **(A) 모든 claude/codex 프로세스 포함** — interactive + non-interactive 둘 다.
- **(B) Non-interactive 만 포함** — argv 필터:
  - `claude` 프로세스 중 argv 에 `-p` 또는 `--print` 포함
  - `codex` 프로세스 중 첫 번째 sub-arg 가 `exec`
- **(C) 사용자가 명시적으로 PID 지정** — discovery 없음, `--pid <pid>` 강제.

## Decision

**(B) Non-interactive 만 포함** 채택.

## Rationale

- Interactive 세션은 사용자가 직접 TUI 를 보고 있으므로 별도 모니터 가치가 낮음. amon 은 자동화/백그라운드 컨텍스트 ("내가 못 보고 있는 동안 잘 돌고 있나") 를 위함.
- argv 기반 필터링은 `ps -o command=` 로 단순 구현 가능. 휴리스틱이지만 mac/linux 양쪽 동작.
- (A) 는 사용자가 활성 TUI 들을 모니터에서 보면서 혼란. (C) 는 자동 발견의 가치 상실.

## Consequences

- **Wrapper script 가 spawn 한 claude/codex 도 동일 필터 적용** — wrapper 가 `-p` 를 박았으면 발견됨. 다른 의미의 invocation (예: `claude doctor`) 는 자동 제외.
- argv 가 (sub)process namespace 너머에 가려진 환경 — 예: container 내부에서 host 의 ps 로 보는 경우 — 에서는 작동 안 함. amon 은 same-host 사용 가정.
- 신규 sub-command (예: `claude mcp serve`) 가 등장하면 argv 필터를 업데이트해야 함. Plan 의 discovery 함수 코멘트에 명시.
- `--include-interactive` 같은 escape hatch 는 일단 미제공. 필요해지면 별도 ADR.
