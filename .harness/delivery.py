"""One delivery step using real quality gates and a GitHub adapter; no daemon."""
import datetime as dt
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

import harness as h
import security

PR_FIELDS = ('number,url,state,isDraft,isCrossRepository,headRefName,headRefOid,baseRefName,'
             'mergeable,mergeStateStatus,reviewDecision,statusCheckRollup,mergeCommit')
REPO_FIELDS = 'nameWithOwner,defaultBranchRef,squashMergeAllowed,mergeCommitAllowed,rebaseMergeAllowed'


class Waiting(h.GateError):
    """The forge requires checks, reviews, or protection conditions to finish."""


class GitHubCLI:
    def call(self, root, args, payload=None, json_output=True):
        result = subprocess.run(['gh', *args], cwd=root, capture_output=True, text=True, encoding="utf-8",
                                input=json.dumps(payload) if payload is not None else None, timeout=60)
        h.require(result.returncode == 0, f"GitHub操作に失敗しました: {result.stderr.strip()}")
        if not json_output:
            return result.stdout.strip()
        try:
            return json.loads(result.stdout)
        except ValueError as exc:
            raise h.GateError('GitHubのJSON応答を読めません') from exc

    def repository(self, root):
        repo = self.call(root, ['repo', 'view', '--json', REPO_FIELDS])
        default = repo.get('defaultBranchRef') or {}
        if default.get('name') and not (default.get('target') or {}).get('oid'):
            default['target'] = {'oid': self.base_sha(root, repo['nameWithOwner'], default['name'])}
        return repo

    def base_sha(self, root, repository, branch):
        return self.call(root, ['api', f'repos/{repository}/commits/{branch}'])['sha']

    def find_pr(self, root, repository, branch):
        prs = self.call(root, ['pr', 'list', '--repo', repository, '--head', branch, '--state', 'all',
                               '--limit', '100', '--json', PR_FIELDS])
        h.require(isinstance(prs, list) and len(prs) <= 1, '同じ作業ブランチのPRが複数あります。対象を確定してください')
        pr = prs[0] if prs else None
        if pr is not None and pr.get('state') == 'OPEN':
            pr['baseRefOid'] = self.base_sha(root, repository, pr['baseRefName'])
        return pr

    def create_pr(self, root, repository, branch, base, identifier):
        goal = h.artifact(root, identifier, 'discovery')['goal']
        body = f"{goal}\n\n品質ゲート: `{identifier}`。独立レビューと登録検証の証跡は `.harness/changes/{identifier}/`。\n"
        with tempfile.TemporaryDirectory(prefix='harness-pr-') as directory:
            path = Path(directory) / 'body.md'
            path.write_text(body, encoding='utf-8')
            self.call(root, ['pr', 'create', '--repo', repository, '--head', branch, '--base', base,
                             '--title', identifier, '--body-file', str(path)], json_output=False)
        pr = self.find_pr(root, repository, branch)
        h.require(pr is not None, '作成したPRの状態を取得できません。再開時に再照合してください')
        return pr

    def merge(self, root, repository, number, expected_head_sha, method):
        return self.call(root, ['api', '--method', 'PUT', f'repos/{repository}/pulls/{number}/merge',
                                '--input', '-'], {'sha': expected_head_sha, 'merge_method': method})


class RecordedGitHub:
    """Read-only bridge for a fresh snapshot collected by a connected tool."""
    def __init__(self, path):
        self.data = h.read_json(Path(path))
        try:
            observed = dt.datetime.fromisoformat(self.data['observed_at'])
            age = (dt.datetime.now(dt.timezone.utc) - observed).total_seconds()
        except (KeyError, TypeError, ValueError) as exc:
            raise h.GateError('forge-stateのobserved_atにタイムゾーン付き時刻が必要です') from exc
        h.require(-5 <= age <= 60, 'forge-stateが古いです。GitHubの状態を取得し直してください')

    def repository(self, root):
        return self.data['repository']

    def base_sha(self, root, repository, branch):
        return self.data.get('base_shas', {}).get(branch)

    def find_pr(self, root, repository, branch):
        return self.data['pull_request']


def git(root, *args):
    result = subprocess.run(['git', *args], cwd=root, capture_output=True, text=True, encoding="utf-8", timeout=15)
    h.require(result.returncode == 0, f"Git状態を確認できません: {' '.join(args[:2])}")
    return result.stdout if '-z' in args else result.stdout.rstrip('\r\n')


def pending_paths(root):
    changed = git(root, 'diff', '--name-only', '-z', 'HEAD').split('\0')
    changed += git(root, 'ls-files', '--others', '--exclude-standard', '-z').split('\0')
    return [path for path in changed if path]


def config_values(root, key):
    result = subprocess.run(['git', 'config', '--get-all', key], cwd=root,
                            capture_output=True, text=True, encoding="utf-8", timeout=15)
    h.require(result.returncode in (0, 1), 'Gitのpush設定を確認できません')
    return result.stdout.splitlines()


def push_branch(root, remote, branch):
    refspecs = config_values(root, f'remote.{remote}.push')
    if refspecs:
        h.require(len(refspecs) == 1, '複数のpush先があります。保存先を--branchで明示してください')
        source, separator, target = refspecs[0].lstrip('+').partition(':')
        h.require(source in ('HEAD', branch, f'refs/heads/{branch}'),
                  'push先を一意に解釈できません。保存先を--branchで明示してください')
        target = target if separator else (branch if source == 'HEAD' else source)
        h.require(target and (not target.startswith('refs/') or target.startswith('refs/heads/')),
                  '保存先にはブランチを指定してください')
        return target.removeprefix('refs/heads/')
    modes = config_values(root, 'push.default')
    mode = modes[-1] if modes else 'simple'
    upstream = config_values(root, f'branch.{branch}.remote')
    merged = config_values(root, f'branch.{branch}.merge')
    if mode == 'upstream':
        h.require(upstream == [remote] and len(merged) == 1 and merged[0].startswith('refs/heads/'),
                  'upstreamの保存先を確定できません。--branchで明示してください')
        return merged[0].removeprefix('refs/heads/')
    h.require(mode in ('simple', 'current', 'matching'), '保存先を--branchで明示してください')
    if mode == 'simple' and upstream == [remote] and merged:
        h.require(merged == [f'refs/heads/{branch}'], 'upstreamと作業ブランチが異なります。--branchで明示してください')
    return branch


def save_destination(root, remote, remote_branch):
    """Resolve one named branch and one configured push destination."""
    h.require(isinstance(remote, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', remote),
              '設定済みのリモート名を指定してください')
    h.require(Path(git(root, 'rev-parse', '--show-toplevel')).resolve() == root.resolve(),
              '保存確認の対象はGitリポジトリのルートを指定してください')
    branch = git(root, 'symbolic-ref', '--quiet', '--short', 'HEAD')
    destinations = git(root, 'remote', 'get-url', '--push', '--all', remote).splitlines()
    h.require(len(destinations) == 1, 'push先を一つに確定して保存確認してください')
    target = remote_branch if remote_branch is not None else push_branch(root, remote, branch)
    h.nonempty(target, '保存先ブランチ')
    git(root, 'check-ref-format', f'refs/heads/{target}')
    return branch, destinations[0], target


def unsaved_paths(root):
    """Keep durable artifacts strict while omitting valid transient read cursors."""
    remaining = []
    for relative in pending_paths(root):
        if relative == '.harness/runtime.lock':
            continue
        try:
            if re.fullmatch(r'\.harness/changes/\.execution/[a-f0-9]{32}\.json', relative):
                record = h.execution._load(root, Path(relative).stem)
                if record['finished'] is None:
                    continue
            elif re.fullmatch(r'\.harness/changes/\.execution/contexts/[a-f0-9]{64}\.json', relative):
                cursor, _ = h.execution._json(root, relative)
                record = h.execution._load(root, cursor.get('token'))
                if cursor.get('context') == record['context'] and h.sha(record['context'].encode('utf-8')) == Path(relative).stem:
                    continue
        except (h.GateError, OSError, KeyError, TypeError, ValueError):
            pass
        remaining.append(relative)
    return remaining


def backup_check(root, remote='origin', remote_branch=None, *, allow_pending=False):
    """Verify a clean local HEAD exists at the configured push destination."""
    root = Path(root).resolve()
    branch, destination, target = save_destination(root, remote, remote_branch)
    head = git(root, 'rev-parse', 'HEAD')
    remaining = unsaved_paths(root)
    h.require(allow_pending or not remaining,
              'コード・設定・工程成果物をコミットしてから保存確認してください')
    reference = f'refs/heads/{target}'
    observed = git(root, 'ls-remote', '--exit-code', '--refs', '--', destination, reference).splitlines()
    entries = [line.split() for line in observed]
    h.require(entries == [[head, reference]], 'リモートの保存先と現在のHEADが一致していません。push結果を確認してください')
    h.require(git(root, 'rev-parse', 'HEAD') == head and
              git(root, 'symbolic-ref', '--quiet', '--short', 'HEAD') == branch and
              unsaved_paths(root) == remaining,
              '保存確認中に作業内容が変わりました。コミット・push・確認をやり直してください')
    result = {'status': 'remote_saved', 'remote': remote, 'branch': branch, 'remote_branch': target,
            'head_sha': head, 'remote_sha': head, 'observed_at': h.now()}
    if allow_pending:
        result.update(status='selected_paths_saved' if remaining else 'remote_saved',
                      all_work_saved=not remaining, remaining_paths=remaining)
    return result


def save_git(root, *args, env=None, check=True):
    """Run Git without exposing arbitrary hook output or credential-bearing URLs."""
    try:
        result = subprocess.run(['git', *args], cwd=root, capture_output=True,
                                env=dict(os.environ if env is None else env, GIT_OPTIONAL_LOCKS='0'))
    except (OSError, ValueError) as exc:
        raise h.GateError('保存のGit操作を実行できません') from exc
    h.require(not check or result.returncode == 0,
              f'保存のGit操作に失敗しました: {args[0]}。既存HookとGit状態を確認してください')
    return result


def selected_files(root, paths):
    """Accept literal individual files, including tracked deletions."""
    h.require(isinstance(paths, (list, tuple)) and bool(paths), '保存するファイルを明示してください')
    selected, stage_paths = [], []
    deleted = save_git(root, 'diff-tree', '--root', '--no-commit-id', '--no-renames',
                       '--diff-filter=D', '-r', '--name-only', '-z', 'HEAD', check=False).stdout.split(b'\0')
    for name in paths:
        h.require(isinstance(name, (str, Path)) and bool(str(name)) and '\0' not in str(name),
                  '保存対象にはファイルパスを指定してください')
        candidate = Path(os.path.abspath(root / name))
        try:
            relative = candidate.relative_to(root)
            candidate.resolve().relative_to(root)
        except (ValueError, OSError, RuntimeError) as exc:
            raise h.GateError('保存対象はリポジトリ内のファイルに限定してください') from exc
        h.require(relative.parts and not any(part.lower() == '.git' for part in relative.parts)
                  and not candidate.is_dir(), 'ディレクトリやGitメタデータは保存対象にできません')
        name = relative.as_posix()
        tracked_paths = save_git(root, '--literal-pathspecs', 'ls-files', '-z', '--', name).stdout
        tracked = os.fsencode(name) in tracked_paths.split(b'\0')
        stage = candidate.is_file() or candidate.is_symlink() or tracked
        h.require(stage or os.fsencode(name) in deleted,
                  '保存対象のファイルがありません')
        if name not in selected:
            selected.append(name)
            if stage:
                stage_paths.append(name)
    return selected, stage_paths


def require_selected_index(root, selected, *, env=None):
    changed = save_git(root, 'diff', '--cached', '--no-renames', '--name-only', '-z', env=env).stdout
    paths = [os.fsdecode(path) for path in changed.split(b'\0') if path]
    h.require(set(paths) <= set(selected), '無関係なstage済み変更があります。対象を分けて保存してください')


def promote_index(index, original, snapshot):
    """Publish Git's checked index snapshot while honoring Git's exclusive lock."""
    lock = index.with_name(index.name + '.lock')
    acquired = False
    try:
        with lock.open('xb') as stream:
            acquired = True
            current = index.read_bytes() if index.exists() else None
            h.require(current == original, '検査中にGit indexが変更されました。保存をやり直してください')
            stream.write(snapshot)
        os.replace(lock, index)
    except OSError as exc:
        raise h.GateError('Git indexを保存できません。実行中のGit操作とindex.lockを確認してください') from exc
    finally:
        if acquired and lock.exists():
            lock.unlink()


def save(root, message, paths, remote='origin', remote_branch=None):
    """Check selected content, commit with verified hooks, push, and inspect the remote."""
    root = Path(root).resolve()
    h.nonempty(message, 'コミットメッセージ')
    h.require('\0' not in message, 'コミットメッセージにNULは使えません')
    branch, destination, target = save_destination(root, remote, remote_branch)
    selected, stage_paths = selected_files(root, paths)
    require_selected_index(root, selected)
    index = Path(os.fsdecode(save_git(root, 'rev-parse', '--path-format=absolute',
                                      '--git-path', 'index').stdout).rstrip('\r\n'))
    original = index.read_bytes() if index.exists() else None
    head = save_git(root, 'rev-parse', '--verify', 'HEAD', check=False).stdout.rstrip(b'\r\n')
    with tempfile.TemporaryDirectory(prefix='harness-save-') as directory:
        temporary_index = Path(directory) / 'index'
        environment = dict(os.environ, GIT_INDEX_FILE=str(temporary_index))
        if original is not None:
            temporary_index.write_bytes(original)
        elif head:
            save_git(root, 'read-tree', head.decode('ascii'), env=environment)
        else:
            save_git(root, 'read-tree', '--empty', env=environment)
        require_selected_index(root, selected, env=environment)
        if stage_paths:
            save_git(root, '--literal-pathspecs', 'add', '--', *stage_paths, env=environment)
        scan = subprocess.run([sys.executable, str(Path(security.__file__).resolve()),
                               'check-index', str(root)], env=environment, capture_output=True,
                              text=True, encoding='utf-8')
        h.require(scan.returncode == 0, scan.stderr.rstrip('\r\n') or 'security: index inspection failed')
        tree = json.loads(scan.stdout)['tree']
        snapshot = temporary_index.read_bytes()
    try:
        guard = security.install_hooks(root)
        h.require(guard.get('verified') and security.verify_hooks(root).get('verified'),
                  'GitセキュリティHookを検証できません。固定版・実効Hookを確認してください')
    except security.SecurityError as exc:
        raise h.GateError(str(exc)) from exc
    h.require(save_git(root, 'rev-parse', '--verify', 'HEAD', check=False).stdout.rstrip(b'\r\n') == head
              and git(root, 'symbolic-ref', '--quiet', '--short', 'HEAD') == branch,
              '検査中にHEADが変更されました。保存をやり直してください')
    promote_index(index, original, snapshot)
    changed = save_git(root, 'diff', '--cached', '--quiet', check=False)
    h.require(changed.returncode in (0, 1), '保存対象の差分を確認できません')
    committed = changed.returncode == 1
    if committed:
        environment = dict(os.environ, HARNESS_SAVE_EXPECTED_TREE=tree)
        save_git(root, 'commit', '-m', message, env=environment)
    h.require(git(root, 'rev-parse', 'HEAD^{tree}') == tree,
              'コミット内容が検査済みの内容と異なります。pushを停止しました')
    h.require(security.verify_hooks(root).get('verified'), 'push前のGitセキュリティHook検証に失敗しました')
    h.require(save_destination(root, remote, target) == (branch, destination, target),
              '保存中にGitの保存先が変わりました。pushを停止しました')
    save_git(root, 'push', '--', remote, f'HEAD:refs/heads/{target}')
    result = backup_check(root, remote=remote, remote_branch=target, allow_pending=True)
    h.require(not set(result['remaining_paths']).intersection(selected),
              '保存中に選択ファイルが変更されました。変更分を再度保存してください')
    return {**result, 'selected_paths': selected, 'selected_paths_saved': True,
            'committed': committed, 'security_checked': True, 'hooks_verified': True}


def save_change(root, identifier, message=None):
    """Save a valid completed change and only its explicit audit dependencies."""
    root = Path(root).resolve()
    h.check(root, identifier)
    current = h.state(root, identifier)
    h.require(current['phase'] == 'done', '保存には品質ゲートのdoneが必要です')
    paths = set(h.source_delta(root, current))
    framework = h.read_json(root / '.harness/framework.lock.json')
    paths.update(framework['files'])
    paths.update((framework['agents_path'], '.harness/framework.lock.json', '.harness/project.json'))
    if (h.config(root).get('ui') or {}).get('registry') == '.harness/ui-registry.json':
        h.execution._path(root, '.harness/ui-registry.json')
        paths.add('.harness/ui-registry.json')
    directory = h.change_dir(root, identifier)
    prefix = directory.relative_to(root).as_posix() + '/'
    for path in directory.rglob('*'):
        relative = path.relative_to(root).as_posix()
        h.execution._path(root, relative)
        if path.is_file():
            paths.add(relative)
    tokens = set()
    try:
        events = (directory / 'events.jsonl').read_text(encoding='utf-8').splitlines()
        for line in events:
            event = json.loads(line)
            h.require(isinstance(event, dict) and isinstance(event.get('event'), str), '変更イベントが不正です')
            if event['event'] == 'skill_application_verified':
                tokens.add(h.execution._token(event.get('token')))
    except (OSError, UnicodeError, ValueError) as exc:
        raise h.GateError('変更イベントを読み取れません') from exc
    if 'execution_completion' in current:
        completed = current['execution_completion']
        h.require(isinstance(completed, dict), '完了時の実行記録が不正です')
        tokens.add(h.execution._token(completed.get('token')))
    for token in sorted(tokens):
        record = h.execution._load(root, token)
        h.require(record['binding']['id'] == identifier and record['finished'] is not None and
                  record['application'] is not None, '完了した対象変更の実行記録が必要です')
        paths.add(f'{h.execution.STORE}/{token}.json')
        application = record['application']
        for relative in [application['path'], *application['evidence']]:
            canonical = h.execution._path(root, relative).relative_to(root).as_posix()
            h.require(relative == canonical, '適用根拠には正規化した相対パスが必要です')
            h.require(not relative.casefold().startswith('.harness/changes/') or
                      relative.casefold().startswith(prefix.casefold()),
                      '別の変更記録を保存対象の適用根拠にできません')
            h.require(relative.casefold() != '.harness/runtime.lock' and
                      not any(part.lower() == '.git' for part in Path(relative).parts),
                      'Gitメタデータや実行ロックを適用根拠にできません')
        paths.add(application['path'])
        paths.update(relative for relative in application['evidence']
                     if relative.startswith(prefix) or relative not in current['baseline_files'])
    for relative in paths:
        h.safe_path(root, relative)
        h.require(relative.casefold() != '.harness/runtime.lock' and
                  not any(part.lower() == '.git' for part in Path(relative).parts),
                  'Gitメタデータや実行ロックは保存対象にできません')
    return save(root, message if message is not None else f'Save verified change {identifier}', sorted(paths))


def local_state(root, identifier, require_merge):
    h.check(root, identifier)
    h.require(h.state(root, identifier)['phase'] == 'done', '配送には品質ゲートのdoneが必要です')
    policy = h.config(root).get('autonomy')
    h.require(policy is not None, 'autonomyの明示設定が必要です')
    allowed = ('merged',) if require_merge else ('pr', 'merged')
    h.require(policy['completion'] in allowed, 'このautonomyではPR作成・マージを許可していません')
    branch = git(root, 'symbolic-ref', '--short', 'HEAD')
    h.require(branch == policy['branch_prefix'] + identifier, '変更IDに対応するAI用ブランチが必要です')
    head = git(root, 'rev-parse', 'HEAD')
    dirty = [p for p in pending_paths(root) if not p.startswith('.harness/changes/') and
             p != '.harness/runtime.lock' and not any(part in h.SKIP_DIRS for part in Path(p).parts)]
    h.require(not dirty, 'レビュー済みのコード・設定をコミットしてから配送してください')
    review = h.artifact(root, identifier, 'review')
    h.require(isinstance(review.get('base_sha'), str) and
              re.fullmatch(r'(?:[0-9a-f]{40}|[0-9a-f]{64})', review['base_sha']),
              'review.base_shaにレビュー対象のマージ先SHAが必要です')
    return policy, branch, head, review


def context(root, identifier, github, require_merge):
    policy, branch, head, review = local_state(root, identifier, require_merge)
    repo = github.repository(root)
    repository = repo.get('nameWithOwner')
    h.require(isinstance(repository, str) and re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository),
              'GitHubリポジトリを特定できません')
    default = repo.get('defaultBranchRef') or {}
    base = default.get('name') if policy['base_branch'] == 'default' else policy['base_branch']
    h.nonempty(base, '配送先ブランチ')
    h.require(base != branch, '作業ブランチ自身にはマージできません')
    pr = github.find_pr(root, repository, branch)
    data = {'id': identifier, 'repository': repository, 'branch': branch, 'base_branch': base,
            'expected_head_sha': head, 'project_digest': review['project_digest']}
    record_path = h.change_dir(root, identifier) / 'delivery.json'
    if record_path.exists():
        previous = h.read_json(record_path)
        for key in ('repository', 'branch', 'base_branch'):
            h.require(previous.get(key) == data[key], '配送記録と実際の対象が異なります')
        if previous.get('pr_number') is not None:
            h.require(pr is not None and previous['pr_number'] == pr.get('number'), '配送記録とPRが異なります')
    if pr is not None:
        h.require(pr.get('headRefName') == branch and pr.get('baseRefName') == base and
                  pr.get('isCrossRepository') is False, 'PRの作業元・マージ先が設定と異なります')
        h.require(pr.get('headRefOid') == head, 'PRのheadがレビュー済みのローカルHEADと異なります')
        h.require(type(pr.get('number')) is int and pr['number'] > 0, 'PR番号が不正です')
        data.update(pr_number=pr['number'], url=pr.get('url'))
        if pr.get('state') == 'MERGED':
            h.nonempty((pr.get('mergeCommit') or {}).get('oid'), 'mergeCommit.oid')
            return data, repo, pr, review
        h.require(pr.get('state') == 'OPEN', 'PRは未マージのまま閉じられています')
    base_sha = ((default.get('target') or {}).get('oid') if default.get('name') == base
                else github.base_sha(root, repository, base))
    h.require(pr is None or pr.get('baseRefOid') == base_sha,
              'マージ先が状態取得中に変更されています。取得・検証・レビューをやり直してください')
    h.require(base_sha == review['base_sha'], 'マージ先がレビュー後に変更されています。更新・再検証・再レビューしてください')
    git(root, 'merge-base', '--is-ancestor', base_sha, head)
    data['base_sha'] = base_sha
    return data, repo, pr, review


def ready(data, repo, pr):
    h.require(pr is not None, 'PRがありません。ブランチをpushし、shipまたは接続ツールでPRを作成してください')
    if pr['state'] == 'MERGED':
        return {**data, 'status': 'merged', 'ready': False, 'merge_sha': pr['mergeCommit']['oid']}
    if (pr.get('isDraft') is not False or pr.get('mergeable') != 'MERGEABLE' or
            pr.get('mergeStateStatus') != 'CLEAN' or pr.get('reviewDecision') not in ('APPROVED', '')):
        raise Waiting('GitHubの必須CI・レビュー・競合・保護条件が未完了です')
    checks = pr.get('statusCheckRollup')
    h.require(isinstance(checks, list), 'GitHubのチェック状態を取得できません')
    for check in checks:
        success = ((check.get('__typename') == 'CheckRun' and check.get('status') == 'COMPLETED' and
                    check.get('conclusion') in ('SUCCESS', 'NEUTRAL', 'SKIPPED')) or
                   (check.get('__typename') == 'StatusContext' and check.get('state') == 'SUCCESS'))
        if not success:
            raise Waiting('GitHubのチェックが失敗・実行中・未確認です')
    method = next((method for method, flag in [('squash', 'squashMergeAllowed'),
                    ('merge', 'mergeCommitAllowed'), ('rebase', 'rebaseMergeAllowed')]
                   if repo.get(flag) is True), None)
    h.require(method is not None, '許可されたマージ方式がありません')
    return {**data, 'status': 'ready', 'ready': True, 'merge_method': method}


def ship_check(root, identifier, github=None):
    """Inspect gates and current forge state without writing any project file."""
    data, repo, pr, _ = context(root, identifier, github or GitHubCLI(), True)
    return ready(data, repo, pr)


def save_receipt(root, identifier, data):
    h.write_json(h.change_dir(root, identifier) / 'delivery.json',
                 {'schema_version': 1, 'updated_at': h.now(), **data})
    return data


def ship(root, identifier, github=None):
    """Create or resume one PR, then merge only the currently verified head."""
    github = github or GitHubCLI()
    data, repo, pr, _ = context(root, identifier, github, False)
    if pr is None:
        save_receipt(root, identifier, {**data, 'status': 'creating'})
        github.create_pr(root, data['repository'], data['branch'], data['base_branch'], identifier)
        data, repo, pr, _ = context(root, identifier, github, False)
    if pr.get('state') == 'MERGED':
        return save_receipt(root, identifier, ready(data, repo, pr))
    if h.config(root)['autonomy']['completion'] == 'pr':
        return save_receipt(root, identifier, {**data, 'status': 'pr', 'ready': False})
    try:
        result = ready(data, repo, pr)
    except Waiting as exc:
        return save_receipt(root, identifier, {**data, 'status': 'waiting', 'ready': False, 'reason': str(exc)})
    save_receipt(root, identifier, {**result, 'status': 'merging', 'ready': False})
    response = github.merge(root, data['repository'], data['pr_number'], data['expected_head_sha'], result['merge_method'])
    h.require(isinstance(response, dict) and response.get('merged') is True, 'GitHubがマージを完了していません。実PRを再照合してください')
    data, repo, pr, _ = context(root, identifier, github, True)
    h.require(pr is not None and pr.get('state') == 'MERGED', 'マージ後のPR状態を確認できません。再開時に再照合してください')
    return save_receipt(root, identifier, ready(data, repo, pr))
