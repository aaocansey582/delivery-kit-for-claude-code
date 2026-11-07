import copy
import fnmatch
import json
import os
import re
import subprocess
from pathlib import Path

PROFILE_FILE = ".delivery-kit.json"
LOCAL_PROFILE_FILE = ".claude/delivery-kit.local.json"
DEFAULT_SUITE = "default"

DEFAULT_TEST_MATCH = (
    r"\b(pytest|py\.test|tox|nox|jest|vitest|mocha|rspec|phpunit|playwright\s+test|go\s+test|cargo\s+test"
    r"|dotnet\s+test|node\s+--test|tsx\s+--test|manage\.py\s+test|(npm|pnpm|yarn|bun)\s+(run\s+)?test\b"
    r"|mvn\b.*\btest|gradlew?\b.*\btest)"
)
DEFAULT_FAIL_PATTERN = (
    r"\b[1-9]\d* (failed|failing|errors?)\b|^(FAIL|--- FAIL)\b|^# fail [1-9]|\bno tests (ran|found)\b"
    r"|\bNo test files found\b|\bNo tests found\b"
)
DEFAULT_PASS_PATTERN = r"\b[1-9]\d* (passed|passing)\b|^ok\s+\S+|^# pass [1-9]"

DEFAULTS = {
    "version": 1,
    "project": {
        "name": "",
        "summary": "",
        "stack": [],
        "sensitive_data": [],
        "scope_boundaries": [],
    },
    "paths": {
        "code": ["*"],
        "exclude": [
            "*.md", "docs/*", ".claude/*", ".github/*",
            "node_modules/*", "*/node_modules/*", ".next/*", "*/.next/*", "dist/*", "*/dist/*",
            "build/*", "coverage/*", "*/coverage/*", ".turbo/*", "public/*", "*/public/*",
            "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "bun.lock", "bun.lockb",
            "graphify-out/*",
        ],
        "docs": [],
        "api_docs": [],
        "conventions": ["CLAUDE.md"],
        "deployment_rules": "",
        "plans": [],
    },
    "tests": {
        "command": "",
        "lane_command": "",
        "match": DEFAULT_TEST_MATCH,
        "pass_pattern": DEFAULT_PASS_PATTERN,
        "fail_pattern": DEFAULT_FAIL_PATTERN,
        "suites": [],
        "checks": [],
        "e2e_command": "",
        "full_suite": {"command": "", "note": ""},
    },
    "data": {
        "orm": "",
        "schema": "",
        "migrations": "",
        "check_command": "",
    },
    "git": {
        "main_branch": "main",
        "integration_branch": "",
        "commit": {"single_line": False, "subject_pattern": "", "forbid_patterns": []},
        "pr": {"forbid_patterns": []},
    },
    "guards": {
        "secret_files": [".env", ".env.*", "*/.env", "*/.env.*", "*.pem", "*.key"],
        "secret_file_exceptions": [".env.example", ".env.sample", ".env.template", "*/.env.example"],
        "protected_paths": {},
    },
    "lifecycle": {"enabled": True, "state_dir": ".claude/lifecycle"},
    "graph": {
        "provider": "graphify",
        "dir": "graphify-out",
        "update_command": "graphify update .",
        "update_match": r"\bgraphify\s+update\b",
        "require_before_ship": True,
    },
    "agents": {"house_rules": []},
}

KNOWN_KEYS = set(DEFAULTS)
REGEX_FIELDS = [
    ("tests", "match"),
    ("tests", "pass_pattern"),
    ("tests", "fail_pattern"),
    ("git", "commit", "subject_pattern"),
    ("graph", "update_match"),
]
LIST_REGEX_FIELDS = [("git", "commit", "forbid_patterns"), ("git", "pr", "forbid_patterns")]


def project_dir():
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        return Path(env)
    try:
        top = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, timeout=5
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        top = ""
    return Path(top) if top else Path.cwd()


def deep_merge(base, override):
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def compile_regex(pattern):
    if not pattern:
        return None
    try:
        return re.compile(pattern, re.S | re.M | re.I)
    except re.error:
        return None


class Profile:
    def __init__(self, root, data, sources, errors):
        self.root = Path(root)
        self.data = data
        self.sources = sources
        self.errors = errors

    def get(self, *keys, default=None):
        node = self.data
        for key in keys:
            if not isinstance(node, dict) or key not in node:
                return default
            node = node[key]
        return node

    @property
    def configured(self):
        return bool(self.sources)

    @property
    def name(self):
        return self.get("project", "name") or "this project"

    @property
    def stacks(self):
        stack = self.get("project", "stack", default=[])
        if isinstance(stack, str):
            stack = [stack] if stack else []
        return [str(item).lower() for item in stack]

    @property
    def state_dir(self):
        return self.root / self.get("lifecycle", "state_dir", default=".claude/lifecycle")

    @property
    def graph_file(self):
        if not self.get("graph", "provider"):
            return None
        return self.root / self.get("graph", "dir", default="graphify-out") / "graph.json"

    @property
    def graph_active(self):
        graph = self.graph_file
        return bool(graph and graph.is_file())

    def relative(self, file_path):
        if not file_path:
            return None
        try:
            return Path(file_path).resolve().relative_to(self.root.resolve()).as_posix()
        except ValueError:
            return None

    def is_tracked_code(self, file_path):
        rel = self.relative(file_path)
        if rel is None:
            return False
        if any(fnmatch.fnmatch(rel, pattern) for pattern in self.get("paths", "exclude", default=[])):
            return False
        return any(fnmatch.fnmatch(rel, pattern) for pattern in self.get("paths", "code", default=["*"]))

    def suites(self):
        result = []
        for suite in self.get("tests", "suites", default=[]) or []:
            if isinstance(suite, dict) and suite.get("name"):
                result.append({
                    "name": suite["name"],
                    "paths": suite.get("paths") or [],
                    "command": suite.get("command") or "",
                    "match": compile_regex(suite.get("match")),
                })
        return result

    def suites_for_file(self, file_path):
        rel = self.relative(file_path) or ""
        names = [suite["name"] for suite in self.suites() if any(fnmatch.fnmatch(rel, p) for p in suite["paths"])]
        return names or [DEFAULT_SUITE]

    def suites_run_by(self, command):
        names = [suite["name"] for suite in self.suites() if suite["match"] and suite["match"].search(command)]
        default = self.regex("tests", "match")
        if default and default.search(command):
            names.append(DEFAULT_SUITE)
        return names

    def test_hint(self, names=None):
        commands = []
        for suite in self.suites():
            if names is None or suite["name"] in names:
                if suite["command"]:
                    commands.append(f"{suite['name']}: {suite['command'].replace('{target}', '<path>')}")
        default = self.get("tests", "command")
        if default and (names is None or DEFAULT_SUITE in names or not commands):
            commands.append(default.replace("{target}", "<path>"))
        return "; ".join(commands) if commands else "the project's targeted test command"

    def regex(self, *keys):
        return compile_regex(self.get(*keys))


def read_json(path, sources, errors):
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError) as error:
        errors.append(f"{path.name}: {error}")
        return {}
    if not isinstance(data, dict):
        errors.append(f"{path.name}: top level must be a JSON object")
        return {}
    sources.append(str(path))
    return data


def load_profile(root=None):
    root = Path(root) if root else project_dir()
    sources, errors = [], []
    data = deep_merge(DEFAULTS, read_json(root / PROFILE_FILE, sources, errors))
    data = deep_merge(data, read_json(root / LOCAL_PROFILE_FILE, sources, errors))
    return Profile(root, data, sources, errors)


def check_regex(label, pattern, problems):
    try:
        re.compile(pattern)
    except re.error as error:
        problems.append(f"{label}: invalid regex '{pattern}' ({error})")
        return False
    return True


def validate(profile):
    problems = list(profile.errors)
    warnings = []
    for source in profile.sources:
        try:
            raw = json.loads(Path(source).read_text())
        except (OSError, ValueError):
            continue
        for key in raw:
            if key not in KNOWN_KEYS and not key.startswith("$"):
                warnings.append(f"{Path(source).name}: unknown key '{key}'")
    for keys in REGEX_FIELDS:
        pattern = profile.get(*keys)
        if pattern:
            check_regex(".".join(keys), pattern, problems)
    for keys in LIST_REGEX_FIELDS:
        for pattern in profile.get(*keys, default=[]):
            check_regex(".".join(keys), pattern, problems)
    command = profile.get("tests", "command")
    if command and "{target}" not in command:
        warnings.append("tests.command has no {target} placeholder")
    lane = profile.get("tests", "lane_command")
    if lane and "{lane}" not in lane:
        warnings.append("tests.lane_command has no {lane} placeholder")
    match = profile.regex("tests", "match")
    if command and match and not match.search(command.replace("{target}", "x")):
        problems.append("tests.match does not match tests.command, so passing runs would never clear the untested mark")
    seen = set()
    for index, suite in enumerate(profile.get("tests", "suites", default=[]) or []):
        label = f"tests.suites[{index}]"
        if not isinstance(suite, dict) or not suite.get("name"):
            problems.append(f"{label}: needs a name")
            continue
        label = f"tests.suites '{suite['name']}'"
        if suite["name"] in seen:
            problems.append(f"{label}: duplicate name")
        seen.add(suite["name"])
        if not suite.get("paths"):
            warnings.append(f"{label}: no paths, so no edit will ever require it")
        if not suite.get("match"):
            problems.append(f"{label}: needs a match regex")
        elif check_regex(f"{label}.match", suite["match"], problems):
            suite_command = (suite.get("command") or "").replace("{target}", "x")
            if suite_command and not compile_regex(suite["match"]).search(suite_command):
                problems.append(f"{label}: match does not match its command")
    for rel in profile.get("paths", "conventions", default=[]):
        if not (profile.root / rel).exists():
            warnings.append(f"paths.conventions: {rel} not found")
    deployment = profile.get("paths", "deployment_rules")
    if deployment and not (profile.root / deployment).exists():
        warnings.append(f"paths.deployment_rules: {deployment} not found")
    schema = profile.get("data", "schema")
    if schema and not (profile.root / schema).exists():
        warnings.append(f"data.schema: {schema} not found")
    protected = profile.get("guards", "protected_paths", default={})
    if not isinstance(protected, dict):
        problems.append("guards.protected_paths must be an object of glob -> warn|ask|deny")
    else:
        for pattern, mode in protected.items():
            if mode not in ("warn", "ask", "deny"):
                problems.append(f"guards.protected_paths '{pattern}': mode must be warn, ask or deny")
    return problems, warnings
