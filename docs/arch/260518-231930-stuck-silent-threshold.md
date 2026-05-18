# ADR: Stuck 판정은 단순 silent 임계치 (tool 실행 구분 안 함)

- Date: 2026-05-18
- Status: Accepted

## Context

"stuck/idle" 판정은 amon 의 핵심 가치 중 하나다 (사용자가 명시한 최우선 signal). 그러나 "마지막 이벤트 후 60초 침묵" 이 실제로 의미하는 바는 여러 가지다.

| 상황 | jsonl 동작 |
|---|---|
| API 응답 대기 중 | jsonl write 없음 (LLM 응답 stream 도착 전) |
| 긴 Bash 명령 실행 중 (npm install, pytest) | jsonl write 없음 (tool 결과는 명령 완료 후 1회) |
| 정말 멈춤 (네트워크 hang, deadlock) | jsonl write 없음 |

세 경우 모두 동일하게 보이지만 의미가 다르다.

## Options considered

- **(A) 단순 silent 임계치** — 마지막 event 후 N초 침묵이면 모두 stuck. 단순.
- **(B) Tool 실행 중 제외** — 마지막 event 가 `tool_use_start` 류면 임계치 완화 (예: 5분), `assistant_message` 끝나고 침묵이면 짧은 임계치 (예: 60s).
- **(C) 별도 추적 + 두 임계치** — `tool_running_for` 와 `awaiting_llm_for` 를 분리 측정하고 각각 다른 임계치.

## Decision

**(A) 단순 silent 임계치** 채택. default 60초, `--idle-threshold` flag 로 조정.

## Rationale

- (B)/(C) 는 정확하지만 event type 매핑이 claude/codex 사이에 일관되지 않음. claude 의 `tool_use_start` ↔ codex 의 `function_call` 차이를 정밀하게 추적하려면 event normalization 레이어가 비대해짐 — YAGNI.
- 단순성 우선 가치 (CLAUDE.md "Simplicity First"). false positive 가 발생해도 사용자가 임계치를 늘리는 단일 dial 로 대응 가능.
- 사용자가 명시적으로 "표시만 (default 60s)" 선택 — auto-action (kill, notify) 이 없으므로 false positive 비용이 낮다.

## Consequences

- 긴 Bash 명령 실행 중 (`npm test`, `cargo build`) 도 60초 넘으면 `⚠ idle 60s` 표시됨. 사용자가 컨텍스트로 판단해야 함 — false positive 명확히 문서화.
- 사용자가 자주 false positive 보면 `--idle-threshold 300` 같은 식으로 alias 만들거나, 향후 (B) 로 superseded 가능.
- 정밀한 stuck 추적이 필요해지면 이 ADR 을 deprecate 하고 새 ADR 작성.
