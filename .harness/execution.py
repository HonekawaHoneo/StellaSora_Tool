"""Request-scoped, content-bound workflow receipts; no semantic certification."""
import json
import os
from pathlib import Path
import re
import stat
import uuid

import common

STORE = '.harness/changes/.execution'
ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}\Z')
HASH = re.compile(r'[a-f0-9]{64}\Z')
PHASES = {'discovery', 'requirements', 'design', 'implementation', 'review', 'done', None}
ORIGINALS = {'discovery.json', 'requirements.json', 'design.json'}


def _text(value, label):
    return common.nonempty(value, label)


def _identifier(value):
    common.require(value is None or isinstance(value, str) and ID.fullmatch(value), '実行記録の変更IDが不正です')
    return value


def _token(value):
    common.require(isinstance(value, str) and re.fullmatch(r'[a-f0-9]{32}', value), '実行tokenが不正です')
    return value


def _hash(value):
    common.require(isinstance(value, str) and HASH.fullmatch(value), '実行記録の指紋が不正です')
    return value


def _path(root, relative):
    path = common.safe_path(root, relative)
    for part in [path, *path.parents]:
        common.require(not common.is_link(part), f'実行記録にリンクは使えません: {relative}')
        if part == root:
            break
    return path


def _relative(root, value):
    common.require(isinstance(value, (str, Path)), '実ファイルのpathが必要です')
    path = Path(value)
    if path.is_absolute():
        common.require(path.is_relative_to(root), f'プロジェクト外への参照: {value}')
        value = path.relative_to(root).as_posix()
    else:
        value = str(value)
    return _path(root, value).relative_to(root).as_posix()


def _read(root, relative):
    """Hash and decode the same regular file bytes, rejecting replacement races."""
    path = _path(root, relative)
    try:
        common.require(stat.S_ISREG(path.stat().st_mode), f'通常ファイルが必要です: {relative}')
        descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) |
                             getattr(os, 'O_NONBLOCK', 0) | getattr(os, 'O_BINARY', 0))
        with os.fdopen(descriptor, 'rb') as stream:
            before = os.fstat(stream.fileno())
            common.require(stat.S_ISREG(before.st_mode), f'通常ファイルが必要です: {relative}')
            data = stream.read()
            after = os.fstat(stream.fileno())
        current = _path(root, relative).stat()
        identity = lambda item: (item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns, item.st_ctime_ns)
        common.require(identity(before) == identity(after) == identity(current), f'読出し中にファイルが変化しました: {relative}')
        return data.decode('utf-8-sig'), common.sha(data)
    except (OSError, UnicodeError) as exc:
        raise common.GateError(f'実ファイルをUTF-8で読めません: {relative}: {exc}') from exc


def _json(root, relative):
    content, fingerprint = _read(root, relative)
    try:
        value = json.loads(content)
    except ValueError as exc:
        raise common.GateError(f'実行JSONを読めません: {relative}: {exc}') from exc
    common.require(isinstance(value, dict), f'JSONオブジェクトが必要です: {relative}')
    return value, fingerprint


def _write(root, relative, value):
    common.write_json(_path(root, relative), value)


def _binding(root, guidance):
    common.require(isinstance(guidance, dict), 'guideの結果が必要です')
    common.require(guidance.get('workflow_status') != 'selection_required', '対象変更を明示してください')
    identifier = _identifier(guidance.get('id'))
    phase = guidance.get('phase')
    common.require(isinstance(phase, (str, type(None))) and phase in PHASES, 'guideの工程が不正です')
    activities = common.strings(guidance.get('activities'), 'activities')
    skills = guidance.get('required_skills')
    common.require(isinstance(skills, dict) and skills, '必須Skillの割当がありません')
    required = {}
    for role, path in skills.items():
        _text(role, 'Skill role')
        relative = _relative(root, path)
        common.require(relative.startswith('.agents/skills/') and relative.endswith('/SKILL.md'), '実際のSkill本文が必要です')
        required[role] = relative
    continuity = guidance.get('continuity')
    common.require(isinstance(continuity, dict), 'continuityが必要です')
    paths = common.strings(continuity.get('context_paths'), 'context_paths')
    context_paths = sorted({_relative(root, path) for path in paths})
    prefix = f'.harness/changes/{identifier}/' if identifier is not None else None
    originals = [path for path in context_paths if prefix and path.startswith(prefix) and Path(path).name in ORIGINALS]
    _, config_sha = _read(root, '.harness/project.json')
    return {'id': identifier, 'phase': phase, 'activities': sorted(set(activities)),
            'required_skills': required, 'context_paths': originals, 'config_sha256': config_sha}, context_paths


def _pointer(context):
    return f'{STORE}/contexts/{common.sha(context.encode("utf-8"))}.json'


def _record_path(token):
    return f'{STORE}/{_token(token)}.json'


def _validate_binding(binding):
    common.require(isinstance(binding, dict), 'bindingが不正です')
    _identifier(binding.get('id'))
    common.require(isinstance(binding.get('phase'), (str, type(None))) and binding.get('phase') in PHASES, '工程が不正です')
    common.strings(binding.get('activities'), 'activities')
    common.strings(binding.get('context_paths'), 'context_paths')
    skills = binding.get('required_skills')
    common.require(isinstance(skills, dict) and skills, '必須Skillが不正です')
    for role, path in skills.items():
        _text(role, 'Skill role')
        _text(path, 'Skill path')
    _hash(binding.get('config_sha256'))


def _load(root, token):
    record, _ = _json(root, _record_path(token))
    common.require(type(record.get('schema_version')) is int and record['schema_version'] == 1, '実行記録のschema_versionが不正です')
    common.require(record.get('token') == token, '実行記録のtokenが一致しません')
    _text(record.get('context'), 'context')
    _text(record.get('started_at'), 'started_at')
    _hash(record.get('request_digest'))
    _validate_binding(record.get('binding'))
    common.strings(record.get('allowed_context_paths'), 'allowed_context_paths')
    for key in ('pins', 'reads'):
        values = record.get(key)
        common.require(isinstance(values, dict), f'{key}が不正です')
        for path, fingerprint in values.items():
            _path(root, path)
            _hash(fingerprint)
    required = set(record['binding']['required_skills'].values()) | set(record['binding']['context_paths'])
    common.require(set(record['pins']) == required and set(record['reads']) <= required, '読出し対象がbindingと一致しません')
    common.require(record.get('finished') is None or isinstance(record['finished'], str) and record['finished'].strip(), 'finishedが不正です')
    application = record.get('application')
    common.require(application is None or isinstance(application, dict), 'applicationが不正です')
    if application is not None:
        _path(root, application.get('path'))
        _hash(application.get('sha256'))
        common.require(isinstance(application.get('evidence'), dict) and application['evidence'], '適用根拠の指紋が不正です')
        for path, fingerprint in application['evidence'].items():
            _path(root, path)
            _hash(fingerprint)
    return record


def _current(root, record):
    pointer, _ = _json(root, _pointer(record['context']))
    common.require(pointer.get('context') == record['context'] and pointer.get('token') == record['token'], '新しい発言・再開により実行tokenが失効しました')


def _active(root, token):
    record = _load(root, token)
    _current(root, record)
    common.require(record['finished'] is None, '完了した実行記録を再利用できません')
    return record


def begin(root, identifier, context, request_text, guidance):
    root = Path(root).absolute()
    _identifier(identifier)
    _text(context, 'context')
    _text(request_text, 'request_text')
    binding, context_paths = _binding(root, guidance)
    common.require(identifier is None or identifier == binding['id'], 'guideと対象変更が一致しません')
    pins = {path: _read(root, path)[1] for path in set(binding['required_skills'].values()) | set(binding['context_paths'])}
    token = uuid.uuid4().hex
    record = {'schema_version': 1, 'token': token, 'context': context,
              'request_digest': common.sha(request_text.encode('utf-8')), 'started_at': common.now(),
              'binding': binding, 'allowed_context_paths': context_paths,
              'pins': pins, 'reads': {}, 'application': None, 'finished': None}
    _write(root, _record_path(token), record)
    _write(root, _pointer(context), {'context': context, 'token': token})
    return status(root, token, guidance)


def read_skill(root, token, role):
    root = Path(root).absolute()
    record = _active(root, token)
    _text(role, 'Skill role')
    common.require(role in record['binding']['required_skills'], f'未割当のSkill roleです: {role}')
    relative = record['binding']['required_skills'][role]
    content, fingerprint = _read(root, relative)
    common.require(fingerprint == record['pins'][relative], 'Skillが変わりました。新しい実行を開始してください')
    record['reads'][relative] = fingerprint
    _write(root, _record_path(token), record)
    return {'token': token, 'role': role, 'path': relative, 'sha256': fingerprint, 'content': content}


def read_context(root, token, relative):
    root = Path(root).absolute()
    record = _active(root, token)
    common.require(isinstance(relative, str) and not Path(relative).is_absolute(), 'contextはプロジェクト相対パスが必要です')
    relative = _relative(root, relative)
    common.require(relative in record['allowed_context_paths'], 'guideにないcontextは読出し記録にできません')
    content, fingerprint = _read(root, relative)
    if relative in record['pins']:
        common.require(fingerprint == record['pins'][relative], '原指示・条件が変わりました。新しい実行を開始してください')
        record['reads'][relative] = fingerprint
        _write(root, _record_path(token), record)
    return {'token': token, 'path': relative, 'sha256': fingerprint, 'content': content}


def _resolve_pointer(content, pointer):
    common.require(isinstance(pointer, str) and pointer.startswith('/') and not re.search(r'~(?![01])', pointer), 'JSON pointerが不正です')
    try:
        value = json.loads(content)
        for part in pointer[1:].split('/'):
            key = part.replace('~1', '/').replace('~0', '~')
            if isinstance(value, list):
                common.require(re.fullmatch(r'0|[1-9][0-9]*', key), 'JSON配列の添字が不正です')
                value = value[int(key)]
            else:
                common.require(isinstance(value, dict), 'JSON pointerの参照先がありません')
                value = value[key]
        common.require(value is not None and value != '' and value != [] and value != {}, 'JSON pointerの参照先が空です')
    except (ValueError, KeyError, IndexError) as exc:
        raise common.GateError(f'JSON pointerの参照先がありません: {pointer}') from exc


def _application(root, record, relative):
    value, fingerprint = _json(root, relative)
    common.require(value.get('token') == record['token'] and value.get('request_digest') == record['request_digest'], '適用記録の発言・実行tokenが一致しません')
    intent = value.get('intent')
    common.require(isinstance(intent, dict), 'intentが必要です')
    _text(intent.get('goal'), 'intent.goal')
    common.require(intent.get('relation') in ('continue', 'correction', 'status', 'new'), 'intent.relationが不正です')
    _text(intent.get('question_check'), 'intent.question_check')
    skills = value.get('skills')
    common.require(isinstance(skills, dict) and set(skills) == set(record['binding']['required_skills']), '全必須Skill roleの適用根拠が必要です')
    evidence = {}
    for role, application in skills.items():
        common.require(isinstance(application, dict), f'Skill適用記録が不正です: {role}')
        _text(application.get('applied'), f'{role}.applied')
        for reference in common.sequence(application.get('evidence'), f'{role}.evidence', 1):
            common.require(isinstance(reference, dict), '実ファイルの根拠参照が必要です')
            path = _relative(root, reference.get('path'))
            common.require(not path.startswith(STORE + '/'), '実行記録自身を適用根拠にできません')
            content, file_sha = _read(root, path)
            common.require(('anchor' in reference) != ('pointer' in reference), 'anchorまたはpointerの一方が必要です')
            if 'anchor' in reference:
                anchor = _text(reference['anchor'], 'evidence.anchor')
                common.require(anchor in content, f'根拠のanchorが実ファイルにありません: {path}')
            else:
                _resolve_pointer(content, reference['pointer'])
            common.require(path not in evidence or evidence[path] == file_sha, '根拠ファイルが読出し中に変化しました')
            evidence[path] = file_sha
    return {'path': relative, 'sha256': fingerprint, 'evidence': evidence}


def apply(root, token, application_path, guidance):
    root = Path(root).absolute()
    record = _active(root, token)
    binding, _ = _binding(root, guidance)
    common.require(binding == record['binding'], '工程・設定・担当が変わりました。新しい実行を開始してください')
    relative = _relative(root, application_path)
    common.require(not relative.startswith(STORE + '/'), '実行記録自身を適用記録にできません')
    record['application'] = _application(root, record, relative)
    _write(root, _record_path(token), record)
    return status(root, token, guidance)


def status(root, token, guidance):
    root = Path(root).absolute()
    result = {'token': token, 'ready': False, 'finished': False, 'valid': False,
              'completion_usable': False, 'blockers': []}
    try:
        record = _load(root, token)
        binding = record['binding']
        result.update({key: binding[key] for key in ('id', 'phase', 'activities', 'required_skills', 'context_paths')})
        result.update(context=record['context'], request_digest=record['request_digest'], finished=record['finished'] is not None)
        if not result['finished']:
            _current(root, record)
        current, _ = _binding(root, guidance)
        common.require(current == binding, '工程・設定・担当・原資料一覧が変わりました')
        blockers = common.strings(guidance.get('blockers', []), 'guide.blockers')
        result['blockers'].extend(blockers)
        for path, fingerprint in record['pins'].items():
            common.require(_read(root, path)[1] == fingerprint, f'Skillまたは原資料が変わりました: {path}')
            if record['reads'].get(path) != fingerprint:
                result['blockers'].append(f'本文の読出しが必要です: {path}')
        application = record['application']
        if application is None:
            result['blockers'].append('現在の発言へのSkill適用根拠が必要です')
        else:
            common.require(_application(root, record, application['path']) == application, '適用記録または実ファイルの根拠が変わりました')
        result['valid'] = not result['blockers']
        result['completion_usable'] = result['valid'] and result['finished']
        result['ready'] = result['valid'] and not result['finished']
        if result['finished']:
            result['blockers'].append('完了した実行記録は編集・工程移行に再利用できません')
    except (common.GateError, OSError, ValueError, TypeError, KeyError) as exc:
        result['blockers'].append(str(exc))
    return result


def finish(root, token, guidance):
    root = Path(root).absolute()
    record = _active(root, token)
    result = status(root, token, guidance)
    common.require(result['ready'], '\n'.join(result['blockers']))
    record['finished'] = common.now()
    _write(root, _record_path(token), record)
    return status(root, token, guidance)
