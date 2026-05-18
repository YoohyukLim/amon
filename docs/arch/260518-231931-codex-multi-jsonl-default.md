# ADR: Codex multi-jsonl default = 최신 mtime 1개

- Date: 2026-05-18
- Status: Accepted

## Context

`lsof` 실측에서 codex 한 프로세스 (PID 35933) 가 jsonl 을 동시에 3개 열고 있는 케이스가 관찰됨:

```
codex 35933 ... 37w ... rollout-2026-05-18T14-19-30-019e3986...jsonl
codex 35933 ... 41w ... rollout-2026-05-18T21-20-17-019e3b07...jsonl
codex 35933 ... 53w ... rollout-2026-05-18T21-23-11-019e3b0a...jsonl
```

Mode B discovery 가 codex PID 를 발견했을 때, 이 다중 jsonl 을 어떻게 처리할지 결정해야 한다.

## Options considered

- **(A) 최신 mtime 1개만 선택** — "활성 turn 수행 중인" 세션은 하나라고 가정.
- **(B) 모든 jsonl 을 분리 pane 으로 spawn** — Mode B 가 codex 1 PID → 3 session 이면 xpanes 입력 목록에 3개 추가.
- **(C) 사용자가 매번 prompt 받음** — 다중 jsonl 발견 시 어느 것 선택할지 인터랙티브로.

## Decision

**(A) 최신 mtime 1개만 선택** 을 default. `--codex-all-sessions` flag 로 (B) 동작 활성화.

## Rationale

- 사용자 멘탈 모델: "지금 일하고 있는" 세션 1개를 보고 싶음. archive/idle 세션이 함께 spawn 되면 pane 수가 폭발 (3 codex → 9 pane).
- 다중 jsonl 의 의미는 codex 내부 구현 디테일 (세션 rollover, 백그라운드 thread 등). 사용자가 매번 의식하기 부담.
- 그러나 정말로 3개 모두 활성인 케이스 (병렬 codex 작업) 가 있을 수 있으므로 `--codex-all-sessions` 로 escape hatch 제공.
- (C) interactive prompt 는 Mode B 의 "그냥 `amon` 만 치면 다 알아서" 멘탈 모델 깨뜨림.

## Consequences

- **단일 PID 다중 활성 세션을 보는 데 추가 flag 필요** — 일반적이지 않은 use case 라 OK 판단.
- "최신 mtime" 휴리스틱이 틀릴 수 있음 — 두 세션이 동시 진행 중이면 잘못된 쪽을 선택할 가능성. 사용자가 발견하면 `--codex-all-sessions` 사용.
- Claude 는 lsof 에 jsonl fd 자체가 안 잡히므로 이 ADR 은 codex 전용. Claude 의 PID→jsonl 매핑은 cwd 기반 별도 처리 (Plan Task 2 참조).
