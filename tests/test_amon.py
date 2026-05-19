import importlib.util
import json
import io
from importlib.machinery import SourceFileLoader
import os
import tempfile
import time
from unittest import mock
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"

loader = SourceFileLoader("amon", str(ROOT / "amon"))
spec = importlib.util.spec_from_loader(loader.name, loader)
amon = importlib.util.module_from_spec(spec)
loader.exec_module(amon)


class TestFixtureFiles(unittest.TestCase):
    def test_fixture_files_exist(self):
        self.assertTrue((FIXTURES / "claude_session.jsonl").exists())
        self.assertTrue((FIXTURES / "codex_session.jsonl").exists())


class TestSkeleton(unittest.TestCase):
    def test_imports_extensionless_executable(self):
        self.assertTrue(hasattr(amon, "main"))

    def test_main_accepts_argv(self):
        with mock.patch.object(amon, "run_mode_b", return_value=0):
            self.assertEqual(amon.main([]), 0)

    def test_help_exits_successfully(self):
        with self.assertRaises(SystemExit) as caught:
            amon.main(["--help"])
        self.assertEqual(caught.exception.code, 0)

    def test_invalid_argument_exits_one(self):
        with mock.patch.object(amon.sys, "stderr", io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                amon.main(["--definitely-invalid"])
        self.assertEqual(caught.exception.code, 1)


class TestCliWiring(unittest.TestCase):
    def test_main_missing_session_id_exits_one(self):
        err = io.StringIO()
        with mock.patch.object(amon, "resolve_path_from_session_id", return_value=None):
            with mock.patch.object(amon.sys, "stderr", err):
                code = amon.main(["--session-id", "missing"])
        self.assertEqual(code, 1)
        self.assertIn("session id not found", err.getvalue())

    def test_main_session_path_once_calls_snapshot(self):
        with mock.patch.object(amon, "run_snapshot", return_value=0) as snapshot:
            code = amon.main([
                "--session-path",
                "/tmp/.codex/sessions/session-123456789.jsonl",
                "--once",
            ])
        self.assertEqual(code, 0)
        snapshot.assert_called_once_with(
            "/tmp/.codex/sessions/session-123456789.jsonl",
            "codex",
            "session-",
            60.0,
            color="never",
        )

    def test_main_session_spec_calls_tail_with_decoded_pid(self):
        spec = amon.encode_session_spec(
            {"agent": "claude", "pid": 321, "path": "/tmp/claude-session.jsonl"}
        )
        with mock.patch.object(amon.Path, "exists", return_value=True):
            with mock.patch.object(amon, "run_tail", return_value=0) as tail:
                code = amon.main(["--session-spec", spec, "--idle-threshold", "7"])
        self.assertEqual(code, 0)
        tail.assert_called_once_with(
            "/tmp/claude-session.jsonl",
            "claude",
            "claude-s",
            7.0,
            pid=321,
            color="never",
        )

    def test_main_session_title_prints_runtime_and_session_stem(self):
        out = io.StringIO()
        spec = amon.encode_session_spec(
            {
                "agent": "codex",
                "pid": 321,
                "path": (
                    "/tmp/.codex/sessions/"
                    "rollout-2026-05-19T09-00-00-019cb430-debf-70e3-9449-e4cde0120f9c.jsonl"
                ),
            }
        )
        with mock.patch.object(amon.sys, "stdout", out):
            code = amon.main(["--session-title", spec])
        self.assertEqual(code, 0)
        self.assertEqual(out.getvalue().strip(), "codex/019cb430-debf-70e3-9449-e4cde0120f9c")

    def test_main_no_args_calls_mode_b(self):
        with mock.patch.object(amon, "run_mode_b", return_value=0) as mode_b:
            code = amon.main([])
        self.assertEqual(code, 0)
        mode_b.assert_called_once_with(60.0, codex_all=False, color="always")

    def test_main_session_id_resolves_and_uses_snapshot_when_once(self):
        with mock.patch.object(
            amon,
            "resolve_path_from_session_id",
            return_value="/tmp/.codex/sessions/run-abcdef.jsonl",
        ):
            with mock.patch.object(amon, "run_snapshot", return_value=2) as snapshot:
                code = amon.main([
                    "--session-id",
                    "abcdef",
                    "--once",
                    "--color",
                    "always",
                ])
        self.assertEqual(code, 2)
        snapshot.assert_called_once_with(
            "/tmp/.codex/sessions/run-abcdef.jsonl",
            "codex",
            "run-abcd",
            60.0,
            color="always",
        )


class TestPathAndSessionResolution(unittest.TestCase):
    def test_cwd_to_claude_slug_replaces_slashes_and_dots(self):
        self.assertEqual(
            amon.cwd_to_claude_slug("/Users/dane.lim/dev/.amon"),
            "-Users-dane-lim-dev--amon",
        )

    def test_parse_lsof_cwd_preserves_spaces(self):
        output = (
            "COMMAND PID USER FD TYPE DEVICE SIZE/OFF NODE NAME\n"
            "python 123 user cwd DIR 1,4 128 999 /tmp/path with spaces\n"
        )
        self.assertEqual(amon.parse_lsof_cwd(output), "/tmp/path with spaces")

    def test_pick_latest_jsonl_and_empty_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertIsNone(amon.pick_latest_jsonl(str(root)))
            old = root / "old.jsonl"
            new = root / "new.jsonl"
            old.write_text("{}\n", encoding="utf-8")
            new.write_text("{}\n", encoding="utf-8")
            os.utime(old, (100, 100))
            os.utime(new, (200, 200))
            self.assertEqual(amon.pick_latest_jsonl(str(root)), str(new))

    def test_resolve_claude_session_path_uses_lsof_cwd_slug(self):
        with tempfile.TemporaryDirectory() as home:
            session_dir = Path(home) / ".claude" / "projects" / "-tmp-path with spaces"
            session_dir.mkdir(parents=True)
            session = session_dir / "session.jsonl"
            session.write_text("{}\n", encoding="utf-8")
            lsof = (
                "COMMAND PID USER FD TYPE DEVICE SIZE/OFF NODE NAME\n"
                "python 123 user cwd DIR 1,4 128 999 /tmp/path with spaces\n"
            )
            with mock.patch.object(amon.Path, "home", return_value=Path(home)):
                with mock.patch.object(amon, "_run_lsof", return_value=lsof):
                    self.assertEqual(amon.resolve_claude_session_path(123), str(session))

    def test_parse_lsof_codex_jsonls_excludes_logs(self):
        output = "\n".join(
            [
                "COMMAND PID USER FD TYPE DEVICE SIZE/OFF NODE NAME",
                "codex 12 user 3r REG 1,4 10 1 /Users/me/.codex/sessions/2026/05/19/a.jsonl",
                "codex 12 user 4r REG 1,4 10 2 /Users/me/.codex/log/codex.log",
            ]
        )
        self.assertEqual(
            amon.parse_lsof_codex_jsonls(output),
            ["/Users/me/.codex/sessions/2026/05/19/a.jsonl"],
        )

    def test_resolve_codex_session_paths_default_newest_and_all_existing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old = root / "old.jsonl"
            new = root / "new.jsonl"
            missing = root / "missing.jsonl"
            old.write_text("{}\n", encoding="utf-8")
            new.write_text("{}\n", encoding="utf-8")
            os.utime(old, (100, 100))
            os.utime(new, (200, 200))
            lsof = "\n".join(
                [
                    "COMMAND PID USER FD TYPE DEVICE SIZE/OFF NODE NAME",
                    f"codex 12 user 3r REG 1,4 10 1 {old}",
                    f"codex 12 user 4r REG 1,4 10 2 {missing}",
                    f"codex 12 user 5r REG 1,4 10 3 {new}",
                ]
            ).replace(str(root), str(root / ".codex" / "sessions"), 1)
            session_root = root / ".codex" / "sessions"
            session_root.mkdir(parents=True)
            moved_old = session_root / "old.jsonl"
            moved_new = session_root / "new.jsonl"
            old.rename(moved_old)
            new.rename(moved_new)
            os.utime(moved_old, (100, 100))
            os.utime(moved_new, (200, 200))
            lsof = "\n".join(
                [
                    "COMMAND PID USER FD TYPE DEVICE SIZE/OFF NODE NAME",
                    f"codex 12 user 3r REG 1,4 10 1 {moved_old}",
                    f"codex 12 user 4r REG 1,4 10 2 {session_root / 'missing.jsonl'}",
                    f"codex 12 user 5r REG 1,4 10 3 {moved_new}",
                ]
            )
            with mock.patch.object(amon, "_run_lsof", return_value=lsof):
                self.assertEqual(amon.resolve_codex_session_paths(12), [str(moved_new)])
                self.assertEqual(
                    amon.resolve_codex_session_paths(12, all_sessions=True),
                    [str(moved_old), str(moved_new)],
                )

    def test_resolve_path_from_session_id_claude_exact_and_codex_newest(self):
        with tempfile.TemporaryDirectory() as home:
            home_path = Path(home)
            claude_dir = home_path / ".claude" / "projects" / "-tmp-work"
            claude_dir.mkdir(parents=True)
            claude_exact = claude_dir / "abc123.jsonl"
            claude_near = claude_dir / "abc123-extra.jsonl"
            claude_exact.write_text("{}\n", encoding="utf-8")
            claude_near.write_text("{}\n", encoding="utf-8")

            codex_dir = home_path / ".codex" / "sessions" / "2026" / "05" / "19"
            codex_dir.mkdir(parents=True)
            codex_old = codex_dir / "run-xyz789-old.jsonl"
            codex_new = codex_dir / "run-xyz789-new.jsonl"
            codex_old.write_text("{}\n", encoding="utf-8")
            codex_new.write_text("{}\n", encoding="utf-8")
            os.utime(codex_old, (100, 100))
            os.utime(codex_new, (200, 200))

            with mock.patch.object(amon.Path, "home", return_value=home_path):
                self.assertEqual(amon.resolve_path_from_session_id("abc123"), str(claude_exact))
                self.assertEqual(amon.resolve_path_from_session_id("xyz789"), str(codex_new))
                self.assertIsNone(amon.resolve_path_from_session_id("missing"))


class TestEventFormatting(unittest.TestCase):
    def _fixture_events(self, name):
        path = FIXTURES / name
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

    def test_truncate_collapses_newlines_and_limits(self):
        self.assertEqual(amon._truncate("first\nsecond\tthird", 20), "first second third")
        self.assertEqual(amon._truncate("abcdefghijklmnopqrstuvwxyz", 10), "abcdefg...")

    def test_tool_detail_prefers_primary_keys_and_fallbacks(self):
        self.assertEqual(amon._tool_detail({"command": "ls -la"}), "ls -la")
        self.assertEqual(amon._tool_detail({"file_path": "/tmp/a.py"}), "/tmp/a.py")
        self.assertEqual(amon._tool_detail({"path": "/tmp/b.py"}), "/tmp/b.py")
        self.assertEqual(amon._tool_detail({"description": "fallback"}), "fallback")

    def test_claude_fixture_formats_text_and_tools(self):
        events = self._fixture_events("claude_session.jsonl")
        lines = [
            amon.format_event(event, "claude", "abc123", color="never")
            for event in events
        ]
        self.assertIn("[claude/abc123] Msg I will inspect the file. Then summarize it.", lines)
        self.assertIn("[claude/abc123] Tool Bash ls -la", lines)
        self.assertIn("[claude/abc123] Tool Read /tmp/example.py", lines)
        self.assertIsNone(lines[-1])

    def test_claude_legacy_attachment_tool_use_fallback(self):
        event = {
            "type": "attachment",
            "attachment": {
                "type": "tool_use",
                "tool_name": "Edit",
                "input": {"file_path": "/tmp/edit.py"},
            },
        }
        self.assertEqual(
            amon.format_event(event, "claude", "sid", color="never"),
            "[claude/sid] Tool Edit /tmp/edit.py",
        )

    def test_codex_fixture_formats_text_and_function_call(self):
        events = self._fixture_events("codex_session.jsonl")
        lines = [
            amon.format_event(event, "codex", "def456", color="never")
            for event in events
        ]
        self.assertIn("[codex/def456] Msg Done. Second line.", lines)
        self.assertIn("[codex/def456] Tool exec_command ls -la", lines)
        self.assertIsNone(lines[2])
        self.assertIsNone(lines[3])

    def test_color_never_has_no_ansi_and_always_has_ansi_for_tool(self):
        event = self._fixture_events("codex_session.jsonl")[1]
        plain = amon.format_event(event, "codex", "sid", color="never")
        colored = amon.format_event(event, "codex", "sid", color="always")
        self.assertNotIn("\033[", plain)
        self.assertIn("\033[", colored)


class TestJsonlTail(unittest.TestCase):
    def test_initial_read_and_second_read_without_new_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "session.jsonl"
            path.write_text('{"a":1}\n{"b":2}\n', encoding="utf-8")
            tail = amon.JsonlTail(str(path))
            self.assertEqual(tail.read_new_lines(), [{"a": 1}, {"b": 2}])
            self.assertEqual(tail.read_new_lines(), [])

    def test_appended_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "session.jsonl"
            path.write_text('{"a":1}\n', encoding="utf-8")
            tail = amon.JsonlTail(str(path))
            tail.read_new_lines()
            with path.open("a", encoding="utf-8") as handle:
                handle.write('{"b":2}\n')
            self.assertEqual(tail.read_new_lines(), [{"b": 2}])

    def test_malformed_and_empty_lines_are_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "session.jsonl"
            path.write_text('\nnot-json\n{"ok":true}\n', encoding="utf-8")
            tail = amon.JsonlTail(str(path))
            self.assertEqual(tail.read_new_lines(), [{"ok": True}])

    def test_truncation_resets_offset(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "session.jsonl"
            path.write_text('{"a":1}\n{"b":2}\n', encoding="utf-8")
            tail = amon.JsonlTail(str(path))
            tail.read_new_lines()
            path.write_text('{"c":3}\n', encoding="utf-8")
            self.assertEqual(tail.read_new_lines(), [{"c": 3}])

    def test_missing_file_returns_empty_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            tail = amon.JsonlTail(str(Path(tmp) / "missing.jsonl"))
            self.assertEqual(tail.read_new_lines(), [])


class TestIdleAndProcessState(unittest.TestCase):
    def test_idle_state_no_warning_before_threshold(self):
        idle = amon.IdleStateMachine(threshold=10, now=100)
        self.assertFalse(idle.should_warn(now=109.9))

    def test_idle_state_warns_once_at_threshold(self):
        idle = amon.IdleStateMachine(threshold=10, now=100)
        self.assertTrue(idle.should_warn(now=110))
        self.assertFalse(idle.should_warn(now=111))

    def test_idle_state_touch_rearms_warning(self):
        idle = amon.IdleStateMachine(threshold=10, now=100)
        self.assertTrue(idle.should_warn(now=110))
        idle.touch(now=120)
        self.assertFalse(idle.should_warn(now=129))
        self.assertTrue(idle.should_warn(now=130))

    def test_pid_alive_process_lookup_error_means_dead(self):
        with mock.patch.object(amon.os, "kill", side_effect=ProcessLookupError):
            self.assertFalse(amon._pid_alive(123))

    def test_pid_alive_permission_error_means_alive(self):
        with mock.patch.object(amon.os, "kill", side_effect=PermissionError):
            self.assertTrue(amon._pid_alive(123))

    def test_pid_alive_other_os_error_means_dead(self):
        with mock.patch.object(amon.os, "kill", side_effect=OSError):
            self.assertFalse(amon._pid_alive(123))

    def test_pid_alive_no_error_means_alive(self):
        with mock.patch.object(amon.os, "kill", return_value=None):
            self.assertTrue(amon._pid_alive(123))


class TestRunTail(unittest.TestCase):
    def test_run_tail_primes_existing_history_and_prints_new_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "session.jsonl"
            path.write_text('{"type":"response_item","payload":{"type":"message","role":"assistant","content":[{"type":"output_text","text":"old"}]}}\n', encoding="utf-8")
            out = io.StringIO()

            def sleep(_seconds):
                with path.open("a", encoding="utf-8") as handle:
                    handle.write('{"type":"response_item","payload":{"type":"message","role":"assistant","content":[{"type":"output_text","text":"new"}]}}\n')

            code = amon.run_tail(
                str(path),
                "codex",
                "sid",
                idle_threshold=99,
                poll_interval=0,
                max_iterations=2,
                sleep_func=sleep,
                output=out,
            )
            self.assertEqual(code, 0)
            self.assertNotIn("old", out.getvalue())
            self.assertIn("[codex/sid] Msg new", out.getvalue())

    def test_run_tail_prints_idle_warning_once_and_rearms_after_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "session.jsonl"
            path.write_text("", encoding="utf-8")
            out = io.StringIO()
            times = iter([0, 0, 10, 10, 11, 11])

            amon.run_tail(
                str(path),
                "claude",
                "sid",
                idle_threshold=10,
                poll_interval=0,
                max_iterations=2,
                now_func=lambda: next(times),
                sleep_func=lambda _seconds: None,
                output=out,
            )
            self.assertEqual(out.getvalue().count("IDLE"), 1)

    def test_run_tail_prints_agent_exited_when_pid_disappears(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "session.jsonl"
            path.write_text("", encoding="utf-8")
            out = io.StringIO()
            with mock.patch.object(amon, "_pid_alive", return_value=False):
                code = amon.run_tail(
                    str(path),
                    "claude",
                    "sid",
                    idle_threshold=10,
                    pid=123,
                    poll_interval=0,
                    max_iterations=1,
                    output=out,
                )
            self.assertEqual(code, 0)
            self.assertIn("AGENT EXITED", out.getvalue())


class TestSnapshot(unittest.TestCase):
    def test_snapshot_working_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "session.jsonl"
            path.write_text((FIXTURES / "codex_session.jsonl").read_text(encoding="utf-8"), encoding="utf-8")
            os.utime(path, (900, 900))
            code, line = amon.snapshot_status(
                str(path),
                "codex",
                "sid",
                idle_threshold=200,
                now_func=lambda: 1000,
            )
            self.assertEqual(code, 0)
            clock = time.strftime("%H:%M:%S", time.localtime(1000))
            self.assertIn(f"{clock} [codex/sid] status=working idle=100s last=Tool exec_command ls -la", line)

    def test_snapshot_idle_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "session.jsonl"
            path.write_text((FIXTURES / "claude_session.jsonl").read_text(encoding="utf-8"), encoding="utf-8")
            os.utime(path, (800, 800))
            code, line = amon.snapshot_status(
                str(path),
                "claude",
                "sid",
                idle_threshold=100,
                now_func=lambda: 1000,
            )
            self.assertEqual(code, 2)
            self.assertIn("status=idle idle=200s", line)
            self.assertIn("last=Tool Read /tmp/example.py", line)

    def test_snapshot_no_useful_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "session.jsonl"
            path.write_text('{"type":"user"}\n', encoding="utf-8")
            os.utime(path, (1000, 1000))
            code, line = amon.snapshot_status(
                str(path),
                "claude",
                "sid",
                idle_threshold=100,
                now_func=lambda: 1000,
            )
            self.assertEqual(code, 0)
            self.assertIn("last=(no events)", line)

    def test_snapshot_skips_malformed_before_valid_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "session.jsonl"
            path.write_text(
                'not-json\n{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"ok"}]}}\n',
                encoding="utf-8",
            )
            os.utime(path, (1000, 1000))
            code, line = amon.snapshot_status(
                str(path),
                "claude",
                "sid",
                idle_threshold=100,
                now_func=lambda: 1000,
            )
            self.assertEqual(code, 0)
            self.assertIn("last=Msg ok", line)

    def test_snapshot_missing_path_exits_one(self):
        code, line = amon.snapshot_status(
            "/tmp/amon-definitely-missing.jsonl",
            "codex",
            "sid",
            idle_threshold=100,
            now_func=lambda: 1000,
        )
        self.assertEqual(code, 1)
        self.assertIn("missing", line)

    def test_snapshot_color_passthrough(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "session.jsonl"
            path.write_text((FIXTURES / "codex_session.jsonl").read_text(encoding="utf-8"), encoding="utf-8")
            os.utime(path, (1000, 1000))
            code, line = amon.snapshot_status(
                str(path),
                "codex",
                "sid",
                idle_threshold=100,
                color="always",
                now_func=lambda: 1000,
            )
            self.assertEqual(code, 0)
            self.assertIn("\033[", line)

    def test_run_snapshot_writes_to_error_for_missing_path(self):
        err = io.StringIO()
        code = amon.run_snapshot(
            "/tmp/amon-definitely-missing.jsonl",
            "codex",
            "sid",
            idle_threshold=100,
            error=err,
        )
        self.assertEqual(code, 1)
        self.assertIn("ERROR", err.getvalue())


class TestDiscovery(unittest.TestCase):
    def test_candidate_pids_deduplicates_pgrep_results(self):
        outputs = {
            ("pgrep", "-f", "claude"): "10\nbad\n11\n",
            ("pgrep", "-f", "codex"): "11\n12\n",
        }

        def fake_run(args, **_kwargs):
            return mock.Mock(stdout=outputs[tuple(args)])

        with mock.patch.object(amon.subprocess, "run", side_effect=fake_run):
            self.assertEqual(amon.candidate_pids(["claude", "codex"]), [10, 11, 12])

    def test_process_command_uses_ps_command(self):
        def fake_run(args, **_kwargs):
            self.assertEqual(args, ["ps", "-o", "command=", "-p", "123"])
            return mock.Mock(stdout="/opt/bin/claude -p hello\n")

        with mock.patch.object(amon.subprocess, "run", side_effect=fake_run):
            self.assertEqual(amon.process_command(123), "/opt/bin/claude -p hello")

    def test_claude_noninteractive_accepts_print_flags(self):
        self.assertTrue(amon.is_claude_noninteractive("/opt/bin/claude -p hello"))
        self.assertTrue(amon.is_claude_noninteractive("claude --print hello"))

    def test_claude_noninteractive_rejects_interactive_and_resume_without_print(self):
        self.assertFalse(amon.is_claude_noninteractive("claude"))
        self.assertFalse(amon.is_claude_noninteractive("claude --resume abc123"))

    def test_codex_exec_accepts_direct_vendor_command_only(self):
        self.assertTrue(amon.is_codex_exec("/opt/homebrew/bin/codex exec run this"))
        self.assertFalse(amon.is_codex_exec("/usr/bin/node /pkg/codex exec run this"))
        self.assertFalse(amon.is_codex_exec("codex app-server"))
        self.assertFalse(amon.is_codex_exec("codex"))

    def test_discover_active_sessions_uses_filters_and_resolvers(self):
        commands = {
            1: "claude -p hello",
            2: "claude --resume abc",
            3: "codex exec run",
            4: "codex app-server",
        }
        with mock.patch.object(amon, "candidate_pids", return_value=[1, 2, 3, 4]):
            with mock.patch.object(amon, "process_command", side_effect=lambda pid: commands[pid]):
                with mock.patch.object(amon, "resolve_claude_session_path", return_value="/tmp/claude.jsonl"):
                    with mock.patch.object(
                        amon,
                        "resolve_codex_session_paths",
                        return_value=["/tmp/codex-a.jsonl", "/tmp/codex-b.jsonl"],
                    ) as codex_resolver:
                        sessions = amon.discover_active_sessions(codex_all=True)
        self.assertEqual(
            sessions,
            [
                {"agent": "claude", "pid": 1, "path": "/tmp/claude.jsonl"},
                {"agent": "codex", "pid": 3, "path": "/tmp/codex-a.jsonl"},
                {"agent": "codex", "pid": 3, "path": "/tmp/codex-b.jsonl"},
            ],
        )
        codex_resolver.assert_called_once_with(3, all_sessions=True)


class TestModeBLauncher(unittest.TestCase):
    def test_encode_decode_session_spec_round_trip_preserves_spaces(self):
        session = {"agent": "codex", "pid": 123, "path": "/tmp/path with spaces/session.jsonl"}
        spec = amon.encode_session_spec(session)
        self.assertEqual(amon.decode_session_spec(spec), session)
        self.assertNotIn("path with spaces", spec)

    def test_session_title_uses_runtime_and_full_session_stem(self):
        self.assertEqual(
            amon.session_title(
                {
                    "agent": "claude",
                    "pid": 123,
                    "path": "/tmp/550e8400-e29b-41d4-a716-446655440000.jsonl",
                }
            ),
            "claude/550e8400-e29b-41d4-a716-446655440000",
        )
        self.assertEqual(
            amon.session_title(
                {
                    "agent": "codex",
                    "pid": 123,
                    "path": (
                        "/tmp/rollout-2026-05-19T09-00-00-"
                        "019cb430-debf-70e3-9449-e4cde0120f9c.jsonl"
                    ),
                }
            ),
            "codex/019cb430-debf-70e3-9449-e4cde0120f9c",
        )
        self.assertEqual(
            amon.session_title(
                {"agent": "codex", "pid": 123, "path": "/tmp/custom-session.jsonl"}
            ),
            "codex/custom-session",
        )

    def test_decode_session_spec_rejects_invalid_payload(self):
        with self.assertRaises(ValueError):
            amon.decode_session_spec("not-base64")

    def test_run_mode_b_missing_xpanes_exits_three(self):
        err = io.StringIO()
        with mock.patch.object(amon.shutil, "which", return_value=None):
            code = amon.run_mode_b(30, codex_all=False, error=err)
        self.assertEqual(code, 3)
        self.assertIn("xpanes", err.getvalue())

    def test_run_mode_b_no_sessions_exits_zero(self):
        err = io.StringIO()
        with mock.patch.object(amon.shutil, "which", return_value="/opt/homebrew/bin/xpanes"):
            with mock.patch.object(amon, "discover_active_sessions", return_value=[]):
                code = amon.run_mode_b(30, codex_all=False, error=err)
        self.assertEqual(code, 0)
        self.assertIn("no active", err.getvalue())

    def test_run_mode_b_xpanes_command_shape(self):
        session = {"agent": "claude", "pid": 456, "path": "/tmp/path with spaces/session.jsonl"}
        captured = {}

        def fake_run(args, **_kwargs):
            captured["args"] = args
            return mock.Mock(returncode=0)

        with mock.patch.object(amon.shutil, "which", return_value="/opt/homebrew/bin/xpanes"):
            with mock.patch.object(amon, "discover_active_sessions", return_value=[session]):
                with mock.patch.object(amon.subprocess, "run", side_effect=fake_run):
                    code = amon.run_mode_b(45, codex_all=True)
        self.assertEqual(code, 0)
        args = captured["args"]
        self.assertEqual(args[0], "/opt/homebrew/bin/xpanes")
        self.assertEqual(args[1], "-t")
        self.assertEqual(args[2], "-c")
        self.assertIn("--session-title {}", args[3])
        self.assertIn("--session-spec {}", args[3])
        self.assertIn("--idle-threshold 45", args[3])
        self.assertIn("--color=always", args[3])
        self.assertNotIn("/tmp/path with spaces/session.jsonl", args[3])
        self.assertEqual(amon.decode_session_spec(args[4]), session)

    def test_run_mode_b_preserves_fractional_idle_threshold(self):
        captured = {}

        def fake_run(args, **_kwargs):
            captured["args"] = args
            return mock.Mock(returncode=0)

        with mock.patch.object(amon.shutil, "which", return_value="/opt/homebrew/bin/xpanes"):
            with mock.patch.object(
                amon,
                "discover_active_sessions",
                return_value=[{"agent": "codex", "pid": 123, "path": "/tmp/session.jsonl"}],
            ):
                with mock.patch.object(amon.subprocess, "run", side_effect=fake_run):
                    code = amon.run_mode_b(0.5, codex_all=False)
        self.assertEqual(code, 0)
        self.assertIn("--idle-threshold 0.5", captured["args"][3])


if __name__ == "__main__":
    unittest.main()
