"""Shared file identity and safe artifact I/O; Python standard library only."""
import datetime as dt
import base64
import fnmatch
import hashlib
import json
import os
import re
import signal
import shlex
import shutil
import sys
from pathlib import Path, PureWindowsPath
import subprocess
import tempfile

WINDOWS = os.name == "nt"


def configure_stdio():
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def shell_command(argv, windows=None):
    """Render an explicit argv for PowerShell or POSIX; never execute it here."""
    windows = WINDOWS if windows is None else windows
    if windows:
        return "& " + " ".join("'" + str(arg).replace("'", "''") + "'" for arg in argv)
    return shlex.join([str(arg) for arg in argv])


def hook_command(argv, windows=None):
    windows = WINDOWS if windows is None else windows
    command = shell_command(argv, windows=windows)
    if not windows:
        return command
    # Codex runs Windows command hooks via cmd.exe. Keep shell metacharacters
    # and Unicode paths out of that command line, and explicitly pipe JSON stdin.
    script = ("[Console]::InputEncoding = New-Object System.Text.UTF8Encoding($false); "
              "[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false); "
              "$OutputEncoding = [Console]::OutputEncoding; "
              "$payload = [Console]::In.ReadToEnd(); $payload | " + command + "; exit $LASTEXITCODE")
    return "powershell.exe -NoLogo -NoProfile -NonInteractive -EncodedCommand " + base64.b64encode(script.encode("utf-16-le")).decode("ascii")


def codex_command():
    executable = (shutil.which("codex.exe") if WINDOWS else None) or shutil.which("codex")
    require(executable is not None, "Codex CLIがありません")
    if WINDOWS and Path(executable).suffix.lower() in (".cmd", ".bat", ".ps1"):
        script = Path(executable).parent / "node_modules/@openai/codex/bin/codex.js"
        node = shutil.which("node")
        require(script.is_file() and node is not None,
                "Codexのnpm入口を確認できません。公式npm版とNode、またはcodex.exeが必要です")
        return [node, str(script)]
    return [executable]


def mode_matches(path, expected, windows=None):
    mode = path.stat().st_mode & 0o777
    return ((mode & 0o200) == (expected & 0o200) if (WINDOWS if windows is None else windows)
            else mode == expected)


def is_link(path):
    return path.is_symlink() or (path.exists() and getattr(path.lstat(), "st_reparse_tag", 0) == 0xA0000003)


def lock_file(stream, acquire):
    if WINDOWS:
        import msvcrt
        if acquire:
            stream.seek(0, os.SEEK_END)
            if stream.tell() == 0:
                stream.write(b"\0")
                stream.flush()
        stream.seek(0)
        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK if acquire else msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(stream, (fcntl.LOCK_EX | fcntl.LOCK_NB) if acquire else fcntl.LOCK_UN)


def process_options():
    return ({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if WINDOWS
            else {"start_new_session": True})


def stop_process_tree(process):
    if WINDOWS:
        try:
            subprocess.run(["taskkill.exe", "/PID", str(process.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            pass
        finally:
            if process.poll() is None:
                process.kill()
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

class GateError(Exception):
    pass


def require(condition, message):
    if not condition:
        raise GateError(message)


def nonempty(value, label):
    require(isinstance(value, str) and value.strip() and
            value.strip().upper() not in {"TODO", "TBD", "未記入", "要記入"}, f"{label}: 内容が必要です")
    return value


def sequence(value, label, minimum=0):
    require(isinstance(value, list) and len(value) >= minimum, f"{label}: 配列（最低{minimum}件）が必要です")
    return value


def strings(value, label, minimum=0):
    items = sequence(value, label, minimum)
    for item in items:
        nonempty(item, label)
    return items


def sha(data):
    return hashlib.sha256(data).hexdigest()


def file_sha(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def digest(value):
    return sha(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode())


def read_json(path):
    require(path.is_file(), f"成果物がありません: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (ValueError, UnicodeError) as exc:
        raise GateError(f"JSONを読めません: {path}: {exc}") from exc
    require(isinstance(value, dict), f"{path}: JSONオブジェクトが必要です")
    return value


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        temp = Path(stream.name)
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    os.replace(temp, path)


def safe_path(root, relative):
    nonempty(relative, "path")
    path = Path(relative)
    require(not path.is_absolute() and ".." not in path.parts and "\\" not in relative,
            f"プロジェクト内の相対パスが必要です: {relative}")
    require(not PureWindowsPath(relative).drive and ":" not in relative and
            not any(re.fullmatch(r"(?i)(?:CON|PRN|AUX|NUL|CONIN\$|CONOUT\$|COM[0-9¹²³]|LPT[0-9¹²³])(?:\..*)?", part.rstrip(" ."))
                    or part.endswith((".", " ")) for part in path.parts),
            f"Windowsでも扱える相対パスが必要です: {relative}")
    target = root / path
    require(target.resolve().is_relative_to(root.resolve()), f"プロジェクト外への参照: {relative}")
    return target


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


SKIP_DIRS = {".git", "__pycache__", ".venv", "node_modules", ".pytest_cache", ".mypy_cache", ".ruff_cache"}


def project_entries(root, settings):
    git_modes = {}
    try:
        probe = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=root,
                               capture_output=True, text=True, encoding="utf-8", check=False)
    except FileNotFoundError:
        probe = None
    if probe and probe.returncode == 0 and Path(probe.stdout.strip()).resolve() == root.resolve():
        result = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                                cwd=root, capture_output=True, check=False)
        require(result.returncode == 0, "Gitファイル一覧を取得できません")
        paths = {os.fsdecode(p) for p in result.stdout.split(b"\0") if p}
        if WINDOWS:
            index = subprocess.run(["git", "ls-files", "--stage", "-z"], cwd=root, capture_output=True)
            require(index.returncode == 0, "Gitの実行属性を取得できません")
            for record in index.stdout.split(b"\0"):
                if record:
                    metadata, name = record.split(b"\t", 1)
                    git_modes[os.fsdecode(name)] = metadata.split()[0] == b"100755"
    else:
        paths = set()
        for directory, dirs, files in os.walk(root, followlinks=False):
            dirs[:] = [name for name in dirs if name not in SKIP_DIRS]
            for name in list(dirs):
                path = Path(directory) / name
                if is_link(path):
                    paths.add(path.relative_to(root).as_posix())
                    dirs.remove(name)
            for name in files:
                paths.add((Path(directory) / name).relative_to(root).as_posix())
    extra = strings(settings.get("verification_inputs", []), "verification_inputs")
    for relative in extra:
        path = safe_path(root, relative)
        require(path.is_file(), f"検証入力がありません: {relative}")
        require(relative != ".harness/runtime.lock" and not relative.startswith(".harness/changes/") and
                not any(part in SKIP_DIRS for part in Path(relative).parts) and
                not any(fnmatch.fnmatchcase(relative, pattern) for pattern in settings.get("snapshot_ignore", [])),
                f"検証入力を除外できません: {relative}")
    paths.update(extra)
    entries = {}
    for relative in sorted(paths):
        parts = Path(relative).parts
        if (any(p in SKIP_DIRS for p in parts) or relative.startswith(".harness/changes/") or
                relative == ".harness/runtime.lock" or
                any(fnmatch.fnmatchcase(relative, p) for p in settings.get("snapshot_ignore", []))):
            continue
        path = safe_path(root, relative)
        if is_link(path):
            require(path.exists(), f"壊れたリンク: {relative}")
            target = path.resolve()
            require(target.is_file(), f"指紋対象のディレクトリリンクは使えません: {relative}")
            entries[relative] = {"link": os.readlink(path), "sha256": file_sha(target)}
        elif path.is_file():
            executable = git_modes.get(relative, False) if WINDOWS else bool(path.stat().st_mode & 0o111)
            entries[relative] = {"sha256": file_sha(path), "executable": executable}
        else:
            entries[relative] = {"missing": True}
    return entries


def validate_checks(checks):
    ids = set()
    for entry in sequence(checks, "checks"):
        require(isinstance(entry, dict), "checksの各要素はオブジェクトです")
        name = nonempty(entry.get("id"), "check.id")
        require(re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}", name) and name not in ids, f"不正・重複したcheck.id: {name}")
        ids.add(name)
        strings(entry.get("argv"), f"{name}.argv", 1)
        timeout = entry.get("timeout_seconds")
        require(type(timeout) in (int, float) and 0 < timeout <= 3600, f"{name}: timeout_secondsは0超3600以下です")


def execute_check(root, directory, token, entry, env):
    log = directory / f"{token}-{entry['id']}.log"
    started, timed_out = now(), False
    child_env = env.copy()
    if entry["argv"][1:] == [".harness/structure.py", "check"]:
        child_env.update(PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    with log.open("wb") as output:
        try:
            process = subprocess.Popen(entry["argv"], cwd=root, stdout=output, stderr=subprocess.STDOUT,
                                       **process_options(), env=child_env)
            try:
                code = process.wait(timeout=entry["timeout_seconds"])
            except subprocess.TimeoutExpired:
                timed_out = True
                stop_process_tree(process)
                code = process.wait()
        except OSError as exc:
            output.write(str(exc).encode())
            code = 127
    return {"id": entry["id"], "argv": entry["argv"], "returncode": code,
            "timed_out": timed_out, "started_at": started, "finished_at": now(),
            "log": log.relative_to(root).as_posix(), "log_digest": file_sha(log)}
