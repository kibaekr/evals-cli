#!/usr/bin/env python3
"""evals: run one brief on up to eight AI setups through Evals.ag, from Claude Code, Codex or a terminal."""
from __future__ import annotations

import argparse
import base64
import concurrent.futures
import hashlib
import json
import mimetypes
import os
import re
import secrets
import stat
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE = "https://evals.ag"
TOKEN = re.compile(r"evcli_[A-Za-z0-9_-]{43}")
PLAN_ID = re.compile(r"req_[0-7][0-9A-HJKMNP-TV-Z]{25}")
RUN_ID = re.compile(r"run_[0-7][0-9A-HJKMNP-TV-Z]{25}")
DONE = {"completed", "failed", "cancelled", "waiting_for_input"}
PAYER = {
    "openrouter": "OpenRouter · Evals Balance",
    "codex": "Connected ChatGPT Account",
    "claude_subscription": "Connected Claude Account",
}


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        self.status = status
        super().__init__(message)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def origin() -> str:
    raw = os.environ.get("EVALS_CLI_ORIGIN", BASE).rstrip("/")
    parsed = urllib.parse.urlsplit(raw)
    local = parsed.hostname in {"127.0.0.1", "::1", "localhost"}
    if (
        not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path or parsed.query or parsed.fragment
        or not (parsed.scheme == "https" or (parsed.scheme == "http" and local))
    ):
        raise ValueError("EVALS_CLI_ORIGIN must be an HTTPS origin or loopback HTTP.")
    return raw


def state_dir() -> Path:
    path = Path(os.environ.get("EVALS_CLI_HOME", "~/.config/evals")).expanduser()
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    mode = path.lstat()
    if not stat.S_ISDIR(mode.st_mode) or (
        os.name == "posix" and (mode.st_mode & 0o077 or mode.st_uid != os.getuid())
    ):
        raise ValueError("Use an Evals CLI directory owned by you with mode 0700.")
    return path


def load_state(path: Path) -> dict:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(descriptor, encoding="utf-8") as file:
        mode = os.fstat(file.fileno())
        if not stat.S_ISREG(mode.st_mode) or (
            os.name == "posix" and (mode.st_mode & 0o077 or mode.st_uid != os.getuid())
        ):
            raise ValueError("Evals CLI state files must be owned by you with mode 0600.")
        if mode.st_size > 512_000:
            raise ValueError("Evals CLI state file is too large.")
        state = json.load(file)
    if not isinstance(state, dict):
        raise ValueError("Invalid Evals CLI state file.")
    return state


def save_state(path: Path, state: dict) -> None:
    descriptor, name = tempfile.mkstemp(prefix=".evals-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            json.dump(state, file, ensure_ascii=False)
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def credential(site: str) -> dict:
    try:
        saved = load_state(state_dir() / "device.json")
    except FileNotFoundError as error:
        raise ValueError("Run evals login to connect your account.") from error
    token = saved.get("token")
    if saved.get("origin") != site or not isinstance(token, str) or not TOKEN.fullmatch(token):
        raise ValueError("This device credential is for another Evals origin. Run evals login.")
    return saved


def api(site: str, path: str, *, method: str = "GET", token: str | None = None, body: dict | None = None, timeout: int = 20) -> Any:
    headers = {"Accept": "application/json", "User-Agent": "evals-cli/0.4"}
    if token:
        headers["Authorization"] = "Bearer " + token
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode()
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(site + "/api/v1" + path, headers=headers, method=method, data=data)
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=timeout) as response:
            return None if response.status == 204 else json.load(response)
    except urllib.error.HTTPError as error:
        if error.code == 422:
            raise ApiError(error.code, "Evals rejected the request fields.") from error
        with error:
            try:
                payload = json.loads(error.read(4096))
                detail = payload.get("detail")
            except (ValueError, AttributeError):
                detail = None
        message = detail if isinstance(detail, str) and error.code < 500 else f"Evals returned HTTP {error.code}."
        raise ApiError(error.code, message) from error


def upload_file(site: str, token: str, path: Path) -> Any:
    """Send one local file as multipart/form-data. Standard library only."""
    if not path.is_file():
        raise ValueError(f"No file at {path}.")
    boundary = "evals-" + secrets.token_hex(16)
    name = path.name.replace('"', "_").replace("\r", "_").replace("\n", "_")
    kind = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    data = path.read_bytes()
    # The same file under the same name is the same input on a retry, never a duplicate.
    request_id = uuid.uuid5(uuid.NAMESPACE_URL, f"evals-cli-upload:{hashlib.sha256(data).hexdigest()}:{name}")
    body = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="request_id"\r\n\r\n{request_id}\r\n'
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{name}"\r\n'
        f"Content-Type: {kind}\r\n\r\n"
    ).encode() + data + f"\r\n--{boundary}--\r\n".encode()
    request = urllib.request.Request(
        site + "/api/v1/cli/uploads", method="POST", data=body,
        headers={
            "Accept": "application/json", "User-Agent": "evals-cli/0.4", "Authorization": "Bearer " + token,
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=300) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        with error:
            try:
                detail = json.loads(error.read(4096)).get("detail")
            except (ValueError, AttributeError):
                detail = None
        raise ApiError(error.code, detail if isinstance(detail, str) and error.code < 500 else f"Evals returned HTTP {error.code}.") from error


def output(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def search(kind: str, query: str, limit: int) -> dict:
    if kind not in ("skills", "tasks", "outputs"):
        raise ValueError("Choose skills, tasks or outputs.")
    if not query.strip() or len(query) > 250:
        raise ValueError("Enter a search term of 1 to 250 characters.")
    if not 1 <= limit <= 30:
        raise ValueError("Limit must be between 1 and 30.")
    params: dict[str, str | int] = {"q": query, "limit": limit}
    if kind == "skills":
        path = "/skills/search"
    else:
        path = "/catalog/search"
        params["kind"] = kind
    result = api(origin(), path + "?" + urllib.parse.urlencode(params))
    if not isinstance(result, dict) or not isinstance(result.get("items"), list):
        raise ValueError("Evals returned an unexpected response.")
    return result


def login(site: str, open_browser: bool) -> dict:
    folder = state_dir()
    try:
        saved = credential(site)
    except ValueError:
        saved = None
    if saved:
        try:
            return api(site, "/cli/me", token=saved["token"])
        except ApiError as error:
            if error.status != 401:
                raise
    token = "evcli_" + secrets.token_urlsafe(32)
    fingerprint = hashlib.sha256(token.encode()).hexdigest()
    url = site + "/settings/cli#pair=" + fingerprint
    print(f"Approve this device in Evals\n{url}\nDevice code: {fingerprint[:10].upper()}", file=sys.stderr, flush=True)
    if open_browser:
        webbrowser.open(url)
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        try:
            account = api(site, "/cli/me", token=token, timeout=8)
        except ApiError as error:
            if error.status != 401:
                raise
            time.sleep(3)
            continue
        save_state(folder / "device.json", {"origin": site, "token": token, "device_id": account["device"]["id"]})
        return account
    raise ValueError("Device approval expired. Run evals login again.")


def prompt_input(args: argparse.Namespace) -> str:
    if args.prompt_file == "-":
        prompt = sys.stdin.read(20_001)
    elif args.prompt_file:
        with Path(args.prompt_file).open(encoding="utf-8", newline="") as file:
            prompt = file.read(20_001)
    else:
        prompt = args.prompt or ""
    if not prompt.strip() or len(prompt) > 20_000:
        raise ValueError("Provide a brief of 1 to 20,000 characters.")
    return prompt


def plan_path(plan_id: str) -> Path:
    if not PLAN_ID.fullmatch(plan_id):
        raise ValueError("Enter the plan ID returned by evals prepare.")
    return state_dir() / f"{plan_id}.json"


def expires(plan: dict) -> datetime:
    return datetime.fromisoformat(plan["expires_at"].replace("Z", "+00:00"))


EFFORTS = ("none", "minimal", "low", "medium", "high", "xhigh", "max")
MAX_SETUPS = 8
SKILL_ID = re.compile(r"[A-Za-z0-9_-]{1,100}")


def parse_setup(spec: str) -> dict:
    """`model=ID[,gen=ID|auto|none][,skill=auto|none|ID]...[,effort=LEVEL]` -> one comparison option."""
    option: dict[str, Any] = {"model_id": None}
    skills: list[str] = []
    for part in filter(None, (piece.strip() for piece in spec.split(","))):
        key, sep, value = part.partition("=")
        key, value = key.strip().lower(), value.strip()
        if not sep or not value:
            raise ValueError(f"Write each setup part as key=value: {part!r}.")
        if key == "model":
            option["model_id"] = value
        elif key in ("gen", "generation"):
            option["generation"] = value
        elif key == "skill":
            if not SKILL_ID.fullmatch(value):
                raise ValueError(f"Not a skill ID: {value!r}. Use auto, none or an ID from evals search skills.")
            skills.append(value)
        elif key == "effort":
            if value not in EFFORTS:
                raise ValueError(f"Effort must be one of {', '.join(EFFORTS)}.")
            option["reasoning_effort"] = value
        else:
            raise ValueError(f"Unknown setup part {key!r}. Use model, gen, skill or effort.")
    if not option["model_id"]:
        raise ValueError("Each --setup needs model=ID. Run evals models for IDs.")
    if len(skills) > 1 and ({"auto", "none"} & set(skills)):
        raise ValueError("Use skill=auto or skill=none alone, or one or more skill IDs.")
    if len(skills) > 20:
        raise ValueError("A setup can use at most 20 skills.")
    if len(skills) > 1:
        option["skills"] = skills
    else:
        option["skill"] = skills[0] if skills else "auto"
    return option


def plan_body(args: argparse.Namespace) -> dict:
    body: dict[str, Any] = {
        "prompt": prompt_input(args),
        "visibility": args.visibility,
        "attachment_ids": (getattr(args, "input", None) or []) + (getattr(args, "attachment_id", None) or []),
    }
    if getattr(args, "suggestion", None):
        if args.setup or args.model or args.skill:
            raise ValueError("A Battle suggestion brings its own setups; leave out --setup, --model and --skill.")
        saved = json.loads(Path(args.suggestion).expanduser().read_text(encoding="utf-8"))
        if not isinstance(saved, dict) or not isinstance(saved.get("envelope"), str):
            raise ValueError("Pass the JSON file that evals suggest printed.")
        body["suggestion"] = saved["envelope"]
        return body
    if args.setup:
        if args.model or args.skill:
            raise ValueError("Use --setup, or --model with --skill, not both.")
        options = [parse_setup(spec) for spec in args.setup]
    else:
        models = args.model or []
        skills = args.skill or ["auto"] * len(models)
        if len(skills) != len(models):
            raise ValueError("Give one --skill per --model, or none.")
        options = [{"model_id": model, "skill": skill} for model, skill in zip(models, skills)]
    if not 2 <= len(options) <= MAX_SETUPS:
        raise ValueError(f"Choose 2 to {MAX_SETUPS} setups. Run evals models for IDs.")
    body["options"] = options
    return body


def prepare(site: str, device: dict, args: argparse.Namespace) -> dict:
    plan = api(site, "/cli/comparisons/prepare", method="POST", token=device["token"], body=plan_body(args), timeout=90)
    check_review(plan)
    path = plan_path(plan["id"])
    for prior in path.parent.glob("req_*.json"):
        if not PLAN_ID.fullmatch(prior.stem):
            continue
        try:
            if expires(load_state(prior)["plan"]) <= datetime.now(timezone.utc):
                prior.unlink(missing_ok=True)
        except (OSError, ValueError, KeyError, TypeError):
            continue
    save_state(path, {"origin": site, "device_id": device["device_id"], "plan": plan})
    return plan


def check_review(plan: dict) -> None:
    try:
        data = plan["envelope"].split(".", 1)[0]
        reviewed = json.loads(base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)))["review"]
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        raise ValueError("This comparison plan is invalid. Prepare it again.") from error
    if reviewed != {key: value for key, value in plan.items() if key != "envelope"}:
        raise ValueError("The saved review differs from the signed comparison. Prepare it again.")


def terminal_text(text: str) -> str:
    return "".join(char if char.isprintable() or char in "\n\t" else repr(char)[1:-1] for char in text)


def option_line(option: dict) -> str:
    payer = PAYER.get(option.get("route"), option.get("payer") or "unknown payer")
    skills = option.get("skills") or [option.get("skill", "auto")]
    skill = ", ".join({"none": "Don’t Use Skills", "auto": "Auto skills"}.get(s, s) for s in skills)
    gen = option.get("generation") or {"name": "Don’t Use"}
    gen_text = gen if isinstance(gen, str) else gen.get("name", "Don’t Use") + (f" ({gen['payer']})" if gen.get("choice") != "none" and gen.get("payer") else "")
    effort = f" · {option['reasoning_effort']} effort" if option.get("reasoning_effort") else ""
    return f"{option['name']} · {payer}{effort} · Gen AI: {gen_text} · {skill}"


def review(plan: dict) -> bool:
    if plan.get("battle"):
        print("Battle: setups chosen by Evals' planner for this brief.")
    print(terminal_text(plan["prompt"]))
    print(f"\nVisibility: {plan['visibility'].title()}")
    if plan["visibility"] == "public":
        print("Other people may see the brief, inputs, and outputs.")
    for index, option in enumerate(plan["options"], 1):
        print(terminal_text(f"{index}. {option_line(option)}"))
    if plan["attachments"]:
        print("Inputs:", terminal_text(", ".join(plan["attachments"])))
    if plan["paid_fallback"]:
        print("Eligible paid fallbacks can use your Evals balance.")
    print("Total cost is unknown before execution. Provider usage and Evals charges may apply.")
    return input("Start this comparison? [y/N] ").strip().lower() in {"y", "yes"}


def public_plan(plan: dict, site: str) -> dict:
    return {
        **{key: value for key, value in plan.items() if key != "envelope"},
        "review_url": site + "/runs/" + plan["run_id"],
        "total_cost": None,
        "review_lines": [option_line(option) for option in plan["options"]],
    }


def start(site: str, device: dict, plan: dict) -> dict:
    if expires(plan) <= datetime.now(timezone.utc):
        raise ValueError("This plan expired. Check its run status before preparing another comparison.")
    def submit(index: int) -> dict:
        try:
            attempt = api(
                site, "/cli/comparisons/start", method="POST", token=device["token"], timeout=115,
                body={"envelope": plan["envelope"], "index": index, "confirm_spend": True},
            )
            return {"setup_index": index, "outcome": "accepted", "attempt": attempt}
        except ApiError as error:
            if error.status in {400, 401, 403, 404, 409, 422}:
                return {"setup_index": index, "outcome": "refused", "error": str(error)}
            return {"setup_index": index, "outcome": "uncertain", "error": str(error)}
        except (OSError, ValueError, urllib.error.URLError):
            return {"setup_index": index, "outcome": "uncertain", "error": "No definitive response from Evals."}
    count = len(plan["options"])
    with concurrent.futures.ThreadPoolExecutor(max_workers=count) as pool:
        results = list(pool.map(submit, range(count)))
    return {"run_id": plan["run_id"], "review_url": site + "/runs/" + plan["run_id"], "options": results}


def run_status(site: str, device: dict, run_id: str) -> dict:
    if not RUN_ID.fullmatch(run_id):
        raise ValueError("Enter a run ID returned by Evals.")
    run = api(site, "/cli/runs/" + run_id, token=device["token"])
    return {**run, "review_url": site + "/runs/" + run_id}


def wait_for_run(site: str, device: dict, run_id: str, seconds: int) -> dict:
    deadline = time.monotonic() + seconds
    while True:
        run = run_status(site, device, run_id)
        latest = {row["setup_index"]: row for row in reversed(run["attempts"])}
        if len(latest) == run["setup_count"] and all(row["status"] in DONE for row in latest.values()):
            return {**run, "wait_timed_out": False}
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return {**run, "wait_timed_out": True}
        time.sleep(min(4, remaining))


SAFE_PART = re.compile(r"[^A-Za-z0-9._ -]+")


def safe_relative(name: str) -> Path:
    """A download path that cannot leave its folder."""
    parts = [SAFE_PART.sub("_", part).strip(" .") for part in name.replace("\\", "/").split("/")]
    parts = [part for part in parts if part and part not in {".", ".."}]
    if not parts:
        raise ValueError(f"Unusable file name from Evals: {name!r}")
    return Path(*parts)


def download(url: str, target: Path) -> int:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "::1", "localhost"}):
        raise ValueError(f"Refusing a non-HTTPS download: {url}")
    target.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "evals-cli/0.4"})
    with urllib.request.urlopen(request, timeout=300) as response, target.open("wb") as file:
        size = 0
        while chunk := response.read(1 << 20):
            file.write(chunk)
            size += len(chunk)
    return size


def results(site: str, device: dict, run_id: str, out: Path) -> dict:
    """Download every setup's latest result (final message and files) into out/setup-N/."""
    if not RUN_ID.fullmatch(run_id):
        raise ValueError("Enter a run ID returned by Evals.")
    data = api(site, f"/cli/runs/{run_id}/results", token=device["token"], timeout=60)
    out.mkdir(parents=True, exist_ok=True)
    manifest = {"run_id": run_id, "review_url": site + "/runs/" + run_id, "setups": [], "problems": []}
    for setup in data["setups"]:
        folder = f"setup-{setup['setup_index'] + 1}"
        entry = {
            "setup_index": setup["setup_index"], "label": setup.get("label") or folder, "dir": folder,
            "model": setup.get("model"), "generation": setup.get("generation"), "status": setup.get("status"),
            "attempt_id": setup.get("attempt_id"), "turns": setup.get("turns"), "elapsed_ms": setup.get("elapsed_ms"),
            "tokens": setup.get("tokens"), "charge_usd": setup.get("charge_usd"), "main_output": setup.get("main_output"),
            "output_id": setup.get("output_id"), "files": [],
        }
        base = out / folder
        base.mkdir(parents=True, exist_ok=True)
        if setup.get("final_message"):
            (base / "final_message.md").write_text(setup["final_message"], encoding="utf-8")
        for item in setup.get("files") or []:
            relative = safe_relative(item["name"])
            try:
                size = download(item["url"], base / relative)
                entry["files"].append({"name": item["name"], "path": str(base / relative), "bytes": size})
            except (OSError, ValueError, urllib.error.URLError) as error:
                manifest["problems"].append({"setup": folder, "file": item["name"], "error": str(error)})
        manifest["setups"].append(entry)
    save_state(out / "manifest.json", manifest)
    return manifest | {"folder": str(out)}


def continue_turn(site: str, device: dict, args: argparse.Namespace) -> dict:
    if not RUN_ID.fullmatch(args.run_id):
        raise ValueError("Enter a run ID returned by Evals.")
    body = {
        "setup_index": args.setup - 1,
        "prompt": prompt_input(args),
        "attachment_ids": args.input or [],
        "confirm_spend": bool(args.confirm_spend),
    }
    if not args.confirm_spend:
        preview = api(site, f"/cli/runs/{args.run_id}/follow-ups/preview", method="POST", token=device["token"], body=body)
        return {"started": False, "preview": preview, "next": "Show this to the user. After they approve, repeat with --confirm-spend."}
    attempt = api(site, f"/cli/runs/{args.run_id}/follow-ups", method="POST", token=device["token"], body=body, timeout=115)
    return {"started": True, "attempt": attempt, "review_url": site + "/runs/" + args.run_id}


def _jsonl(path: Path):
    """Yield every JSON object in a transcript, counting lines that do not parse."""
    bad = 0
    with path.open(encoding="utf-8", errors="replace") as file:
        for line in file:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except ValueError:
                bad += 1
                continue
            if isinstance(row, dict):
                yield row
    if bad:
        yield {"__unparsed_lines__": bad}


def _add_usage(total: dict, usage: dict, keys: tuple[str, ...]) -> None:
    for key in keys:
        value = usage.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            total[key] = total.get(key, 0) + value


def _stamp(record: dict, stamp: Any) -> None:
    if isinstance(stamp, str) and stamp:
        record["started_at"] = min(filter(None, (record["started_at"], stamp)))
        record["ended_at"] = max(filter(None, (record["ended_at"], stamp)))


def _claude_session(path: Path) -> dict:
    """Facts from one Claude Code transcript. Every typed message is kept word for word."""
    record: dict[str, Any] = {
        "tool": "claude-code", "file": str(path), "session_id": path.stem, "title": None, "cwd": None,
        "started_at": None, "ended_at": None, "models": {}, "usage": {}, "subagent_usage": {},
        "tool_calls": {}, "files_written": [], "messages": [], "unparsed_lines": 0, "claude_code_cost_usd": None,
    }
    seen: set[str] = set()
    keys = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
    for row in _jsonl(path):
        if "__unparsed_lines__" in row:
            record["unparsed_lines"] += row["__unparsed_lines__"]
            continue
        _stamp(record, row.get("timestamp"))
        record["cwd"] = record["cwd"] or row.get("cwd")
        kind = row.get("type")
        if kind == "custom-title" and row.get("customTitle"):
            record["title"] = row["customTitle"]
        elif kind == "cost-state" and isinstance(row.get("totalCostUSD"), (int, float)):
            record["claude_code_cost_usd"] = row["totalCostUSD"]
        message = row.get("message") if isinstance(row.get("message"), dict) else {}
        if kind == "assistant":
            # One API response is stored as one row per content block; count its usage once.
            ident = message.get("id") or row.get("requestId") or row.get("uuid")
            if ident not in seen:
                seen.add(ident)
                if message.get("model"):
                    record["models"][message["model"]] = record["models"].get(message["model"], 0) + 1
                if isinstance(message.get("usage"), dict):
                    _add_usage(record["usage"], message["usage"], keys)
            for block in message.get("content") or []:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    name = block.get("name") or "unknown"
                    record["tool_calls"][name] = record["tool_calls"].get(name, 0) + 1
                    given = block.get("input") if isinstance(block.get("input"), dict) else {}
                    target = given.get("file_path") or given.get("notebook_path")
                    if name in {"Write", "Edit", "MultiEdit", "NotebookEdit"} and target and target not in record["files_written"]:
                        record["files_written"].append(target)
        elif kind == "user" and not row.get("isSidechain"):
            content = message.get("content")
            texts: list[str] = []
            images = 0
            if isinstance(content, str):
                texts.append(content)
            elif isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict) or block.get("type") == "tool_result":
                        continue
                    if block.get("type") == "text":
                        texts.append(block.get("text") or "")
                    elif block.get("type") == "image":
                        images += 1
            if texts or images:
                record["messages"].append({
                    "at": row.get("timestamp"), "text": "\n".join(texts), "images": images,
                    "source": row.get("promptSource"), "meta": bool(row.get("isMeta")),
                })
    for sub in sorted((path.parent / path.stem / "subagents").glob("*.jsonl")):
        seen_sub: set[str] = set()
        for row in _jsonl(sub):
            message = row.get("message") if isinstance(row.get("message"), dict) else {}
            if row.get("type") == "assistant" and isinstance(message.get("usage"), dict):
                ident = message.get("id") or row.get("uuid")
                if ident in seen_sub:
                    continue
                seen_sub.add(ident)
                _add_usage(record["subagent_usage"].setdefault(message.get("model") or "unknown", {}), message["usage"], keys)
    return record


def _codex_session(path: Path) -> dict:
    """Facts from one Codex rollout. Typed messages come from UserMessage items, word for word."""
    record: dict[str, Any] = {
        "tool": "codex", "file": str(path), "session_id": path.stem, "title": None, "cwd": None,
        "started_at": None, "ended_at": None, "models": {}, "efforts": {}, "usage": {}, "tool_calls": {},
        "files_written": [], "messages": [], "unparsed_lines": 0,
    }
    fallback: list[dict] = []
    for row in _jsonl(path):
        if "__unparsed_lines__" in row:
            record["unparsed_lines"] += row["__unparsed_lines__"]
            continue
        _stamp(record, row.get("timestamp"))
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
        kind, sub = row.get("type"), payload.get("type")
        if kind == "session_meta":
            record["session_id"] = payload.get("id") or record["session_id"]
            record["cwd"] = payload.get("cwd") or record["cwd"]
        elif kind == "turn_context":
            record["cwd"] = record["cwd"] or payload.get("cwd")
            for field, bucket in (("model", "models"), ("effort", "efforts")):
                if payload.get(field):
                    record[bucket][payload[field]] = record[bucket].get(payload[field], 0) + 1
        elif kind == "token_usage_record" and isinstance(payload.get("thread_token_usage"), dict):
            record["usage"] = payload["thread_token_usage"]
        elif kind == "event_msg" and sub == "token_count" and isinstance((payload.get("info") or {}).get("total_token_usage"), dict):
            record["usage"] = payload["info"]["total_token_usage"]
        elif kind == "event_msg" and sub == "item_completed":
            item = payload.get("item") if isinstance(payload.get("item"), dict) else {}
            if item.get("type") == "UserMessage":
                content = item.get("content")
                parts = content if isinstance(content, list) else [{"type": "text", "text": str(content or "")}]
                record["messages"].append({
                    "at": row.get("timestamp"),
                    "text": "\n".join(p.get("text") or "" for p in parts if isinstance(p, dict) and p.get("type") == "text"),
                    "images": sum(1 for p in parts if isinstance(p, dict) and "image" in str(p.get("type"))),
                    "source": "typed", "meta": False,
                })
            elif item.get("type") == "McpToolCall":
                name = f"mcp:{item.get('server')}:{item.get('tool')}"
                record["tool_calls"][name] = record["tool_calls"].get(name, 0) + 1
            elif item.get("type") == "CommandExecution":
                record["tool_calls"]["command"] = record["tool_calls"].get("command", 0) + 1
            elif item.get("type") == "SubAgentActivity" and item.get("model"):
                key = "subagent:" + item["model"]
                record["models"][key] = record["models"].get(key, 0) + 1
        elif kind == "response_item" and sub in {"function_call", "custom_tool_call"}:
            name = payload.get("name") or "unknown"
            record["tool_calls"][name] = record["tool_calls"].get(name, 0) + 1
            text = payload.get("input") if isinstance(payload.get("input"), str) else payload.get("arguments")
            if isinstance(text, str):
                for line in text.splitlines():
                    for marker in ("*** Add File: ", "*** Update File: "):
                        target = line[len(marker):].strip() if line.startswith(marker) else ""
                        if target and target not in record["files_written"]:
                            record["files_written"].append(target)
        elif kind == "response_item" and sub == "message" and payload.get("role") == "user":
            parts = payload.get("content") if isinstance(payload.get("content"), list) else []
            fallback.append({
                "at": row.get("timestamp"), "text": "\n".join(p.get("text") or "" for p in parts if isinstance(p, dict)),
                "images": 0, "source": "model-input", "meta": True,
            })
    if not record["messages"]:
        # Older rollouts have no UserMessage items. Keep what the model was sent, labelled, rather than nothing.
        record["messages"] = fallback
    return record


def sessions(days: int, out: Path, claude_root: Path, codex_root: Path) -> dict:
    """List local Claude Code and Codex sessions changed in the last `days` days. Reads only; uploads nothing."""
    if not 1 <= days <= 365:
        raise ValueError("Choose 1 to 365 days.")
    cutoff = time.time() - days * 86400
    found: list[tuple[str, Path]] = []
    if claude_root.is_dir():
        found += [("claude-code", p) for p in claude_root.glob("*/*.jsonl") if p.stat().st_mtime >= cutoff]
    if codex_root.is_dir():
        found += [("codex", p) for p in codex_root.rglob("*.jsonl") if p.stat().st_mtime >= cutoff]
    out.mkdir(mode=0o700, parents=True, exist_ok=True)
    index, failed = [], []
    for tool, path in sorted(found, key=lambda item: item[1].stat().st_mtime):
        try:
            record = _claude_session(path) if tool == "claude-code" else _codex_session(path)
        except OSError as error:
            failed.append({"file": str(path), "error": str(error)})
            continue
        name = f"{tool}-{hashlib.sha256(str(path).encode()).hexdigest()[:16]}.json"
        save_state(out / name, record)
        index.append({
            "file": name, "tool": tool, "title": record["title"], "cwd": record["cwd"],
            "started_at": record["started_at"], "ended_at": record["ended_at"], "models": record["models"],
            "usage": record["usage"], "messages": len(record["messages"]),
            "typed_characters": sum(len(m["text"]) for m in record["messages"]),
            "unparsed_lines": record["unparsed_lines"],
        })
    summary = {"days": days, "folder": str(out), "sessions": len(index), "unreadable": failed, "index": index}
    save_state(out / "index.json", summary)
    return {key: value for key, value in summary.items() if key != "index"} | {"index_file": str(out / "index.json")}


def _verdicts(folder: Path) -> tuple[list[dict], list[dict]]:
    """Find every judge's verdict.json under a folder written by `evals results`."""
    manifest_path = folder / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        judges = [
            {"judge": row.get("label") or f"setup {row.get('setup_index', 0) + 1}", "dir": folder / row["dir"]}
            for row in manifest.get("setups", [])
        ]
    else:
        judges = [{"judge": path.name, "dir": path} for path in sorted(p for p in folder.iterdir() if p.is_dir())]
    found, problems = [], []
    for judge in judges:
        files = sorted(judge["dir"].rglob("verdict.json"))
        if not files:
            problems.append({"judge": judge["judge"], "problem": "no verdict.json", "dir": str(judge["dir"])})
            continue
        if len(files) > 1:
            problems.append({"judge": judge["judge"], "problem": "several verdict.json files; used the last", "files": [str(f) for f in files]})
        try:
            verdict = json.loads(files[-1].read_text(encoding="utf-8"))
            if not isinstance(verdict, dict) or not isinstance(verdict.get("scores"), dict):
                raise ValueError("scores is missing")
        except ValueError as error:
            problems.append({"judge": judge["judge"], "problem": f"unreadable verdict.json: {error}", "file": str(files[-1])})
            continue
        found.append({"judge": judge["judge"], "file": str(files[-1]), "verdict": verdict})
    return found, problems


def tally(folder: Path, key_path: Path | None = None, weights_path: Path | None = None) -> dict:
    """Arithmetic only: each judge's weighted total per candidate, means, first-place votes and spread."""
    if not folder.is_dir():
        raise ValueError("Pass the folder that evals results wrote.")
    found, problems = _verdicts(folder)
    names = json.loads(key_path.read_text(encoding="utf-8")) if key_path else {}
    weights = json.loads(weights_path.read_text(encoding="utf-8")) if weights_path else None
    per: dict[str, list[dict]] = {}
    firsts: dict[str, int] = {}
    reasons: dict[str, list[dict]] = {}
    for row in found:
        verdict = row["verdict"]
        for candidate, scores in verdict["scores"].items():
            numbers = {
                k: float(v) for k, v in (scores if isinstance(scores, dict) else {}).items()
                if isinstance(v, (int, float)) and not isinstance(v, bool)
            }
            if not numbers:
                problems.append({"judge": row["judge"], "problem": f"no numeric scores for {candidate}"})
                continue
            if weights:
                weight = sum(float(weights.get(k, 0)) for k in numbers)
                total = sum(numbers[k] * float(weights.get(k, 0)) for k in numbers) / weight * 10 if weight else 0.0
                unweighted = sorted(k for k in numbers if k not in weights)
                if unweighted:
                    problems.append({"judge": row["judge"], "problem": f"criteria with no weight for {candidate}: {unweighted}"})
            else:
                total = sum(numbers.values()) / len(numbers) * 10
            per.setdefault(candidate, []).append({"judge": row["judge"], "score": round(total, 2)})
        winner = verdict.get("winner")
        if isinstance(winner, str):
            firsts[winner] = firsts.get(winner, 0) + 1
            reason = (verdict.get("reasons") or {}).get(winner) if isinstance(verdict.get("reasons"), dict) else None
            reasons.setdefault(winner, []).append({"judge": row["judge"], "reason": reason})
    table = []
    for candidate, scored in per.items():
        totals = [item["score"] for item in scored]
        mean = sum(totals) / len(totals)
        spread = (sum((t - mean) ** 2 for t in totals) / len(totals)) ** 0.5
        table.append({
            "candidate": candidate, "name": names.get(candidate, candidate), "mean_score_0_100": round(mean, 2),
            "spread": round(spread, 2), "judges_scored": len(totals), "scores": scored,
            "first_place_votes": firsts.get(candidate, 0), "winner_reasons": reasons.get(candidate, []),
        })
    table.sort(key=lambda row: (-row["mean_score_0_100"], -row["first_place_votes"]))
    return {"judges_read": len(found), "problems": problems, "weights": weights or "equal", "ranking": table}


def brief_args(command: argparse.ArgumentParser, required: bool = True) -> None:
    prompt = command.add_mutually_exclusive_group(required=required)
    prompt.add_argument("prompt", nargs="?", help="The brief, word for word")
    prompt.add_argument("--prompt-file", help="Read the brief from a file, or use - for stdin")


def plan_args(command: argparse.ArgumentParser) -> None:
    command.add_argument("--visibility", choices=("public", "private"), required=True)
    command.add_argument("--setup", action="append", metavar="SPEC", help=(
        "One option: model=ID[,gen=ID|auto|none][,skill=auto|none|ID ...][,effort=LEVEL]. Repeat 2 to 8 times."))
    command.add_argument("--model", action="append", help="Shorthand: one model ID per option (with --skill)")
    command.add_argument("--skill", action="append", help="Shorthand: one per --model: auto, none, or a skill ID")
    command.add_argument("--input", action="append", metavar="UPLOAD_ID", help="An input ID from evals upload")
    command.add_argument("--attachment-id", action="append", help=argparse.SUPPRESS)
    command.add_argument("--suggestion", metavar="FILE", help="Use the setups from evals suggest for this same brief")
    command.add_argument("--prepare-only", action="store_true", help="Print the plan without prompting to start")


def finish_plan(site: str, device: dict, args: argparse.Namespace) -> int:
    plan = prepare(site, device, args)
    if not args.prepare_only and sys.stdin.isatty() and sys.stdout.isatty() and getattr(args, "prompt_file", None) != "-":
        if review(plan):
            result = start(site, device, plan)
            output(result)
            return int(any(row["outcome"] != "accepted" for row in result["options"]))
        print("Comparison left unstarted.", file=sys.stderr)
    output(public_plan(plan, site))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evals", description=__doc__)
    parser.add_argument("--version", action="version", version="evals 0.4.0")
    sub = parser.add_subparsers(dest="command", required=True)
    pairing = sub.add_parser("login", help="Connect your Evals account in the browser")
    pairing.add_argument("--no-browser", action="store_true")
    sub.add_parser("logout", help="Revoke this device")
    sub.add_parser("whoami", help="Show the connected account and private-run eligibility")
    models = sub.add_parser("models", help="List LLMs, or Gen AI tools with --gen-ai, and who pays for each")
    models.add_argument("--gen-ai", action="store_true", help="List image, video, audio and 3D tools instead of LLMs")
    find = sub.add_parser("search", help="Search public Evals records")
    find.add_argument("kind", choices=("skills", "tasks", "outputs"))
    find.add_argument("query")
    find.add_argument("--limit", type=int, default=5)
    upload = sub.add_parser("upload", help="Upload local files as inputs and print their IDs")
    upload.add_argument("paths", nargs="+", type=Path)
    suggest = sub.add_parser("suggest", help="The setups Battle would pick for this brief")
    brief_args(suggest)
    suggest.add_argument("--count", type=int, choices=range(2, MAX_SETUPS + 1), default=4, metavar="N")
    suggest.add_argument("--input", action="append", metavar="UPLOAD_ID", help="An input ID from evals upload")
    for name, text in (("prepare", "Prepare a plan for 2 to 8 setups without starting it"),
                       ("compare", "Same as prepare; kept for earlier scripts")):
        command = sub.add_parser(name, help=text)
        brief_args(command)
        plan_args(command)
    launch = sub.add_parser("start", help="Start a reviewed plan")
    launch.add_argument("comparison_id")
    launch.add_argument("--confirm-spend", action="store_true", help="Use only after reviewing this exact plan and authorizing its visibility and charges")
    status = sub.add_parser("status", help="Read attempts and recorded usage")
    status.add_argument("run_id")
    wait = sub.add_parser("wait", help="Wait for the current options to settle or need input")
    wait.add_argument("run_id")
    wait.add_argument("--timeout", type=int, choices=range(1, 601), metavar="SECONDS", default=120)
    fetch = sub.add_parser("results", help="Download every setup's latest result into a folder")
    fetch.add_argument("run_id")
    fetch.add_argument("--out", type=Path, required=True)
    follow = sub.add_parser("continue", help="Send a follow-up turn to one setup of a run")
    follow.add_argument("run_id")
    follow.add_argument("--setup", type=int, required=True, help="Setup number, starting at 1")
    brief_args(follow)
    follow.add_argument("--input", action="append", metavar="UPLOAD_ID")
    follow.add_argument("--confirm-spend", action="store_true", help="Use only after the user approved this follow-up")
    local = sub.add_parser("sessions", help="List your recent Claude Code and Codex sessions locally (uploads nothing)")
    local.add_argument("--days", type=int, default=14)
    local.add_argument("--out", type=Path, required=True)
    local.add_argument("--claude-root", type=Path, default=Path("~/.claude/projects").expanduser())
    local.add_argument("--codex-root", type=Path, default=Path("~/.codex/sessions").expanduser())
    count = sub.add_parser("tally", help="Add up judges' verdict.json files from evals results")
    count.add_argument("folder", type=Path)
    count.add_argument("--key", type=Path, help="key.json mapping blind letters to real names")
    count.add_argument("--weights", type=Path, help="weights.json mapping criteria to weights")
    args = parser.parse_args(argv)
    try:
        if args.command == "sessions":
            output(sessions(args.days, args.out.expanduser(), args.claude_root, args.codex_root))
            return 0
        if args.command == "tally":
            output(tally(args.folder.expanduser(), args.key, args.weights))
            return 0
        site = origin()
        if args.command == "search":
            output(search(args.kind, args.query, args.limit))
            return 0
        if args.command == "login":
            output(login(site, not args.no_browser))
            return 0
        device = credential(site)
        token = device["token"]
        if args.command == "logout":
            try:
                api(site, "/cli/me", method="DELETE", token=token)
            except ApiError as error:
                if error.status != 401:
                    raise
            (state_dir() / "device.json").unlink(missing_ok=True)
            output({"disconnected": True})
        elif args.command == "whoami":
            output(api(site, "/cli/me", token=token))
        elif args.command == "models":
            output(api(site, "/cli/generation-models" if args.gen_ai else "/cli/models", token=token))
        elif args.command == "upload":
            output([upload_file(site, token, path.expanduser()) for path in args.paths])
        elif args.command == "suggest":
            body = {"prompt": prompt_input(args), "count": args.count, "attachment_ids": args.input or []}
            output(api(site, "/cli/comparisons/suggest", method="POST", token=token, body=body, timeout=150))
        elif args.command == "status":
            output(run_status(site, device, args.run_id))
        elif args.command == "wait":
            output(wait_for_run(site, device, args.run_id, args.timeout))
        elif args.command == "results":
            output(results(site, device, args.run_id, args.out.expanduser()))
        elif args.command == "continue":
            output(continue_turn(site, device, args))
        elif args.command in ("prepare", "compare"):
            return finish_plan(site, device, args)
        else:
            stored = load_state(plan_path(args.comparison_id))
            if stored["origin"] != site or stored["device_id"] != device["device_id"]:
                raise ValueError("Prepare the comparison again on this device.")
            plan = stored["plan"]
            check_review(plan)
            if not args.confirm_spend:
                if not sys.stdin.isatty() or not sys.stdout.isatty():
                    raise ValueError("Review the plan with the user before using --confirm-spend.")
                if not review(plan):
                    return 0
            result = start(site, device, plan)
            output(result)
            return int(any(row["outcome"] != "accepted" for row in result["options"]))
        return 0
    except (ValueError, ApiError, OSError, EOFError) as error:
        print(terminal_text(f"Evals: {error}"), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Evals: cancelled. Check the run status if a start was already submitted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
