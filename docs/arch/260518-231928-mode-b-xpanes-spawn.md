# ADR: Mode B = xpanes spawn (in-process multiplex 미채택)

- Date: 2026-05-18
- Status: Accepted

## Context

Mode B 는 "모든 활성 agent 세션을 실시간으로" 모니터링한다. 다중 세션을 사용자에게 보이는 방식을 결정해야 한다.

## Options considered

- **(A) In-process multiplex** — 단일 amon 프로세스가 모든 세션 jsonl 을 동시 tail 하고, `[agent/sid] ...` prefix 로 한 stream 에 모두 흘려보냄. 사용자가 grep/awk 로 분리.
- **(B) xpanes spawn** — amon 이 활성 세션 목록을 발견한 뒤 `xpanes -c 'amon --session-id {}' <sid1> <sid2> ...` 를 호출. xpanes 가 tmux pane 을 세션 수만큼 생성하고 각 pane 에 단일 세션 모니터 1개씩 분배.
- **(C) 내장 TUI** — blessed/textual 같은 lib 으로 다중 pane 시각화를 amon 자체에 내장.

## Decision

**(B) xpanes spawn** 채택.

## Rationale

- amon 자체는 **항상 단일 세션만 담당** 하는 단순 모델이 됨. Mode A 와 Mode B 가 spawn 된 monitor 입장에서는 구분이 없음 — Mode B 는 사실상 *"discover + xpanes launcher"* 일 뿐.
- 사용자가 시각적으로 세션을 분리 보기를 원함. (A) 의 prefix 방식은 정신없음.
- (C) 내장 TUI 는 외부 lib 의존 + Python stdlib only 제약 위반 + 구현 비용 큼.
- xpanes 는 tmux 기반이라 mac/linux 양쪽 동작. 사용자가 이미 xpanes 워크플로우에 익숙함.

## Consequences

- **xpanes hard requirement** — 없으면 Mode B 가 error 로 거부. fallback 없음. 사용자가 직접 설치 (`brew install tmux/xpanes` 또는 패키지매니저). 이는 의도된 trade-off.
- **Dynamic discovery 불가** — xpanes 가 시작 시 pane 분배를 끝내므로, Mode B 실행 후 새로 뜬 agent 세션은 보이지 않음. 사용자가 재실행 필요. 자동 tmux pane 추가는 의도적으로 미지원 (별도 ADR 없음 — 자명한 trade-off).
- 모니터 한 인스턴스의 코드가 단순해지고, Mode A/B 의 코드 경로가 거의 같아짐.
- xpanes 가 만드는 tmux 세션 내부에서 동작하므로 `--color=always` 가 자연스럽게 작동 (각 pane 이 pty).
