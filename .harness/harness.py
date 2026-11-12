#!/usr/bin/env python3
"""Deterministic workflow gates for Python 3.10+ and supported desktop hosts."""
import argparse
import errno
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid
from contextlib import contextmanager
from functools import partial

if __name__ == "__main__":
    sys.modules["harness"] = sys.modules[__name__]
    sys.dont_write_bytecode = True

VERSION = "0.17.0"
PHASES = ("discovery", "requirements", "design", "implementation", "review", "done")
DEFAULT_BINDINGS = {"orchestrator": "poteto-mode", "requirements": "grill-me", "design": "ponytail",
                    "review": "ponytail-review", "ui_design": "semantic-ui-design",
                    "ui_implementation": "ui-implementation-harness", "response": "evidence-first-response",
                    "general": "ponytail", "writing": "unslop", "technical_writing": "technical-writing",
                    "implementation": "implementation-planning", "code_review": "quality-review",
                    "impact": "blast-radius", "comments": "no-comments", "architecture": "architect",
                    "performance": "benchmark-checklist", "measurement": "principle-explain-the-number",
                    "typescript": "typescript-best-practices", "verification_create": "create-verification-skill",
                    "verification_maintain": "maintain-verification-skill", "context": "recall",
                    "context_guard": "principle-guard-the-context-window", "decision_trail": "show-me-your-work",
                    "correction": "correct", "encode_lessons": "principle-encode-lessons-in-structure",
                    "root_cause": "principle-fix-root-causes", "design_options": "arena",
                    "adversarial": "interrogate", "parallel": "swarm", "planning": "figure-it-out",
                    "how": "how", "why": "why", "teach": "teach", "sharpen": "sharpen",
                    "recap": "ketchup", "personalize": "automate-me", "reflect": "reflect", "bot_ui": "make-bot-ui"}
ALWAYS_ROLES = ("response", "orchestrator", "general", "writing", "technical_writing")
ACTIVITY_ROLES = {
    "code": ("implementation",), "review": ("review", "code_review", "impact", "comments"),
    "ui": ("ui_design", "ui_implementation"), "ux": ("ui_design", "ui_implementation"),
    "architecture": ("architecture",), "performance": ("performance", "measurement"),
    "typescript": ("typescript",), "impact": ("impact",), "verification": ("verification_create",),
    "verification-maintenance": ("verification_maintain",), "context": ("context", "context_guard"),
    "long-running": ("decision_trail", "context_guard"),
    "correction": ("correction", "encode_lessons", "root_cause"),
    "docs": ("writing", "technical_writing"), "design-options": ("design_options",),
    "adversarial": ("adversarial",), "parallel": ("parallel",), "planning": ("planning",),
    "how": ("how",), "why": ("why",), "teach": ("teach",), "sharpen": ("sharpen",),
    "recap": ("recap",), "personalize": ("personalize",), "reflect": ("reflect",), "bot-ui": ("bot_ui",)}
ID = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}\Z")


from common import (GateError, require, nonempty, sequence, strings, sha, file_sha, digest,
                    read_json, write_json, safe_path, now, SKIP_DIRS, execute_check)
import common
import structure
import quality_history
import execution
from ui_rules import UIContract, WorkflowHooks


@contextmanager
def exclusive(root):
    with (root / ".harness/runtime.lock").open("a+b") as stream:
        try:
            common.lock_file(stream, True)
        except OSError as exc:
            if exc.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                raise
            raise GateError("別の工程操作が実行中です") from exc
        try:
            yield
        finally:
            common.lock_file(stream, False)


def config(root):
    value = read_json(root / ".harness/project.json")
    require(value.get("schema_version") == 1, "project.json: schema_versionは1が必要です")
    common.validate_checks(value.get("checks"))
    common.validate_checks(value.get('inspection_checks', []))
    strings(value.get("snapshot_ignore", []), "snapshot_ignore")
    strings(value.get("verification_inputs", []), "verification_inputs")
    structure.validate_settings(root, value)
    if "autonomy" in value:
        autonomy(value["autonomy"])
    if "ui" in value:
        ui_gate().settings(root, value)
    return value


def autonomy(value):
    require(isinstance(value, dict), "autonomyはオブジェクトです")
    require(value.get("completion") in ("review", "pr", "merged"), "autonomy.completionはreview/pr/mergedです")
    prefix = value.get("branch_prefix")
    require(isinstance(prefix, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9/_-]*/", prefix) and
            "//" not in prefix, "autonomy.branch_prefixにはai/などの接頭辞が必要です")
    base = value.get("base_branch")
    require(isinstance(base, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9/_.-]*", base) and
            ".." not in base and "//" not in base, "autonomy.base_branchが不正です")
    return value


def personal_profile(path=None):
    value = read_json(Path(path)) if path is not None else {
        "schema_version": 1, "model": "inherit-parent", "principles": [],
        "autonomy": {"completion": "review", "branch_prefix": "ai/", "base_branch": "default"}}
    require(value.get("schema_version") == 1, "個人プロファイルのschema_versionは1が必要です")
    require(value.get("model") == "inherit-parent", "初版のmodelはinherit-parentです")
    strings(value.get("principles"), "principles")
    autonomy(value.get("autonomy"))
    return value


def integrity(root):
    lock = read_json(root / ".harness/framework.lock.json")
    require(lock.get("version") == VERSION, f"ランタイムと固定版が異なります（runtime={VERSION}）")
    files = lock.get("files")
    require(isinstance(files, dict) and files, "固定版のファイル一覧がありません")
    require(digest(files) == lock.get("bundle_digest"), "固定版の指紋が不整合です")
    for relative, expected in files.items():
        path = safe_path(root, relative)
        require(path.is_file() and file_sha(path) == expected, f"共通ファイルが変更されています: {relative}")
    agents = safe_path(root, lock["agents_path"])
    require(agents.is_file() and lock["agents_block"] in agents.read_text(encoding="utf-8"),
            "AGENTSの共通指示ブロックが変更・削除されています")


def project_entries(root):
    return common.project_entries(root, config(root))

def project_fingerprint(root):
    return digest(project_entries(root))


def source_delta(root, current):
    before = current.get("baseline_files")
    require(isinstance(before, dict), "変更開始時のファイル記録がありません")
    after = project_entries(root)
    framework = read_json(root / ".harness/framework.lock.json")
    managed = set(framework["files"]) | {framework["agents_path"]}
    return sorted(p for p in set(before) | set(after)
                  if not p.startswith(".harness/") and p not in managed and before.get(p) != after.get(p))


def change_dir(root, identifier):
    require(bool(ID.fullmatch(identifier)), "変更IDは英数字・ハイフン・アンダースコア（最大80文字）です")
    return safe_path(root, f".harness/changes/{identifier}")


def state(root, identifier, *, _allow_ui_repin=False):
    value = read_json(change_dir(root, identifier) / "state.json")
    require(value.get("schema_version") == 1 and value.get("id") == identifier and
            value.get("phase") in PHASES and value.get("kind") in ("new", "change"), "工程状態が不正です")
    nonempty(value.get("author"), "author")
    nonempty(value.get("context"), "context")
    require(isinstance(value.get("approvals"), dict), "工程の完了記録が不正です")
    require("intent_contract" not in value or
            (type(value["intent_contract"]) is int and value["intent_contract"] == 1),
            "未対応のintent_contractです")
    require('execution_contract' not in value or type(value['execution_contract']) is int and
            value['execution_contract'] == 1, '未対応のexecution_contractです')
    if value.get("ui_policy") is not None and not _allow_ui_repin:
        require(ui_gate().policy_snapshot(config(root)) == value["ui_policy"],
                "変更開始時に固定したUI policy・check設定が変更されています")
    return value


def artifact(root, identifier, phase):
    return read_json(change_dir(root, identifier) / f"{phase}.json")


def artifact_hash(root, identifier, phase):
    return sha((change_dir(root, identifier) / f"{phase}.json").read_bytes())


def fingerprints(root, identifier):
    values = {p: artifact_hash(root, identifier, p) for p in PHASES[:4]}
    return {"project_digest": project_fingerprint(root), "artifacts_digest": digest(values)}


def request_ids(root, identifier):
    return [item["id"] for item in artifact(root, identifier, "requirements")["requirements"]]


def validate_intent(root, identifier, phase, item):
    """Check recorded coverage, not the semantic truth of an agent's judgment."""
    if phase == "discovery":
        nonempty(item.get("request"), "discovery.request（元の指示）")
    elif phase == "requirements":
        original = artifact(root, identifier, "discovery")["request"]
        sources, binding = set(), set()
        quoted_positions = set()
        for source in sequence(item.get("request_items"), "requirements.request_items", 1):
            require(isinstance(source, dict), "request_itemsの各要素はオブジェクトです")
            name = nonempty(source.get("id"), "request_item.id")
            require(bool(ID.fullmatch(name)) and name not in sources, f"原指示IDが不正・重複: {name}")
            sources.add(name)
            quote = nonempty(source.get("text"), f"{name}.text")
            require(quote in original, f"{name}: 原指示にない引用です")
            if state(root, identifier).get('execution_contract'):
                span = source.get('span')
                require(isinstance(span, dict) and type(span.get('start')) is int and
                        type(span.get('end')) is int and 0 <= span['start'] < span['end'] <= len(original) and
                        original[span['start']:span['end']] == quote, f'{name}: 原指示の引用範囲spanが不正です')
                quoted_positions.update(range(span['start'], span['end']))
            require(source.get("kind") in ("purpose", "problem", "requirement", "constraint", "means", "example", "hypothesis"),
                    f"{name}: 原指示のkindが不正です")
            require(type(source.get("binding")) is bool, f"{name}.bindingは真偽値です")
            require(source["binding"] or source["kind"] not in ("requirement", "constraint"),
                    f"{name}: 確定要求・制約はbindingが必要です")
            if source["binding"]:
                binding.add(name)
        if state(root, identifier).get('execution_contract'):
            require(all(index in quoted_positions for index, char in enumerate(original) if not char.isspace()),
                    '原指示の引用範囲に漏れがあります。非確定の前提・例示も分類してください')
        require(binding, "確定した目的・要求・制約への対応が必要です")
        covered = set()
        for requirement in item["requirements"]:
            refs = strings(requirement.get("sources"), f"{requirement['id']}.sources", 1)
            require(len(refs) == len(set(refs)) and set(refs) <= sources,
                    f"{requirement['id']}: 原指示参照が不正・重複です")
            require(set(refs) & binding, f"{requirement['id']}: 仮説だけを確定要求にできません")
            covered.update(refs)
        require(binding <= covered, "確定した原指示の要件対応が不足しています")
    elif phase == "review":
        review = item.get("intent_review")
        require(isinstance(review, dict), "review.intent_reviewが必要です")
        for key in ("purpose", "minimality"):
            entry = review.get(key)
            require(isinstance(entry, dict), f"intent_review.{key}が必要です")
            require(entry.get("status") == "passed", f"intent_review.{key}は未達・未検証です")
            nonempty(entry.get("evidence"), f"intent_review.{key}.evidence")
        expected = {s["id"] for s in artifact(root, identifier, "requirements")["request_items"]}
        checked = set()
        for entry in sequence(review.get("sources"), "intent_review.sources", 1):
            require(isinstance(entry, dict), "intent_review.sourcesの各要素はオブジェクトです")
            name = nonempty(entry.get("source"), "intent_review.source")
            require(name in expected and name not in checked, f"レビュー原指示参照が不正・重複: {name}")
            checked.add(name)
            require(entry.get("status") == "passed", f"{name}: 原指示は未達・未検証です")
            nonempty(entry.get("evidence"), f"{name}.evidence")
        require(checked == expected, "レビューが元の指示を全て照合していません")


def validate_phase(root, identifier, phase, current, portable=False):
    item = artifact(root, identifier, phase)
    enabled = current.get("structural_quality")
    require(enabled == config(root).get("structural_quality"), "構造検査設定が開始時から変更されています")
    if enabled:
        structure.validate_contract(root, phase, item, current["baseline_files"])
        validate_baseline(root, identifier)
    if enabled and enabled.get("cumulative") and phase == "design":
        quality_history.validate_design(root, quality_history.load_policy(root, config(root)), item,
            set(request_ids(root, identifier)), {entry["id"] for entry in config(root)["checks"]})
    if phase == "discovery":
        nonempty(item.get("goal"), "discovery.goal")
        nonempty(item.get("current_behavior"), "discovery.current_behavior")
        strings(item.get("constraints"), "discovery.constraints")
        strings(item.get("evidence"), "discovery.evidence", int(current["kind"] == "change"))
        require(sequence(item.get("open_questions"), "discovery.open_questions") == [], "調査に未解決の質問があります")
    elif phase == "requirements":
        ids = set()
        for requirement in sequence(item.get("requirements"), "requirements", 1):
            require(isinstance(requirement, dict), "各要件はオブジェクトです")
            name = nonempty(requirement.get("id"), "requirement.id")
            require(bool(ID.fullmatch(name)) and name not in ids, f"要件IDが不正・重複: {name}")
            ids.add(name)
            nonempty(requirement.get("description"), f"{name}.description")
            strings(requirement.get("acceptance"), f"{name}.acceptance", 1)
        strings(item.get("out_of_scope"), "out_of_scope")
        strings(item.get("assumptions"), "assumptions")
    elif phase == "design":
        nonempty(item.get("approach"), "design.approach")
        strings(item.get("decisions"), "design.decisions")
        nonempty(item.get("rollback"), "design.rollback")
        impact = strings(item.get("impact_paths"), "design.impact_paths", 1)
        for path in impact:
            require(Path(path).parts and Path(path).parts[0] != ".harness", "成果物自身を実装影響範囲に指定できません")
            safe_path(root, path)
        registered = {c["id"] for c in config(root)["checks"]}
        covered = set()
        for entry in sequence(item.get("traceability"), "design.traceability", 1):
            require(isinstance(entry, dict), "traceabilityの各要素はオブジェクトです")
            name = entry.get("requirement")
            require(name in request_ids(root, identifier) and name not in covered, f"要件参照が不正・重複: {name}")
            covered.add(name)
            for path in strings(entry.get("paths"), "traceability.paths", 1):
                safe_path(root, path)
                require(path in impact, f"要件の変更パスが影響範囲にありません: {path}")
            require(set(strings(entry.get("checks"), "traceability.checks", 1)) <= registered,
                    f"{name}: 未登録の検証コマンドです")
        require(covered == set(request_ids(root, identifier)), "設計が全要件をカバーしていません")
    elif phase == "implementation":
        nonempty(item.get("summary"), "implementation.summary")
        require(item.get("author") == current["author"], "実装者が工程の作業者と一致しません")
        impact = artifact(root, identifier, "design")["impact_paths"]
        declared = strings(item.get("changed_paths"), "implementation.changed_paths", 1)
        deleted = strings(item.get("deleted_paths", []), "implementation.deleted_paths")
        for path in deleted:
            require(path in declared and path in current["baseline_files"] and not safe_path(root, path).exists(),
                    f"削除パスが変更開始時のファイルと一致しません: {path}")
        require(set(source_delta(root, current)) <= set(declared), "実際の変更パスがimplementation.changed_pathsに記録されていません")
        if enabled and any(path.endswith(".py") and path not in current["baseline_files"] for path in declared):
            strings(artifact(root, identifier, "design").get("new_module_reasons"), "新規Pythonモジュールの設計理由", 1)
        for path in declared:
            safe_path(root, path)
            require(any(path == base or path.startswith(base.rstrip("/") + "/") for base in impact),
                    f"設計の影響範囲外です: {path}")
            # A missing path is valid for a planned deletion; require an explicit explanation.
            require((root / path).exists() or path in deleted, f"変更パスが存在しません: {path}")
        strings(item.get("limitations"), "implementation.limitations")
        validate_receipt(root, identifier, portable=portable)
    elif phase == "review":
        reviewer = nonempty(item.get("reviewer"), "review.reviewer")
        context = nonempty(item.get("context"), "review.context")
        require(reviewer.strip().casefold() != current["author"].strip().casefold(), "独立したレビュアーが必要です")
        require(context != current["context"], "実装と異なるレビューコンテキストが必要です")
        nonempty(item.get("summary"), "review.summary")
        require(item.get("decision") == "passed", "レビューはpassedではありません")
        reviewed = strings(item.get("checked_requirements"), "review.checked_requirements", 1)
        require(len(reviewed) == len(set(reviewed)) and set(reviewed) == set(request_ids(root, identifier)),
                "レビューが全要件を確認していません")
        for finding in sequence(item.get("findings"), "review.findings"):
            require(isinstance(finding, dict), "レビュー指摘はオブジェクトです")
            nonempty(finding.get("description"), "finding.description")
            severity = finding.get("severity")
            require(severity in ("blocker", "major", "minor"), "指摘のseverityが不正です")
            require(finding.get("status") == "resolved" or
                    (severity == "minor" and finding.get("status") == "accepted"), "未解決のレビュー指摘があります")
            nonempty(finding.get("resolution"), "finding.resolution")
        strings(item.get("limitations"), "review.limitations")
        for key, value in fingerprints(root, identifier).items():
            require(item.get(key) == value, "コード・成果物がレビュー時点から変わっています。再レビューしてください")
        if enabled and enabled.get("cumulative", {}).get("mode") == "enforce":
            receipt = read_json(change_dir(root, identifier) / "evidence/latest.json")
            completed = {entry["id"] for entry in receipt["results"]} - set(enabled["required_checks"])
            for entry in receipt["results"]:
                if entry["id"] in enabled["required_checks"]:
                    assessment = read_json(safe_path(root, entry["log"]))["cumulative"]
                    quality_history.validate_review(root, assessment, item.get("cumulative_review"), completed)

    if current.get("intent_contract") == 1:
        validate_intent(root, identifier, phase, item)
    if "ui" in config(root):
        ui_gate().validate_phase(root, identifier, phase, current, item, portable=portable)


def validate_receipt(root, identifier, portable=False, receipt=None):
    if receipt is None:
        receipt = read_json(change_dir(root, identifier) / "evidence/latest.json")
    require(receipt.get("schema_version") == 1 and receipt.get("success") is True, "検証が未実行、失敗、またはタイムアウトです")
    for key, value in fingerprints(root, identifier).items():
        require(receipt.get(key) == value, "古い検証証跡です。runで再実行してください")
    checks = config(root)["checks"]
    require(receipt.get("checks_digest") == digest(checks), "検証コマンドが変更されています")
    observed = receipt.get("results")
    require(isinstance(observed, list) and len(observed) == len(checks), "全検証の証跡がありません")
    for expected, result in zip(checks, observed):
        require(isinstance(result, dict) and result.get("id") == expected["id"] and
                result.get("argv") == expected["argv"] and result.get("returncode") == 0 and
                result.get("timed_out") is False, f"検証証跡が不正です: {expected['id']}")
        log = safe_path(root, result.get("log"))
        require(log.is_file() and sha(log.read_bytes()) == result.get("log_digest"), "検証ログが変更・削除されています")
    if state(root, identifier).get("structural_quality"):
        require(receipt.get("base_sha") == state(root, identifier).get("base_sha"), "検証の基準SHAが不一致です")
        validate_structural_results(root, identifier, receipt, portable=portable)
    if "ui" in config(root):
        ui_gate().validate_receipt(root, identifier, receipt)


def validate_structural_results(root, identifier, receipt, portable=False):
    policy = config(root)["structural_quality"]
    before = validate_baseline(root, identifier)
    for name in policy["required_checks"]:
        matches = [r for r in receipt["results"] if r["id"] == name]
        require(len(matches) == 1, "必須構造検査の証跡がありません")
        report = read_json(safe_path(root, matches[0]["log"]))
        require(report.get("ok") is True and report.get("project_digest") == receipt["project_digest"],
                "構造検査の対象・結果が一致しません")
        require(report.get("policy_digest") == before.get("policy_digest"), "構造検査の条件がbaselineと一致しません")
        require(report.get("ci_base_sha") == receipt.get("ci_base_sha"), "構造検査のCI基準が一致しません")
        if not portable:
            require(report.get("provenance") == structure.toolchain(root), "ツール・実行環境が検証時から変わっています")
        require(policy["mode"] == "observe" or (report["new_clones"] == 0 and not report["new_cycles"] and
                not report["new_boundary_violations"]), "新しい構造違反が残っています")
        if policy.get("cumulative"):
            assessment = report.get("cumulative")
            require(isinstance(assessment, dict) and before.get("cumulative", {}).get("policy_digest") == assessment.get("policy_digest"),
                    "累積品質基準が開始時から変わっています")
            require(assessment.get("analysis_digest") == structure.analysis_contract(root, config(root)), "累積解析契約が一致しません")
            quality_history.validate_assessment(root, config(root), assessment, state(root, identifier)["base_sha"])
            declared = {entry["id"] for entry in artifact(root, identifier, "design")["responsibility_changes"]}
            require(set(assessment["history"]["changed_responsibilities"]) <= declared, "実際の変更責務が設計にありません")


def git_head(root):
    probe = subprocess.run(["git", "rev-parse", "--verify", "HEAD"], cwd=root, capture_output=True, text=True, encoding="utf-8")
    return probe.stdout.strip() if probe.returncode == 0 else None


def select_change(root, base):
    require(isinstance(base, str) and re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", base), "CIの固定基準SHAが必要です")
    result = subprocess.run(["git", "diff", "--name-only", "-z", "--diff-filter=AM", base, "--", ".harness/changes"],
                            cwd=root, capture_output=True, text=True, encoding="utf-8")
    require(result.returncode == 0, "CIの基準コミットを取得できません")
    identifiers = set()
    for relative in result.stdout.split("\0"):
        parts = Path(relative).parts
        if len(parts) == 4 and parts[:2] == (".harness", "changes") and parts[3] == "review.json":
            require(bool(ID.fullmatch(parts[2])), "CIの変更IDが不正です")
            identifiers.add(parts[2])
    require(len(identifiers) == 1, "現在のレビュー成果物を持つ変更IDが1件必要です（0件・複数件は不可）")
    return identifiers.pop()


def verification_env(root, identifier, ci_base=None):
    env = {key: value for key, value in os.environ.items() if not key.startswith("HARNESS_")}
    env.update(HARNESS_PROJECT=str(root), HARNESS_CHANGE_ID=identifier)
    if ci_base:
        env["HARNESS_CI_BASE"] = ci_base
    discovery = artifact(root, identifier, "discovery")
    if "structure_baseline" in discovery:
        env["HARNESS_BASELINE_LOG"] = str(safe_path(root, discovery["structure_baseline"]["log"]))
    return env


def validate_recorded_phases(root, identifier, current, portable=False, include_current=True):
    end = min(PHASES.index(current["phase"]) + int(include_current), 5)
    for phase in PHASES[:end]:
        if phase != current["phase"]:
            require(current["approvals"].get(phase) == artifact_hash(root, identifier, phase),
                    f"完了済みの{phase}が変更されています。reopenで戻してください")
        validate_phase(root, identifier, phase, current, portable=portable)


def check(root, identifier, portable=False, *, _execution=True):
    integrity(root)
    config(root)
    current = state(root, identifier)
    validate_recorded_phases(root, identifier, current, portable=portable)
    if _execution and current.get('execution_contract') and current['phase'] == 'done':
        validate_execution_completion(root, identifier, current)
    result = {"id": identifier, "phase": current["phase"], "valid": True}
    cumulative = (current.get("structural_quality") or {}).get("cumulative")
    if cumulative and current["phase"] in ("implementation", "review", "done"):
        receipt = read_json(change_dir(root, identifier) / "evidence/latest.json")
        reports = [read_json(safe_path(root, entry["log"]))["cumulative"] for entry in receipt["results"]
                   if entry["id"] in current["structural_quality"]["required_checks"]]
        status = max((entry["status"] for entry in reports), key=("PASS", "REVIEW_REQUIRED", "BLOCK").index)
        if cumulative["mode"] == "enforce" and current["phase"] == "done":
            status = "PASS"
        result.update(quality_status=status, quality_enforced=cumulative["mode"] == "enforce",
                      completion_allowed=current["phase"] == "done")
    return result


def record(root, identifier, event, **fields):
    path = change_dir(root, identifier) / "events.jsonl"
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"time": now(), "event": event, **fields}, ensure_ascii=False) + "\n")


def template(phase, author=""):
    return {
        "discovery": {"request": "", "goal": "", "current_behavior": "", "constraints": [], "evidence": [], "open_questions": []},
        "requirements": {"request_items": [{"id": "SRC-001", "text": "", "kind": "requirement", "binding": True}],
                         "requirements": [{"id": "REQ-001", "description": "", "acceptance": [""], "sources": ["SRC-001"]}],
                         "out_of_scope": [], "assumptions": []},
        "design": {"approach": "", "decisions": [], "impact_paths": [], "rollback": "", "traceability": []},
        "implementation": {"summary": "", "author": author, "changed_paths": [], "deleted_paths": [], "limitations": []},
        "review": {"reviewer": "", "context": "", "decision": "pending", "summary": "", "checked_requirements": [],
                   "findings": [], "limitations": [], "project_digest": "", "artifacts_digest": "",
                   "intent_review": {"purpose": {"status": "unverified", "evidence": ""},
                                     "sources": [], "minimality": {"status": "unverified", "evidence": ""}}},
    }[phase]


def new(root, identifier, kind, author, context, base=None, ui=False, *, execution_contract=True, request=None):
    integrity(root)
    settings = config(root)
    require(type(execution_contract) is bool, 'execution_contractは真偽値です')
    if request is not None:
        nonempty(request, '元の依頼')
    if ui:
        policy = settings.get("ui") or {}
        require(policy.get("schema_version") == 3 and policy.get("mode") == "enforce",
                "新規UI作業はUI v3/enforceを接続してからnew --uiで開始してください")
        if execution_contract:
            require(policy.get('copy_policy') == 'object-first',
                    '新規UI作業にはcopy_policy=object-firstが必要です')
        ui_gate().validate_registry(root, read_json(safe_path(root, policy.get("registry"))), allow_empty=kind == "new")
    nonempty(author, "author")
    nonempty(context, "context")
    directory = change_dir(root, identifier)
    execution._path(root, directory.relative_to(root).as_posix())
    if directory.exists():
        require(directory.is_dir() and all(path.name == 'inputs' and path.is_dir() for path in directory.iterdir()),
                f'変更IDは使用済みです: {identifier}')
        for path in directory.rglob('*'):
            execution._path(root, path.relative_to(root).as_posix())
    base_sha = None
    probe = subprocess.run(["git", "rev-parse", "--verify", "HEAD"], cwd=root, capture_output=True, text=True, encoding="utf-8")
    if base is not None or (settings.get("structural_quality") and probe.returncode == 0):
        nonempty(base, "構造検査の基準 --base")
        resolved = subprocess.run(["git", "rev-parse", "--verify", "--end-of-options", f"{base}^{{commit}}"],
                                  cwd=root, capture_output=True, text=True, encoding="utf-8")
        require(resolved.returncode == 0, "Gitの基準コミットを取得できません")
        base_sha = resolved.stdout.strip()
    directory.mkdir(parents=True, exist_ok=True)
    value = {"schema_version": 1, "id": identifier, "kind": kind,
               "author": author, "context": context, "phase": "discovery", "approvals": {}, "intent_contract": 1,
               "baseline_files": project_entries(root), "base_sha": base_sha,
               "structural_quality": settings.get("structural_quality"),
               "ui_policy": ui_gate().policy_snapshot(settings), "ui_required": ui}
    if execution_contract:
        value['execution_contract'] = 1
    write_json(directory / "state.json", value)
    discovery = template('discovery')
    if request is not None:
        discovery['request'] = nonempty(request, '元の依頼')
    write_json(directory / "discovery.json", discovery)
    record(root, identifier, "created", kind=kind, author=author, context=context)
    return {"id": identifier, "phase": "discovery", "artifact": str(directory / "discovery.json")}


def guide(root, identifier=None, ui=False, activities=(), turn=None, *, _execution=True):
    """Derive the next handoff from real gates without advancing or editing work."""
    integrity(root)
    settings = config(root)
    require(isinstance(activities, (list, tuple)) and all(isinstance(item, str) for item in activities),
            "activitiesは作業種別の配列です")
    selected = set(activities)
    require(selected <= ACTIVITY_ROLES.keys(), "未対応のactivityです")
    changes = [state(root, p.parent.name, _allow_ui_repin=True)
               for p in sorted((root / ".harness/changes").glob("*/state.json"))]
    active = [item for item in changes if item["phase"] != "done"]
    current = state(root, identifier, _allow_ui_repin=True) if identifier else (active[0] if len(active) == 1 else None)
    phase = current["phase"] if current else None
    selection = not identifier and len(active) > 1
    result = {"supported": True, "workflow_status": "selection_required" if selection else "done" if phase == "done" else "active" if current else "not_started",
              "id": current["id"] if current else None, "phase": phase,
              "changes": [{"id": item["id"], "phase": item["phase"]} for item in changes],
              "artifact": str(change_dir(root, current["id"]) / f"{phase}.json") if current and phase != "done" else None,
              "can_edit_product": False, "work_complete": False, "required_skills": {}, "blockers": []}
    paths = [root / '.harness/project.json']
    if current:
        directory = change_dir(root, current['id'])
        paths.extend(path for path in [directory / 'state.json',
                     *(directory / f'{name}.json' for name in PHASES[:-1])] if path.is_file())
    result['continuity'] = {
        'trigger': 'each_user_message_or_resume',
        'instruction_path': str(root / '.harness/protocol.md'),
        'context_paths': [str(path) for path in paths],
        'discovery_digest': artifact_hash(root, current['id'], 'discovery')
            if current and (change_dir(root, current['id']) / 'discovery.json').is_file() else None}
    if selection:
        result["blockers"].append("複数の進行中の変更があります。guide <変更ID>で対象を選んでください")
    if phase in ("design", "implementation"):
        selected.add("code")
    if phase in ("review", "done"):
        selected.add("review")
    paths = []
    if current:
        design_path = change_dir(root, current['id'])/'design.json'
        if design_path.is_file():
            planned = artifact(root, current['id'], 'design').get('impact_paths', [])
            if isinstance(planned, list):
                paths.extend(path for path in planned if isinstance(path, str))
        paths.extend(source_delta(root, current))
    extensions = {Path(path).suffix.lower() for path in paths}
    if extensions & {'.ts', '.tsx'}:
        selected.add('typescript')
    if extensions & {'.html', '.htm', '.css', '.scss', '.sass', '.less', '.jsx', '.tsx', '.vue', '.svelte'}:
        selected.add('ui')
    wants_ui = bool(ui or selected & {"ui", "ux"} or (current and current.get("ui_required")))
    if current and (change_dir(root, current["id"]) / "design.json").is_file():
        design_ui = artifact(root, current["id"], "design").get("ui")
        wants_ui = wants_ui or bool(design_ui and design_ui.get("scope") != "none")
    policy = settings.get("ui") or {}
    needs_v3 = current is None or "ui_required" in current
    supported_mode = policy.get("mode") == "enforce" if needs_v3 else policy.get("mode") in ("observe", "enforce")
    connected = supported_mode and bool(policy.get("check_ids")) and (
        not needs_v3 or policy.get("schema_version") == 3)
    if current is None or current.get('execution_contract'):
        connected = connected and policy.get('copy_policy') == 'object-first'
    if connected and wants_ui:
        try:
            ui_gate().validate_registry(root, read_json(safe_path(root, policy.get("registry"))),
                                        allow_empty=current is None or current["kind"] == "new")
        except (GateError, OSError, KeyError, TypeError, ValueError) as exc:
            connected = False
            result["blockers"].append(str(exc))
    result["ui_contract_connected"] = connected
    result["ui_validation_mode"] = policy.get("mode")
    result["ui_enforced"] = connected and policy.get("mode") == "enforce"
    if wants_ui and not connected:
        result["blockers"].append("UI契約が未接続です。実Registry・checkとUI v3/enforceを準備してください")
    if wants_ui and current and current.get('execution_contract') and not current.get('ui_required'):
        result['blockers'].append('UI対象を検出しました。reopen <id> discovery --uiで契約を固定してください')
    role = "review" if phase is None and "review" in selected else "requirements" if phase in (None, "discovery", "requirements") else "design" if phase in ("design", "implementation") else "review"
    roles = [*ALWAYS_ROLES, role, *[role for name in sorted(selected) for role in ACTIVITY_ROLES[name]],
             *(["ui_design", "ui_implementation"] if wants_ui else [])]
    result["activities"] = sorted(selected | ({"ui"} if wants_ui else set()))
    configured = settings.get("skill_bindings", {})
    require(isinstance(configured, dict), "skill_bindingsはオブジェクトが必要です")
    bindings = {**DEFAULT_BINDINGS, **configured}
    assignments = {role: bindings.get(role) for role in dict.fromkeys(roles)}
    fixed = set(ALWAYS_ROLES)
    fixed.update(role for name in selected for role in ACTIVITY_ROLES[name])
    if wants_ui:
        fixed.update(('ui_design', 'ui_implementation'))
    for role in sorted(fixed):
        if assignments.get(role) != DEFAULT_BINDINGS[role]:
            prefix = 'always' if role in ALWAYS_ROLES else 'required'
            assignments[f'{prefix}_{role}'] = DEFAULT_BINDINGS[role]
    for role, name in assignments.items():
        if not isinstance(name, str) or not name.strip():
            result["blockers"].append(f"担当Skillの割当がありません: {role}")
            continue
        path = safe_path(root, f".agents/skills/{name}/SKILL.md")
        if not path.is_relative_to(root / ".agents/skills") or not path.is_file():
            result["blockers"].append(f"担当Skillを参照できません: {role}={name}")
        else:
            result["required_skills"][role] = str(path)
    if current:
        try:
            state(root, current['id'])
            validate_recorded_phases(root, current["id"], current, include_current=False)
        except (GateError, OSError, KeyError, TypeError, ValueError) as exc:
            result["blockers"].append(str(exc))
        try:
            check(root, current["id"], _execution=False)
            result["work_complete"] = phase == "done" and not result["blockers"]
        except (GateError, OSError, KeyError, TypeError, ValueError) as exc:
            result["phase_gate_error"] = str(exc)
            if phase == "done":
                result["blockers"].append(str(exc))
        result["can_edit_product"] = phase == "implementation" and not result["blockers"]
        if result["can_edit_product"]:
            result["impact_paths"] = artifact(root, current["id"], "design")["impact_paths"]
    if selection:
        result["candidates"] = {item["id"]: guide(root, item["id"], ui=ui, activities=activities,
                                                  turn=turn, _execution=_execution) for item in active}
    if _execution and current and current.get('execution_contract'):
        result['historical_work_complete'] = result['work_complete']
        if phase == 'done' and turn and turn == current.get('execution_completion', {}).get('token'):
            try:
                result['execution'] = validate_execution_completion(root, current['id'], current)
            except (GateError, OSError, KeyError, TypeError, ValueError) as exc:
                result['execution'] = {'ready': False, 'valid': False, 'blockers': [str(exc)]}
            result['work_complete'] = result['work_complete'] and result['execution'].get('completion_usable', False)
        else:
            result['execution'] = execution.status(root, turn, result)
            result['can_edit_product'] = result['can_edit_product'] and result['execution']['ready']
            if result['can_edit_product'] and result['execution'].get('context') != current['context']:
                result['can_edit_product'] = False
                result['blockers'].append('実装担当の実行コンテキストが一致しません')
            result['work_complete'] = False
            result['blockers'].extend(result['execution']['blockers'])
    return result


def require_execution(root, identifier, turn, activities=()):
    current = state(root, identifier)
    if not current.get('execution_contract'):
        return None
    require(isinstance(turn, str) and re.fullmatch(r'[a-f0-9]{32}', turn), '現在の実行turnが必要です')
    saved = read_json(safe_path(root, f'{execution.STORE}/{turn}.json'))
    selected = saved.get('binding', {}).get('activities', activities)
    guidance = guide(root, identifier, activities=selected, _execution=False)
    status = execution.status(root, turn, guidance)
    require(status['ready'], '実行契約が未成立です: ' + '; '.join(status['blockers']))
    if current['phase'] == 'review':
        require(status['context'] == artifact(root, identifier, 'review').get('context') and
                status['context'] != current['context'], '独立レビューの実読出し・適用コンテキストが一致しません')
    else:
        require(status['context'] == current['context'], '実装担当の実行コンテキストが一致しません')
    if current['phase'] in ('design', 'implementation', 'review'):
        common.validate_quality_checks(config(root)['checks'])
    return guidance


def validate_execution_completion(root, identifier, current):
    completed = current.get('execution_completion')
    require(isinstance(completed, dict), '完了時のSkill適用記録がありません')
    token = completed.get('token')
    require(isinstance(token, str) and re.fullmatch(r'[a-f0-9]{32}', token), '完了時の実行tokenが不正です')
    path = safe_path(root, f'{execution.STORE}/{token}.json')
    require(path.is_file() and file_sha(path) == completed.get('sha256'), '完了時の実行記録が変更されています')
    guidance = guide(root, identifier, activities=completed.get('activities', ()), _execution=False)
    guidance['phase'] = 'review'
    result = execution.status(root, token, guidance)
    require(result.get('completion_usable'), '完了時の適用根拠が失効しています: ' + '; '.join(result['blockers']))
    return result


def validate_baseline(root, identifier):
    discovery = artifact(root, identifier, "discovery")
    baseline = discovery.get("structure_baseline")
    require(isinstance(baseline, dict), "baselineが未実行です")
    log = safe_path(root, baseline.get("log"))
    require(log.is_file() and file_sha(log) == baseline.get("log_digest"), "baselineの証跡が変更されています")
    report = read_json(log)
    require(report.get("ok") is True and report.get("project_digest") == digest(state(root, identifier)["baseline_files"]),
            "baselineの対象が開始時の状態と一致しません")
    return report


def baseline(root, identifier):
    integrity(root)
    current = state(root, identifier)
    require(current["phase"] == "discovery" and current.get("structural_quality"), "baselineは構造検査のdiscoveryで実行します")
    require(project_entries(root) == current["baseline_files"], "開始時から変更されています。baselineを取り直せません")
    discovery = artifact(root, identifier, "discovery")
    require("structure_baseline" not in discovery, "baselineは取得済みです")
    directory = change_dir(root, identifier) / "evidence"
    directory.mkdir(exist_ok=True)
    entry = {"id": "baseline", "argv": [sys.executable, ".harness/structure.py", "baseline"]}
    result = execute_check(root, directory, uuid.uuid4().hex, entry, verification_env(root, identifier))
    require(result["returncode"] == 0 and not result["timed_out"], f"baselineの解析に失敗しました: {result['log']}")
    require(project_entries(root) == current["baseline_files"], "baselineの解析中に対象が変更されています")
    discovery["structure_baseline"] = {"log": result["log"], "log_digest": result["log_digest"]}
    write_json(change_dir(root, identifier) / "discovery.json", discovery)
    validate_baseline(root, identifier)
    record(root, identifier, "baseline", **discovery["structure_baseline"])
    return {"id": identifier, "baseline": discovery["structure_baseline"]}


def advance(root, identifier, turn=None):
    current = state(root, identifier)
    require(current["phase"] != "done", "既にdoneです。次の変更をnewで開始してください")
    guidance = require_execution(root, identifier, turn)
    try:
        check(root, identifier)
    except GateError as exc:
        record(root, identifier, "gate_failed", phase=current["phase"], reason=str(exc))
        raise
    old = current["phase"]
    target = PHASES[PHASES.index(old) + 1]
    if guidance is not None:
        finished = execution.finish(root, turn, guidance)
        record(root, identifier, 'skill_application_verified', token=turn, phase=old,
               request_digest=finished['request_digest'])
        if target == 'done':
            current['execution_completion'] = {'token': turn, 'activities': finished['activities'],
                'sha256': file_sha(safe_path(root, f'{execution.STORE}/{turn}.json'))}
    current["approvals"][old] = artifact_hash(root, identifier, old)
    current["phase"] = target
    if target != "done":
        path = change_dir(root, identifier) / f"{target}.json"
        if not path.exists():
            write_json(path, template(target, current["author"]))
    write_json(change_dir(root, identifier) / "state.json", current)
    record(root, identifier, "advanced", previous=old, phase=target, artifact_digest=current["approvals"][old])
    return {"id": identifier, "previous": old, "phase": target}


def reopen(root, identifier, phase, reason, *, ui=False):
    integrity(root)
    nonempty(reason, "reason")
    current = state(root, identifier, _allow_ui_repin=ui and phase == 'discovery')
    require(phase != "done" and PHASES.index(phase) <= PHASES.index(current["phase"]), "現在以前の工程だけに戻れます")
    if ui:
        require(phase == 'discovery', 'UI対象の追加はdiscoveryからやり直します')
        settings = config(root)
        policy = settings.get('ui') or {}
        require(policy.get('schema_version') == 3 and policy.get('mode') == 'enforce' and
                policy.get('copy_policy') == 'object-first', 'UI v3/enforceとobject-firstを先に接続してください')
        ui_gate().validate_registry(root, read_json(safe_path(root, policy.get('registry'))),
                                    allow_empty=current['kind'] == 'new')
        current.update(ui_required=True, ui_policy=ui_gate().policy_snapshot(settings))
    old = current["phase"]
    current["phase"] = phase
    current["approvals"] = {p: h for p, h in current["approvals"].items() if PHASES.index(p) < PHASES.index(phase)}
    write_json(change_dir(root, identifier) / "state.json", current)
    record(root, identifier, "reopened", previous=old, phase=phase, reason=reason)
    return {"id": identifier, "phase": phase}


def inspect(root, identifier, name, turn=None):
    integrity(root)
    current = state(root, identifier)
    require(current['phase'] in ('discovery', 'requirements', 'design'), 'inspectは実装前の観察だけに使います')
    require_execution(root, identifier, turn)
    checks = {entry['id']: entry for entry in config(root).get('inspection_checks', [])}
    require(name in checks, '登録済みのinspection_checksを指定してください')
    before = project_fingerprint(root)
    directory = change_dir(root, identifier)/'evidence'/f'inspection-{uuid.uuid4().hex}'
    directory.mkdir(parents=True)
    result = execute_check(root, directory, uuid.uuid4().hex, checks[name], {
        **os.environ, 'HARNESS_PROJECT': str(root), 'HARNESS_CHANGE_ID': identifier,
        'CODEXENVSET_CHANGE_ID': identifier, 'CODEXENVSET_CHECK_ID': name,
        'CODEXENVSET_EVIDENCE_DIR': str(directory), 'CODEXENVSET_UI_MODE': 'before'})
    result.update(inspection_only=True, source_unchanged=before == project_fingerprint(root),
                  evidence_dir=str(directory), phase=current['phase'])
    write_json(directory/'inspection.json', result)
    require(result['returncode'] == 0 and not result['timed_out'] and result['source_unchanged'],
            '事前観察が失敗またはソースを変更しました。観察の成功にはできません')
    record(root, identifier, 'inspection', check=name, log=result['log'], log_digest=result['log_digest'])
    return result


def run_checks(root, identifier, ci_base=None, turn=None):
    integrity(root)
    current = state(root, identifier)
    require(current["phase"] in ("implementation", "review", "done"), "runはimplementation以降で使います")
    if current['phase'] != 'done':
        require_execution(root, identifier, turn)
    elif current.get('execution_contract'):
        validate_execution_completion(root, identifier, current)
    # Verify the entire upstream contract, but do not require a prior test receipt.
    for phase in PHASES[:3]:
        require(current["approvals"].get(phase) == artifact_hash(root, identifier, phase), f"{phase}が変更されています。reopenが必要です")
        validate_phase(root, identifier, phase, current)
    settings = config(root)
    require(settings["checks"], "検証コマンドが未登録です")
    before = fingerprints(root, identifier)
    directory = change_dir(root, identifier) / "evidence"
    directory.mkdir(exist_ok=True)
    receipt = {"schema_version": 1, "started_at": now(), **before, "checks": settings["checks"], "checks_digest": digest(settings["checks"]),
               "source_changes": source_delta(root, current), "base_sha": current.get("base_sha"),
               "ci_base_sha": ci_base, "provenance": {"python": sys.version, "head_sha": git_head(root)},
               "results": [], "success": False}
    # Invalidate the previous success even if the runner is interrupted.
    write_json(directory / "latest.json", receipt)
    token = uuid.uuid4().hex
    output_directory = directory / token
    output_directory.mkdir()
    for entry in settings["checks"]:
        check_directory = output_directory / entry["id"]
        check_directory.mkdir()
        environment = {**verification_env(root, identifier, ci_base),
                       "CODEXENVSET_CHANGE_ID": identifier, "CODEXENVSET_CHECK_ID": entry["id"],
                       "CODEXENVSET_EVIDENCE_DIR": str(check_directory)}
        result = execute_check(root, directory, token, entry, environment)
        receipt["results"].append(result)
        if result["returncode"] != 0 or result["timed_out"]:
            break
    after = fingerprints(root, identifier)
    receipt["success"] = len(receipt["results"]) == len(settings["checks"]) and all(
        r["returncode"] == 0 and not r["timed_out"] for r in receipt["results"]) and before == after
    if receipt["success"] and current.get("structural_quality"):
        try:
            validate_structural_results(root, identifier, receipt)
        except (GateError, ValueError, KeyError, TypeError) as exc:
            receipt["success"] = False
            receipt["structural_error"] = str(exc)
    if receipt["success"] and "ui" in settings:
        try:
            observed_ui = ui_gate().collect(root, identifier, receipt, output_directory)
            if observed_ui is not None:
                receipt["ui"] = observed_ui
                receipt["success"] = settings["ui"]["mode"] == "observe" or observed_ui["status"] == "passed"
        except (GateError, OSError, KeyError, TypeError, ValueError) as exc:
            receipt["success"] = False
            receipt["ui"] = {"status": "invalid", "error": str(exc)}
    receipt["finished_at"] = now()
    receipt["source_unchanged"] = before == after
    write_json(directory / f"{token}.json", receipt)
    write_json(directory / "latest.json", receipt)
    record(root, identifier, "verification", success=receipt["success"], receipt=f"evidence/{token}.json")
    detail = receipt.get("ui", {}).get("error", receipt.get("ui", {}).get("status", ""))
    require(receipt["success"], f"検証失敗・タイムアウト・対象変更・UI未確認を検出しました: {directory / 'latest.json'} {detail}")
    return {"id": identifier, "success": True, "checks": [r["id"] for r in receipt["results"]], **before}


def ui_gate():
    return UIContract(WorkflowHooks(artifact=artifact, config=config, exclusive=exclusive,
        integrity=integrity, request_ids=request_ids, source_delta=source_delta,
        state=state, validate_receipt=validate_receipt))


def backup_check(root, remote="origin", remote_branch=None):
    import delivery
    return delivery.backup_check(root, remote=remote, remote_branch=remote_branch)


def ship_check(root, identifier, github=None):
    import delivery
    return delivery.ship_check(root, identifier, github=github)


def ship(root, identifier, github=None):
    import delivery
    return delivery.ship(root, identifier, github=github)


def main(argv=None):
    common.configure_stdio()
    parser = argparse.ArgumentParser(description="共通開発工程: 成果物・検証・レビューのゲート", allow_abbrev=False)
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--json", action="store_true", help="機械可読なJSON結果")
    sub = parser.add_subparsers(dest="command", required=True,
                               parser_class=partial(argparse.ArgumentParser, allow_abbrev=False))
    backup = sub.add_parser("backup-check", help="ローカルHEADとリモートのpush先を読み取り専用で照合")
    backup.add_argument("--remote", default="origin")
    backup.add_argument("--branch", dest="remote_branch", help="保存先ブランチ。複雑なpush設定では明示する")
    saving = sub.add_parser('save', help='指定ファイルを検査し、コミット・pushして実リモートへ照合')
    saving.add_argument('--message', required=True)
    saving.add_argument('--path', action='append', required=True, dest='paths')
    saving.add_argument('--remote', default='origin')
    saving.add_argument('--branch', dest='remote_branch')
    for name in ("status", "check", "advance", "run", "fingerprint", "baseline"):
        command = sub.add_parser(name)
        command.add_argument("id")
        if name in ('advance', 'run'):
            command.add_argument('--turn')
        if name == 'advance':
            command.add_argument('--local-only', action='store_true',
                                 help='本人がローカル限定を明示した場合だけ使用')
    saved_change = sub.add_parser('save-change', help='完了した変更の対象だけを検査し自動保存を再開')
    saved_change.add_argument('id')
    inspecting = sub.add_parser('inspect', help='登録済みの実装前観察を実行し、ソース不変を検査')
    inspecting.add_argument('id')
    inspecting.add_argument('--check', required=True)
    inspecting.add_argument('--turn')
    ci_parser = sub.add_parser("ci")
    ci_parser.add_argument("id", nargs="?")
    ci_parser.add_argument("--base")
    shipping = sub.add_parser("ship-check", help="品質ゲート・Git・実PRを読み取り専用で確認")
    shipping.add_argument("id")
    shipping.add_argument("--forge-state", type=Path, help="接続ツールで取得した60秒以内のGitHub状態JSON")
    sub.add_parser("ship", help="push済みブランチのPRを作成・再開し、許可条件内でマージ").add_argument("id")
    create = sub.add_parser("new")
    create.add_argument("id")
    create.add_argument("--kind", choices=("new", "change"), required=True)
    create.add_argument("--author", required=True)
    create.add_argument("--context", required=True)
    create.add_argument("--base")
    create.add_argument("--ui", action="store_true", help="新規UI作業。UI v3/enforce未接続では開始しない")
    create.add_argument('--request-file', type=Path, help='現在の元依頼を含むUTF-8の実ファイル')
    guidance = sub.add_parser("guide", help="現在工程・担当Skill・製品編集と完了の可否を読取り専用で確認")
    guidance.add_argument("id", nargs="?")
    guidance.add_argument("--ui", action="store_true", help="UI担当と契約の接続も確認")
    guidance.add_argument('--turn', help='現在の入力へのSkill適用記録')
    guidance.add_argument("--activity", action="append", default=[], choices=sorted(ACTIVITY_ROLES),
                          help="該当作業の必須Skillを追加。複数指定可")
    starting = sub.add_parser('begin', help='新しい発言・再開の実行記録を作り、前の未完了記録を失効させる')
    starting.add_argument('id', nargs='?')
    starting.add_argument('--context', required=True)
    starting.add_argument('--request-file', type=Path, required=True)
    starting.add_argument('--activity', action='append', default=[], choices=sorted(ACTIVITY_ROLES))
    starting.add_argument('--ui', action='store_true')
    for name in ('skill-read', 'context-read', 'apply-skills', 'execution-status', 'finish'):
        command = sub.add_parser(name)
        command.add_argument('--turn', required=True)
        if name == 'skill-read':
            command.add_argument('--role', required=True)
        elif name == 'context-read':
            command.add_argument('--path', required=True)
        elif name == 'apply-skills':
            command.add_argument('--file', required=True)
    back = sub.add_parser("reopen")
    back.add_argument("id")
    back.add_argument("phase", choices=PHASES[:-1])
    back.add_argument("--reason", required=True)
    back.add_argument('--ui', action='store_true', help='新しく検出したUI契約をdiscoveryで固定')
    args = parser.parse_args(argv)
    root = args.project.resolve()
    try:
        if args.command == 'save':
            import delivery
            result = delivery.save(root, args.message, args.paths, remote=args.remote, remote_branch=args.remote_branch)
            print(json.dumps({'ok': True, **result}, ensure_ascii=False, indent=2))
            return 0
        if args.command == "backup-check":
            result = backup_check(root, remote=args.remote, remote_branch=args.remote_branch)
            print(json.dumps({"ok": True, **result}, ensure_ascii=False, indent=2))
            return 0
        require((root / ".harness").is_dir(), "導入されていません。先にinstall.pyを実行してください")
        if args.command == "guide":
            result = guide(root, args.id, ui=args.ui, activities=args.activity, turn=args.turn)
            print(json.dumps({"ok": True, **result}, ensure_ascii=False, indent=2))
            return 0
        if args.command == "ci" and args.id is None:
            args.id = select_change(root, args.base)
        if args.command == "ship-check":
            import delivery
            github = delivery.RecordedGitHub(args.forge_state) if args.forge_state else None
            result = ship_check(root, args.id, github=github)
            print(json.dumps({"ok": True, **result}, ensure_ascii=False, indent=2))
            return 0
        with exclusive(root):
            if args.command in ('begin', 'new'):
                require(args.request_file is not None and
                        (str(args.request_file) == '-' or args.request_file.is_file()),
                        '実行開始には元の依頼を含む--request-fileが必要です')
                request = nonempty(sys.stdin.read() if str(args.request_file) == '-' else
                                   args.request_file.read_text(encoding='utf-8-sig'), '元の依頼')
                if args.command == 'new':
                    result = new(root, args.id, args.kind, args.author, args.context, args.base,
                                 ui=args.ui, request=request)
                    selected = ()
                else:
                    result = {}
                    selected = args.activity
                handoff = guide(root, args.id, ui=args.ui, activities=selected, _execution=False)
                result.update(handoff)
                result['execution'] = execution.begin(root, handoff['id'], args.context, request, handoff)
            elif args.command in ('skill-read', 'context-read', 'apply-skills', 'execution-status', 'finish'):
                integrity(root)
                if args.command == 'skill-read':
                    result = execution.read_skill(root, args.turn, args.role)
                elif args.command == 'context-read':
                    result = execution.read_context(root, args.turn, args.path)
                else:
                    require(re.fullmatch(r'[a-f0-9]{32}', args.turn), '実行turnが不正です')
                    saved = read_json(safe_path(root, f'{execution.STORE}/{args.turn}.json'))
                    binding = saved['binding']
                    handoff = guide(root, binding['id'], activities=binding['activities'], _execution=False)
                    if args.command == 'apply-skills':
                        result = execution.apply(root, args.turn, args.file, handoff)
                    elif args.command == 'finish':
                        result = execution.finish(root, args.turn, handoff)
                    else:
                        result = execution.status(root, args.turn, handoff)
            elif args.command == "baseline":
                result = baseline(root, args.id)
            elif args.command == "advance":
                result = advance(root, args.id, turn=args.turn)
                if result['phase'] == 'done':
                    if args.local_only:
                        result['delivery'] = {'status': 'local_only', 'remote_saved': False}
                    else:
                        import delivery
                        result['delivery'] = delivery.save_change(root, args.id)
            elif args.command == 'save-change':
                import delivery
                result = delivery.save_change(root, args.id)
            elif args.command == 'inspect':
                result = inspect(root, args.id, args.check, turn=args.turn)
            elif args.command == "reopen":
                result = reopen(root, args.id, args.phase, args.reason, ui=args.ui)
            elif args.command == "run":
                result = run_checks(root, args.id, turn=args.turn)
            elif args.command == "ship":
                result = ship(root, args.id)
            elif args.command == "ci":
                require(state(root, args.id)["phase"] == "done", "CI対象変更はdoneである必要があります")
                ci_base = args.base
                if state(root, args.id).get("structural_quality"):
                    require(ci_base and ci_base == state(root, args.id).get("base_sha"), "CIの基準SHAが開始時と一致しません")
                    require(ci_base == artifact(root, args.id, "review").get("base_sha"), "レビューの基準SHAがCIと一致しません")
                    ancestor = subprocess.run(["git", "merge-base", "--is-ancestor", ci_base, "HEAD"], cwd=root)
                    require(ancestor.returncode == 0, "マージ先を更新して再検証・再レビューしてください")
                    changed = subprocess.run(["git", "diff", "--name-only", "-z", "HEAD"], cwd=root,
                                             capture_output=True, text=True, encoding="utf-8", check=True).stdout.split("\0")
                    changed += subprocess.run(["git", "ls-files", "--others", "--exclude-standard", "-z"], cwd=root,
                                              capture_output=True, text=True, encoding="utf-8", check=True).stdout.split("\0")
                    require(not set(changed) & set(project_entries(root)), "CI対象のコード・設定をコミットしてください")
                check(root, args.id, portable=True)  # Never reuse the local OS/tool bytes as CI evidence.
                run_checks(root, args.id, ci_base=ci_base)
                result = check(root, args.id)
            else:
                integrity(root)
                if args.command == "check":
                    result = check(root, args.id)
                elif args.command == "fingerprint":
                    result = fingerprints(root, args.id)
                else:
                    result = state(root, args.id)
        print(json.dumps({"ok": True, **result}, ensure_ascii=False, indent=2))
        return 0
    except (GateError, OSError, KeyError, TypeError, ValueError, subprocess.TimeoutExpired) as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        else:
            print(f"STOP: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
