import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from . import __version__, hooks, lifecycle
from .detect import detect
from .profile import PROFILE_FILE, load_profile, validate

JS_STACKS = {"nextjs", "express", "fastify", "nestjs", "hono", "react", "typescript", "node", "prisma"}

USAGE = """usage: delivery-kit <command> [args]

  lifecycle start <fix|feature> <slug>   start a tracked fix or feature
  lifecycle phase <name>                 understand|plan|implement|test|review|ship
  lifecycle review --open-high <N>       record the review result
  lifecycle status | claim | end [--abort]
  brief [--read-only]                    print the project brief for subagent prompts
  profile show | check                   inspect or validate .delivery-kit.json
  profile init [--print] [--force]       detect the stack and write .delivery-kit.json
  doctor                                 check requirements and setup
  version
"""


def bullet_list(items):
    return "; ".join(items)


def brief(profile, args):
    read_only = "--read-only" in args
    lines = []
    summary = profile.get("project", "summary")
    lines.append(f"You are working on {profile.name}" + (f": {summary}." if summary else "."))
    if profile.stacks:
        lines.append(f"Stack: {', '.join(profile.stacks)}.")
    conventions = profile.get("paths", "conventions", default=[])
    if conventions:
        lines.append(f"The project's conventions are in {bullet_list(conventions)}; judge code against them, not against generic advice.")
    rules = profile.get("agents", "house_rules", default=[])
    if rules:
        lines.append("House rules: " + " ".join(rules))
    if profile.graph_active:
        graph_dir = profile.get("graph", "dir")
        lines.append(
            f"A code knowledge graph exists at {graph_dir}/. Before your first grep, search or source read for a codebase question, "
            "run `graphify query \"<question>\"`; use `graphify path \"<A>\" \"<B>\"` for relationships, "
            "`graphify explain \"<concept>\"` for one concept and `graphify affected \"<X>\"` for impact; "
            "if a name is ambiguous (exit 3) retry with one of the listed candidates instead of falling back to a broad grep. "
            "Read raw files only for lines the graph located, and don't assume the graph is current: confirm against the code."
        )
    if read_only:
        lines.append("This is read-only: do not edit, create or delete files, run migrations, or run anything that writes.")
    secrets = profile.get("guards", "secret_files", default=[])
    if secrets:
        lines.append(f"Never read secret files ({bullet_list(secrets)}); if a setting matters, name it and ask.")
    if profile.get("tests", "command") or profile.suites():
        lines.append(f"Run only targeted tests ({profile.test_hint()}).")
    checks = profile.get("tests", "checks", default=[])
    if checks and not read_only:
        lines.append(f"Before declaring work done, run the quality checks: {'; '.join(checks)}.")
    orm = profile.get("data", "orm")
    if orm == "prisma":
        lines.append(
            "Data access uses Prisma"
            + (f" (schema {profile.get('data', 'schema')})" if profile.get("data", "schema") else "")
            + ". Never run `prisma migrate reset`, `prisma db push --force-reset` or `--accept-data-loss`, and never `prisma migrate deploy` against a shared database."
        )
    note = profile.get("tests", "full_suite", "note")
    lines.append("Never run the full test suite" + (f" ({note})." if note else "."))
    lines.append("Cite `path/file:LINE` for every claim and mark it Confirmed (you read the code path) or Suspected. Report concrete problems in this codebase, not generic advice.")
    print(" ".join(lines))


def profile_cmd(profile, args):
    action = args[0] if args else "show"
    if action == "show":
        print(json.dumps({"sources": profile.sources, "profile": profile.data}, indent=2))
        return
    if action == "check":
        problems, warnings = validate(profile)
        if not profile.configured and not problems:
            print(f"No {PROFILE_FILE} found in {profile.root}; running on defaults. Create one with: delivery-kit profile init")
        for warning in warnings:
            print(f"warning: {warning}")
        for problem in problems:
            print(f"error: {problem}")
        if problems:
            raise SystemExit(1)
        if profile.configured:
            print(f"Profile OK ({', '.join(profile.sources)}).")
        return
    if action == "init":
        detected, notes = detect(profile.root)
        text = json.dumps(detected, indent=2) + "\n"
        if "--print" in args:
            print(text, end="")
            for note in notes:
                print(f"note: {note}", file=sys.stderr)
            return
        target = profile.root / PROFILE_FILE
        if target.exists() and "--force" not in args:
            raise SystemExit(f"{target} already exists (use --force to overwrite, or --print to preview).")
        target.write_text(text)
        stack = ", ".join(detected["project"].get("stack") or []) or "nothing recognised"
        print(f"Wrote {target} (detected: {stack}).")
        for note in notes:
            print(f"note: {note}")
        print("Review it, then run: delivery-kit profile check")
        return
    raise SystemExit("usage: delivery-kit profile show|check|init [--print] [--force]")


def git_ignored(root, rel):
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "check-ignore", "-q", rel], capture_output=True, timeout=5
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.returncode == 0


def ecc_installed():
    config = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    try:
        installed = json.loads((config / "plugins" / "installed_plugins.json").read_text())
    except (OSError, ValueError):
        return None
    text = json.dumps(installed)
    return '"ecc@' in text


def doctor(profile, _args):
    rows = []
    rows.append(("python >= 3.9", sys.version_info >= (3, 9), sys.version.split()[0]))
    ecc = ecc_installed()
    rows.append(("ECC plugin installed", ecc, "required by the review and planning skills" if not ecc else "ecc"))
    rows.append(("profile present", profile.configured, ", ".join(profile.sources) or f"no {PROFILE_FILE}; defaults in use"))
    problems, warnings = validate(profile)
    rows.append(("profile valid", not problems, "; ".join(problems + warnings) or "ok"))
    rows.append(("test command set", bool(profile.get("tests", "command") or profile.suites()), profile.test_hint()))
    if JS_STACKS & set(profile.stacks):
        node = shutil.which("node")
        version = ""
        if node:
            try:
                version = subprocess.run([node, "--version"], capture_output=True, text=True, timeout=5).stdout.strip()
            except (OSError, subprocess.SubprocessError):
                version = ""
        rows.append(("node available", bool(node), version or "install Node.js; the test and check commands need it"))
    if profile.get("graph", "provider") == "graphify":
        tool = shutil.which("graphify")
        rows.append(("graphify installed", bool(tool) or None, tool or "optional; pip install graphifyy && graphify install"))
        graph_dir = profile.get("graph", "dir")
        rows.append(("code graph built", profile.graph_active or None, f"{graph_dir}/graph.json" if profile.graph_active else f"none yet; run /graphify in Claude Code to build {graph_dir}/"))
    state_rel = profile.state_dir.relative_to(profile.root).as_posix() + "/"
    ignored = git_ignored(profile.root, state_rel + "active.json")
    rows.append(("lifecycle state gitignored", ignored, state_rel))
    failed = False
    for label, ok, detail in rows:
        mark = "ok  " if ok else ("??  " if ok is None else "FAIL")
        failed = failed or ok is False
        print(f"{mark} {label}: {detail}")
    if failed:
        raise SystemExit(1)


def lifecycle_cmd(profile, args):
    if not args or args[0] not in lifecycle.COMMANDS:
        raise SystemExit(f"usage: delivery-kit lifecycle <{'|'.join(lifecycle.COMMANDS)}> ...")
    lifecycle.COMMANDS[args[0]](profile, args[1:])


def hook_cmd(profile, args):
    name = args[0] if args else ""
    if name not in hooks.HOOKS:
        raise SystemExit(f"usage: delivery-kit hook <{'|'.join(hooks.HOOKS)}>")
    try:
        hooks.HOOKS[name](profile, hooks.read_payload())
    except Exception as error:
        print(f"delivery-kit hook {name} failed open: {error}", file=sys.stderr)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(USAGE)
        return
    name, args = argv[0], argv[1:]
    if name == "version":
        print(__version__)
        return
    try:
        profile = load_profile()
    except Exception as error:
        if name == "hook":
            print(f"delivery-kit could not load the profile, failing open: {error}", file=sys.stderr)
            return
        raise
    handlers = {
        "lifecycle": lifecycle_cmd,
        "brief": brief,
        "profile": profile_cmd,
        "doctor": doctor,
        "hook": hook_cmd,
    }
    if name not in handlers:
        raise SystemExit(f"unknown command: {name}\n\n{USAGE}")
    handlers[name](profile, args)
