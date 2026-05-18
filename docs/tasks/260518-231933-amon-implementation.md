# amon Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Single Python file `amon` that monitors active claude/codex non-interactive sessions — Mode A (single-session tail / snapshot via `--session-id`) and Mode B (auto-discover all active sessions, spawn one monitor per pane via xpanes).

**Architecture:** PID → session jsonl resolver (claude via cwd→slug + mtime, codex via lsof) → incremental jsonl tail (offset-tracking poll loop) → event-type-aware line formatter → idle detection on the same loop. Mode B is a launcher that runs discovery + invokes `xpanes -c "amon --session-id {}" SID1 SID2 ...`.

**Tech Stack:** Python 3.8+ stdlib only (`json`, `subprocess`, `os`, `time`, `argparse`, `signal`, `unittest`). xpanes required only for Mode B (runtime dependency, not Python dep).

---

## File Structure

- Create: `amon` (single executable Python script, shebang `#!/usr/bin/env python3`)
- Create: `tests/test_amon.py` (unittest, runs via `python3 -m unittest`)
- Create: `tests/fixtures/claude_session.jsonl` (3-5 line sample)
- Create: `tests/fixtures/codex_session.jsonl` (3-5 line sample)
- Create: `README.md` (usage, installation)

Single-file rationale: per ADR `260518-231929-python-stdlib`, no packaging. `amon` is `chmod +x` and dropped into `~/.local/bin/`.

---

### Task 1: Project skeleton + first failing test (cwd→slug)

**Files:**
- Create: `amon`
- Create: `tests/test_amon.py`

- [ ] **Step 1: Create minimal executable shell**

Write `amon`:

```python
#!/usr/bin/env python3
"""amon — monitor active claude/codex non-interactive sessions."""
import argparse
import sys


def cwd_to_claude_slug(cwd: str) -> str:
    raise NotImplementedError


def main() -> int:
    parser = argparse.ArgumentParser(prog="amon")
    parser.parse_args()
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Then `chmod +x amon`.

- [ ] **Step 2: Write failing test for slug conversion**

Write `tests/test_amon.py`:

```python
import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "amon", Path(__file__).parent.parent / "amon"
)
amon = importlib.util.module_from_spec(spec)
spec.loader.exec_module(amon)


class TestCwdToClaudeSlug(unittest.TestCase):
    def test_basic_path(self):
        self.assertEqual(
            amon.cwd_to_claude_slug("/Users/dane/src/foo"),
            "-Users-dane-src-foo",
        )

    def test_dotted_username(self):
        self.assertEqual(
            amon.cwd_to_claude_slug("/Users/dane.lim/src/foo"),
            "-Users-dane-lim-src-foo",
        )

    def test_dotfile_dir(self):
        # /Users/x/.claude → -Users-x--claude (leading dot becomes extra dash)
        self.assertEqual(
            amon.cwd_to_claude_slug("/Users/x/.claude"),
            "-Users-x--claude",
        )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run test to verify failure**

Run: `python3 -m unittest tests.test_amon -v`
Expected: 3 errors — `NotImplementedError`.

- [ ] **Step 4: Implement slug conversion**

Edit `amon`:

```python
def cwd_to_claude_slug(cwd: str) -> str:
    return "".join("-" if c in "/." else c for c in cwd)
```

- [ ] **Step 5: Run test to verify pass**

Run: `python3 -m unittest tests.test_amon -v`
Expected: 3 OK.

- [ ] **Step 6: Commit**

```bash
git init  # if not yet a repo
git add amon tests/test_amon.py
git commit -m "feat(amon): skeleton + cwd→claude slug converter"
```

---

### Task 2: Resolve claude session jsonl from PID

**Files:**
- Modify: `amon` (add `resolve_claude_session_path`)
- Modify: `tests/test_amon.py`

**Logic:** PID → cwd via `lsof -a -p $PID -d cwd` → slug → `~/.claude/projects/<slug>/*.jsonl` with most recent mtime. Ambiguity (multiple jsonl recent) is acknowledged limitation — we always pick latest mtime.

- [ ] **Step 1: Write failing test (parser only — shell out is integration-tested in Task 9)**

Add to `tests/test_amon.py`:

```python
class TestParseLsofCwd(unittest.TestCase):
    def test_extract_cwd_from_lsof_output(self):
        # Real lsof output sample
        sample = (
            "COMMAND  PID     USER   FD   TYPE DEVICE SIZE/OFF      NODE NAME\n"
            "claude  30446 dane.lim  cwd    DIR   1,18     1184  85298596 /Users/dane.lim/src/foo bar\n"
        )
        self.assertEqual(
            amon.parse_lsof_cwd(sample),
            "/Users/dane.lim/src/foo bar",
        )

    def test_returns_none_when_no_cwd_line(self):
        self.assertIsNone(amon.parse_lsof_cwd("COMMAND PID USER\n"))


class TestPickLatestJsonl(unittest.TestCase):
    def test_picks_latest_mtime(self):
        import tempfile, os, time
        with tempfile.TemporaryDirectory() as d:
            a = Path(d) / "a.jsonl"; a.write_text("")
            time.sleep(0.01)
            b = Path(d) / "b.jsonl"; b.write_text("")
            self.assertEqual(amon.pick_latest_jsonl(d), str(b))

    def test_returns_none_when_no_jsonl(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(amon.pick_latest_jsonl(d))
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python3 -m unittest tests.test_amon -v`
Expected: `AttributeError: module 'amon' has no attribute 'parse_lsof_cwd'`.

- [ ] **Step 3: Implement parsers**

Add to `amon`:

```python
import os
import subprocess
from pathlib import Path
from typing import Optional


def parse_lsof_cwd(lsof_output: str) -> Optional[str]:
    for line in lsof_output.splitlines():
        parts = line.split(None, 8)  # split first 8 cols, keep rest as name
        if len(parts) >= 9 and parts[3] == "cwd":
            return parts[8]
    return None


def pick_latest_jsonl(directory: str) -> Optional[str]:
    p = Path(directory)
    if not p.is_dir():
        return None
    files = list(p.glob("*.jsonl"))
    if not files:
        return None
    return str(max(files, key=lambda f: f.stat().st_mtime))


def resolve_claude_session_path(pid: int) -> Optional[str]:
    """Returns None if no active claude session found for PID."""
    result = subprocess.run(
        ["lsof", "-a", "-p", str(pid), "-d", "cwd"],
        capture_output=True, text=True, check=False,
    )
    cwd = parse_lsof_cwd(result.stdout)
    if cwd is None:
        return None
    slug = cwd_to_claude_slug(cwd)
    project_dir = os.path.expanduser(f"~/.claude/projects/{slug}")
    return pick_latest_jsonl(project_dir)
```

- [ ] **Step 4: Run tests to verify pass**

Run: `python3 -m unittest tests.test_amon -v`
Expected: 5 OK.

- [ ] **Step 5: Commit**

```bash
git add amon tests/test_amon.py
git commit -m "feat(amon): claude PID→session jsonl resolver"
```

---

### Task 3: Resolve codex session jsonl from PID

**Files:**
- Modify: `amon` (add `resolve_codex_session_paths`)
- Modify: `tests/test_amon.py`

**Logic:** codex keeps session jsonl fd open. `lsof -p $PID` shows them directly. Default returns the single latest-mtime path; `all_sessions=True` returns all.

- [ ] **Step 1: Write failing test**

Add to `tests/test_amon.py`:

```python
class TestParseLsofJsonl(unittest.TestCase):
    SAMPLE = (
        "codex 35933 dane.lim   18w   REG  1,18 18993386 71324555 /Users/x/.codex/log/codex-tui.log\n"
        "codex 35933 dane.lim   37w   REG  1,18  2632374 103171766 /Users/x/.codex/sessions/2026/05/18/rollout-A.jsonl\n"
        "codex 35933 dane.lim   53w   REG  1,18   674054 103287784 /Users/x/.codex/sessions/2026/05/18/rollout-B.jsonl\n"
    )

    def test_extracts_codex_session_jsonls_only(self):
        paths = amon.parse_lsof_codex_jsonls(self.SAMPLE)
        self.assertEqual(len(paths), 2)
        self.assertTrue(all("/.codex/sessions/" in p for p in paths))
        # log file excluded
        self.assertFalse(any(p.endswith(".log") for p in paths))
```

- [ ] **Step 2: Run test to verify failure**

Run: `python3 -m unittest tests.test_amon -v`
Expected: `AttributeError`.

- [ ] **Step 3: Implement parser + resolver**

Add to `amon`:

```python
from typing import List


def parse_lsof_codex_jsonls(lsof_output: str) -> List[str]:
    paths = []
    for line in lsof_output.splitlines():
        parts = line.split(None, 8)
        if len(parts) < 9:
            continue
        name = parts[8]
        if "/.codex/sessions/" in name and name.endswith(".jsonl"):
            paths.append(name)
    return paths


def resolve_codex_session_paths(pid: int, all_sessions: bool = False) -> List[str]:
    result = subprocess.run(
        ["lsof", "-p", str(pid)],
        capture_output=True, text=True, check=False,
    )
    paths = parse_lsof_codex_jsonls(result.stdout)
    if not paths:
        return []
    if all_sessions:
        return paths
    latest = max(paths, key=lambda p: os.stat(p).st_mtime if os.path.exists(p) else 0)
    return [latest]
```

- [ ] **Step 4: Run tests, verify pass**

Run: `python3 -m unittest tests.test_amon -v`
Expected: 6 OK.

- [ ] **Step 5: Commit**

```bash
git add amon tests/test_amon.py
git commit -m "feat(amon): codex PID→session jsonl resolver"
```

---

### Task 4: Incremental jsonl tail reader

**Files:**
- Modify: `amon` (add `JsonlTail` class)
- Modify: `tests/test_amon.py`
- Create: `tests/fixtures/sample.jsonl`

**Logic:** Open file, remember byte offset, on `read_new_lines()` seek to offset, read to EOF, update offset. Returns list of parsed json objects (skipping malformed lines). Supports file rotation/truncation detection (if size < offset → re-open from 0).

- [ ] **Step 1: Create fixture**

Write `tests/fixtures/sample.jsonl`:

```
{"type": "first", "n": 1}
{"type": "second", "n": 2}
```

- [ ] **Step 2: Write failing test**

Add to `tests/test_amon.py`:

```python
class TestJsonlTail(unittest.TestCase):
    def setUp(self):
        import tempfile, shutil
        self.tmpdir = tempfile.mkdtemp()
        self.path = Path(self.tmpdir) / "x.jsonl"
        self.path.write_text('{"type":"a"}\n{"type":"b"}\n')
        self.addCleanup(shutil.rmtree, self.tmpdir)

    def test_reads_all_existing_lines_on_first_call(self):
        t = amon.JsonlTail(str(self.path))
        events = t.read_new_lines()
        self.assertEqual([e["type"] for e in events], ["a", "b"])

    def test_second_call_with_no_new_data_returns_empty(self):
        t = amon.JsonlTail(str(self.path))
        t.read_new_lines()
        self.assertEqual(t.read_new_lines(), [])

    def test_picks_up_appended_lines(self):
        t = amon.JsonlTail(str(self.path))
        t.read_new_lines()
        with open(self.path, "a") as f:
            f.write('{"type":"c"}\n')
        self.assertEqual(
            [e["type"] for e in t.read_new_lines()], ["c"]
        )

    def test_skips_malformed_json_lines(self):
        with open(self.path, "a") as f:
            f.write("not json\n")
            f.write('{"type":"d"}\n')
        t = amon.JsonlTail(str(self.path))
        events = t.read_new_lines()
        types = [e["type"] for e in events]
        self.assertEqual(types, ["a", "b", "d"])

    def test_handles_truncation(self):
        t = amon.JsonlTail(str(self.path))
        t.read_new_lines()  # offset now at end
        self.path.write_text('{"type":"x"}\n')  # rewrite shorter
        events = t.read_new_lines()
        self.assertEqual([e["type"] for e in events], ["x"])
```

- [ ] **Step 3: Run tests, verify failure**

Run: `python3 -m unittest tests.test_amon -v`
Expected: 5 errors (`JsonlTail` missing).

- [ ] **Step 4: Implement JsonlTail**

Add to `amon`:

```python
import json


class JsonlTail:
    def __init__(self, path: str):
        self.path = path
        self.offset = 0

    def read_new_lines(self) -> list:
        try:
            size = os.path.getsize(self.path)
        except OSError:
            return []
        if size < self.offset:
            self.offset = 0  # truncation
        if size == self.offset:
            return []
        with open(self.path, "r", encoding="utf-8", errors="replace") as f:
            f.seek(self.offset)
            data = f.read()
            self.offset = f.tell()
        events = []
        for line in data.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return events
```

- [ ] **Step 5: Run tests, verify pass**

Run: `python3 -m unittest tests.test_amon -v`
Expected: 11 OK total.

- [ ] **Step 6: Commit**

```bash
git add amon tests/test_amon.py tests/fixtures/sample.jsonl
git commit -m "feat(amon): incremental JsonlTail reader"
```

---

### Task 5: Event → display line formatting (claude + codex)

**Files:**
- Modify: `amon` (add `format_event`)
- Modify: `tests/test_amon.py`

**Logic:** Per spec, line format is `HH:MM:SS [agent/sid_short] kind details`. Per ADR `260518-231930` (event scope), output: tool calls (name + key args) + assistant message first line. Other event types return `None` (skipped).

`kind` taxonomy (cross-CLI):
- `Tool <Name>` — both claude and codex tool_use; details = primary arg (file path / command)
- `Msg` — assistant message first line, truncated to 80 chars
- `Exit` — emitted by tail loop on process exit (Task 6), not here

Claude event sources:
- `attachment` events with `attachment.type=="tool_use"` or similar — verify against real jsonl in Task 9 smoke. **For Task 5 use only the documented fields below; treat unknowns as None.**

Codex event sources:
- `response_item` with `payload.type=="function_call"` → tool
- `response_item` with `payload.type=="message"` and role `assistant` → message

- [ ] **Step 1: Write failing tests**

Add to `tests/test_amon.py`:

```python
class TestFormatEvent(unittest.TestCase):
    def test_codex_function_call(self):
        ev = {
            "type": "response_item",
            "payload": {
                "type": "function_call",
                "name": "shell",
                "arguments": '{"command":["bash","-lc","ls -la"]}',
            },
        }
        line = amon.format_event(ev, agent="codex", sid_short="abc1")
        self.assertIn("[codex/abc1]", line)
        self.assertIn("Tool shell", line)
        self.assertIn("ls -la", line)

    def test_codex_assistant_message(self):
        ev = {
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": "Done.\nSecond line."}],
            },
        }
        line = amon.format_event(ev, agent="codex", sid_short="abc1")
        self.assertIn("[codex/abc1] Msg Done.", line)
        self.assertNotIn("Second line", line)  # only first line

    def test_codex_ignored_type(self):
        ev = {"type": "reasoning", "payload": {"text": "thinking..."}}
        self.assertIsNone(amon.format_event(ev, "codex", "abc1"))

    def test_claude_tool_use_via_attachment(self):
        ev = {
            "type": "attachment",
            "attachment": {
                "type": "tool_use",
                "tool_name": "Edit",
                "tool_input": {"file_path": "/foo/bar.py"},
            },
        }
        line = amon.format_event(ev, "claude", "636a")
        self.assertIn("[claude/636a]", line)
        self.assertIn("Tool Edit", line)
        self.assertIn("/foo/bar.py", line)

    def test_line_starts_with_timestamp(self):
        import re
        ev = {"type": "response_item", "payload": {"type": "function_call",
              "name": "shell", "arguments": "{}"}}
        line = amon.format_event(ev, "codex", "abc1")
        self.assertRegex(line, r"^\d{2}:\d{2}:\d{2} ")
```

- [ ] **Step 2: Run tests, verify failure**

Run: `python3 -m unittest tests.test_amon -v`
Expected: 5 errors (`format_event` missing).

- [ ] **Step 3: Implement format_event**

Add to `amon`:

```python
import time as _time


def _ts() -> str:
    return _time.strftime("%H:%M:%S", _time.localtime())


def _truncate(s: str, n: int = 80) -> str:
    s = s.replace("\n", " ").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def _format_codex_event(ev: dict) -> Optional[tuple]:
    if ev.get("type") != "response_item":
        return None
    p = ev.get("payload", {})
    ptype = p.get("type")
    if ptype == "function_call":
        name = p.get("name", "?")
        args = p.get("arguments", "")
        try:
            parsed = json.loads(args) if isinstance(args, str) else args
        except json.JSONDecodeError:
            parsed = {}
        detail = ""
        if isinstance(parsed, dict):
            if "command" in parsed:
                cmd = parsed["command"]
                detail = " ".join(cmd) if isinstance(cmd, list) else str(cmd)
            elif "file_path" in parsed:
                detail = str(parsed["file_path"])
            elif "path" in parsed:
                detail = str(parsed["path"])
        return ("Tool " + name, _truncate(detail))
    if ptype == "message" and p.get("role") == "assistant":
        content = p.get("content", [])
        for item in content:
            if isinstance(item, dict) and "text" in item:
                first_line = item["text"].split("\n", 1)[0]
                return ("Msg", _truncate(first_line))
    return None


def _format_claude_event(ev: dict) -> Optional[tuple]:
    if ev.get("type") != "attachment":
        return None
    a = ev.get("attachment", {})
    if a.get("type") == "tool_use":
        name = a.get("tool_name", "?")
        inp = a.get("tool_input", {})
        detail = ""
        if isinstance(inp, dict):
            for key in ("file_path", "path", "command"):
                if key in inp:
                    v = inp[key]
                    detail = " ".join(v) if isinstance(v, list) else str(v)
                    break
        return ("Tool " + name, _truncate(detail))
    return None


def format_event(ev: dict, agent: str, sid_short: str) -> Optional[str]:
    formatter = _format_codex_event if agent == "codex" else _format_claude_event
    parts = formatter(ev)
    if parts is None:
        return None
    kind, detail = parts
    suffix = f" {detail}" if detail else ""
    return f"{_ts()} [{agent}/{sid_short}] {kind}{suffix}"
```

- [ ] **Step 4: Run tests, verify pass**

Run: `python3 -m unittest tests.test_amon -v`
Expected: 16 OK total.

- [ ] **Step 5: Commit**

```bash
git add amon tests/test_amon.py
git commit -m "feat(amon): event→display line formatter (claude + codex)"
```

> **Note:** Real claude/codex event schemas may differ from the test fixtures. Task 9 will verify against live jsonl files and adjust formatter dispatch.

---

### Task 6: Mode A tail loop (idle detection + AGENT EXITED)

**Files:**
- Modify: `amon` (add `run_tail`)
- Modify: `tests/test_amon.py`

**Logic:** Poll JsonlTail every 1s. Emit each new event's formatted line to stdout. Track `last_event_ts`. If `now - last_event_ts >= idle_threshold` AND warning not yet emitted → print `⚠ idle Ns`, set `warned=True`. On new event after warning, reset `warned=False`. If target PID specified, check `os.kill(pid, 0)` periodically; on `ProcessLookupError`, print `AGENT EXITED` and exit 0.

- [ ] **Step 1: Write failing test for the pure idle-state-machine part**

Add to `tests/test_amon.py`:

```python
class TestIdleStateMachine(unittest.TestCase):
    def test_no_warning_before_threshold(self):
        s = amon.IdleStateMachine(threshold=60)
        s.touch(at=100.0)
        self.assertIsNone(s.tick(now=130.0))  # only 30s passed

    def test_warning_at_threshold(self):
        s = amon.IdleStateMachine(threshold=60)
        s.touch(at=100.0)
        msg = s.tick(now=160.0)
        self.assertEqual(msg, "⚠ idle 60s")

    def test_no_repeat_warning(self):
        s = amon.IdleStateMachine(threshold=60)
        s.touch(at=100.0)
        s.tick(now=160.0)
        self.assertIsNone(s.tick(now=200.0))

    def test_reset_after_touch(self):
        s = amon.IdleStateMachine(threshold=60)
        s.touch(at=100.0)
        s.tick(now=160.0)  # warned
        s.touch(at=170.0)
        self.assertIsNone(s.tick(now=180.0))
        msg = s.tick(now=230.0)
        self.assertEqual(msg, "⚠ idle 60s")  # re-armed
```

- [ ] **Step 2: Run, verify failure**

Run: `python3 -m unittest tests.test_amon -v`
Expected: 4 errors (`IdleStateMachine` missing).

- [ ] **Step 3: Implement IdleStateMachine + run_tail**

Add to `amon`:

```python
import signal


class IdleStateMachine:
    def __init__(self, threshold: int):
        self.threshold = threshold
        self.last_touch: Optional[float] = None
        self.warned = False

    def touch(self, at: float) -> None:
        self.last_touch = at
        self.warned = False

    def tick(self, now: float) -> Optional[str]:
        if self.last_touch is None or self.warned:
            return None
        if now - self.last_touch >= self.threshold:
            self.warned = True
            return f"⚠ idle {self.threshold}s"
        return None


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False
    except OSError:
        return False


def run_tail(session_path: str, agent: str, sid_short: str,
             idle_threshold: int, pid: Optional[int] = None,
             poll_interval: float = 1.0) -> int:
    """Stream events from session_path to stdout until process exits / Ctrl-C."""
    tail = JsonlTail(session_path)
    idle = IdleStateMachine(threshold=idle_threshold)
    # Prime with existing content so we don't replay history.
    tail.read_new_lines()
    idle.touch(at=_time.time())

    def _handler(signum, frame):
        sys.exit(0)
    signal.signal(signal.SIGINT, _handler)
    signal.signal(signal.SIGTERM, _handler)

    while True:
        events = tail.read_new_lines()
        for ev in events:
            line = format_event(ev, agent, sid_short)
            if line:
                print(line, flush=True)
        if events:
            idle.touch(at=_time.time())
        else:
            warn = idle.tick(now=_time.time())
            if warn:
                print(f"{_ts()} [{agent}/{sid_short}] {warn}", flush=True)
        if pid is not None and not _pid_alive(pid):
            print(f"{_ts()} [{agent}/{sid_short}] AGENT EXITED", flush=True)
            return 0
        _time.sleep(poll_interval)
```

- [ ] **Step 4: Run, verify pass**

Run: `python3 -m unittest tests.test_amon -v`
Expected: 20 OK.

- [ ] **Step 5: Commit**

```bash
git add amon tests/test_amon.py
git commit -m "feat(amon): Mode A tail loop with idle detection + exit handling"
```

---

### Task 7: Mode A `--once` snapshot

**Files:**
- Modify: `amon` (add `run_snapshot`)
- Modify: `tests/test_amon.py`

**Logic:** Read entire jsonl, derive: last formatted event, total event count (turns approximated as assistant messages), last event mtime → idle seconds. Emit one line; exit 0 if working (idle < threshold), exit 2 if stuck.

Output format (one line):
`HH:MM:SS [agent/sid_short] status={working|idle} idle=Ns last=<kind details>`

- [ ] **Step 1: Write failing test**

Add to `tests/test_amon.py`:

```python
class TestRunSnapshot(unittest.TestCase):
    def _make_jsonl(self, lines):
        import tempfile
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False
        )
        for l in lines:
            tmp.write(json.dumps(l) + "\n")
        tmp.close()
        self.addCleanup(os.unlink, tmp.name)
        return tmp.name

    def test_working_status_exits_zero(self):
        p = self._make_jsonl([
            {"type": "response_item",
             "payload": {"type": "function_call",
                         "name": "shell", "arguments": '{"command":["ls"]}'}}
        ])
        # Pretend the file was just written; mtime is now.
        code, line = amon.snapshot_status(p, agent="codex", sid_short="abc1",
                                          idle_threshold=60, now=os.path.getmtime(p))
        self.assertEqual(code, 0)
        self.assertIn("status=working", line)
        self.assertIn("[codex/abc1]", line)

    def test_idle_status_exits_two(self):
        p = self._make_jsonl([
            {"type": "response_item",
             "payload": {"type": "function_call",
                         "name": "shell", "arguments": '{}'}}
        ])
        future = os.path.getmtime(p) + 9999
        code, line = amon.snapshot_status(p, "codex", "abc1", 60, now=future)
        self.assertEqual(code, 2)
        self.assertIn("status=idle", line)
        self.assertIn("idle=", line)
```

- [ ] **Step 2: Run, verify failure**

Run: `python3 -m unittest tests.test_amon -v`
Expected: 2 errors.

- [ ] **Step 3: Implement snapshot_status + run_snapshot**

Add to `amon`:

```python
def snapshot_status(session_path: str, agent: str, sid_short: str,
                    idle_threshold: int, now: Optional[float] = None) -> tuple:
    """Returns (exit_code, status_line)."""
    if now is None:
        now = _time.time()
    last_kind = "(no events)"
    with open(session_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            formatted = (_format_codex_event if agent == "codex"
                         else _format_claude_event)(ev)
            if formatted:
                kind, detail = formatted
                last_kind = f"{kind} {detail}".strip()
    try:
        mtime = os.path.getmtime(session_path)
    except OSError:
        mtime = now
    idle_sec = int(max(0, now - mtime))
    status = "idle" if idle_sec >= idle_threshold else "working"
    exit_code = 2 if status == "idle" else 0
    line = (f"{_ts()} [{agent}/{sid_short}] status={status} "
            f"idle={idle_sec}s last={last_kind}")
    return exit_code, line


def run_snapshot(session_path: str, agent: str, sid_short: str,
                 idle_threshold: int) -> int:
    code, line = snapshot_status(session_path, agent, sid_short, idle_threshold)
    print(line, flush=True)
    return code
```

- [ ] **Step 4: Run, verify pass**

Run: `python3 -m unittest tests.test_amon -v`
Expected: 22 OK.

- [ ] **Step 5: Commit**

```bash
git add amon tests/test_amon.py
git commit -m "feat(amon): Mode A --once snapshot with stuck exit code"
```

---

### Task 8: Mode B — discovery + xpanes spawn

**Files:**
- Modify: `amon` (add `discover_active_sessions`, `run_mode_b`)
- Modify: `tests/test_amon.py`

**Logic:** Discovery — `pgrep -lf claude` and `pgrep -lf codex`, then per PID inspect `ps -o command= -p $PID`. Filter:
- claude: `command` contains ` -p` or `--print`
- codex: first sub-arg after `codex` is `exec`

For each surviving PID → resolve session path(s) (Task 2/3). Build list of `(agent, session_path, pid)` triples. Then `subprocess.run(["xpanes", "-c", f"{amon_path} --session-id {{}} --color=always --pid {{...}}", *args])` — pass session path identifier. Since xpanes substitutes `{}` per argument, we encode `agent:sid:pid` and have spawned amon parse it.

Simplification: instead of `--session-id` UUID we can pass session jsonl path directly via `--session-path`. Decided: add `--session-path` flag (internal) that Mode B uses; `--session-id` remains public Mode A entry.

**xpanes missing** → error message + exit 3.

- [ ] **Step 1: Write failing tests for parsers + filter logic**

Add to `tests/test_amon.py`:

```python
class TestProcessFilter(unittest.TestCase):
    def test_claude_non_interactive_detected(self):
        self.assertTrue(amon.is_claude_noninteractive("claude -p 'hello world'"))
        self.assertTrue(amon.is_claude_noninteractive("claude --print 'x'"))

    def test_claude_interactive_rejected(self):
        self.assertFalse(amon.is_claude_noninteractive("claude"))
        self.assertFalse(amon.is_claude_noninteractive("claude doctor"))

    def test_codex_exec_detected(self):
        self.assertTrue(amon.is_codex_exec("codex exec 'do thing'"))
        self.assertTrue(amon.is_codex_exec("/path/to/codex exec --json"))

    def test_codex_interactive_rejected(self):
        self.assertFalse(amon.is_codex_exec("codex"))
        self.assertFalse(amon.is_codex_exec("codex --yolo"))
```

- [ ] **Step 2: Run, verify failure**

Run: `python3 -m unittest tests.test_amon -v`
Expected: 4 errors.

- [ ] **Step 3: Implement filters and discovery**

Add to `amon`:

```python
import shlex
import shutil


def is_claude_noninteractive(cmdline: str) -> bool:
    parts = shlex.split(cmdline)
    if not parts:
        return False
    if not parts[0].endswith("claude") and parts[0] != "claude":
        return False
    return "-p" in parts or "--print" in parts


def is_codex_exec(cmdline: str) -> bool:
    parts = shlex.split(cmdline)
    if not parts:
        return False
    base = os.path.basename(parts[0])
    if base != "codex":
        return False
    return len(parts) >= 2 and parts[1] == "exec"


def _pgrep_with_cmdline(pattern: str) -> List[tuple]:
    """Returns list of (pid, cmdline)."""
    result = subprocess.run(
        ["pgrep", "-fl", pattern],
        capture_output=True, text=True, check=False,
    )
    out = []
    for line in result.stdout.splitlines():
        sp = line.split(None, 1)
        if len(sp) == 2 and sp[0].isdigit():
            out.append((int(sp[0]), sp[1]))
    return out


def discover_active_sessions(codex_all: bool = False) -> List[dict]:
    """Returns [{agent, pid, session_path}, ...] for non-interactive sessions."""
    sessions = []
    for pid, cmd in _pgrep_with_cmdline("claude"):
        if not is_claude_noninteractive(cmd):
            continue
        path = resolve_claude_session_path(pid)
        if path:
            sessions.append({"agent": "claude", "pid": pid, "session_path": path})
    for pid, cmd in _pgrep_with_cmdline("codex"):
        if not is_codex_exec(cmd):
            continue
        for path in resolve_codex_session_paths(pid, all_sessions=codex_all):
            sessions.append({"agent": "codex", "pid": pid, "session_path": path})
    return sessions


def run_mode_b(idle_threshold: int, codex_all: bool) -> int:
    if shutil.which("xpanes") is None:
        print("error: xpanes not found. Install it (e.g. brew install xpanes) "
              "or use Mode A with --session-id.", file=sys.stderr)
        return 3
    sessions = discover_active_sessions(codex_all=codex_all)
    if not sessions:
        print("no active non-interactive claude/codex sessions found.",
              file=sys.stderr)
        return 0
    amon_path = os.path.realpath(sys.argv[0])
    # Build xpanes invocation: -c is the per-arg command, {} substituted.
    template = (
        f"{shlex.quote(amon_path)} --session-path {{}} "
        f"--idle-threshold {idle_threshold} --color=always"
    )
    args = [s["session_path"] for s in sessions]
    cmd = ["xpanes", "-c", template] + args
    return subprocess.call(cmd)
```

- [ ] **Step 4: Run, verify pass**

Run: `python3 -m unittest tests.test_amon -v`
Expected: 26 OK.

- [ ] **Step 5: Commit**

```bash
git add amon tests/test_amon.py
git commit -m "feat(amon): Mode B discovery + xpanes spawn launcher"
```

---

### Task 9: CLI wiring + smoke test against live agents

**Files:**
- Modify: `amon` (complete `main()`)
- Create: `README.md`

- [ ] **Step 1: Complete main()**

Replace `main()` in `amon`:

```python
def _agent_from_path(path: str) -> str:
    return "codex" if "/.codex/sessions/" in path else "claude"


def _sid_short(path: str) -> str:
    """Extract first 4 chars of UUID-like substring of filename stem."""
    stem = os.path.splitext(os.path.basename(path))[0]
    # codex: rollout-...-<uuid> | claude: <uuid>
    if "-" in stem:
        for chunk in reversed(stem.split("-")):
            if len(chunk) >= 4:
                return chunk[:4]
    return stem[:4]


def _resolve_path_from_session_id(sid: str) -> Optional[str]:
    """Search ~/.claude/projects/*/ for <sid>.jsonl and codex sessions."""
    claude_root = Path(os.path.expanduser("~/.claude/projects"))
    if claude_root.is_dir():
        for proj in claude_root.iterdir():
            cand = proj / f"{sid}.jsonl"
            if cand.exists():
                return str(cand)
    codex_root = Path(os.path.expanduser("~/.codex/sessions"))
    if codex_root.is_dir():
        for p in codex_root.rglob("*.jsonl"):
            if sid in p.name:
                return str(p)
    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="amon",
        description="Monitor active claude/codex non-interactive sessions.",
        epilog=(
            "examples:\n"
            "  amon                              Mode B: discover + xpanes\n"
            "  amon --session-id <uuid>          Mode A: tail single session\n"
            "  amon --session-id <uuid> --once   Mode A: 1-line snapshot\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--session-id", help="UUID of session to monitor (Mode A)")
    parser.add_argument("--session-path",
                        help="Direct path to jsonl (internal, used by Mode B)")
    parser.add_argument("--once", action="store_true",
                        help="Snapshot mode: emit 1 line and exit (Mode A)")
    parser.add_argument("--idle-threshold", type=int, default=60,
                        help="Seconds of silence before ⚠ idle (default: 60)")
    parser.add_argument("--codex-all-sessions", action="store_true",
                        help="Mode B: include all open codex jsonls per PID")
    parser.add_argument("--color", choices=["always", "never", "auto"],
                        default="never",
                        help="Color output (default: never; Mode B forces always)")
    args = parser.parse_args()

    if args.session_id or args.session_path:
        path = (args.session_path or
                _resolve_path_from_session_id(args.session_id))
        if not path:
            print(f"error: no session file found for {args.session_id}",
                  file=sys.stderr)
            return 1
        agent = _agent_from_path(path)
        sid_short = _sid_short(path)
        if args.once:
            return run_snapshot(path, agent, sid_short, args.idle_threshold)
        return run_tail(path, agent, sid_short, args.idle_threshold)

    return run_mode_b(args.idle_threshold, args.codex_all_sessions)
```

- [ ] **Step 2: Verify `--help` works**

Run: `./amon --help`
Expected: usage block + examples shown.

- [ ] **Step 3: Smoke test — Mode A snapshot against a real (or recently-modified) claude session**

Identify a recent claude session file:

```bash
ls -t ~/.claude/projects/*/*.jsonl | head -1
```

Extract its UUID (filename stem) and run:

```bash
SID=$(ls -t ~/.claude/projects/*/*.jsonl | head -1 | xargs -n1 basename | sed 's/\.jsonl//')
./amon --session-id "$SID" --once
```

Expected: 1 line `HH:MM:SS [claude/xxxx] status=... idle=...s last=...`. If `last=(no events)` or formatting looks wrong, **adjust `_format_claude_event` based on observed jsonl event types** — sample with:

```bash
ls -t ~/.claude/projects/*/*.jsonl | head -1 | xargs head -20
```

This is the verification gate per ADR `260518-231929` (Python stdlib): real-world event schema may differ from fixtures.

- [ ] **Step 4: Smoke test — Mode A tail (manually start a long claude -p)**

In one terminal:

```bash
claude -p --session-id $(uuidgen | tr A-Z a-z) "write a python script to ..." > /tmp/claude.out
```

In another:

```bash
./amon --session-id <that-uuid>
```

Expected: lines stream as claude works. Wait 60+ idle seconds → `⚠ idle 60s` once. Kill claude → `AGENT EXITED` line, amon exits 0.

- [ ] **Step 5: Smoke test — Mode B**

With at least one `claude -p` or `codex exec` running:

```bash
./amon
```

Expected: xpanes opens tmux with one pane per active session, each streaming events.

- [ ] **Step 6: Document in README**

Write `README.md`:

```markdown
# amon

Monitor active claude/codex non-interactive sessions.

## Install

    cp amon ~/.local/bin/
    chmod +x ~/.local/bin/amon

Mode B additionally requires [xpanes](https://github.com/greymd/tmux-xpanes).

## Usage

    amon                              # auto-discover + xpanes spawn
    amon --session-id <uuid>          # tail a single session
    amon --session-id <uuid> --once   # 1-line status snapshot

## Flags

- `--idle-threshold N` — seconds of silence before ⚠ idle (default 60)
- `--codex-all-sessions` — Mode B: include every open jsonl per codex PID
- `--color {always,never,auto}` — default never; Mode B forces always

## Design

See `docs/arch/` for ADRs and `docs/tasks/` for the plan.
```

- [ ] **Step 7: Commit**

```bash
git add amon README.md
git commit -m "feat(amon): CLI wiring + README"
```

---

## Self-Review Notes

**Spec coverage check:**
- amon single command + flags → Task 9 main()
- Python stdlib + mac/linux → all tasks (no external imports)
- Claude + Codex resolve → Tasks 2, 3
- Non-interactive filter → Task 8
- Mode A tail + ⚠ idle 60s + AGENT EXITED → Task 6
- Mode A --once + exit 2 stuck → Task 7
- Mode B xpanes spawn (--color=always forced) → Task 8
- xpanes missing → exit 3 → Task 8
- Codex multi-jsonl default = latest 1 → Task 3
- Codex `--codex-all-sessions` flag → Tasks 8, 9
- Dynamic discovery NOT supported (re-run required) → implicit in Task 8 (one-shot launch)
- Line format `HH:MM:SS [agent/sid_short] kind details` → Task 5
- Event scope: tool + assistant msg first line → Task 5

**Known schema risk (Task 5):** claude jsonl event types in fixtures (`attachment.type=="tool_use"`) are inferred; real format may use different keys. Task 9 Step 3 is the verification gate where Task 5 may need follow-up edits.

**Out of scope (deliberate, per ADRs):**
- Tool-execution-aware stuck detection (ADR `260518-231930`)
- Dynamic pane addition (ADR `260518-231928`)
- xpanes fallback (ADR `260518-231928`)
- Interactive session inclusion (ADR `260518-231932`)

---

## Execution Handoff

After plan complete:

**1. Subagent-Driven (recommended)** — fresh subagent per task, review between tasks  
**2. Inline Execution** — execute tasks in this session via executing-plans

User decides which path when ready to implement.
