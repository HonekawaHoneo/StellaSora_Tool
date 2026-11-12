"""Bounded, fail-closed Git secret checks; stdlib-only and safe to copy to Git metadata.

Checks cover defined sensitive paths and high-confidence credential formats, not
unknown secrets, arbitrary code safety, or deliberate ``--no-verify`` bypasses.
Git for Windows runs the sh launchers with the recorded Python executable;
native Windows execution still requires validation on a Windows host.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


MANAGED_NAME = 'harness-security'
MANIFEST = 'manifest.json'
SCHEMA = 1
LIMITATIONS = ['defined_secret_rules_only', 'explicit_hook_bypass_possible',
               'native_windows_requires_host_validation']
HOOK_EVENTS = set(('applypatch-msg pre-applypatch post-applypatch pre-commit '
                   'pre-merge-commit prepare-commit-msg commit-msg post-commit '
                   'pre-rebase post-checkout post-merge pre-push pre-receive update '
                   'proc-receive post-receive post-update reference-transaction '
                   'push-to-checkout pre-auto-gc post-rewrite sendemail-validate '
                   'fsmonitor-watchman p4-changelist p4-prepare-changelist '
                   'p4-post-changelist p4-pre-submit post-index-change').split())
COMMIT_EVENTS = {'pre-commit', 'pre-merge-commit', 'pre-applypatch', 'prepare-commit-msg'}


class SecurityError(RuntimeError):
    """Only paths and rule names are included; never include matched content."""
    def __init__(self, message, findings=None):
        self.findings = findings or []
        details = '; '.join(json.dumps(f, ensure_ascii=True) for f in self.findings)
        super().__init__(message + (': ' + details if details else ''))


def _git(root, *args, check=True, input=None):
    try:
        # Replacement/graft views are not the object content that Git transmits.
        environment = dict(os.environ, GIT_NO_REPLACE_OBJECTS='1', GIT_GRAFT_FILE=os.devnull)
        result = subprocess.run(['git', *args], cwd=root, input=input,
                                capture_output=True, env=environment)
    except (OSError, ValueError) as exc:
        raise SecurityError('security: Git could not inspect repository') from exc
    if check and result.returncode:
        raise SecurityError('security: Git inspection failed')
    return result


def _decode(value):
    return os.fsdecode(value[:-1] if value.endswith(b'\n') else value)


def _repository(root):
    root = Path(root).resolve()
    if _git(root, 'rev-parse', '--git-dir', check=False).returncode:
        return None
    common = Path(_decode(_git(root, 'rev-parse', '--path-format=absolute',
                               '--git-common-dir').stdout)).resolve()
    worktree_config = _git(root, 'config', '--bool', 'extensions.worktreeConfig', check=False)
    metadata = common
    if worktree_config.stdout.strip() == b'true':
        metadata = Path(_decode(_git(root, 'rev-parse', '--absolute-git-dir').stdout)).resolve()
    return root, metadata, metadata / MANAGED_NAME


def _digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


_TOKENS = [
    ('private_key', re.compile(rb'-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----')),
    ('github_token', re.compile(rb'(?<![A-Za-z0-9_])(?:gh[pousr]_[A-Za-z0-9]{36,255}|github_pat_[A-Za-z0-9_]{60,255})(?![A-Za-z0-9_])')),
    ('aws_access_key', re.compile(rb'(?<![A-Z0-9])(?:AKIA|ASIA)[A-Z0-9]{16}(?![A-Z0-9])')),
    ('slack_token', re.compile(rb'xox[baprs]-[0-9A-Za-z-]{20,}')),
    ('stripe_live_key', re.compile(rb'(?:sk|rk)_live_[0-9A-Za-z]{16,}')),
    ('credential_url', re.compile(rb'[a-z][a-z0-9+.-]*://[^\s/:@]+:([^\s/@]{8,})@', re.I)),
]
_ASSIGNMENT = re.compile(
    rb'''(?im)(?:^|[\s{,])['"]?(?:password|passwd|api[_-]?key|api[_-]?token|access[_-]?token|client[_-]?secret|secret[_-]?access[_-]?key)['"]?\s*[:=]\s*(?:(?P<quote>['"])(?P<quoted>[^'"\r\n]{8,})(?P=quote)|(?P<bare>[^\s'"`,;}\r\n]{8,}))''')
_SOURCE_EXTENSIONS = {'.py', '.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs', '.java',
                      '.rb', '.go', '.rs', '.cs', '.c', '.cpp', '.h', '.ps1',
                      '.php', '.swift', '.kt', '.scala', '.vue', '.svelte'}


def _placeholder(value):
    value = value.lower().strip(b'"\'')
    return (value.startswith((b'$', b'{{', b'<', b'your_', b'your-', b'example',
                              b'placeholder', b'dummy', b'fake', b'test_', b'test-',
                              b'changeme', b'replace_', b'replace-', b'redacted',
                              b'os.environ', b'os.getenv', b'process.env'))
            or value in {b'password', b'not-a-secret', b'not_a_secret'}
            or len(set(value)) == 1)


def _rules(path, data):
    normalized = path.replace('\\', '/').lower()
    parts = normalized.split('/')
    name = parts[-1]
    rules = []
    if (name == '.env' or (name.startswith('.env.') and
                          name.rsplit('.', 1)[-1] not in {'example', 'sample', 'template', 'dist'})
            or name in {'.netrc', '_netrc', 'credentials.json', 'service-account.json',
                        'id_rsa', 'id_dsa', 'id_ecdsa', 'id_ed25519', 'id_xmss'}
            or normalized.endswith(('.aws/credentials', '.docker/config.json'))
            or name.endswith(('.p12', '.pfx', '.jks', '.keystore'))):
        rules.append('sensitive_file')
    for rule, pattern in _TOKENS:
        matches = list(pattern.finditer(data))
        if any(rule != 'credential_url' or not _placeholder(m.group(1)) for m in matches):
            rules.append(rule)
    literal_values = (m.group('quoted') or m.group('bare') for m in _ASSIGNMENT.finditer(data)
                      if m.group('quoted') is not None or Path(path).suffix.lower() not in _SOURCE_EXTENSIONS)
    if any(not _placeholder(value) for value in literal_values):
        rules.append('secret_assignment')
    first_line = data.lstrip().splitlines()[:1]
    if first_line and first_line[0].strip() in {
            b'version https://git-lfs.github.com/spec/v1',
            b'version https://hawser.github.com/spec/v1'}:
        rules.append('uninspectable_lfs_object')
    return rules


def _scan_tree(root, tree, cache=None):
    cache = cache if cache is not None else {}
    findings = []
    entries = _git(root, 'ls-tree', '-rz', '--full-tree', tree).stdout
    for entry in entries.split(b'\0'):
        if not entry:
            continue
        metadata, raw_path = entry.split(b'\t', 1)
        mode, kind, oid = metadata.split()
        path = os.fsdecode(raw_path)
        if kind != b'blob':
            findings.append({'path': path, 'rule': 'uninspectable_gitlink'})
            continue
        key = (raw_path, oid)
        if key not in cache:
            data = _git(root, 'cat-file', 'blob', oid.decode('ascii')).stdout
            cache[key] = _rules(path, data)
        findings.extend({'path': path, 'rule': rule} for rule in cache[key])
    if findings:
        raise SecurityError('security: rejected Git content', findings)


def check_index(root):
    """Scan the entire exact index tree, including ignored files force-added to it."""
    tree = _decode(_git(root, 'write-tree').stdout)
    _scan_tree(root, tree)
    return {'passed': True, 'tree': tree, 'scope': 'index_tree', 'limitations': LIMITATIONS}


def check_push(root, input_updates):
    """Inspect every outgoing commit tree, retaining leaks deleted in later commits."""
    if _git(root, 'rev-parse', '--is-shallow-repository').stdout.strip() != b'false':
        raise SecurityError('security: incomplete shallow history cannot be inspected')
    if isinstance(input_updates, bytes):
        try:
            input_updates = input_updates.decode('utf-8')
        except UnicodeError as exc:
            raise SecurityError('security: invalid pre-push input') from exc
    cache, seen = {}, set()
    for line in input_updates.splitlines():
        fields = line.split()
        if len(fields) != 4:
            raise SecurityError('security: invalid pre-push input')
        local_ref, local, remote_ref, remote = fields
        if not all(re.fullmatch(r'(?:[0-9a-f]{40}|[0-9a-f]{64})', oid) for oid in (local, remote)):
            raise SecurityError('security: invalid pre-push object ID')
        if set(local) == {'0'}:
            continue
        # Non-commit references cannot be silently declared inspected.
        commit = _decode(_git(root, 'rev-parse', '--verify', local + '^{commit}').stdout)
        exclusions = []
        if set(remote) != {'0'}:
            known = _git(root, 'rev-parse', '--verify', remote + '^{commit}', check=False)
            if not known.returncode:
                exclusions = ['^' + _decode(known.stdout)]
        commits = _git(root, 'rev-list', commit, *exclusions).stdout.splitlines()
        for revision in commits:
            oid = revision.decode('ascii')
            if oid not in seen:
                _scan_tree(root, oid, cache)
                seen.add(oid)
    return {'passed': True, 'scope': 'outgoing_history', 'commits': len(seen),
            'limitations': LIMITATIONS}


def _status(reason, **extra):
    return {'supported': True, 'verified': False, 'reason': reason,
            'limitations': LIMITATIONS, **extra}


def _effective_hooks(root):
    return Path(_decode(_git(root, 'rev-parse', '--path-format=absolute',
                             '--git-path', 'hooks').stdout)).resolve()


def _verify_hooks(root, allow_old_source=False):
    repository = _repository(root)
    if repository is None:
        return _status('not_git_repository')
    root, common, managed = repository
    try:
        manifest = json.loads((managed / MANIFEST).read_text(encoding='utf-8'))
        if manifest.get('schema') != SCHEMA:
            return _status('unsupported_guard_manifest')
        if _effective_hooks(root) != managed.resolve():
            return _status('hooks_path_mismatch')
        files = manifest['files']
        required = {'scanner.py', 'pre-commit', 'pre-push'}
        if not allow_old_source:
            required.update(COMMIT_EVENTS)
        if not required <= files.keys():
            return _status('incomplete_guard_manifest')
        for name, expected in files.items():
            if Path(name).name != name or _digest(managed / name) != expected:
                return _status('guard_file_tampered', path=name)
            if name != 'scanner.py' and os.name != 'nt' and not os.access(managed / name, os.X_OK):
                return _status('hook_not_executable', path=name)
        if not allow_old_source and _digest(__file__) != files['scanner.py']:
            return _status('guard_version_mismatch')
        if not Path(manifest['python_executable']).is_file():
            return _status('python_executable_missing')
        return {'supported': True, 'verified': True, 'hooks_path': str(managed),
                'limitations': LIMITATIONS}
    except (OSError, ValueError, KeyError, TypeError):
        return _status('guard_missing_or_invalid')


def verify_hooks(root):
    """Check effective hook location and each installed executable against its pin."""
    return _verify_hooks(root)


def _shell_quote(value):
    # This quotes the Git-provided sh launcher, including Git for Windows sh.
    return "'" + str(value).replace("'", "'\\''") + "'"


def _previous_hook_path(directory, event, windows=None):
    windows = os.name == 'nt' if windows is None else windows
    exact = directory / event
    return directory / (event + '.exe') if windows and not exact.is_file() else exact


def _prior_events(directory, windows=None):
    windows = os.name == 'nt' if windows is None else windows
    events = set()
    if directory.is_dir():
        for path in directory.iterdir():
            event = path.name[:-4] if windows and path.name.endswith('.exe') else path.name
            if (event in HOOK_EVENTS and path.is_file()
                    and (windows or os.access(path, os.X_OK))):
                events.add(event)
    return events


def install_hooks(root, python_executable=None, update=False):
    """Install in Git metadata; change an intact older pin only on explicit update."""
    repository = _repository(root)
    if repository is None:
        return _status('not_git_repository')
    root, common, managed = repository
    old_manifest = None
    if managed.exists():
        status = verify_hooks(root)
        if status['verified'] or not update:
            return status
        intact = _verify_hooks(root, allow_old_source=True)
        if not intact['verified']:
            return intact
        old_manifest = json.loads((managed / MANIFEST).read_text(encoding='utf-8'))
    previous = Path(old_manifest['previous_hooks_path']) if old_manifest else _effective_hooks(root)
    python = Path(python_executable or sys.executable).resolve()
    if not python.is_file():
        raise SecurityError('security: Python executable not found')
    if previous == managed:
        return _status('guard_missing_or_invalid')
    events = COMMIT_EVENTS | {'pre-push'}
    if old_manifest:
        events.update(set(old_manifest['files']) - {'scanner.py'})
    events.update(_prior_events(previous))
    worktree_config = _git(root, 'config', '--bool', 'extensions.worktreeConfig', check=False)
    config_scope = '--worktree' if worktree_config.stdout.strip() == b'true' else '--local'
    previous_config = _git(root, 'config', config_scope, '--null', '--get-all',
                           'core.hooksPath', check=False)
    previous_values = [os.fsdecode(value) for value in previous_config.stdout.split(b'\0') if value]
    if old_manifest:
        previous_values = old_manifest['previous_config_values']
    temporary = Path(tempfile.mkdtemp(prefix='harness-security-', dir=common))
    try:
        shutil.copyfile(__file__, temporary / 'scanner.py')
        files = {'scanner.py': _digest(temporary / 'scanner.py')}
        for event in sorted(events):
            # Names come from immediate directory entries, never shell source.
            launcher = '#!/bin/sh\nexec {} {} hook {} "$@"\n'.format(
                _shell_quote(python.as_posix()), _shell_quote((managed / 'scanner.py').as_posix()),
                _shell_quote(event))
            target = temporary / event
            target.write_text(launcher, encoding='utf-8', newline='\n')
            target.chmod(0o755)
            files[event] = _digest(target)
        manifest = {'schema': SCHEMA, 'files': files,
                    'previous_hooks_path': str(previous), 'python_executable': str(python),
                    'config_scope': config_scope, 'previous_config_values': previous_values}
        (temporary / MANIFEST).write_text(json.dumps(manifest, ensure_ascii=True, indent=2) + '\n',
                                          encoding='utf-8')
        if old_manifest:
            # Never remove the effective directory or launchers. Interruption leaves
            # mismatched hashes and a refusing guard until explicit repair.
            for name in ['scanner.py', *sorted(events), MANIFEST]:
                os.replace(temporary / name, managed / name)
        else:
            os.rename(temporary, managed)
            _git(root, 'config', config_scope, '--replace-all', 'core.hooksPath', str(managed))
    except (OSError, ValueError) as exc:
        raise SecurityError('security: failed to install Git guard') from exc
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return verify_hooks(root)


def _previous_hook(path, arguments, input_data):
    if not path.is_file() or (os.name != 'nt' and not os.access(path, os.X_OK)):
        return 0
    shell = shutil.which('sh')
    if not shell and os.name == 'nt':
        git_exec = Path(_decode(_git(Path.cwd(), '--exec-path').stdout))
        bundled_shell = git_exec.parents[2] / 'usr/bin/sh.exe'
        if bundled_shell.is_file():
            shell = str(bundled_shell)
    if not shell:
        raise SecurityError('security: Git shell could not be located for prior hook')
    # Shell exec honors executable shebangs and Git's no-shebang shell fallback.
    command = [shell, '-c', 'exec "$0" "$@"', str(path), *arguments]
    try:
        return subprocess.run(command, input=input_data).returncode
    except OSError as exc:
        raise SecurityError('security: prior Git hook could not run') from exc


def _hook(event, arguments):
    root = Path.cwd()
    status = verify_hooks(root)
    if not status['verified']:
        raise SecurityError('security: Git guard verification failed (' + status['reason'] + ')')
    managed = Path(status['hooks_path'])
    manifest = json.loads((managed / MANIFEST).read_text(encoding='utf-8'))
    input_data = sys.stdin.buffer.read() if event == 'pre-push' else None
    previous = _previous_hook_path(Path(manifest['previous_hooks_path']), event)
    if event == 'pre-push':
        # Upload-capable prior hooks (notably LFS) must not see rejected content.
        check_push(root, input_data)
    result = _previous_hook(previous, arguments, input_data)
    if result:
        return result
    if event in COMMIT_EVENTS:
        inspected = check_index(root)
        expected = os.environ.get('HARNESS_SAVE_EXPECTED_TREE')
        if expected is not None:
            if not re.fullmatch(r'(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})', expected):
                raise SecurityError('security: invalid expected save tree')
            if inspected['tree'].lower() != expected.lower():
                raise SecurityError('security: index tree changed after save preflight')
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        if argv and argv[0] == 'hook' and len(argv) >= 2:
            return _hook(argv[1], argv[2:])
        commands = {'check-index': check_index, 'install': install_hooks,
                    'install-hooks': install_hooks, 'verify': verify_hooks}
        update = '--update' in argv
        if update:
            argv.remove('--update')
        if not argv or argv[0] not in commands or len(argv) > 2:
            raise SecurityError('usage: security.py check-index|install|verify [repository]')
        options = {'update': True} if update else {}
        if update and argv[0] not in {'install', 'install-hooks'}:
            raise SecurityError('security: --update applies only to hook installation')
        result = commands[argv[0]](argv[1] if len(argv) == 2 else Path.cwd(), **options)
        print(json.dumps(result, ensure_ascii=True))
        return 0 if (result.get('passed', result.get('verified', False))
                     or result.get('reason') == 'not_git_repository') else 1
    except (SecurityError, OSError, ValueError) as exc:
        print(str(exc) if isinstance(exc, SecurityError) else 'security: inspection failed', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
