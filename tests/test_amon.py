import importlib.util
import json
import io
from importlib.machinery import SourceFileLoader
import os
import subprocess
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


class TestClaudeSessionWrapperInstaller(unittest.TestCase):
    def test_print_contains_lowercase_uuid_session_wrapper(self):
        script = ROOT / "scripts" / "install-claude-session-wrapper.sh"
        proc = subprocess.run(
            [str(script), "--print"],
            check=True,
            stdout=subprocess.PIPE,
            text=True,
        )
        self.assertIn("claude()", proc.stdout)
        self.assertIn("uuidgen | tr '[:upper:]' '[:lower:]'", proc.stdout)
        self.assertIn('command claude --session-id "$amon_claude_session_id" "$@"', proc.stdout)
        self.assertIn("--resume|--continue", proc.stdout)

    def test_installer_replaces_existing_managed_block(self):
        script = ROOT / "scripts" / "install-claude-session-wrapper.sh"
        with tempfile.TemporaryDirectory() as tmp:
            profile = Path(tmp) / ".bash_profile"
            profile.write_text(
                "before\n"
                "# >>> amon claude session wrapper >>>\n"
                "old\n"
                "# <<< amon claude session wrapper <<<\n"
                "after\n",
                encoding="utf-8",
            )
            for _ in range(2):
                subprocess.run(
                    [str(script), "--profile", str(profile)],
                    check=True,
                    stdout=subprocess.PIPE,
                    text=True,
                )
            content = profile.read_text(encoding="utf-8")
        self.assertIn("before", content)
        self.assertIn("after", content)
        self.assertNotIn("\nold\n", content)
        self.assertEqual(content.count("# >>> amon claude session wrapper >>>"), 1)
        self.assertEqual(content.count("command claude --session-id"), 1)

    def test_uninstaller_removes_only_managed_block(self):
        install_script = ROOT / "scripts" / "install-claude-session-wrapper.sh"
        uninstall_script = ROOT / "scripts" / "uninstall-claude-session-wrapper.sh"
        with tempfile.TemporaryDirectory() as tmp:
            profile = Path(tmp) / ".bash_profile"
            profile.write_text("before\nafter\n", encoding="utf-8")
            subprocess.run(
                [str(install_script), "--profile", str(profile)],
                check=True,
                stdout=subprocess.PIPE,
                text=True,
            )
            subprocess.run(
                [str(uninstall_script), "--profile", str(profile)],
                check=True,
                stdout=subprocess.PIPE,
                text=True,
            )
            content = profile.read_text(encoding="utf-8")
        self.assertIn("before", content)
        self.assertIn("after", content)
        self.assertNotIn("# >>> amon claude session wrapper >>>", content)
        self.assertNotIn("command claude --session-id", content)

    def test_uninstaller_is_noop_without_profile_or_block(self):
        uninstall_script = ROOT / "scripts" / "uninstall-claude-session-wrapper.sh"
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing_profile"
            proc = subprocess.run(
                [str(uninstall_script), "--profile", str(missing)],
                check=True,
                stdout=subprocess.PIPE,
                text=True,
            )
            self.assertIn("nothing to remove", proc.stdout)

            profile = Path(tmp) / ".bash_profile"
            profile.write_text("plain\n", encoding="utf-8")
            proc = subprocess.run(
                [str(uninstall_script), "--profile", str(profile)],
                check=True,
                stdout=subprocess.PIPE,
                text=True,
            )
            self.assertIn("nothing to remove", proc.stdout)
            self.assertEqual(profile.read_text(encoding="utf-8"), "plain\n")


class TestSkeleton(unittest.TestCase):
    def test_imports_extensionless_executable(self):
        self.assertTrue(hasattr(amon, "main"))

    def test_main_accepts_argv(self):
        with mock.patch.object(amon, "run_sessions_mode", return_value=0):
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
            pid=None,
            process_state=None,
        )

    def test_main_session_path_once_marks_existing_file_exited_without_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".codex" / "sessions" / "session-123456789.jsonl"
            path.parent.mkdir(parents=True)
            path.write_text("{}\n", encoding="utf-8")
            with mock.patch.object(amon, "resolve_session_pid", return_value=None):
                with mock.patch.object(amon, "run_snapshot", return_value=4) as snapshot:
                    code = amon.main(["--session-path", str(path), "--once"])
        self.assertEqual(code, 4)
        snapshot.assert_called_once_with(
            str(path),
            "codex",
            "session-",
            60.0,
            color="never",
            pid=None,
            process_state="exited",
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

    def test_main_session_id_opens_detail_with_lines(self):
        with mock.patch.object(
            amon,
            "resolve_path_from_session_id",
            return_value="/tmp/.codex/sessions/run-abcdef.jsonl",
        ):
            with mock.patch.object(amon, "run_session_detail_path", return_value=0) as detail:
                code = amon.main(["--session-id", "abcdef", "--lines", "12"])
        self.assertEqual(code, 0)
        detail.assert_called_once_with(
            "/tmp/.codex/sessions/run-abcdef.jsonl",
            "codex",
            lines=12,
            color="auto",
        )

    def test_main_session_path_tail_exits_when_no_live_process_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".codex" / "sessions" / "session-123456789.jsonl"
            path.parent.mkdir(parents=True)
            path.write_text("{}\n", encoding="utf-8")
            out = io.StringIO()
            with mock.patch.object(amon, "resolve_session_pid", return_value=None):
                with mock.patch.object(amon, "run_tail") as tail:
                    with mock.patch.object(amon.sys, "stdout", out):
                        code = amon.main(["--session-path", str(path)])
        self.assertEqual(code, 0)
        self.assertIn("AGENT EXITED", out.getvalue())
        tail.assert_not_called()

    def test_main_session_spec_once_calls_snapshot_with_decoded_pid(self):
        spec = amon.encode_session_spec(
            {"agent": "claude", "pid": 321, "path": "/tmp/claude-session.jsonl"}
        )
        with mock.patch.object(amon, "run_snapshot", return_value=4) as snapshot:
            code = amon.main(["--session-spec", spec, "--once"])
        self.assertEqual(code, 4)
        snapshot.assert_called_once_with(
            "/tmp/claude-session.jsonl",
            "claude",
            "claude-s",
            60.0,
            color="never",
            pid=321,
            process_state=None,
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

    def test_main_no_args_calls_sessions_mode(self):
        with mock.patch.object(amon, "run_sessions_mode", return_value=0) as sessions_mode:
            code = amon.main([])
        self.assertEqual(code, 0)
        sessions_mode.assert_called_once_with(
            60.0,
            codex_all=False,
            scope=amon.SCOPE_ALL,
            lines=amon.DEFAULT_DETAIL_LINES,
            color="auto",
        )

    def test_main_current_calls_sessions_mode_current_scope(self):
        with mock.patch.object(amon, "run_sessions_mode", return_value=0) as sessions_mode:
            code = amon.main(["--current"])
        self.assertEqual(code, 0)
        sessions_mode.assert_called_once_with(
            60.0,
            codex_all=False,
            scope=amon.SCOPE_CURRENT,
            lines=amon.DEFAULT_DETAIL_LINES,
            color="auto",
        )

    def test_main_lines_passes_to_sessions_mode(self):
        with mock.patch.object(amon, "run_sessions_mode", return_value=0) as sessions_mode:
            code = amon.main(["--lines", "25"])
        self.assertEqual(code, 0)
        sessions_mode.assert_called_once_with(
            60.0,
            codex_all=False,
            scope=amon.SCOPE_ALL,
            lines=25,
            color="auto",
        )

    def test_main_lines_rejects_non_positive_values(self):
        with mock.patch.object(amon.sys, "stderr", io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                amon.main(["--lines", "0"])
        self.assertEqual(caught.exception.code, 1)

    def test_main_xpane_calls_mode_b(self):
        with mock.patch.object(amon, "run_mode_b", return_value=0) as mode_b:
            code = amon.main(["xpane"])
        self.assertEqual(code, 0)
        mode_b.assert_called_once_with(
            60.0,
            codex_all=False,
            color="always",
            scope=amon.SCOPE_ALL,
        )

    def test_main_xpane_current_calls_mode_b_current_scope(self):
        with mock.patch.object(amon, "run_mode_b", return_value=0) as mode_b:
            code = amon.main(["xpane", "--current"])
        self.assertEqual(code, 0)
        mode_b.assert_called_once_with(
            60.0,
            codex_all=False,
            color="always",
            scope=amon.SCOPE_CURRENT,
        )

    def test_main_positional_session_id_opens_detail(self):
        with mock.patch.object(
            amon,
            "resolve_path_from_session_id",
            return_value="/tmp/.codex/sessions/run-abcdef.jsonl",
        ):
            with mock.patch.object(amon, "run_session_detail_path", return_value=0) as detail:
                code = amon.main(["abcdef"])
        self.assertEqual(code, 0)
        detail.assert_called_once_with(
            "/tmp/.codex/sessions/run-abcdef.jsonl",
            "codex",
            lines=amon.DEFAULT_DETAIL_LINES,
            color="auto",
        )

    def test_main_unknown_positional_target_points_to_xpane(self):
        err = io.StringIO()
        with mock.patch.object(amon, "resolve_path_from_session_id", return_value=None):
            with mock.patch.object(amon.sys, "stderr", err):
                code = amon.main(["legacy-arg"])
        self.assertEqual(code, 1)
        self.assertIn("unknown session id or mode: legacy-arg", err.getvalue())
        self.assertIn("amon xpane", err.getvalue())

    def test_main_unknown_positional_targets_point_to_xpane(self):
        err = io.StringIO()
        with mock.patch.object(amon, "resolve_path_from_session_id") as resolve:
            with mock.patch.object(amon.sys, "stderr", err):
                code = amon.main(["foo", "bar"])
        self.assertEqual(code, 1)
        resolve.assert_not_called()
        self.assertIn("unknown session id or mode: foo bar", err.getvalue())
        self.assertIn("amon xpane", err.getvalue())
        self.assertNotIn("unrecognized arguments", err.getvalue())

    def test_main_session_id_resolves_and_uses_snapshot_when_once(self):
        with mock.patch.object(
            amon,
            "resolve_path_from_session_id",
            return_value="/tmp/.codex/sessions/run-abcdef.jsonl",
        ):
            with mock.patch.object(amon.Path, "exists", return_value=True):
                with mock.patch.object(amon, "resolve_session_pid", return_value=555):
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
            color="never",
            pid=555,
            process_state="alive",
        )

    def test_main_session_id_detail_uses_requested_color(self):
        with mock.patch.object(
            amon,
            "resolve_path_from_session_id",
            return_value="/tmp/.codex/sessions/run-abcdef.jsonl",
        ):
            with mock.patch.object(amon, "run_session_detail_path", return_value=0) as detail:
                code = amon.main(["--session-id", "abcdef", "--color", "always"])
        self.assertEqual(code, 0)
        detail.assert_called_once_with(
            "/tmp/.codex/sessions/run-abcdef.jsonl",
            "codex",
            lines=amon.DEFAULT_DETAIL_LINES,
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

    def test_process_cwd_uses_lsof_cwd(self):
        output = (
            "COMMAND PID USER FD TYPE DEVICE SIZE/OFF NODE NAME\n"
            "python 123 user cwd DIR 1,4 128 999 /tmp/path with spaces\n"
        )
        with mock.patch.object(amon, "_run_lsof", return_value=output):
            self.assertEqual(amon.process_cwd(123), "/tmp/path with spaces")

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

    def test_resolve_claude_session_path_prefers_cmdline_session_id(self):
        with tempfile.TemporaryDirectory() as home:
            session_dir = Path(home) / ".claude" / "projects" / "-tmp-path"
            session_dir.mkdir(parents=True)
            selected = session_dir / "11111111-1111-1111-1111-111111111111.jsonl"
            latest = session_dir / "22222222-2222-2222-2222-222222222222.jsonl"
            selected.write_text("{}\n", encoding="utf-8")
            latest.write_text("{}\n", encoding="utf-8")
            os.utime(selected, (100, 100))
            os.utime(latest, (200, 200))
            lsof = (
                "COMMAND PID USER FD TYPE DEVICE SIZE/OFF NODE NAME\n"
                "python 123 user cwd DIR 1,4 128 999 /tmp/path\n"
            )
            cmdline = (
                "claude --session-id 11111111-1111-1111-1111-111111111111 "
                "-p hello"
            )
            with mock.patch.object(amon.Path, "home", return_value=Path(home)):
                with mock.patch.object(amon, "_run_lsof", return_value=lsof):
                    self.assertEqual(
                        amon.resolve_claude_session_path(123, cmdline=cmdline),
                        str(selected),
                    )

    def test_resolve_claude_session_path_does_not_fallback_when_session_id_missing(self):
        with tempfile.TemporaryDirectory() as home:
            session_dir = Path(home) / ".claude" / "projects" / "-tmp-path"
            session_dir.mkdir(parents=True)
            latest = session_dir / "latest.jsonl"
            latest.write_text("{}\n", encoding="utf-8")
            lsof = (
                "COMMAND PID USER FD TYPE DEVICE SIZE/OFF NODE NAME\n"
                "python 123 user cwd DIR 1,4 128 999 /tmp/path\n"
            )
            with mock.patch.object(amon.Path, "home", return_value=Path(home)):
                with mock.patch.object(amon, "_run_lsof", return_value=lsof):
                    self.assertIsNone(
                        amon.resolve_claude_session_path(
                            123,
                            cmdline="claude --session-id missing -p hello",
                        )
                    )

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

    def test_scope_current_uses_realpath_subtree_matching(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            child = root / "child"
            sibling = Path(tmp) / "repo-other"
            root.mkdir()
            child.mkdir()
            sibling.mkdir()
            link = Path(tmp) / "repo-link"
            link.symlink_to(root, target_is_directory=True)

            self.assertTrue(amon._is_path_at_or_under(str(link / "child"), str(root)))
            self.assertTrue(amon._is_path_at_or_under(str(root), str(link)))
            self.assertFalse(amon._is_path_at_or_under(str(sibling), str(root)))


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

    def test_agent_exit_event_detection(self):
        self.assertTrue(amon.is_agent_exit_event({"type": "result"}, "claude"))
        self.assertTrue(amon.is_agent_exit_event({"type": "agent_exit"}, "codex"))
        self.assertTrue(
            amon.is_agent_exit_event(
                {"type": "event", "payload": {"type": "session_exit"}},
                "codex",
            )
        )
        self.assertFalse(amon.is_agent_exit_event({"type": "response_item"}, "codex"))


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

    def test_run_tail_exits_when_agent_exit_event_arrives(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "session.jsonl"
            path.write_text("", encoding="utf-8")
            out = io.StringIO()

            def sleep(_seconds):
                with path.open("a", encoding="utf-8") as handle:
                    handle.write('{"type":"result","subtype":"success"}\n')

            code = amon.run_tail(
                str(path),
                "claude",
                "sid",
                idle_threshold=99,
                poll_interval=0,
                max_iterations=2,
                sleep_func=sleep,
                output=out,
            )
            self.assertEqual(code, 0)
            self.assertIn("AGENT EXITED", out.getvalue())


class TestSessionDetail(unittest.TestCase):
    class _FakeDetailScreen:
        def __init__(self, keys=None, on_getch=None):
            self.keys = list(keys or [])
            self.on_getch = on_getch
            self.getch_calls = 0

        def timeout(self, _milliseconds):
            pass

        def getmaxyx(self):
            return (10, 120)

        def erase(self):
            pass

        def addnstr(self, _row, _column, _line, _width):
            pass

        def refresh(self):
            pass

        def getch(self):
            self.getch_calls += 1
            if self.on_getch is not None:
                self.on_getch(self.getch_calls)
            if self.keys:
                return self.keys.pop(0)
            return -1

    def _write_codex_log(self, root, name, messages):
        path = Path(root) / name
        path.write_text(
            "".join(
                json.dumps(
                    {
                        "type": "response_item",
                        "payload": {
                            "type": "message",
                            "role": "assistant",
                            "content": [{"type": "output_text", "text": message}],
                        },
                    }
                )
                + "\n"
                for message in messages
            ),
            encoding="utf-8",
        )
        return path

    def test_recent_jsonl_events_loads_recent_physical_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "session.jsonl"
            path.write_text(
                '{"idx":1}\nnot-json\n{"idx":2}\n{"idx":3}\n',
                encoding="utf-8",
            )

            events = amon.read_recent_jsonl_events(str(path), 2)

        self.assertEqual(events, [{"idx": 2}, {"idx": 3}])

    def test_recent_log_lines_formats_only_recent_messages(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_codex_log(tmp, "session.jsonl", ["old", "middle", "new"])

            lines = amon.read_recent_log_lines(str(path), "codex", "sid", 2)

        self.assertNotIn("old", "\n".join(lines))
        self.assertIn("[codex/sid] Msg middle", lines)
        self.assertIn("[codex/sid] Msg new", lines)

    def test_tail_policy_tails_running_and_unknown_only(self):
        self.assertTrue(amon.should_tail_detail_status("running"))
        self.assertTrue(amon.should_tail_detail_status("unknown"))
        self.assertFalse(amon.should_tail_detail_status("exited"))
        self.assertFalse(amon.should_tail_detail_status("failed"))

    def test_list_detail_back_keys_leave_detail(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_codex_log(tmp, "session.jsonl", ["one"])
            entry = amon.SessionEntry(
                session_id="session",
                agent="codex",
                path=str(path),
                status="exited",
                label="Session",
            )
            state = amon.SessionDetailState(entry, line_count=1)

            for key in ("q", "BACKSPACE", "ESC"):
                with self.subTest(key=key):
                    self.assertEqual(
                        amon.handle_session_detail_key(
                            state,
                            key,
                            viewport_lines=2,
                            exit_keys=amon.DETAIL_LIST_DETAIL_EXIT_KEYS,
                        ),
                        "quit",
                    )

    def test_direct_detail_exit_keys_stay_q_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_codex_log(tmp, "session.jsonl", ["one"])
            entry = amon.SessionEntry(
                session_id="session",
                agent="codex",
                path=str(path),
                status="exited",
                label="Session",
            )
            state = amon.SessionDetailState(entry, line_count=1)

            self.assertEqual(
                amon.handle_session_detail_key(state, "q", viewport_lines=2),
                "quit",
            )
            self.assertIsNone(amon.handle_session_detail_key(state, "BACKSPACE", 2))
            self.assertIsNone(amon.handle_session_detail_key(state, "ESC", 2))

    def test_curses_key_name_normalizes_detail_back_keys(self):
        self.assertEqual(amon._curses_key_name(27), "ESC")
        self.assertEqual(amon._curses_key_name(8), "BACKSPACE")
        self.assertEqual(amon._curses_key_name(127), "BACKSPACE")

    def test_detail_header_names_contextual_exit_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_codex_log(tmp, "session.jsonl", ["one"])
            entry = amon.SessionEntry(
                session_id="session",
                agent="codex",
                path=str(path),
                status="exited",
                label="Session",
            )
            state = amon.SessionDetailState(entry, line_count=1)

            list_lines = amon.render_session_detail_lines(
                state,
                width=140,
                height=4,
                exit_label="back",
                exit_keys=amon.DETAIL_LIST_DETAIL_EXIT_KEYS,
            )
            direct_lines = amon.render_session_detail_lines(
                state,
                width=140,
                height=4,
                exit_label="quit",
            )

        self.assertIn("q/Backspace/Esc back", list_lines[2])
        self.assertIn("q quit", direct_lines[2])

    def test_detail_body_style_marks_tool_warning_and_exit_lines(self):
        self.assertEqual(amon._detail_body_style("[codex/sid] Tool exec_command ls"), "tool")
        self.assertEqual(amon._detail_body_style("[codex/sid] IDLE idle=60s"), "warn")
        self.assertEqual(amon._detail_body_style("[codex/sid] AGENT EXITED"), "exited")

    def test_detail_state_follow_pauses_on_scroll_up_and_resumes_at_bottom(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_codex_log(tmp, "session.jsonl", ["one", "two", "three"])
            entry = amon.SessionEntry(
                session_id="session",
                agent="codex",
                path=str(path),
                status="exited",
                label="Session",
            )
            state = amon.SessionDetailState(entry, line_count=3)
            state.clamp_scroll(viewport_lines=2)
            self.assertTrue(state.follow)
            self.assertEqual(state.scroll_top, 1)

            amon.handle_session_detail_key(state, "UP", viewport_lines=2)
            self.assertFalse(state.follow)
            self.assertEqual(state.scroll_top, 0)

            amon.handle_session_detail_key(state, "DOWN", viewport_lines=2)
            self.assertTrue(state.follow)
            self.assertEqual(state.scroll_top, 1)

    def test_detail_state_tails_running_sessions_and_stops_on_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_codex_log(tmp, "session.jsonl", ["old"])
            entry = amon.SessionEntry(
                session_id="session",
                agent="codex",
                path=str(path),
                status="running",
                label="Session",
            )
            state = amon.SessionDetailState(entry, line_count=1)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(
                    '{"type":"response_item","payload":{"type":"message","role":"assistant",'
                    '"content":[{"type":"output_text","text":"new"}]}}\n'
                )
                handle.write('{"type":"agent_exit"}\n')

            state.poll_tail()

        self.assertIn("[codex/session] Msg new", state.lines)
        self.assertTrue(any("AGENT EXITED" in line for line in state.lines))
        self.assertFalse(state.tail_enabled)
        self.assertEqual(state.entry.status, "exited")

    def test_direct_detail_tui_exits_when_process_ends(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_codex_log(tmp, "session.jsonl", ["old"])
            entry = amon.SessionEntry(
                session_id="session",
                agent="codex",
                path=str(path),
                status="running",
                label="Session",
                pids=(123,),
            )
            screen = self._FakeDetailScreen()

            code = amon._run_session_detail_tui(
                screen,
                entry,
                line_count=1,
                exit_label="quit",
                exit_on_end=True,
                pid_alive_func=lambda _pid: False,
                poll_interval=0,
            )

        self.assertEqual(code, 0)
        self.assertEqual(entry.status, "exited")
        self.assertEqual(entry.pids, ())
        self.assertEqual(screen.getch_calls, 0)

    def test_direct_detail_tui_exits_when_agent_exit_arrives(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_codex_log(tmp, "session.jsonl", ["old"])
            entry = amon.SessionEntry(
                session_id="session",
                agent="codex",
                path=str(path),
                status="running",
                label="Session",
            )

            def append_exit(call_count):
                if call_count == 1:
                    with path.open("a", encoding="utf-8") as handle:
                        handle.write('{"type":"agent_exit"}\n')

            screen = self._FakeDetailScreen(on_getch=append_exit)

            code = amon._run_session_detail_tui(
                screen,
                entry,
                line_count=1,
                exit_label="quit",
                exit_on_end=True,
                poll_interval=0,
            )

        self.assertEqual(code, 0)
        self.assertEqual(entry.status, "exited")
        self.assertEqual(screen.getch_calls, 1)

    def test_list_detail_tui_waits_for_back_key_after_process_ends(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_codex_log(tmp, "session.jsonl", ["old"])
            entry = amon.SessionEntry(
                session_id="session",
                agent="codex",
                path=str(path),
                status="running",
                label="Session",
                pids=(123,),
            )
            screen = self._FakeDetailScreen(keys=[ord("q")])

            code = amon._run_session_detail_tui(
                screen,
                entry,
                line_count=1,
                exit_label="back",
                exit_keys=amon.DETAIL_LIST_DETAIL_EXIT_KEYS,
                exit_on_end=False,
                pid_alive_func=lambda _pid: False,
                poll_interval=0,
            )

        self.assertEqual(code, 0)
        self.assertEqual(entry.status, "running")
        self.assertEqual(screen.getch_calls, 1)

    def test_render_detail_header_includes_identity_status_and_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_codex_log(tmp, "session.jsonl", ["hello"])
            entry = amon.SessionEntry(
                session_id="session",
                agent="codex",
                path=str(path),
                status="running",
                label="Deploy watcher",
                project_display="amon",
                status_counts={"failed": 1, "running": 2, "unknown": 3, "exited": 4},
            )
            state = amon.SessionDetailState(entry, line_count=1)
            lines = amon.render_session_detail_lines(state, width=140, height=6)

        self.assertIn("amon detail Deploy watcher", lines[0])
        self.assertIn("session=session", lines[1])
        self.assertIn("project=amon", lines[1])
        self.assertIn("status=running", lines[1])
        self.assertIn("running=2 failed=1 unknown=3 exited=4", lines[1])

    def test_explicit_detail_existing_inactive_log_is_exited_static(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_codex_log(tmp, "session.jsonl", ["finished without marker"])
            out = io.StringIO()
            with mock.patch.object(amon, "resolve_active_session_record", return_value=None):
                code = amon.run_session_detail_path(
                    str(path),
                    "codex",
                    lines=10,
                    output=out,
                )

        self.assertEqual(code, 0)
        lines = out.getvalue().splitlines()
        self.assertTrue(any("status=exited" in line for line in lines))
        self.assertTrue(any("tail=static" in line for line in lines))
        self.assertTrue(any("exited=1" in line for line in lines))


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
            self.assertIn(
                f"{clock} [codex/sid] status=working idle=100s "
                "process=unknown last=Tool exec_command ls -la",
                line,
            )

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
            self.assertIn("process=unknown", line)
            self.assertIn("last=Tool Read /tmp/example.py", line)

    def test_snapshot_live_process_includes_pid(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "session.jsonl"
            path.write_text((FIXTURES / "codex_session.jsonl").read_text(encoding="utf-8"), encoding="utf-8")
            os.utime(path, (900, 900))
            with mock.patch.object(amon, "_pid_alive", return_value=True):
                code, line = amon.snapshot_status(
                    str(path),
                    "codex",
                    "sid",
                    idle_threshold=200,
                    pid=123,
                    now_func=lambda: 1000,
                )
            self.assertEqual(code, 0)
            self.assertIn("status=working idle=100s process=alive pid=123", line)

    def test_snapshot_exited_process_overrides_idle_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "session.jsonl"
            path.write_text((FIXTURES / "codex_session.jsonl").read_text(encoding="utf-8"), encoding="utf-8")
            os.utime(path, (999, 999))
            with mock.patch.object(amon, "_pid_alive", return_value=False):
                code, line = amon.snapshot_status(
                    str(path),
                    "codex",
                    "sid",
                    idle_threshold=200,
                    pid=123,
                    now_func=lambda: 1000,
                )
            self.assertEqual(code, 4)
            self.assertIn("status=exited idle=1s process=exited pid=123", line)

    def test_snapshot_exited_process_state_without_pid(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "session.jsonl"
            path.write_text((FIXTURES / "codex_session.jsonl").read_text(encoding="utf-8"), encoding="utf-8")
            os.utime(path, (999, 999))
            code, line = amon.snapshot_status(
                str(path),
                "codex",
                "sid",
                idle_threshold=200,
                process_state="exited",
                now_func=lambda: 1000,
            )
            self.assertEqual(code, 4)
            self.assertIn("status=exited idle=1s process=exited", line)
            self.assertNotIn("pid=", line)

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
            self.assertIn("process=unknown", line)

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

    def test_snapshot_ignores_color_and_stays_plain(self):
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
            self.assertNotIn("\033[", line)
            self.assertIn("last=Tool exec_command ls -la", line)

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

    def test_claude_session_id_from_cmdline(self):
        self.assertEqual(
            amon.claude_session_id_from_cmdline("/opt/bin/claude --session-id abc -p hello"),
            "abc",
        )
        self.assertEqual(
            amon.claude_session_id_from_cmdline("claude --session-id=def --print hello"),
            "def",
        )
        self.assertIsNone(amon.claude_session_id_from_cmdline("claude -p hello"))

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
        cwds = {
            1: "/repo/claude",
            3: "/repo/codex",
        }
        with mock.patch.object(amon, "candidate_pids", return_value=[1, 2, 3, 4]):
            with mock.patch.object(amon, "process_command", side_effect=lambda pid: commands[pid]):
                with mock.patch.object(amon, "process_cwd", side_effect=lambda pid: cwds[pid]):
                    with mock.patch.object(
                        amon,
                        "resolve_claude_session_path",
                        return_value="/tmp/claude.jsonl",
                    ) as claude_resolver:
                        with mock.patch.object(
                            amon,
                            "resolve_codex_session_paths",
                            return_value=["/tmp/codex-a.jsonl", "/tmp/codex-b.jsonl"],
                        ) as codex_resolver:
                            sessions = amon.discover_active_sessions(codex_all=True)
        self.assertEqual(
            sessions,
            [
                {
                    "agent": "claude",
                    "pid": 1,
                    "path": "/tmp/claude.jsonl",
                    "cwd": "/repo/claude",
                    "command": "claude -p hello",
                },
                {
                    "agent": "codex",
                    "pid": 3,
                    "path": "/tmp/codex-a.jsonl",
                    "cwd": "/repo/codex",
                    "command": "codex exec run",
                },
                {
                    "agent": "codex",
                    "pid": 3,
                    "path": "/tmp/codex-b.jsonl",
                    "cwd": "/repo/codex",
                    "command": "codex exec run",
                },
            ],
        )
        claude_resolver.assert_called_once_with(
            1,
            cmdline="claude -p hello",
            cwd="/repo/claude",
        )
        codex_resolver.assert_called_once_with(3, all_sessions=True)

    def test_discover_active_sessions_all_scope_preserves_cwd_for_project_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            alpha = Path(tmp) / "alpha-session.jsonl"
            beta = Path(tmp) / "beta-session.jsonl"
            alpha.write_text("{}\n", encoding="utf-8")
            beta.write_text("{}\n", encoding="utf-8")
            os.utime(alpha, (200, 200))
            os.utime(beta, (100, 100))

            commands = {1: "codex exec run alpha", 2: "codex exec run beta"}
            cwds = {1: "/workspace/team-a/api", 2: "/workspace/team-b/api"}
            paths = {1: [str(alpha)], 2: [str(beta)]}

            with mock.patch.object(amon, "candidate_pids", return_value=[1, 2]):
                with mock.patch.object(amon, "process_command", side_effect=lambda pid: commands[pid]):
                    with mock.patch.object(amon, "process_cwd", side_effect=lambda pid: cwds[pid]):
                        with mock.patch.object(
                            amon,
                            "resolve_codex_session_paths",
                            side_effect=lambda pid, all_sessions=False: paths[pid],
                        ):
                            sessions = amon.discover_active_sessions(scope=amon.SCOPE_ALL)

            state = amon.SessionListState(scope=amon.SCOPE_ALL)
            state.merge_discovered(sessions, now=10, pid_alive_func=lambda _pid: True)
            lines = amon.render_session_list_lines(state, width=140, height=10, now=11)

        self.assertEqual(
            [session["cwd"] for session in sessions],
            ["/workspace/team-a/api", "/workspace/team-b/api"],
        )
        self.assertTrue(any("team-a/api" in line for line in lines))
        self.assertTrue(any("team-b/api" in line for line in lines))

    def test_discover_active_sessions_current_scope_filters_by_process_cwd(self):
        commands = {
            1: "claude -p hello",
            2: "codex exec run",
            3: "claude -p outside",
            4: "codex app-server",
        }
        cwds = {
            1: "/repo",
            2: "/repo/sub",
            3: "/other",
            4: "/repo/ignored",
        }
        with mock.patch.object(amon, "candidate_pids", return_value=[1, 2, 3, 4]):
            with mock.patch.object(amon, "process_command", side_effect=lambda pid: commands[pid]):
                with mock.patch.object(amon, "process_cwd", side_effect=lambda pid: cwds[pid]):
                    with mock.patch.object(
                        amon,
                        "resolve_claude_session_path",
                        return_value="/tmp/claude.jsonl",
                    ) as claude_resolver:
                        with mock.patch.object(
                            amon,
                            "resolve_codex_session_paths",
                            return_value=["/tmp/codex.jsonl"],
                        ) as codex_resolver:
                            sessions = amon.discover_active_sessions(
                                codex_all=True,
                                scope=amon.SCOPE_CURRENT,
                                cwd="/repo",
                            )
        self.assertEqual(
            sessions,
            [
                {
                    "agent": "claude",
                    "pid": 1,
                    "path": "/tmp/claude.jsonl",
                    "cwd": "/repo",
                    "command": "claude -p hello",
                },
                {
                    "agent": "codex",
                    "pid": 2,
                    "path": "/tmp/codex.jsonl",
                    "cwd": "/repo/sub",
                    "command": "codex exec run",
                },
            ],
        )
        claude_resolver.assert_called_once_with(
            1,
            cmdline="claude -p hello",
            cwd="/repo",
        )
        codex_resolver.assert_called_once_with(2, all_sessions=True)

    def test_resolve_session_pid_matches_discovered_path_and_agent(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target.jsonl"
            other = Path(tmp) / "other.jsonl"
            target.write_text("{}\n", encoding="utf-8")
            other.write_text("{}\n", encoding="utf-8")
            sessions = [
                {"agent": "claude", "pid": 111, "path": str(target)},
                {"agent": "codex", "pid": 222, "path": str(other)},
                {"agent": "codex", "pid": 333, "path": str(target)},
            ]
            with mock.patch.object(amon, "discover_active_sessions", return_value=sessions) as discover:
                self.assertEqual(amon.resolve_session_pid(str(target), "codex"), 333)
        discover.assert_called_once_with(codex_all=True)

    def test_resolve_session_pid_returns_none_without_live_match(self):
        with mock.patch.object(amon, "discover_active_sessions", return_value=[]):
            self.assertIsNone(amon.resolve_session_pid("/tmp/session.jsonl", "codex"))


class TestSessionAggregation(unittest.TestCase):
    def _write_jsonl(self, root, relative, lines, mtime):
        path = Path(root) / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(f"{json.dumps(line)}\n" for line in lines), encoding="utf-8")
        os.utime(path, (mtime, mtime))
        return str(path)

    def test_session_id_status_priority_counts_and_label_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            failed = self._write_jsonl(
                tmp,
                "a/same-session.jsonl",
                [
                    {"metadata": {"title": "Release watcher"}},
                    {"type": "result", "subtype": "error_during_execution"},
                ],
                100,
            )
            running = self._write_jsonl(tmp, "b/same-session.jsonl", [], 200)
            command_only = self._write_jsonl(tmp, "solo-session.jsonl", [], 150)

            sessions = [
                {
                    "agent": "claude",
                    "pid": 1,
                    "path": failed,
                    "cwd": "/repo/service",
                    "command": "claude -p release",
                },
                {
                    "agent": "claude",
                    "pid": 2,
                    "path": running,
                    "cwd": "/repo/service",
                    "command": "claude -p release",
                },
                {
                    "agent": "codex",
                    "pid": 3,
                    "path": command_only,
                    "cwd": "/repo/tool",
                    "command": "codex exec inspect",
                },
            ]
            entries = amon.aggregate_sessions(
                sessions,
                pid_alive_func=lambda pid: pid in {2, 3},
            )

        same = next(entry for entry in entries if entry.session_id == "same-session")
        solo = next(entry for entry in entries if entry.session_id == "solo-session")
        self.assertEqual(same.status, "failed")
        self.assertEqual(amon.representative_status(["running", "failed"]), "failed")
        self.assertEqual(same.label, "Release watcher")
        self.assertIn("claude -p release", same.search_text)
        self.assertEqual(same.status_counts["failed"], 1)
        self.assertEqual(same.status_counts["running"], 1)
        self.assertEqual(solo.status, "running")
        self.assertEqual(solo.label, "codex exec inspect")
        self.assertEqual(amon.count_session_statuses(entries)["failed"], 1)
        self.assertEqual(amon.count_session_statuses(entries)["running"], 1)
        self.assertLess(entries.index(same), entries.index(solo))

    def test_disambiguate_project_paths_expands_from_right(self):
        displays = amon.disambiguate_project_paths(
            [
                "/Users/dane/work/api",
                "/Users/dane/side/api",
                "/Users/dane/work/web",
            ]
        )
        self.assertEqual(displays["/Users/dane/work/api"], "work/api")
        self.assertEqual(displays["/Users/dane/side/api"], "side/api")
        self.assertEqual(displays["/Users/dane/work/web"], "web")

    def test_missing_activity_sorts_last(self):
        with tempfile.TemporaryDirectory() as tmp:
            active = self._write_jsonl(tmp, "active.jsonl", [], 100)
            missing = str(Path(tmp) / "missing.jsonl")
            entries = amon.aggregate_sessions(
                [
                    {"agent": "codex", "path": missing},
                    {"agent": "codex", "path": active},
                ]
            )
        self.assertEqual([entry.session_id for entry in entries], ["active", "missing"])
        self.assertEqual(entries[-1].activity_mtime, None)


class TestSessionListState(unittest.TestCase):
    def _write_jsonl(self, root, name, lines, mtime):
        path = Path(root) / name
        path.write_text("".join(f"{json.dumps(line)}\n" for line in lines), encoding="utf-8")
        os.utime(path, (mtime, mtime))
        return str(path)

    def _status_column_bounds(self, table_header):
        agent_col = table_header.index("agent")
        return agent_col - amon.LIST_STATUS_WIDTH - 1, agent_col

    def test_merge_search_hide_and_render_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            active = self._write_jsonl(
                tmp,
                "active.jsonl",
                [{"metadata": {"label": "Alpha task"}}],
                200,
            )
            exited = self._write_jsonl(
                tmp,
                "exited.jsonl",
                [{"type": "result", "subtype": "success"}],
                100,
            )
            state = amon.SessionListState(scope=amon.SCOPE_ALL)
            state.merge_discovered(
                [
                    {
                        "agent": "claude",
                        "pid": 10,
                        "path": active,
                        "cwd": "/repo/alpha",
                        "command": "claude -p alpha",
                    },
                    {
                        "agent": "claude",
                        "path": exited,
                        "cwd": "/repo/beta",
                        "command": "claude -p beta",
                    },
                ],
                now=10,
                pid_alive_func=lambda pid: pid == 10,
            )

            with mock.patch.object(amon, "_use_unicode_status_icons", return_value=True):
                lines = amon.render_session_list_lines(state, width=120, height=10, now=11)
                later_lines = amon.render_session_list_lines(
                    state,
                    width=120,
                    height=10,
                    now=11 + amon.STATUS_ICON_FRAME_SECONDS,
                )
            self.assertIn("●1", lines[0])
            self.assertIn("○1", lines[0])
            self.assertEqual(lines[0], later_lines[0])
            self.assertNotIn("running=", lines[0])
            self.assertTrue(any(
                line.startswith("> * ✧") and "claude active" in line
                for line in lines
            ))
            self.assertFalse(any(line.strip() and set(line.strip()) == {"-"} for line in lines))

            amon.handle_session_list_key(state, "/")
            amon.handle_session_list_key(state, "a")
            amon.handle_session_list_key(state, "l")
            self.assertEqual([entry.session_id for entry in state.visible_entries()], ["active"])

            amon.handle_session_list_key(state, "ENTER")
            state.query = ""
            hidden = state.hide_visible_finished()
            self.assertEqual(hidden, 1)
            self.assertEqual(state.visible_counts()["exited"], 0)

    def test_missing_discovered_session_transitions_running_to_exited(self):
        with tempfile.TemporaryDirectory() as tmp:
            active = self._write_jsonl(tmp, "active.jsonl", [], 100)
            state = amon.SessionListState(scope=amon.SCOPE_ALL)
            state.merge_discovered(
                [{"agent": "codex", "pid": 10, "path": active, "command": "codex exec run"}],
                now=1,
                pid_alive_func=lambda pid: True,
            )
            self.assertEqual(state.entries["active"].status, "running")

            state.merge_discovered([], now=2)
            self.assertEqual(state.entries["active"].status, "exited")
            self.assertEqual(state.entries["active"].pids, ())

    def test_key_handling_quit_and_empty_enter(self):
        state = amon.SessionListState()
        self.assertEqual(amon.handle_session_list_key(state, "q"), "quit")
        self.assertIsNone(amon.handle_session_list_key(state, "ENTER"))
        self.assertIn("no session selected", state.status_message)

    def test_key_handling_enter_opens_selected_detail(self):
        state = amon.SessionListState()
        state.entries["session"] = amon.SessionEntry(
            session_id="session",
            agent="codex",
            path="/tmp/session.jsonl",
            status="running",
            label="Session",
        )
        self.assertEqual(amon.handle_session_list_key(state, "ENTER"), "detail")

    def test_session_list_layout_carries_status_selection_and_new_highlight(self):
        state = amon.SessionListState()
        state.entries["session"] = amon.SessionEntry(
            session_id="session",
            agent="codex",
            path="/tmp/session.jsonl",
            status="running",
            label="Session",
            highlight_until=20,
        )

        layout = amon.render_session_list_layout(state, width=120, height=6, now=10)
        row = next(line for line in layout if line.style == "row" and line.status == "running")
        attr = amon._curses_attr_for_line(row, color_enabled=False)

        self.assertEqual(row.style, "row")
        self.assertEqual(row.status, "running")
        self.assertTrue(row.selected)
        self.assertTrue(row.highlighted)
        self.assertTrue(attr & amon.curses.A_REVERSE)
        self.assertTrue(attr & amon.curses.A_UNDERLINE)
        self.assertFalse(attr & amon.curses.A_BOLD)

    def test_session_list_layout_uses_single_rows_with_aligned_truncating_columns(self):
        state = amon.SessionListState()
        state.entries["newer"] = amon.SessionEntry(
            session_id="newer-session",
            agent="codex",
            path="/tmp/newer.jsonl",
            status="running",
            label="This is a very long session label that should be clipped",
            project_display="very-long-project-name",
            activity_mtime=1240,
            status_counts={"failed": 0, "running": 1, "unknown": 0, "exited": 0},
        )
        state.entries["older"] = amon.SessionEntry(
            session_id="older-session",
            agent="claude",
            path="/tmp/older.jsonl",
            status="exited",
            label="Older task",
            project_display="project-b",
            activity_mtime=1180,
            status_counts={"failed": 0, "running": 0, "unknown": 0, "exited": 1},
        )

        with mock.patch.object(amon.time, "time", return_value=1300), \
            mock.patch.object(amon, "_use_unicode_status_icons", return_value=True):
            layout = amon.render_session_list_layout(state, width=80, height=10, now=10)

        header = layout[2].text
        rows = [line.text for line in layout if line.style == "row"]
        label_col = header.index("label")
        activity_col = header.index("activity")
        counts_col = header.index("counts")

        self.assertEqual(len(rows), 2)
        self.assertFalse(any(line.style == "divider" for line in layout))
        self.assertTrue(all(len(row) <= 80 for row in rows))
        self.assertTrue(rows[0][label_col:activity_col].rstrip().endswith("..."))
        self.assertEqual(rows[0][activity_col:counts_col].strip(), "1m ago")
        self.assertEqual(rows[1][activity_col:counts_col].strip(), "2m ago")
        self.assertEqual(rows[0][counts_col:].strip(), "●1 ●0 ?0 ○0")
        self.assertEqual(rows[1][counts_col:].strip(), "●0 ●0 ?0 ○1")

    def test_session_list_layout_groups_statuses_and_uses_status_icons(self):
        state = amon.SessionListState()
        state.entries["running-old"] = amon.SessionEntry(
            session_id="running-old",
            agent="codex",
            path="/tmp/running-old.jsonl",
            status="running",
            label="Running old",
            project_display="project-a",
            activity_mtime=100,
        )
        state.entries["running-new"] = amon.SessionEntry(
            session_id="running-new",
            agent="codex",
            path="/tmp/running-new.jsonl",
            status="running",
            label="Running new",
            project_display="project-a",
            activity_mtime=300,
        )
        state.entries["failed"] = amon.SessionEntry(
            session_id="failed",
            agent="claude",
            path="/tmp/failed.jsonl",
            status="failed",
            label="Failed task",
            project_display="project-b",
            activity_mtime=400,
        )
        state.entries["exited"] = amon.SessionEntry(
            session_id="exited",
            agent="claude",
            path="/tmp/exited.jsonl",
            status="exited",
            label="Exited task",
            project_display="project-c",
            activity_mtime=500,
        )

        with mock.patch.object(amon, "_use_unicode_status_icons", return_value=True):
            layout = amon.render_session_list_layout(state, width=110, height=20, now=10)
        section_headers = [
            line.text
            for line in layout
            if line.style == "subtle" and line.text.endswith(")")
        ]
        rows = [line.text for line in layout if line.style == "row"]
        table_header = layout[2].text
        status_col, agent_col = self._status_column_bounds(table_header)

        self.assertEqual(
            section_headers,
            ["Running (2)", "Failed (1)", "Unknown (0)", "Exited (1)"],
        )
        self.assertEqual([entry.session_id for entry in state.grouped_visible_entries()], [
            "running-new",
            "running-old",
            "failed",
            "exited",
        ])
        self.assertEqual(rows[0][status_col:agent_col].strip(), "✧")
        self.assertEqual(rows[2][status_col:agent_col].strip(), "●")
        self.assertEqual(rows[3][status_col:agent_col].strip(), "○")
        status_cells = [row[status_col:agent_col].strip() for row in rows]
        self.assertFalse(any(
            status in cell
            for cell in status_cells
            for status in ("running", "failed", "exited")
        ))
        self.assertFalse(any(line.style == "divider" for line in layout))

    def test_session_list_table_header_omits_status_and_narrows_icon_column(self):
        state = amon.SessionListState()
        state.entries["running"] = amon.SessionEntry(
            session_id="running",
            agent="codex",
            path="/tmp/running.jsonl",
            status="running",
            label="Running",
        )

        with mock.patch.object(amon, "_use_unicode_status_icons", return_value=True):
            layout = amon.render_session_list_layout(state, width=100, height=9, now=0.0)

        table_header = layout[2].text
        row = next(line.text for line in layout if line.style == "row")
        status_col, agent_col = self._status_column_bounds(table_header)
        old_wide_agent_col = 1 + 1 + 1 + 1 + 9 + 1

        self.assertNotIn("status", table_header)
        self.assertEqual(amon.LIST_STATUS_WIDTH, 1)
        self.assertLess(agent_col, old_wide_agent_col)
        self.assertEqual(table_header[status_col:agent_col].strip(), "")
        self.assertEqual(row[status_col:agent_col].strip(), "✧")
        self.assertEqual(row.index("codex"), agent_col)

    def test_session_list_layout_renders_empty_status_groups(self):
        state = amon.SessionListState()

        with mock.patch.object(amon, "_use_unicode_status_icons", return_value=True):
            layout = amon.render_session_list_layout(state, width=100, height=10, now=10)

        section_headers = [
            line.text
            for line in layout
            if line.style == "subtle" and line.text.endswith(")")
        ]

        self.assertEqual(
            section_headers,
            ["Running (0)", "Failed (0)", "Unknown (0)", "Exited (0)"],
        )
        self.assertFalse(any(line.style == "row" or line.selected for line in layout))

    def test_session_list_constrained_running_group_preserves_empty_headers(self):
        state = amon.SessionListState()
        for index in range(8):
            state.entries[f"running-{index}"] = amon.SessionEntry(
                session_id=f"running-{index}",
                agent="codex",
                path=f"/tmp/running-{index}.jsonl",
                status="running",
                label=f"Run {index}",
                activity_mtime=100 + index,
            )
        state.cursor = 3

        with mock.patch.object(amon, "_use_unicode_status_icons", return_value=True):
            layout = amon.render_session_list_layout(state, width=100, height=9, now=10)

        section_headers = [
            line.text
            for line in layout
            if line.style == "subtle" and line.text.endswith(")")
        ]
        rows = [line for line in layout if line.style == "row"]

        self.assertEqual(
            section_headers,
            ["Running (8)", "Failed (0)", "Unknown (0)", "Exited (0)"],
        )
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0].selected)
        self.assertIn("Run 4", rows[0].text)

    def test_session_list_running_status_icon_animates_without_column_shift(self):
        state = amon.SessionListState()
        state.entries["running"] = amon.SessionEntry(
            session_id="running",
            agent="codex",
            path="/tmp/running.jsonl",
            status="running",
            label="Running",
            activity_mtime=100,
        )

        with mock.patch.object(amon, "_use_unicode_status_icons", return_value=True):
            first = amon.render_session_list_layout(state, width=100, height=9, now=0.0)
            second = amon.render_session_list_layout(
                state,
                width=100,
                height=9,
                now=amon.STATUS_ICON_FRAME_SECONDS,
            )

        header = first[2].text
        first_row = next(line.text for line in first if line.style == "row")
        second_row = next(line.text for line in second if line.style == "row")
        status_col, agent_col = self._status_column_bounds(header)

        self.assertEqual(first_row[status_col:agent_col].strip(), "✧")
        self.assertEqual(second_row[status_col:agent_col].strip(), "✦")
        self.assertEqual(
            amon._display_width(first_row[: first_row.index("codex")]),
            amon._display_width(header[: header.index("agent")]),
        )
        self.assertEqual(
            amon._display_width(second_row[: second_row.index("codex")]),
            amon._display_width(header[: header.index("agent")]),
        )

    def test_running_status_icon_frames_grow_and_shrink_at_faster_interval(self):
        interval = amon.STATUS_ICON_FRAME_SECONDS

        self.assertLess(interval, 0.5)
        self.assertEqual(
            [
                amon._status_icon("running", interval * index, unicode_icons=True)
                for index in range(5)
            ],
            ["✧", "✦", "✶", "✦", "✧"],
        )
        self.assertEqual(
            [
                amon._status_icon("running", interval * index, unicode_icons=False)
                for index in range(5)
            ],
            [".", "*", "X", "*", "."],
        )

    def test_status_count_labels_use_display_order_and_static_icons(self):
        counts = {"failed": 2, "running": 1, "unknown": 3, "exited": 4}

        with mock.patch.object(amon, "_use_unicode_status_icons", return_value=True):
            first = amon._session_counts_label(counts, 0.0)
            second = amon._session_counts_label(
                counts,
                amon.STATUS_ICON_FRAME_SECONDS,
            )

        self.assertEqual(first, "●1 ●2 ?3 ○4")
        self.assertEqual(second, first)

    def test_session_list_header_count_segments_use_status_color_order(self):
        state = amon.SessionListState()
        state.entries["running"] = amon.SessionEntry(
            session_id="running",
            agent="codex",
            path="/tmp/running.jsonl",
            status="running",
            label="Running",
        )
        state.entries["failed"] = amon.SessionEntry(
            session_id="failed",
            agent="codex",
            path="/tmp/failed.jsonl",
            status="failed",
            label="Failed",
        )

        with mock.patch.object(amon, "_use_unicode_status_icons", return_value=True):
            header = amon.render_session_list_layout(
                state,
                width=120,
                height=6,
                now=amon.STATUS_ICON_FRAME_SECONDS,
            )[0]

        count_segments = [
            (text, style)
            for text, style in header.segments or []
            if style in amon.STATUS_COUNT_DISPLAY_ORDER
        ]
        self.assertEqual(header.text, "amon sessions total=2 ●1 ●1 ?0 ○0")
        self.assertEqual(
            count_segments,
            [("●1", "running"), ("●1", "failed"), ("?0", "unknown"), ("○0", "exited")],
        )

    def test_session_list_row_count_segments_use_complement_style_order(self):
        state = amon.SessionListState()
        state.entries["mixed"] = amon.SessionEntry(
            session_id="mixed",
            agent="codex",
            path="/tmp/mixed.jsonl",
            status="running",
            label="Mixed counts",
            status_counts={"failed": 2, "running": 1, "unknown": 3, "exited": 4},
        )

        with mock.patch.object(amon, "_use_unicode_status_icons", return_value=True):
            row = next(
                line
                for line in amon.render_session_list_layout(
                    state,
                    width=120,
                    height=6,
                    now=amon.STATUS_ICON_FRAME_SECONDS,
                )
                if line.style == "row"
            )

        count_segments = [
            (text, style)
            for text, style in row.segments or []
            if style in amon.ROW_COUNT_STYLE_BY_STATUS.values()
        ]
        self.assertEqual(row.status, "running")
        self.assertEqual(amon._segments_text(row.segments), row.text)
        self.assertTrue(row.text.endswith("●1 ●2 ?3 ○4"))
        self.assertEqual(
            count_segments,
            [
                ("●1", "count_running"),
                ("●2", "count_failed"),
                ("?3", "count_unknown"),
                ("○4", "count_exited"),
            ],
        )

    def test_session_list_row_count_segment_styles_do_not_collapse_to_row_status(self):
        state = amon.SessionListState()
        state.entries["mixed"] = amon.SessionEntry(
            session_id="mixed",
            agent="codex",
            path="/tmp/mixed.jsonl",
            status="running",
            label="Mixed counts",
            status_counts={"failed": 5, "running": 1, "unknown": 0, "exited": 0},
        )

        with mock.patch.object(amon, "_use_unicode_status_icons", return_value=True):
            row = next(
                line
                for line in amon.render_session_list_layout(
                    state,
                    width=120,
                    height=6,
                    now=0.0,
                )
                if line.style == "row"
            )

        self.assertEqual(row.status, "running")
        self.assertIn(("●5", "count_failed"), row.segments)
        self.assertNotIn(("●5", "failed"), row.segments)
        self.assertNotIn(("●5", "running"), row.segments)

    def test_draw_render_line_uses_count_segment_color_with_row_modifiers(self):
        class FakeScreen:
            def __init__(self):
                self.calls = []

            def addnstr(self, *args):
                self.calls.append(args)

        screen = FakeScreen()
        line = amon.RenderLine(
            "row ●1 ●2",
            "row",
            status="running",
            selected=True,
            segments=[
                ("row ", "row"),
                ("●1", "count_running"),
                (" ", "row"),
                ("●2", "count_failed"),
            ],
        )
        reverse = 1 << 20

        with mock.patch.object(amon.curses, "A_REVERSE", reverse, create=True), \
            mock.patch.object(amon.curses, "color_pair", side_effect=lambda pair: pair << 8):
            amon._draw_render_line(screen, 0, line, 80, color_enabled=True)

        attrs_by_text = {args[2]: args[4] for args in screen.calls}
        self.assertEqual(
            attrs_by_text["row "],
            (amon.TUI_COLOR_PAIRS["running"] << 8) | reverse,
        )
        self.assertEqual(
            attrs_by_text["●1"],
            (amon.TUI_COLOR_PAIRS["count_running"] << 8) | reverse,
        )
        self.assertEqual(
            attrs_by_text["●2"],
            (amon.TUI_COLOR_PAIRS["count_failed"] << 8) | reverse,
        )
        self.assertNotEqual(attrs_by_text["row "], attrs_by_text["●1"])

    def test_draw_render_line_keeps_segment_output_plain_without_colors(self):
        class FakeScreen:
            def __init__(self):
                self.calls = []

            def addnstr(self, *args):
                self.calls.append(args)

        screen = FakeScreen()
        line = amon.RenderLine(
            "row ●1",
            "row",
            status="running",
            segments=[("row ", "row"), ("●1", "count_failed")],
        )

        amon._draw_render_line(screen, 0, line, 80, color_enabled=False)

        self.assertEqual([args[2] for args in screen.calls], ["row ", "●1"])
        self.assertEqual([len(args) for args in screen.calls], [4, 4])

    def test_status_icon_frames_are_single_cell_with_ascii_fallback(self):
        for frames in amon.UNICODE_STATUS_ICON_FRAMES.values():
            for icon in frames:
                self.assertEqual(amon._display_width(icon), 1)
        for icon in amon.UNICODE_STATIC_STATUS_ICONS.values():
            self.assertEqual(amon._display_width(icon), 1)
        for frames in amon.ASCII_STATUS_ICON_FRAMES.values():
            for icon in frames:
                self.assertEqual(amon._display_width(icon), 1)
        for icon in amon.ASCII_STATIC_STATUS_ICONS.values():
            self.assertEqual(amon._display_width(icon), 1)

        with mock.patch.object(amon, "_display_width", return_value=2):
            self.assertEqual(amon._status_icon("running", 0.0, unicode_icons=True), ".")
            self.assertEqual(amon._static_status_icon("running", unicode_icons=True), "*")

    def test_session_list_cursor_moves_across_grouped_rows_not_headers(self):
        state = amon.SessionListState()
        state.entries["running"] = amon.SessionEntry(
            session_id="running",
            agent="codex",
            path="/tmp/running.jsonl",
            status="running",
            label="Running",
            activity_mtime=100,
        )
        state.entries["failed"] = amon.SessionEntry(
            session_id="failed",
            agent="codex",
            path="/tmp/failed.jsonl",
            status="failed",
            label="Failed",
            activity_mtime=300,
        )
        state.entries["exited"] = amon.SessionEntry(
            session_id="exited",
            agent="codex",
            path="/tmp/exited.jsonl",
            status="exited",
            label="Exited",
            activity_mtime=500,
        )

        self.assertEqual(state.selected_entry().session_id, "running")
        amon.handle_session_list_key(state, "DOWN")
        self.assertEqual(state.selected_entry().session_id, "failed")
        amon.handle_session_list_key(state, "DOWN")
        self.assertEqual(state.selected_entry().session_id, "exited")
        amon.handle_session_list_key(state, "DOWN")
        self.assertEqual(state.selected_entry().session_id, "exited")
        amon.handle_session_list_key(state, "UP")
        self.assertEqual(state.selected_entry().session_id, "failed")

        with mock.patch.object(amon, "_use_unicode_status_icons", return_value=True):
            layout = amon.render_session_list_layout(state, width=100, height=12, now=10)
        selected_rows = [line.text for line in layout if line.style == "row" and line.selected]
        table_header = layout[2].text
        status_col, agent_col = self._status_column_bounds(table_header)
        self.assertEqual(len(selected_rows), 1)
        self.assertEqual(selected_rows[0][status_col:agent_col].strip(), "●")

    def test_session_list_constrained_group_viewport_keeps_headers_with_rows(self):
        state = amon.SessionListState()
        state.entries["running-old"] = amon.SessionEntry(
            session_id="running-old",
            agent="codex",
            path="/tmp/running-old.jsonl",
            status="running",
            label="Running old",
            activity_mtime=100,
        )
        state.entries["running-new"] = amon.SessionEntry(
            session_id="running-new",
            agent="codex",
            path="/tmp/running-new.jsonl",
            status="running",
            label="Running new",
            activity_mtime=200,
        )
        state.entries["failed"] = amon.SessionEntry(
            session_id="failed",
            agent="codex",
            path="/tmp/failed.jsonl",
            status="failed",
            label="Failed",
            activity_mtime=300,
        )
        state.entries["exited"] = amon.SessionEntry(
            session_id="exited",
            agent="codex",
            path="/tmp/exited.jsonl",
            status="exited",
            label="Exited",
            activity_mtime=400,
        )
        state.cursor = 2

        layout = amon.render_session_list_layout(state, width=100, height=6, now=10)
        body = layout[3:-1]

        self.assertEqual(len(body), 2)
        self.assertEqual(body[0].text, "Failed (1)")
        self.assertEqual(body[0].style, "subtle")
        self.assertEqual(body[1].style, "row")
        self.assertEqual(body[1].status, "failed")
        self.assertTrue(body[1].selected)

    def test_session_list_long_wide_label_does_not_shift_activity_or_counts(self):
        state = amon.SessionListState()
        state.entries["wide"] = amon.SessionEntry(
            session_id="wide",
            agent="codex",
            path="/tmp/wide.jsonl",
            status="running",
            label="작업" * 40,
            project_display="project",
            activity_mtime=1240,
            status_counts={"failed": 0, "running": 1, "unknown": 0, "exited": 0},
        )

        with mock.patch.object(amon.time, "time", return_value=1300), \
            mock.patch.object(amon, "_use_unicode_status_icons", return_value=True):
            layout = amon.render_session_list_layout(state, width=80, height=9, now=10)

        header = layout[2].text
        row = next(line.text for line in layout if line.style == "row")
        activity_col = amon._display_width(header[: header.index("activity")])
        counts_col = amon._display_width(header[: header.index("counts")])
        row_activity_col = amon._display_width(row[: row.index("1m ago")])
        row_counts_col = amon._display_width(row[: row.index("●1 ●0 ?0 ○0")])

        self.assertLessEqual(amon._display_width(row), 80)
        self.assertIn("...", row[: row.index("1m ago")])
        self.assertEqual(row_activity_col, activity_col)
        self.assertEqual(row_counts_col, counts_col)

    def test_session_list_narrow_width_hides_low_priority_columns_and_stays_bounded(self):
        state = amon.SessionListState()
        state.entries["narrow"] = amon.SessionEntry(
            session_id="narrow-session",
            agent="codex",
            path="/tmp/narrow.jsonl",
            status="running",
            label="A very long label that has to fit",
            project_display="project",
            activity_mtime=1240,
        )

        with mock.patch.object(amon.time, "time", return_value=1300), \
            mock.patch.object(amon, "_use_unicode_status_icons", return_value=True):
            layout = amon.render_session_list_layout(state, width=30, height=9, now=10)

        table_header = layout[2].text
        row = next(line.text for line in layout if line.style == "row")

        self.assertTrue(all(amon._display_width(line.text) <= 30 for line in layout))
        self.assertNotIn("status", table_header)
        self.assertIn("label", table_header)
        self.assertNotIn("activity", table_header)
        self.assertNotIn("counts", table_header)
        self.assertNotIn("project", table_header)
        self.assertNotIn("●1 ●0 ?0 ○0", row)
        self.assertFalse(any(line.style == "divider" for line in layout))

    def test_curses_attr_uses_status_color_pair_when_enabled(self):
        line = amon.RenderLine("row", "row", status="failed")
        with mock.patch.object(amon.curses, "color_pair", side_effect=lambda pair: pair * 1000):
            attr = amon._curses_attr_for_line(line, color_enabled=True)
        self.assertNotEqual(attr, 0)
        self.assertEqual(attr, amon.TUI_COLOR_PAIRS["failed"] * 1000)

    def test_curses_attr_uses_status_color_for_status_headers(self):
        line = amon.RenderLine("Failed (1)", "subtle", status="failed")
        with mock.patch.object(amon.curses, "color_pair", side_effect=lambda pair: pair * 1000):
            attr = amon._curses_attr_for_line(line, color_enabled=True)
        self.assertTrue(attr & (amon.TUI_COLOR_PAIRS["failed"] * 1000))

    def test_init_curses_colors_uses_muted_custom_palette_when_supported(self):
        with mock.patch.object(amon.curses, "has_colors", return_value=True), \
            mock.patch.object(amon.curses, "start_color"), \
            mock.patch.object(amon.curses, "use_default_colors"), \
            mock.patch.object(amon.curses, "can_change_color", return_value=True), \
            mock.patch.object(amon.curses, "COLORS", 64, create=True), \
            mock.patch.object(amon.curses, "init_color") as init_color, \
            mock.patch.object(amon.curses, "init_pair") as init_pair:
            self.assertTrue(amon._init_curses_colors("auto"))

        running_color = amon.TUI_MUTED_COLOR_BASE + list(amon.TUI_MUTED_RGB).index("running")
        count_failed_color = (
            amon.TUI_MUTED_COLOR_BASE + list(amon.TUI_MUTED_RGB).index("count_failed")
        )
        init_color.assert_any_call(running_color, *amon.TUI_MUTED_RGB["running"])
        init_color.assert_any_call(count_failed_color, *amon.TUI_MUTED_RGB["count_failed"])
        init_pair.assert_any_call(
            amon.TUI_COLOR_PAIRS["running"],
            running_color,
            -1,
        )
        init_pair.assert_any_call(
            amon.TUI_COLOR_PAIRS["count_failed"],
            count_failed_color,
            -1,
        )

    def test_init_curses_colors_falls_back_to_basic_low_intensity_colors(self):
        with mock.patch.object(amon.curses, "has_colors", return_value=True), \
            mock.patch.object(amon.curses, "start_color"), \
            mock.patch.object(amon.curses, "use_default_colors"), \
            mock.patch.object(amon.curses, "can_change_color", return_value=False), \
            mock.patch.object(amon.curses, "init_color") as init_color, \
            mock.patch.object(amon.curses, "init_pair") as init_pair:
            self.assertTrue(amon._init_curses_colors("auto"))

        init_color.assert_not_called()
        init_pair.assert_any_call(
            amon.TUI_COLOR_PAIRS["running"],
            amon.TUI_BASIC_COLOR_FALLBACKS["running"],
            -1,
        )
        init_pair.assert_any_call(
            amon.TUI_COLOR_PAIRS["count_running"],
            amon.TUI_BASIC_COLOR_FALLBACKS["count_running"],
            -1,
        )


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
            with mock.patch.object(amon, "discover_active_sessions", return_value=[]) as discover:
                code = amon.run_mode_b(30, codex_all=False, error=err)
        self.assertEqual(code, 0)
        self.assertIn("no active", err.getvalue())
        discover.assert_called_once_with(codex_all=False, scope=amon.SCOPE_ALL, cwd=None)

    def test_run_mode_b_current_scope_passes_scope_to_discovery(self):
        err = io.StringIO()
        with mock.patch.object(amon.shutil, "which", return_value="/opt/homebrew/bin/xpanes"):
            with mock.patch.object(amon, "discover_active_sessions", return_value=[]) as discover:
                code = amon.run_mode_b(
                    30,
                    codex_all=True,
                    scope=amon.SCOPE_CURRENT,
                    cwd="/repo",
                    error=err,
                )
        self.assertEqual(code, 0)
        discover.assert_called_once_with(
            codex_all=True,
            scope=amon.SCOPE_CURRENT,
            cwd="/repo",
        )

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
        self.assertNotIn("exec ", args[3])
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
