import json
import re
import subprocess
from pathlib import Path

LOCKFILES = [
    ("pnpm-lock.yaml", "pnpm"),
    ("yarn.lock", "yarn"),
    ("bun.lockb", "bun"),
    ("bun.lock", "bun"),
    ("package-lock.json", "npm"),
]
EXEC = {"pnpm": "pnpm exec", "yarn": "yarn", "bun": "bunx", "npm": "npx"}
RUNNERS = [
    ("vitest", "vitest run {target}"),
    ("jest", "jest {target}"),
    ("mocha", "mocha {target}"),
]
FRAMEWORKS = [
    ("next", "nextjs"),
    ("express", "express"),
    ("fastify", "fastify"),
    ("@nestjs/core", "nestjs"),
    ("hono", "hono"),
]
CONVENTIONAL = r"^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\([\w./@-]+\))?!?: .+"
CONVENTION_FILES = ["CLAUDE.md", "AGENTS.md", "ARCHITECTURE.md", "docs/architecture.md", "CONTRIBUTING.md"]
FALLBACK_WORKSPACES = ["apps/*", "packages/*", "services/*"]


def read_json(path):
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def dependencies(package):
    names = set()
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        names.update((package.get(key) or {}).keys())
    return names


def package_manager(root):
    for lockfile, manager in LOCKFILES:
        if (root / lockfile).exists():
            return manager
    package = read_json(root / "package.json") or {}
    declared = str(package.get("packageManager") or "")
    for manager in ("pnpm", "yarn", "bun", "npm"):
        if declared.startswith(manager):
            return manager
    return "npm"


def workspace_patterns(root, package):
    patterns = []
    workspaces = package.get("workspaces")
    if isinstance(workspaces, dict):
        workspaces = workspaces.get("packages")
    if isinstance(workspaces, list):
        patterns.extend(str(item) for item in workspaces)
    pnpm = root / "pnpm-workspace.yaml"
    if pnpm.is_file():
        for line in pnpm.read_text().splitlines():
            match = re.match(r"\s*-\s*['\"]?([^'\"#]+?)['\"]?\s*$", line)
            if match and not match.group(1).startswith("!"):
                patterns.append(match.group(1))
    return patterns or FALLBACK_WORKSPACES


def workspace_dirs(root, package):
    found = []
    for pattern in workspace_patterns(root, package):
        pattern = pattern.rstrip("/")
        if pattern.endswith("/**"):
            pattern = pattern[:-1]
        for path in sorted(root.glob(pattern)):
            if path.is_dir() and (path / "package.json").is_file() and "node_modules" not in path.parts:
                rel = path.relative_to(root).as_posix()
                if rel not in found:
                    found.append(rel)
    return found


def prisma_schema(directory, package):
    configured = (package.get("prisma") or {}).get("schema") if isinstance(package.get("prisma"), dict) else None
    candidates = [configured] if configured else []
    candidates += ["prisma/schema.prisma", "prisma/schema", "schema.prisma"]
    for candidate in candidates:
        path = directory / candidate
        if path.exists():
            return path
    return None


def prisma_provider(schema):
    files = [schema] if schema.is_file() else sorted(schema.glob("*.prisma"))
    for path in files:
        try:
            text = path.read_text()
        except OSError:
            continue
        match = re.search(r"datasource\s+\w+\s*\{[^}]*?provider\s*=\s*\"(\w+)\"", text, re.S)
        if match:
            return match.group(1)
    return ""


def in_dir(rel, command):
    return command if rel == "." else f"cd {rel} && {command}"


def scoped_match(rel, name, word):
    script = r"\b(npm|pnpm|yarn|bun)\b[^\n;&|]*\btest\b"
    if rel == ".":
        return rf"\b{word}\b|{script}"
    keys = [re.escape(rel)]
    if name:
        keys.append(rf"(?<![\w@/-]){re.escape(name)}(?![\w-])")
        short = name.split("/")[-1]
        if short != name:
            keys.append(rf"(?<![\w@/-]){re.escape(short)}(?![\w-])")
    return rf"(?=[\s\S]*({'|'.join(keys)}))[\s\S]*(\b{word}\b|{script})"


def describe_package(root, rel, manager):
    directory = root / rel
    package = read_json(directory / "package.json") or {}
    deps = dependencies(package)
    scripts = package.get("scripts") or {}
    info = {
        "rel": rel,
        "name": package.get("name") or "",
        "frameworks": [label for dep, label in FRAMEWORKS if dep in deps],
        "react": "react" in deps,
        "typescript": "typescript" in deps or (directory / "tsconfig.json").exists(),
        "runner": next((runner for runner in RUNNERS if runner[0] in deps), None),
        "playwright": "@playwright/test" in deps,
        "lint": "lint" in scripts,
        "typecheck": next((s for s in ("typecheck", "type-check", "check-types") if s in scripts), None),
        "prisma": None,
    }
    if "prisma" in deps or "@prisma/client" in deps:
        schema = prisma_schema(directory, package)
        if schema:
            info["prisma"] = {"schema": schema.relative_to(root).as_posix(), "provider": prisma_provider(schema)}
    if (directory / "app").is_dir() or (directory / "src" / "app").is_dir():
        info["app_router"] = True
    return info


def git_value(root, *args):
    try:
        result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def branch_exists(root, name):
    return bool(git_value(root, "rev-parse", "--verify", "--quiet", name) or
                git_value(root, "rev-parse", "--verify", "--quiet", f"origin/{name}"))


def detect_git(root, root_deps):
    git = {"main_branch": "main"}
    head = git_value(root, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    if head:
        git["main_branch"] = head.split("/", 1)[-1]
    elif branch_exists(root, "master") and not branch_exists(root, "main"):
        git["main_branch"] = "master"
    if branch_exists(root, "develop"):
        git["integration_branch"] = "develop"
    commitlint = any(root.glob("commitlint.config.*")) or any(root.glob(".commitlintrc*")) or any(
        dep.startswith("@commitlint/") for dep in root_deps
    )
    if commitlint:
        git["commit"] = {"subject_pattern": CONVENTIONAL}
    return git


def detect_python(root):
    for manage in [root / "manage.py", *sorted(root.glob("*/manage.py"))]:
        if not manage.is_file():
            continue
        rel = manage.parent.relative_to(root).as_posix()
        text = ""
        for name in ("requirements.txt", "requirements/base.txt", "pyproject.toml"):
            for base in (manage.parent, root):
                path = base / name
                if path.is_file():
                    text += path.read_text().lower()
        stack = ["django-drf" if "djangorestframework" in text else "django"]
        pytest = "pytest" in text
        command = in_dir(rel, "pytest {target} -q" if pytest else "python manage.py test {target}")
        return {
            "rel": rel,
            "stack": stack,
            "summary": f"Django{' REST Framework' if stack[0] == 'django-drf' else ''} backend in {rel}/" if rel != "." else "Django backend",
            "tests": {"command": command, "match": r"\bpytest\b" if pytest else r"manage\.py\s+test\b"},
            "data": {
                "orm": "django",
                "migrations": f"{rel}/*/migrations/*" if rel != "." else "*/migrations/*",
                "check_command": in_dir(rel, "python manage.py makemigrations --check --dry-run"),
            },
        }
    return None


def unique(items):
    seen = []
    for item in items:
        if item and item not in seen:
            seen.append(item)
    return seen


def detect(root):
    root = Path(root)
    profile = {"version": 1, "project": {"name": root.name, "summary": "", "stack": [], "sensitive_data": [], "scope_boundaries": []}}
    notes = []
    root_package = read_json(root / "package.json")
    python = detect_python(root)

    if root_package is None and python is None:
        notes.append("No package.json or manage.py found; wrote a minimal profile. Set tests.command and tests.match yourself.")
        profile["tests"] = {"command": ""}
    conventions = [name for name in CONVENTION_FILES if (root / name).exists()]
    profile["paths"] = {"conventions": conventions or ["CLAUDE.md"]}
    api_docs = sorted({p.relative_to(root).as_posix() for pattern in ("openapi.*", "*/openapi.*", "*/*/openapi.*", "swagger.*", "*/swagger.*")
                       for p in root.glob(pattern) if "node_modules" not in p.parts})
    if api_docs:
        profile["paths"]["api_docs"] = api_docs

    if root_package is not None:
        manager = package_manager(root)
        run = EXEC[manager]
        profile["project"]["name"] = root_package.get("name") or root.name
        rels = workspace_dirs(root, root_package) if (root_package.get("workspaces") or (root / "pnpm-workspace.yaml").exists()) else []
        packages = [describe_package(root, rel, manager) for rel in rels] or [describe_package(root, ".", manager)]
        if rels and (dependencies(root_package) & {"vitest", "jest", "mocha"}):
            packages.insert(0, describe_package(root, ".", manager))
        stack, parts, suites, checks, e2e = [], [], [], [], []
        for info in packages:
            where = "" if info["rel"] == "." else f" in {info['rel']}/"
            for framework in info["frameworks"]:
                stack.append(framework)
                label = {"nextjs": "Next.js app" + (" (App Router)" if info.get("app_router") else ""),
                         "express": "Express API", "fastify": "Fastify API", "nestjs": "NestJS API", "hono": "Hono API"}[framework]
                parts.append(label + where)
            if info["react"] and "nextjs" not in info["frameworks"]:
                stack.append("react")
            if info["prisma"]:
                stack.append("prisma")
                provider = info["prisma"]["provider"]
                parts.append(f"Prisma{f' ({provider})' if provider else ''}{where}")
                schema = info["prisma"]["schema"]
                schema_dir = Path(schema) if (root / schema).is_dir() else Path(schema).parent
                migrations = (schema_dir / "migrations").as_posix()
                schema_flag = f" --schema {Path(schema).relative_to(info['rel']).as_posix() if info['rel'] != '.' else schema}"
                profile["data"] = {
                    "orm": "prisma",
                    "schema": schema,
                    "migrations": migrations + "/*",
                    "check_command": in_dir(info["rel"], f"{run} prisma validate{schema_flag} && {run} prisma migrate status{schema_flag}"),
                }
            if info["typescript"]:
                stack.append("typescript")
            if info["runner"]:
                word, command = info["runner"]
                name = "app" if info["rel"] == "." else info["rel"].split("/")[-1]
                suites.append({
                    "name": name,
                    "paths": ["*"] if info["rel"] == "." else [f"{info['rel']}/*"],
                    "command": in_dir(info["rel"], f"{run} {command}"),
                    "match": scoped_match(info["rel"], info["name"], word),
                })
            if info["typecheck"]:
                checks.append(in_dir(info["rel"], f"{manager} run {info['typecheck']}"))
            elif info["typescript"]:
                checks.append(in_dir(info["rel"], f"{run} tsc --noEmit"))
            if info["lint"]:
                checks.append(in_dir(info["rel"], f"{manager} run lint"))
            if info["playwright"]:
                e2e.append(in_dir(info["rel"], f"{run} playwright test"))
        root_scripts = root_package.get("scripts") or {}
        if rels and any(s in root_scripts for s in ("typecheck", "lint")):
            checks = [f"{manager} run {s}" for s in ("typecheck", "lint") if s in root_scripts]
        if len(suites) == 1 and suites[0]["paths"] == ["*"]:
            profile["tests"] = {"command": suites[0]["command"], "match": suites[0]["match"]}
        elif suites:
            profile["tests"] = {"suites": suites}
        else:
            notes.append("No Vitest, Jest or Mocha dependency found; set tests.command and tests.match yourself.")
            profile["tests"] = {}
        if checks:
            profile["tests"]["checks"] = unique(checks)
        if e2e:
            profile["tests"]["e2e_command"] = " ; ".join(unique(e2e))
        profile["project"]["stack"] = unique(stack)
        layout = f"{manager} workspace" if rels else manager
        profile["project"]["summary"] = "; ".join(unique(parts)) + f" ({layout})" if parts else f"JavaScript/TypeScript project ({layout})"
        git = detect_git(root, dependencies(root_package))
    else:
        git = detect_git(root, set())

    if python:
        profile["project"]["stack"] = unique(profile["project"]["stack"] + python["stack"])
        profile["project"]["summary"] = "; ".join(filter(None, [profile["project"]["summary"], python["summary"]]))
        if root_package is None:
            profile["tests"] = python["tests"]
        else:
            notes.append("Found both JavaScript and Django code; added the Django tests as their own suite.")
            tests = profile.setdefault("tests", {})
            existing = tests.pop("command", None)
            existing_match = tests.pop("match", None)
            suites = tests.setdefault("suites", [])
            if existing:
                suites.insert(0, {"name": "app", "paths": ["*"], "command": existing, "match": existing_match})
            django_dir = python["rel"]
            suites.append({"name": "django", "paths": [f"{django_dir}/*"] if django_dir != "." else ["*.py", "*/*.py"],
                           "command": python["tests"]["command"], "match": python["tests"]["match"]})
        profile.setdefault("data", python["data"])

    profile["git"] = git
    if not profile["project"]["sensitive_data"]:
        notes.append("Fill in project.sensitive_data and project.scope_boundaries: they decide what counts as Critical in reviews.")
    return profile, notes
