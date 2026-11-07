import json
import re
import time

PHASES = ["understand", "plan", "implement", "test", "review", "ship"]


def state_file(profile):
    return profile.state_dir / "active.json"


def load_state(profile):
    try:
        return json.loads(state_file(profile).read_text())
    except (OSError, ValueError):
        return None


def save_state(profile, state):
    profile.state_dir.mkdir(parents=True, exist_ok=True)
    target = state_file(profile)
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2))
    tmp.replace(target)


def gate_enabled(profile, environ):
    if environ.get("LIFECYCLE_GATE", "on").lower() == "off":
        return False
    return bool(profile.get("lifecycle", "enabled", default=True))


def owned_state(profile, payload):
    state = load_state(profile)
    if not state or not state.get("owner"):
        return None
    session_id = payload.get("session_id")
    if session_id and session_id != state["owner"]:
        return None
    return state


def untested_suites(state):
    suites = state.get("untested_suites")
    if suites is None:
        return ["default"] if state.get("untested") else []
    return list(suites)


def mark_untested(state, names):
    suites = untested_suites(state)
    for name in names:
        if name not in suites:
            suites.append(name)
    state["untested_suites"] = suites
    state["untested"] = bool(suites)


def mark_tested(state, names):
    suites = [name for name in untested_suites(state) if name not in names]
    state["untested_suites"] = suites
    state["untested"] = bool(suites)


def untested_reason(profile, state):
    suites = untested_suites(state)
    if not suites:
        return None
    named = [name for name in suites if name != "default"]
    which = f" in suite(s) {', '.join(named)}" if named else ""
    return f"code changed{which} since the last passing test run. Run the targeted tests: {profile.test_hint(suites)}"


def ship_problem(profile, state):
    slug = state["slug"]
    reason = untested_reason(profile, state)
    if reason:
        return f"Lifecycle '{slug}': {reason}."
    if state.get("graph_stale") and profile.get("graph", "require_before_ship", default=True):
        command = profile.get("graph", "update_command") or "graphify update ."
        return f"Lifecycle '{slug}': the code graph is older than your changes. Run `{command}` and confirm it reflects the change."
    review = state.get("review")
    if not review:
        return f"Lifecycle '{slug}': no review recorded. Run the Review phase, then: delivery-kit lifecycle review --open-high <N>."
    if review.get("open_high", 0) > 0:
        return f"Lifecycle '{slug}': {review['open_high']} Critical/High review finding(s) still open. Fix them, re-test, and record the review again."
    return None


def test_outcome(profile, text, exit_code):
    if exit_code not in (None, 0):
        return "failed"
    fail = profile.regex("tests", "fail_pattern")
    passed = profile.regex("tests", "pass_pattern")
    if fail and fail.search(text):
        return "failed"
    if passed and passed.search(text):
        return "passed"
    return None


def slugify(text):
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:60] or "change"


def require_state(profile):
    state = load_state(profile)
    if not state:
        raise SystemExit("No active lifecycle. Start one: delivery-kit lifecycle start <fix|feature> <slug>")
    return state


def start(profile, args):
    if len(args) < 2 or args[0] not in ("fix", "feature"):
        raise SystemExit("usage: delivery-kit lifecycle start <fix|feature> <slug or title>")
    existing = load_state(profile)
    if existing:
        raise SystemExit(f"Lifecycle '{existing['slug']}' is already active. End it first: delivery-kit lifecycle end [--abort]")
    slug = slugify(" ".join(args[1:]))
    folder = profile.state_dir / slug
    folder.mkdir(parents=True, exist_ok=True)
    plan = (folder / "plan.md").relative_to(profile.root).as_posix()
    save_state(profile, {
        "slug": slug,
        "type": args[0],
        "phase": "understand",
        "started": time.time(),
        "untested": False,
        "untested_suites": [],
        "plan": plan,
    })
    print(f"Lifecycle '{slug}' started. Plan path: {plan}")


def phase(profile, args):
    state = require_state(profile)
    if not args or args[0] not in PHASES:
        raise SystemExit(f"usage: delivery-kit lifecycle phase <{'|'.join(PHASES)}>")
    state["phase"] = args[0]
    save_state(profile, state)
    print(f"Lifecycle '{state['slug']}' phase: {args[0]}")


def review(profile, args):
    state = require_state(profile)
    if len(args) != 2 or args[0] != "--open-high" or not args[1].isdigit():
        raise SystemExit("usage: delivery-kit lifecycle review --open-high <N>")
    state["review"] = {"at": time.time(), "open_high": int(args[1])}
    save_state(profile, state)
    print(f"Lifecycle '{state['slug']}' review recorded: {args[1]} open Critical/High.")


def status(profile, _args):
    state = load_state(profile)
    print(json.dumps(state, indent=2) if state else "No active lifecycle.")


def claim(profile, _args):
    state = require_state(profile)
    if state.get("owner"):
        print(f"Lifecycle '{state['slug']}' is already owned by session {state['owner']}.")
    else:
        print(f"Lifecycle '{state['slug']}' will be owned by this session once the hook records this command.")


def end(profile, args):
    state = require_state(profile)
    aborted = "--abort" in args
    if not aborted:
        problem = ship_problem(profile, state)
        if problem:
            raise SystemExit(problem + " (or end with --abort)")
    history = profile.state_dir / state["slug"] / "state.json"
    state["ended"] = time.time()
    state["aborted"] = aborted
    history.parent.mkdir(parents=True, exist_ok=True)
    history.write_text(json.dumps(state, indent=2))
    state_file(profile).unlink()
    print(f"Lifecycle '{state['slug']}' {'aborted' if aborted else 'ended'}.")


COMMANDS = {
    "start": start,
    "phase": phase,
    "review": review,
    "status": status,
    "claim": claim,
    "end": end,
}
