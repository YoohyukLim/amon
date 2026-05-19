# sessions mode implementation checklist

## 목표

`amon` 기본 실행을 여러 agent session을 목록으로 보는 sessions mode로 전환한다. 기존 xpane 패널 모드는 `amon xpane`으로 명시 실행하고, 단일 세션 모드는 `amon {session-id}`로 유지하되 새 상세 로그 UI를 공유한다.

## 확정 동작

- `amon`: 현재 실행 중인 모든 Claude/Codex 계열 agent session을 목록 TUI로 표시한다.
- `amon --current`: `realpath` 기준 현재 cwd와 그 하위 cwd에서 실행 중인 session만 표시한다.
- `amon xpane`: 기존 xpane 패널 모드를 실행하며 기본 scope는 all이다.
- `amon xpane --current`: xpane 대상도 현재 cwd 하위 scope로 제한한다.
- `amon {session-id}`: scope와 무관하게 전역에서 session을 찾고 상세 로그 UI로 표시한다.
- `--all` 옵션은 만들지 않는다.
- `--lines N`은 sessions mode에서 상세 진입할 때와 단일 session 상세 모두에 적용하며, 양의 정수만 허용한다.
- session discovery는 기존 xpane 대상 선정 로직을 공유하고 1초마다 재실행한다.
- 목록 row는 session-id 기준이며 session-id는 전역 유니크로 취급한다.
- 대표 상태는 `failed > running > unknown > exited` 우선순위로 집계한다.
- 목록 정렬은 기존 session-id 로그 파일 mtime 기반 최근 activity 순이며, activity가 없으면 맨 아래로 둔다.
- label은 metadata label/name/title을 우선하고, 없으면 command 요약, 없으면 session-id를 사용한다.
- 기본 all scope에서는 project를 표시하고 basename 충돌 시 뒤쪽 path segment를 추가해 구분한다.
- 목록에서 `/` 검색은 원본 label/title/command/session-id 기준으로 수행하고 정렬은 유지한다.
- 목록에서 `r`은 현재 보이는 종료 session만 현재 TUI 실행 동안 숨기며 summary count에서도 제외한다.
- 목록에서 새로 발견된 session은 3초 동안 highlight한다.
- 목록 `Enter`는 상세 로그 진입, 목록 `q`는 종료한다.
- 상세 로그는 최근 기본 200줄을 먼저 보여주고 상태에 따라 tail한다.
- 상세 로그는 running만 tail하고, unknown은 가능하면 tail을 시도하며, exited/failed는 정적 viewer로 표시한다.
- 상세 로그에서 사용자가 위로 스크롤하면 follow를 멈추고, 끝으로 이동하면 follow를 재개한다.
- 목록에서 진입한 상세의 `q`는 목록 복귀, 단일 `amon {session-id}` 상세의 `q`는 종료한다.

## 첫 버전 제외 범위

- 프로세스 stop/kill/restart
- CPU/MEM 표시
- 로그 상세 검색
- registry 영구 cleanup
- `--all` 옵션
- xpane 내부 구조 특별 취급
- interactive 여부 구분

## 작업 단계와 커밋 기준

### Stage 0. 계획 고정

- [x] 본 체크리스트를 작성한다.
- [x] 기존 커밋 메시지 스타일을 확인한다.
- [x] 계획 문서만 포함한 커밋을 만든다.

커밋 기준: `docs/tasks/260519-211154-sessions-mode-checklist.md`만 포함한다.

### Stage 1. discovery/scope/CLI 기반 정리

- [x] 기존 xpane session discovery 로직 위치를 확인한다.
- [x] 기존 단일 session 상태/로그 모드 위치를 확인한다.
- [x] discovery를 sessions mode와 xpane이 공유할 수 있는 단위로 분리한다.
- [x] all scope와 `--current` scope를 구현한다.
- [x] `amon`, `amon --current`, `amon xpane`, `amon xpane --current`, `amon {session-id}` 라우팅을 구현한다.
- [x] session-id도 아니고 `xpane`도 아닌 기존식 인자는 `amon xpane ...` 안내 에러를 낸다.
- [x] CLI routing과 scope 단위 테스트를 추가하거나 갱신한다.

커밋 기준: discovery/scope/CLI 변경과 관련 테스트만 포함한다.

### Stage 2. session aggregation과 목록 TUI

- [x] session-id 기준 aggregation 모델을 구현한다.
- [x] 대표 상태와 상태별 count를 계산한다.
- [x] label/title/command/session-id fallback을 구현한다.
- [x] project display disambiguation을 구현한다.
- [x] 1초 polling으로 새 session을 merge한다.
- [x] 최근 activity 정렬과 activity 없음 하단 정렬을 구현한다.
- [x] 목록 TUI에 header, summary count, legend, status line을 표시한다.
- [x] `/` 검색, `r` 숨김, `q` 종료, 3초 highlight를 구현한다.
- [x] aggregation과 목록 상태 전이 테스트를 추가한다.

커밋 기준: sessions 목록 TUI와 aggregation 테스트만 포함한다.

### Stage 3. 상세 로그 UI와 단일 session 공유

- [ ] 기존 session-id 로그 로딩/tail 동작을 새 상세 UI에서 재사용한다.
- [ ] 최근 N줄 기본 200줄과 `--lines N` 옵션을 구현한다.
- [ ] `--lines` 양의 정수 validation을 구현한다.
- [ ] running/unknown/exited/failed별 tail 정책을 구현한다.
- [ ] 스크롤 시 follow 중단과 끝 이동 시 follow 재개를 구현한다.
- [ ] 목록 진입 상세와 단일 `amon {session-id}` 상세의 `q` 동작 차이를 구현한다.
- [ ] 최근 N줄과 tail 정책 테스트를 추가한다.

커밋 기준: 상세 로그 UI, 단일 session 공유, 관련 테스트만 포함한다.

### Stage 4. 문서와 최종 검증

- [ ] README/usage를 새 기본 모드와 `amon xpane` 구조에 맞춰 갱신한다.
- [ ] 테스트 suite를 실행한다.
- [ ] 가능한 경우 TUI를 수동으로 실행해 기본 키 동작을 확인한다.
- [ ] 구현 subagent 결과와 검증 subagent 결과를 main이 리뷰한다.
- [ ] 체크리스트 완료 상태를 갱신한다.

커밋 기준: README/usage, 필요한 테스트 보강, 체크리스트 완료 표시만 포함한다.

## subagent 운영 방식

- main session은 작업 범위, 체크리스트, 커밋 경계, 최종 리뷰를 담당한다.
- implementation subagent는 Stage 1-3의 코드 변경을 수행한다.
- verification subagent는 Stage별 diff와 테스트 결과를 독립적으로 확인한다.
- subagent는 worktree `/Users/dane.lim/dev/amon/.worktrees/sessions-mode`에서만 작업한다.
- subagent는 다른 subagent 또는 main의 변경을 되돌리지 않는다.
- 각 stage 완료 후 main이 diff를 검토하고 커밋한다.
