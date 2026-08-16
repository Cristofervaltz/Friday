"""Robust JSON repair and parsing utility for LLM outputs."""

from __future__ import annotations

import ast
import json
import re
from typing import Any


def repair_json(json_str: str) -> Any:
    """Attempt to parse and repair malformed JSON text locally.

    Handles common LLM formatting anomalies:
    - Top-level Markdown code block fences (```json ... ``` and unclosed fences)
    - JavaScript and Python style comments (//, /* */, #) outside strings
    - Extraneous commentary text surrounding JSON objects or arrays
    - Trailing commas in objects and arrays
    - Single quotes instead of double quotes with proper quote escaping
    - Unquoted dictionary keys ({name: "val", key-dash: "val"}) without corrupting strings
    - Unclosed strings, braces, brackets, and truncated mid-token key/value cutoffs
    - Python literals (True, False, None) and JS constants (undefined, NaN) outside strings
    - Unescaped control characters and literal newlines inside string literals

    Args:
        json_str: Raw JSON or pseudo-JSON string.

    Returns:
        Parsed Python object (dict, list, etc.).

    Raises:
        json.JSONDecodeError: If all repair strategies fail.
    """
    if not isinstance(json_str, str):
        return json_str

    text = json_str.strip()
    if not text:
        raise json.JSONDecodeError("Empty JSON string", "", 0)

    # Strategy 1: Direct parse with strict=False (allows unescaped control chars / newlines)
    try:
        return json.loads(text, strict=False)
    except json.JSONDecodeError:
        pass

    # Strategy 2: Strip top-level code fences if present
    cleaned = _strip_top_level_code_fences(text)
    try:
        return json.loads(cleaned, strict=False)
    except json.JSONDecodeError:
        pass

    # Strategy 3: Search for outermost candidate JSON blocks
    candidates = _find_json_candidates(cleaned)
    targets = [cleaned]
    for cand in candidates:
        if cand not in targets:
            targets.append(cand)

    for cand in candidates:
        try:
            return json.loads(cand, strict=False)
        except json.JSONDecodeError:
            pass

    # Strategy 4: Normalize and parse targets using character scanner
    for target in targets:
        try:
            normalized = _normalize_json_text(target)
            return json.loads(normalized, strict=False)
        except Exception:
            pass

    # Strategy 5: Truncation balance on normalized targets
    for target in targets:
        try:
            normalized = _normalize_json_text(target)
            balanced = _balance_and_repair_truncation(normalized)
            return json.loads(balanced, strict=False)
        except Exception:
            pass

    # Strategy 6: Truncation balance on raw target
    for target in targets:
        try:
            balanced = _balance_and_repair_truncation(target)
            return json.loads(balanced, strict=False)
        except Exception:
            pass

    # Strategy 7: Python AST literal_eval fallback
    for target in targets:
        try:
            evaluated = ast.literal_eval(target)
            if (
                isinstance(evaluated, (dict, list, str, int, float, bool))
                or evaluated is None
            ):
                return evaluated
        except Exception:
            pass

    # Final attempt: standard JSONDecodeError
    return json.loads(text)


def safe_json_loads(json_str: str, default: Any = None) -> tuple[Any, bool]:
    """Safely parse JSON with repair fallback, returning (result, success).

    Args:
        json_str: JSON string to parse.
        default: Fallback value if parsing fails completely.

    Returns:
        Tuple of (parsed_value_or_default, success_boolean).
    """
    try:
        result = repair_json(json_str)
        return result, True
    except Exception:
        return default, False


def _strip_top_level_code_fences(text: str) -> str:
    """Remove markdown code blocks such as ```json ... ``` only if they wrap the payload."""
    trimmed = text.strip()
    fence_match = re.match(
        r"^```(?:json|python)?\s*([\s\S]*?)\s*```$", trimmed, re.IGNORECASE
    )
    if fence_match:
        return fence_match.group(1).strip()

    leading_match = re.match(
        r"^```(?:json|python)?\s*([\s\S]*)$", trimmed, re.IGNORECASE
    )
    if leading_match:
        content = leading_match.group(1).strip()
        if content.endswith("```"):
            content = content[:-3].strip()
        return content

    return trimmed


def _find_json_candidates(text: str) -> list[str]:
    """Find JSON object or array candidate substrings in text, outermost first."""
    candidates = []
    n = len(text)
    idx = 0
    while idx < n:
        ch = text[idx]
        if ch in "{[":
            start_char = ch
            end_char = "}" if start_char == "{" else "]"
            start_idx = idx

            depth = 0
            in_dquote = False
            in_squote = False
            escape = False
            found_end = -1

            for j in range(start_idx, n):
                c = text[j]
                if escape:
                    escape = False
                    continue
                if c == "\\":
                    escape = True
                    continue
                if c == '"' and not in_squote:
                    in_dquote = not in_dquote
                    continue
                if c == "'" and not in_dquote:
                    in_squote = not in_squote
                    continue
                if in_dquote or in_squote:
                    continue

                if c == start_char:
                    depth += 1
                elif c == end_char:
                    depth -= 1
                    if depth == 0:
                        found_end = j
                        break

            if found_end != -1:
                cand = text[start_idx : found_end + 1].strip()
                if cand and cand not in candidates:
                    candidates.append(cand)
                idx = found_end + 1
            else:
                cand = text[start_idx:].strip()
                if cand and cand not in candidates:
                    candidates.append(cand)
                break
        else:
            idx += 1

    return candidates


def _is_number(val: str) -> bool:
    """Check if a string represents a valid numeric constant."""
    if not val:
        return False
    if val.lower() in ("nan", "inf", "-inf", "+inf", "infinity", "-infinity"):
        return False
    try:
        float(val)
        return True
    except ValueError:
        return False


def _normalize_json_text(text: str) -> str:
    """Normalize text into valid JSON syntax using a stateful character scanner."""
    result: list[str] = []
    in_dquote = False
    in_squote = False
    escape = False
    expecting_key = False
    last_sig_char = ""
    i = 0
    n = len(text)

    while i < n:
        ch = text[i]

        # 1. Escape sequences
        if escape:
            if in_squote:
                if ch == "'":
                    result.append("'")
                elif ch == '"':
                    result.append('\\"')
                else:
                    result.append("\\" + ch)
            else:
                result.append("\\" + ch)
            escape = False
            i += 1
            continue

        if ch == "\\":
            escape = True
            i += 1
            continue

        # 2. String handling
        if ch == '"' and not in_squote:
            in_dquote = not in_dquote
            result.append('"')
            if not in_dquote:
                last_sig_char = '"'
                expecting_key = False
            else:
                expecting_key = False
            i += 1
            continue

        if ch == "'" and not in_dquote:
            in_squote = not in_squote
            result.append('"')
            if not in_squote:
                last_sig_char = '"'
                expecting_key = False
            else:
                expecting_key = False
            i += 1
            continue

        if in_dquote:
            result.append(ch)
            i += 1
            continue

        if in_squote:
            if ch == '"':
                result.append('\\"')
            else:
                result.append(ch)
            i += 1
            continue

        # 3. Outside strings: Comments
        if ch == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] != "\n":
                i += 1
            continue

        if ch == "#":
            while i < n and text[i] != "\n":
                i += 1
            continue

        if ch == "/" and i + 1 < n and text[i + 1] == "*":
            i += 2
            while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2
            continue

        # 4. Whitespace outside strings
        if ch.isspace():
            result.append(ch)
            i += 1
            continue

        # 5. Structure markers outside strings
        if ch in "{[":
            result.append(ch)
            last_sig_char = ch
            expecting_key = ch == "{"
            i += 1
            continue

        if ch in "}]":
            result.append(ch)
            last_sig_char = ch
            expecting_key = False
            i += 1
            continue

        if ch == ":":
            result.append(ch)
            last_sig_char = ch
            expecting_key = False
            i += 1
            continue

        if ch == ",":
            # Check for trailing comma before } or ]
            j = i + 1
            while j < n and (text[j].isspace() or text[j] == "/" or text[j] == "#"):
                if text[j] == "/" and j + 1 < n and text[j + 1] == "/":
                    while j < n and text[j] != "\n":
                        j += 1
                elif text[j] == "#":
                    while j < n and text[j] != "\n":
                        j += 1
                elif text[j] == "/" and j + 1 < n and text[j + 1] == "*":
                    j += 2
                    while j + 1 < n and not (text[j] == "*" and text[j + 1] == "/"):
                        j += 1
                    j += 2
                else:
                    j += 1

            if j < n and text[j] in "}]":
                # Skip trailing comma
                i += 1
                continue

            result.append(ch)
            last_sig_char = ch
            expecting_key = last_sig_char == "," and _is_inside_object_context(result)
            i += 1
            continue

        # 6. Identifier / Word scanning (unquoted keys or Python/JS constants)
        if ch.isalnum() or ch in "_-.$":
            start_pos = i
            while i < n and (text[i].isalnum() or text[i] in "_-.$"):
                i += 1
            word = text[start_pos:i]

            # Look ahead to check if followed by colon ':'
            j = i
            while j < n and text[j].isspace():
                j += 1
            is_key = j < n and text[j] == ":"

            if is_key or expecting_key:
                result.append(f'"{word}"')
                last_sig_char = '"'
                expecting_key = False
            elif word in ("true", "false", "null"):
                result.append(word)
                last_sig_char = word[-1]
            elif word == "True":
                result.append("true")
                last_sig_char = "e"
            elif word == "False":
                result.append("false")
                last_sig_char = "e"
            elif word in ("None", "undefined", "NaN"):
                result.append("null")
                last_sig_char = "l"
            elif _is_number(word):
                if word.startswith("+"):
                    result.append(word[1:])
                else:
                    result.append(word)
                last_sig_char = word[-1]
            else:
                # Bare unquoted string literal in value position (e.g. {status: active} or [apple, banana])
                result.append(f'"{word}"')
                last_sig_char = '"'
            continue

        # Other characters
        result.append(ch)
        last_sig_char = ch
        i += 1

    return "".join(result)


def _is_inside_object_context(result_tokens: list[str]) -> bool:
    """Check if the current position is within a JSON object (as opposed to array)."""
    stack = []
    in_str = False
    escape = False
    for ch in "".join(result_tokens):
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch in "{[":
            stack.append(ch)
        elif ch == "}" and stack and stack[-1] == "{":
            stack.pop()
        elif ch == "]" and stack and stack[-1] == "[":
            stack.pop()
    return bool(stack and stack[-1] == "{")


def _balance_and_repair_truncation(text: str) -> str:
    """Balance unclosed quotes, brackets, and repair trailing cutoffs."""
    in_dquote = False
    in_squote = False
    escape = False
    stack: list[str] = []

    for ch in text:
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"' and not in_squote:
            in_dquote = not in_dquote
            continue
        if ch == "'" and not in_dquote:
            in_squote = not in_squote
            continue
        if in_dquote or in_squote:
            continue

        if ch in "{[":
            stack.append(ch)
        elif ch == "}":
            if stack and stack[-1] == "{":
                stack.pop()
        elif ch == "]":
            if stack and stack[-1] == "[":
                stack.pop()

    result = text
    # 1. Close open string
    if in_dquote or in_squote:
        result += '"'

    # 2. Inspect end of string outside quotes for dangling operators/keys
    trimmed = result.rstrip()
    if trimmed.endswith(":"):
        # e.g. {"key": -> {"key": null
        result = trimmed + " null"
    elif trimmed.endswith(","):
        # e.g. {"key": 1, -> {"key": 1
        result = trimmed[:-1].rstrip()
    else:
        # Check if it ended in an incomplete key in an object: e.g. {"a": 1, "incomplete"
        if stack and stack[-1] == "{":
            last_delim_idx = max(result.rfind("{"), result.rfind(","))
            if last_delim_idx != -1:
                after = result[last_delim_idx + 1 :].strip()
                if after and ":" not in after:
                    result += ": null"

    # 3. Remove any trailing comma before balancing
    trimmed = result.rstrip()
    if trimmed.endswith(","):
        result = trimmed[:-1].rstrip()

    # 4. Close all open delimiters in reverse order
    while stack:
        opener = stack.pop()
        if opener == "{":
            result += "}"
        elif opener == "[":
            result += "]"

    return result
