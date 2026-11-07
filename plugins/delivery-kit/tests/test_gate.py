import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MAIN = str(Path(__file__).resolve().parents[1] / "scripts" / "delivery_kit_main.py")
PYTEST = "docker exec demo-api pytest a -q"

PROFILE = {
    "project": {"name": "demo"},
    "paths": {"code": ["api/*"], "exclude": ["api/docs/*", "*.md"]},
    "tests": {"command": "docker exec demo-api pytest {target} -q", "match": r"docker\s+exec\b.*\bdemo-api\b.*\bpytest\b"},
    "git": {
        "commit": {
            "single_line": True,
            "subject_pattern": r"^(feat|fix|docs|chore)(\([\w./-]+\))?: .+",
            "forbid_patterns": ["co-authored-by"],
        },
        "pr": {"forbid_patterns": [r"generated with \[?claude code"]},
    },
}


class Project:
    def __init__(self, profile=None, graph=False):
        self.root = tempfile.mkdtemp()
        os.makedirs(f"{self.root}/api/x")
        os.makedirs(f"{self.root}/api/docs")
        if profile is not None:
            Path(self.root, ".delivery-kit.json").write_text(json.dumps(profile))
        if graph:
            os.makedirs(f"{self.root}/graphify-out")
            Path(self.root, "graphify-out/graph.json").write_text("{}")
        self.env = dict(os.environ, CLAUDE_PROJECT_DIR=self.root)
        self.env.pop("LIFECYCLE_GATE", None)

    def run(self, args, payload=None):
        result = subprocess.run(
            [sys.executable, "-I", MAIN, *args],
            input=json.dumps(payload) if payload is not None else "",
            capture_output=True, text=True, env=self.env,
        )
        return (result.stdout + result.stderr).strip()

    def pre(self, command, session="A"):
        out = self.run(["hook", "pre-bash"], {"session_id": session, "tool_input": {"command": command}})
        return "DENY" if '"deny"' in out else "allow"

    def stop(self, session):
        out = self.run(["hook", "stop"], {"session_id": session, "stop_hook_active": False})
        return "BLOCK" if '"block"' in out else "allow"

    def edit(self, session, rel="api/x/a.py"):
        self.run(["hook", "post-edit"], {"session_id": session, "tool_input": {"file_path": f"{self.root}/{rel}"}})

    def bash(self, session, command, stdout=""):
        self.run(["hook", "post-bash"], {"session_id": session, "tool_input": {"command": command}, "tool_response": {"stdout": stdout}})

    def status(self):
        out = self.run(["lifecycle", "status"])
        return json.loads(out) if out.startswith("{") else None

    def close(self):
        shutil.rmtree(self.root)


results = []


def check(name, got, expected):
    results.append((name, got, expected))


p = Project(PROFILE)
check("echo mentioning commit text", p.pre("echo 'git commit -m x -m Co-Authored-By: a'"), "allow")
check("grep for git push", p.pre("grep -rn 'git push' docs"), "allow")
check("one-line conventional commit", p.pre('git add -A && git commit -m "fix(x): y"'), "allow")
check("subject not matching pattern", p.pre('git commit -m "updated stuff"'), "DENY")
check("git -C commit with trailer", p.pre('git -C api commit -m "fix: y" --trailer "Co-authored-by: a <b>"'), "DENY")
check("coauthor second -m", p.pre('git commit -m "fix: y" -m "Co-Authored-By: C <n@a.com>"'), "DENY")
check("heredoc body", p.pre("git commit -m \"$(cat <<'EOF'\nfix: y\n\nbody\nEOF\n)\""), "DENY")
check("-am multiline", p.pre('git commit -am "fix: y\nbody"'), "DENY")
check("pr footer", p.pre('gh pr create --title t --body "x\n\nGenerated with [Claude Code](https://claude.com/claude-code)"'), "DENY")
check("pr clean", p.pre('gh pr create --title t --body "Summary"'), "allow")

p.run(["lifecycle", "start", "fix", "demo"])
p.edit("A")
check("unowned lifecycle: nobody blocked", p.stop("A"), "allow")
p.bash("B", "delivery-kit lifecycle status")
check("status doesn't claim", p.status().get("owner"), None)
p.bash("A", "delivery-kit lifecycle claim")
p.bash("B", "delivery-kit lifecycle claim")
check("owner is A, not later caller B", p.status().get("owner"), "A")
p.edit("A", "api/docs/x.md")
check("docs edit doesn't mark untested", p.status().get("untested"), False)
p.edit("A", "README.md")
check("file outside code paths doesn't mark untested", p.status().get("untested"), False)
p.edit("B")
check("B's edit doesn't mark A untested", p.stop("A"), "allow")
p.edit("A")
check("A: stop blocked while untested", p.stop("A"), "BLOCK")
check("B: stop allowed", p.stop("B"), "allow")
check("B: push allowed", p.pre("git push origin other", session="B"), "allow")
check("B: coauthor still denied", p.pre('git commit -m "fix: x" -m "Co-Authored-By: a"', session="B"), "DENY")
check("A: grep git push allowed", p.pre("grep -rn 'git push' docs"), "allow")
check("A: push blocked while untested", p.pre("git push origin fix/x"), "DENY")
p.bash("A", "npm test", "5 passed")
check("test command outside tests.match ignored", p.stop("A"), "BLOCK")
p.bash("B", PYTEST, "2 passed in 0.4s")
check("B's passing test doesn't clear A", p.stop("A"), "BLOCK")
p.bash("A", PYTEST, "1 failed, 1 passed in 0.4s")
check("A's failing test keeps it untested", p.stop("A"), "BLOCK")
p.bash("A", PYTEST, "2 passed in 0.4s")
check("A: stop allowed after passing test", p.stop("A"), "allow")
check("A: commit blocked without review", p.pre('git commit -m "fix: y"'), "DENY")
p.run(["lifecycle", "review", "--open-high", "1"])
check("A: stop blocked with open High", p.stop("A"), "BLOCK")
p.run(["lifecycle", "review", "--open-high", "0"])
check("A: commit allowed after test+review", p.pre('git commit -m "fix: y"'), "allow")
check("end succeeds", p.run(["lifecycle", "end"]), "Lifecycle 'demo' ended.")
p.close()

g = Project(PROFILE, graph=True)
g.run(["lifecycle", "start", "feature", "graph demo"])
g.bash("A", "delivery-kit lifecycle claim")
g.edit("A")
check("graph: edit marks graph stale", g.status().get("graph_stale"), True)
g.bash("A", PYTEST, "3 passed in 0.2s")
g.run(["lifecycle", "review", "--open-high", "0"])
check("graph: commit blocked while graph stale", g.pre('git commit -m "feat: y"'), "DENY")
g.bash("A", "graphify update .", "Traceback (most recent call last):\nValueError")
check("graph: failed update keeps it stale", g.status().get("graph_stale"), True)
g.bash("A", "graphify update .", "Updated graph: 812 nodes, 2140 edges")
check("graph: successful update clears it", g.status().get("graph_stale"), False)
check("graph: commit allowed after update", g.pre('git commit -m "feat: y"'), "allow")
check("graph: brief mentions graphify query", "graphify query" in g.run(["brief", "--read-only"]), True)
g.close()

n = Project(None)
check("no profile: commits unrestricted", n.pre('git commit -m "anything\n\nbody" -m "Co-Authored-By: x"'), "allow")
n.run(["lifecycle", "start", "fix", "bare"])
n.bash("A", "delivery-kit lifecycle claim")
n.edit("A", "src/app.py")
check("no profile: any code edit tracked", n.stop("A"), "BLOCK")
n.bash("A", "npx vitest run", " Tests  1 failed | 4 passed (5)")
check("no profile: vitest failure keeps untested", n.stop("A"), "BLOCK")
n.bash("A", "npx vitest run", " Tests  5 passed (5)")
check("no profile: vitest pass clears", n.stop("A"), "allow")
check("no profile: brief has no graph line", "graphify" in n.run(["brief"]), False)
n.close()

bad = Project({"tests": {"command": "pytest {target}", "match": "docker exec"}, "git": {"commit": {"subject_pattern": "("}}})
out = bad.run(["profile", "check"])
check("profile check flags bad regex", "invalid regex" in out, True)
check("profile check flags match/command mismatch", "does not match tests.command" in out, True)
bad.close()

MONO = {
    "project": {"name": "mono", "stack": ["nextjs", "express", "prisma"]},
    "tests": {
        "suites": [
            {"name": "web", "paths": ["apps/web/*"], "command": "cd apps/web && pnpm exec vitest run {target}",
             "match": r"(?=[\s\S]*(apps/web|\bweb\b))[\s\S]*(\bvitest\b|\b(npm|pnpm|yarn|bun)\b[^\n;&|]*\btest\b)"},
            {"name": "api", "paths": ["apps/api/*"], "command": "cd apps/api && pnpm exec jest {target}",
             "match": r"(?=[\s\S]*(apps/api|\bapi\b))[\s\S]*(\bjest\b|\b(npm|pnpm|yarn|bun)\b[^\n;&|]*\btest\b)"},
        ]
    },
}
m = Project(MONO)
os.makedirs(f"{m.root}/apps/web/app")
os.makedirs(f"{m.root}/apps/api/src")
os.makedirs(f"{m.root}/packages/shared")
m.run(["lifecycle", "start", "feature", "mono"])
m.bash("A", "delivery-kit lifecycle claim")
m.edit("A", "apps/web/app/page.tsx")
check("suites: web edit marks only web", m.status().get("untested_suites"), ["web"])
m.bash("A", "cd apps/api && pnpm exec jest src", "Tests:       4 passed, 4 total")
check("suites: api tests don't clear web", m.status().get("untested_suites"), ["web"])
m.bash("A", "pnpm --filter web test", " Test Files  2 passed (2)\n      Tests  9 passed (9)")
check("suites: web package script clears web", m.status().get("untested_suites"), [])
m.edit("A", "apps/api/src/routes.ts")
m.edit("A", "packages/shared/x.ts")
check("suites: api + default marked", m.status().get("untested_suites"), ["api", "default"])
check("suites: stop names the api suite", "api" in m.run(["hook", "stop"], {"session_id": "A"}), True)
m.bash("A", "cd apps/api && pnpm exec jest src/routes.test.ts", "Tests:       1 failed, 3 passed, 4 total")
check("suites: failing api run keeps api", "api" in m.status().get("untested_suites"), True)
m.bash("A", "cd apps/api && pnpm exec jest", "Tests:       4 passed, 4 total")
check("suites: jest run also clears default", m.status().get("untested_suites"), [])
m.edit("A", "apps/web/public/logo.svg")
m.edit("A", "apps/web/.next/server/x.js")
check("suites: public/ and .next/ ignored", m.status().get("untested_suites"), [])
m.close()

nt = Project({"tests": {"command": "node --test {target}", "match": r"\bnode\s+--test\b"}})
nt.run(["lifecycle", "start", "fix", "node"])
nt.bash("A", "delivery-kit lifecycle claim")
nt.edit("A", "src/a.js")
nt.bash("A", "node --test test/", "# tests 3\n# pass 3\n# fail 0")
check("node --test pass clears", nt.status().get("untested"), False)
nt.close()


def write(root, rel, content):
    path = Path(root, rel)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content if isinstance(content, str) else json.dumps(content))


d = Project(None)
write(d.root, "package.json", {"name": "acme", "private": True, "workspaces": ["apps/*", "packages/*"],
                               "scripts": {"typecheck": "turbo typecheck", "lint": "turbo lint"},
                               "devDependencies": {"@commitlint/cli": "19", "turbo": "2"}})
write(d.root, "pnpm-lock.yaml", "lockfileVersion: 9")
write(d.root, "apps/web/package.json", {"name": "@acme/web", "dependencies": {"next": "15", "react": "19"},
                                        "devDependencies": {"vitest": "3", "typescript": "5", "@playwright/test": "1"}})
os.makedirs(f"{d.root}/apps/web/app", exist_ok=True)
write(d.root, "apps/api/package.json", {"name": "@acme/api", "dependencies": {"express": "5", "@prisma/client": "6"},
                                        "devDependencies": {"jest": "30", "prisma": "6", "typescript": "5"}})
write(d.root, "apps/api/prisma/schema.prisma", 'generator client {\n  provider = "prisma-client-js"\n}\ndatasource db {\n  provider = "postgresql"\n  url = env("DATABASE_URL")\n}\n')
write(d.root, "CLAUDE.md", "# rules")
detected = json.loads(d.run(["profile", "init", "--print"]).split("\nnote:")[0])
check("detect: stack", sorted(detected["project"]["stack"]), ["express", "nextjs", "prisma", "react", "typescript"] if "react" in detected["project"]["stack"] else ["express", "nextjs", "prisma", "typescript"])
check("detect: suites", [s["name"] for s in detected["tests"].get("suites", [])], ["api", "web"])
check("detect: pnpm exec in commands", all("pnpm exec" in s["command"] for s in detected["tests"]["suites"]), True)
check("detect: root turbo checks", detected["tests"].get("checks"), ["pnpm run typecheck", "pnpm run lint"])
check("detect: playwright e2e", "playwright test" in detected["tests"].get("e2e_command", ""), True)
check("detect: prisma data", (detected["data"]["orm"], detected["data"]["schema"], detected["data"]["migrations"]),
      ("prisma", "apps/api/prisma/schema.prisma", "apps/api/prisma/migrations/*"))
check("detect: postgres in summary", "Prisma (postgresql) in apps/api/" in detected["project"]["summary"], True)
check("detect: App Router in summary", "Next.js app (App Router) in apps/web/" in detected["project"]["summary"], True)
check("detect: commitlint -> subject pattern", "subject_pattern" in detected["git"].get("commit", {}), True)
d.run(["profile", "init"])
check("detect: generated profile passes check", d.run(["profile", "check"]).startswith("warning") or "Profile OK" in d.run(["profile", "check"]), True)
gen = Project.__new__(Project)
gen.root, gen.env = d.root, d.env
gen.run(["lifecycle", "start", "feature", "detected"])
gen.bash("A", "delivery-kit lifecycle claim")
gen.edit("A", "apps/web/app/page.tsx")
gen.bash("A", "cd apps/web && pnpm exec vitest run app", " Tests  3 passed (3)")
check("detect: generated web suite clears on its own command", gen.status().get("untested_suites"), [])
gen.edit("A", "apps/api/src/index.ts")
gen.bash("A", "cd apps/web && pnpm exec vitest run", " Tests  3 passed (3)")
check("detect: web run doesn't clear generated api suite", gen.status().get("untested_suites"), ["api"])
gen.bash("A", "pnpm --filter @acme/api test", "Tests:       5 passed, 5 total")
check("detect: filter by package name clears api", gen.status().get("untested_suites"), [])
d.close()

s = Project(None)
write(s.root, "package.json", {"name": "shop", "dependencies": {"next": "15", "@prisma/client": "6"},
                               "devDependencies": {"prisma": "6", "vitest": "3", "typescript": "5"}, "scripts": {"lint": "next lint"}})
write(s.root, "package-lock.json", "{}")
write(s.root, "prisma/schema.prisma", 'datasource db {\n  provider = "mysql"\n  url = env("DATABASE_URL")\n}\n')
os.makedirs(f"{s.root}/src/app")
single = json.loads(s.run(["profile", "init", "--print"]).split("\nnote:")[0])
check("detect single: npx vitest command", single["tests"].get("command"), "npx vitest run {target}")
check("detect single: no suites", "suites" in single["tests"], False)
check("detect single: checks", single["tests"].get("checks"), ["npx tsc --noEmit", "npm run lint"])
check("detect single: prisma check command", single["data"]["check_command"],
      "npx prisma validate --schema prisma/schema.prisma && npx prisma migrate status --schema prisma/schema.prisma")
s.close()

e = Project(None)
write(e.root, "package.json", {"name": "orders", "dependencies": {"express": "5", "@prisma/client": "6"},
                               "devDependencies": {"jest": "30", "prisma": "6"}})
write(e.root, "yarn.lock", "")
write(e.root, "prisma/schema.prisma", 'datasource db {\n  provider = "postgresql"\n  url = env("DATABASE_URL")\n}\n')
express = json.loads(e.run(["profile", "init", "--print"]).split("\nnote:")[0])
check("detect express: yarn jest", express["tests"].get("command"), "yarn jest {target}")
check("detect express: stack", express["project"]["stack"], ["express", "prisma"])
e.run(["profile", "init"])
check("detect express: brief warns about destructive prisma", "prisma migrate reset" in e.run(["brief"]), True)
e.close()

failures = 0
for name, got, expected in results:
    failures += got != expected
    print(f"{'ok  ' if got == expected else 'FAIL'} {name}: {got!r}")
print("failures:", failures)
sys.exit(1 if failures else 0)
