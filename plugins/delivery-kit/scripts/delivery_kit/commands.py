import re
import shlex
from pathlib import Path

SEPARATORS = {"&&", "||", ";", "|", "&", "\n"}
GIT_OPTIONS_WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace"}
COMMIT_CMD = re.compile(r"\bgit\b.*\bcommit\b", re.S)
SHIP_CMD = re.compile(r"\bgit\b.*\b(commit|push)\b|\bgh\s+pr\s+create\b", re.S)
PR_BODY_CMD = re.compile(r"\bgh\s+pr\s+(create|edit)\b")
SHIP_COMMANDS = (["git", "commit"], ["git", "push"], ["gh", "pr", "create"])


def split_tokens(command):
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    return list(lexer)


def parsed_tokens(command):
    try:
        return split_tokens(command)
    except ValueError:
        return None


def find_command(tokens, words):
    for start, token in enumerate(tokens):
        if token != words[0] or (start > 0 and tokens[start - 1] not in SEPARATORS | {"(", "$("}):
            continue
        index = start + 1
        matched = True
        for word in words[1:]:
            while index < len(tokens) and tokens[index].startswith("-") and tokens[index] not in SEPARATORS:
                index += 2 if tokens[index] in GIT_OPTIONS_WITH_VALUE else 1
            if index >= len(tokens) or tokens[index] != word:
                matched = False
                break
            index += 1
        if not matched:
            continue
        segment = []
        for item in tokens[index:]:
            if item in SEPARATORS:
                break
            segment.append(item)
        return segment
    return None


def option_values(segment, short_flag, long_flag):
    values = []
    letter = short_flag.lstrip("-")
    index = 0
    while index < len(segment):
        token = segment[index]
        next_token = segment[index + 1] if index + 1 < len(segment) else None
        if token == long_flag:
            if next_token is not None:
                values.append(next_token)
            index += 2
            continue
        if token.startswith(long_flag + "="):
            values.append(token.split("=", 1)[1])
        elif token.startswith("-") and not token.startswith("--") and letter in token[1:]:
            rest = token[1:][token[1:].index(letter) + 1:]
            if rest:
                values.append(rest)
            elif next_token is not None:
                values.append(next_token)
                index += 1
        index += 1
    return values


def read_file_text(root, path_text):
    path = Path(path_text)
    if not path.is_absolute():
        path = Path(root) / path
    try:
        return path.read_text()
    except OSError:
        return ""


def is_ship_command(command):
    if not SHIP_CMD.search(command):
        return False
    tokens = parsed_tokens(command)
    if tokens is None:
        return True
    return any(find_command(tokens, words) is not None for words in SHIP_COMMANDS)


def forbidden_match(patterns, texts):
    for pattern in patterns:
        try:
            compiled = re.compile(pattern, re.I)
        except re.error:
            continue
        for text in texts:
            if compiled.search(text):
                return pattern
    return None


def commit_format_problem(profile, command):
    rules = profile.get("git", "commit", default={})
    single_line = rules.get("single_line")
    subject_pattern = rules.get("subject_pattern")
    forbid = rules.get("forbid_patterns") or []
    if not (single_line or subject_pattern or forbid) or not COMMIT_CMD.search(command):
        return None
    name = profile.name
    tokens = parsed_tokens(command)
    if tokens is None:
        return "Could not parse the commit command. Use a single message: git commit -m \"<summary>\"."
    segment = find_command(tokens, ["git", "commit"])
    if segment is None:
        return None
    hit = forbidden_match(forbid, segment)
    if hit:
        return f"Commit messages in {name} must not match '{hit}' (git.commit.forbid_patterns)."
    messages = option_values(segment, "-m", "--message")
    for file_path in option_values(segment, "-F", "--file"):
        messages.append(read_file_text(profile.root, file_path).strip())
    hit = forbidden_match(forbid, messages)
    if hit:
        return f"Commit messages in {name} must not match '{hit}' (git.commit.forbid_patterns)."
    if single_line:
        if len(messages) > 1:
            return f"Commit messages in {name} must be one line. Use a single -m with a one-line message."
        for message in messages:
            if "\n" in message.strip() or "$(" in message:
                return f"Commit messages in {name} must be one line, with no heredoc or body. Use git commit -m \"<summary>\"."
    if subject_pattern and messages and "$(" not in messages[0]:
        subject = messages[0].strip().splitlines()[0] if messages[0].strip() else ""
        try:
            if not re.search(subject_pattern, subject):
                return f"Commit subject '{subject}' does not match {name}'s format: {subject_pattern} (git.commit.subject_pattern)."
        except re.error:
            return None
    return None


def pr_body_problem(profile, command):
    forbid = profile.get("git", "pr", "forbid_patterns", default=[]) or []
    if not forbid or not PR_BODY_CMD.search(command):
        return None
    tokens = parsed_tokens(command)
    if tokens is None:
        return None
    texts = []
    for second in ("create", "edit"):
        segment = find_command(tokens, ["gh", "pr", second])
        if segment is not None:
            texts.extend(segment)
            for file_path in option_values(segment, "-F", "--body-file"):
                texts.append(read_file_text(profile.root, file_path))
    hit = forbidden_match(forbid, texts)
    if hit:
        return f"PR titles and bodies in {profile.name} must not match '{hit}' (git.pr.forbid_patterns)."
    return None


def is_lifecycle_claim(command):
    tokens = parsed_tokens(command)
    if tokens is None:
        return False
    for index, token in enumerate(tokens[:-2]):
        if Path(token).name in ("delivery-kit", "delivery_kit_main.py") and tokens[index + 1] == "lifecycle":
            return tokens[index + 2] in ("start", "claim")
    return False
