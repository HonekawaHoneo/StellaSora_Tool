#!/usr/bin/env python3
"""Exercise Gitleaks allowlists and detections using synthetic public fixtures."""

import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path


def fixture_cases():
    chars = list('0123456789abcdef' * 2)
    chars[12], chars[16] = '4', '8'
    nonce = ''.join(chars)
    other = list(nonce)
    other[0] = 'f'
    second_nonce = ''.join(other)
    non_v4 = '0123456789abcdef' * 2
    github = 'ghp_' + hashlib.sha256(b'public positive detection fixture').hexdigest()[:36]
    digest = '477cb74d5e54313ab31dacb3c64b8497676093c20f2c66037b889bbb3b17dbec'
    execution = '.harness/changes/.execution/' + nonce + '.json'
    context = '.harness/changes/.execution/contexts/' + 'a' * 64 + '.json'
    phase = '.harness/changes/game-purpose-ui/skill-design.json'
    suffixed = '.harness/changes/game-purpose-ui/skill-design-' + nonce + '.json'
    application = '.harness/changes/game-purpose-ui/inputs/review-skill-application.json'
    install = '.harness/changes/.inputs/cloud-install-application.json'
    event = '.harness/changes/game-purpose-ui/events.jsonl'
    snapshot = '.harness/changes/game-purpose-ui/inputs/ui-4274fbc5be2f48bab5540dfaff4cc611.json'
    event_record = {'time': '2026-11-12T05:43:34.807738+00:00',
                    'event': 'skill_application_verified', 'token': nonce,
                    'phase': 'design', 'request_digest': 'b' * 64}
    cases = [
        ('execution_nonce', execution, '  "token": "' + nonce + '",', None),
        ('context_nonce', context, '  "token": "' + nonce + '"', None),
        ('phase_nonce', phase, '  "token": "' + nonce + '",', None),
        ('phase_suffixed_nonce', suffixed, '  "token": "' + nonce + '",', None),
        ('application_nonce', application, '  "token": "' + nonce + '",', None),
        ('install_nonce', install, '  "token": "' + nonce + '",', None),
        ('new_execution_nonce', '.harness/changes/.execution/' + second_nonce + '.json',
         '  "token": "' + second_nonce + '",', None),
        ('event_nonce', event, json.dumps(event_record), None),
        ('state_nonce', '.harness/changes/game-purpose-ui/state.json', '    "token": "' + nonce + '"', None),
        ('snapshot_digest', snapshot, '  "development/ui/summary-tokens.json": "' + digest + '",', None),
        ('other_field', execution, '  "api_key": "' + nonce + '",', 'generic-api-key'),
        ('non_v4_token', phase, '  "token": "' + non_v4 + '",', 'generic-api-key'),
        ('extra_field', application, '{"token": "' + nonce + '", "extra": true}', 'generic-api-key'),
        ('other_path', 'dist/config.json', '  "token": "' + nonce + '",', 'generic-api-key'),
        ('unapproved_metadata', '.harness/changes/game-purpose-ui/inputs/credentials.json',
         '  "token": "' + nonce + '",', 'generic-api-key'),
        ('wrong_snapshot_digest', snapshot, '  "development/ui/summary-tokens.json": "' + 'fedcba9876543210' * 4 + '",', 'generic-api-key'),
        ('state_other_field', '.harness/changes/game-purpose-ui/state.json', '  "api_key": "' + nonce + '",', 'generic-api-key'),
        ('provider_rule', execution, '  "token": "' + github + '",', 'github-pat'),
        ('event_extra_field', event, json.dumps({**event_record, 'extra': True}), 'generic-api-key'),
        ('other_event', event, json.dumps({**event_record, 'event': 'credentials_loaded'}), 'generic-api-key'),
        ('event_other_field', event, json.dumps({**event_record, 'api_key': nonce}), 'generic-api-key'),
    ]
    return cases


def scan(binary, config, root, report):
    command = [str(binary), 'dir', '.', '--config', str(config), '--no-banner',
               '--redact=100', '--ignore-gitleaks-allow', '--report-format', 'json',
               '--report-path', str(report)]
    result = subprocess.run(command, cwd=root, text=True, capture_output=True)
    if result.returncode not in (0, 1):
        raise RuntimeError('Gitleaks fixture scan failed: ' + result.stderr)
    findings = json.loads(report.read_text())
    return {(Path(entry['File']).relative_to(root).as_posix() if Path(entry['File']).is_absolute()
             else Path(entry['File']).as_posix(), entry['StartLine'], entry['RuleID'])
            for entry in findings}


def check(binary, config, baseline=None):
    with tempfile.TemporaryDirectory(prefix='stella-secret-rules-') as directory:
        temporary = Path(directory)
        fixture = temporary / 'fixture'
        fixture.mkdir()
        expected, allowed = {}, {}
        for name, relative, content, rule in fixture_cases():
            path = fixture / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            line = len(path.read_text().splitlines()) + 1 if path.exists() else 1
            with path.open('a') as target:
                target.write(content + '\n')
            (allowed if rule is None else expected)[(relative, line)] = (name, rule)
        findings = scan(binary, config, fixture, temporary / 'candidate.json')
        for (relative, line), (name, rule) in expected.items():
            if (relative, line, rule) not in findings:
                raise AssertionError('Required detection missing: ' + name)
        for relative, line, rule in findings:
            if (relative, line) not in expected:
                raise AssertionError('Public nonce/hash fixture was flagged: ' + str((relative, line, rule)))
        if baseline:
            prior = scan(binary, baseline, fixture, temporary / 'baseline.json')
            old_flagged = {key for key in allowed if any(p == key[0] and n == key[1] for p, n, _ in prior)}
            if old_flagged != set(allowed):
                raise AssertionError('Baseline did not reproduce all nonce/hash false positives')
        summary = {'accepted_public_metadata_cases': len(allowed),
                   'retained_secret_detection_cases': len(expected),
                   'default_provider_rule': 'github-pat',
                   'baseline_reproduced': bool(baseline)}
        print(json.dumps(summary, sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('gitleaks', type=Path)
    parser.add_argument('--config', type=Path, default=Path('.gitleaks.toml'))
    parser.add_argument('--baseline-config', type=Path)
    arguments = parser.parse_args()
    check(arguments.gitleaks.resolve(), arguments.config.resolve(),
          arguments.baseline_config.resolve() if arguments.baseline_config else None)
