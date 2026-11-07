import json
import os
import re
import sys
import time

from . import commands, lifecycle


def read_payload():
    try:
        return json.loads(sys.stdin.read() or "{}")
    except ValueError:
        return {}


def deny(reason):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))


def tool_input(payload):
    return payload.get("tool_input") or {}


def output_text(response):
    if isinstance(response, str):
        return response
    if isinstance(response, dict):
        return "\n".join(str(response.get(key) or "") for key in ("stdout", "stderr", "output"))
    return ""


def exit_code_of(response):
    if isinstance(response, dict):
        for key in ("exit_code", "exitCode", "returncode", "return_code"):
            if isinstance(response.get(key), int):
                return response[key]
    return None


def claim_if_unowned(profile, payload, command):
    state = lifecycle.load_state(profile)
    session_id = payload.get("session_id")
    if not state or state.get("owner") or not session_id:
        return
    if commands.is_lifecycle_claim(command):
        state["owner"] = session_id
        lifecycle.save_state(profile, state)


def post_edit(profile, payload):
    state = lifecycle.owned_state(profile, payload)
    if not state:
        return
    data = tool_input(payload)
    file_path = data.get("file_path") or data.get("notebook_path")
    if profile.is_tracked_code(file_path):
        lifecycle.mark_untested(state, profile.suites_for_file(file_path))
        if profile.graph_active:
            state["graph_stale"] = True
        state["last_edit"] = {"at": time.time(), "file": profile.relative(file_path)}
        lifecycle.save_state(profile, state)


GRAPH_FAILURE = re.compile(r"Traceback|\berror\b|refus", re.I)


def track_graph_update(profile, state, command, response):
    match = profile.regex("graph", "update_match")
    if not state.get("graph_stale") or not match or not match.search(command):
        return False
    code = exit_code_of(response)
    if code not in (None, 0) or GRAPH_FAILURE.search(output_text(response)):
        return False
    state["graph_stale"] = False
    state["last_graph_update"] = {"at": time.time(), "command": command}
    return True


def post_bash(profile, payload):
    command = tool_input(payload).get("command") or ""
    claim_if_unowned(profile, payload, command)
    state = lifecycle.owned_state(profile, payload)
    if not state:
        return
    response = payload.get("tool_response")
    if track_graph_update(profile, state, command, response):
        lifecycle.save_state(profile, state)
        return
    suites = profile.suites_run_by(command)
    if not suites:
        return
    outcome = lifecycle.test_outcome(profile, output_text(response), exit_code_of(response))
    if outcome is None:
        return
    state["last_test"] = {"at": time.time(), "command": command, "suites": suites, "outcome": outcome}
    if outcome == "passed":
        lifecycle.mark_tested(state, suites)
    lifecycle.save_state(profile, state)


def pre_bash(profile, payload):
    command = tool_input(payload).get("command") or ""
    problem = commands.commit_format_problem(profile, command) or commands.pr_body_problem(profile, command)
    if problem:
        deny(problem)
        return
    if not lifecycle.gate_enabled(profile, os.environ) or not commands.is_ship_command(command):
        return
    state = lifecycle.owned_state(profile, payload)
    if not state:
        return
    problem = lifecycle.ship_problem(profile, state)
    if problem:
        deny(problem)


def stop(profile, payload):
    if payload.get("stop_hook_active") or not lifecycle.gate_enabled(profile, os.environ):
        return
    state = lifecycle.owned_state(profile, payload)
    if not state:
        return
    reasons = []
    untested = lifecycle.untested_reason(profile, state)
    if untested:
        reasons.append(untested)
    review = state.get("review")
    if review and review.get("open_high", 0) > 0:
        reasons.append(f"{review['open_high']} Critical/High review finding(s) are still open")
    if reasons:
        print(json.dumps({
            "decision": "block",
            "reason": f"Lifecycle '{state['slug']}' (phase: {state.get('phase')}): "
            + "; ".join(reasons)
            + ". Resolve this, or tell the user why you are stopping.",
        }))


HOOKS = {
    "post-edit": post_edit,
    "post-bash": post_bash,
    "pre-bash": pre_bash,
    "stop": stop,
}
