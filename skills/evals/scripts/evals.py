#!/usr/bin/env python3
"""Evals CLI. Sign in once, compare setups, and inspect the resulting run."""
from __future__ import annotations

import argparse
import base64
import concurrent.futures
import hashlib
import json
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
    headers = {"Accept": "application/json", "User-Agent": "evals-cli/0.3"}
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
        raise ValueError("Enter the comparison ID returned by evals compare.")
    return state_dir() / f"{plan_id}.json"


def expires(plan: dict) -> datetime:
    return datetime.fromisoformat(plan["expires_at"].replace("Z", "+00:00"))


def prepare(site: str, device: dict, args: argparse.Namespace) -> dict:
    models = args.model or []
    skills = args.skill or ["auto"] * len(models)
    if not 2 <= len(models) <= 4 or len(skills) != len(models):
        raise ValueError("Choose two to four --model IDs, with one --skill per model if used. Run evals models for IDs.")
    plan = api(
        site, "/cli/comparisons/prepare", method="POST", token=device["token"],
        body={
            "prompt": prompt_input(args),
            "visibility": args.visibility,
            "options": [{"model_id": model, "skill": skill} for model, skill in zip(models, skills)],
            "attachment_ids": args.attachment_id or [],
        },
    )
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


def review(plan: dict) -> bool:
    print(terminal_text(plan["prompt"]))
    print(f"\nVisibility: {plan['visibility'].title()}")
    if plan["visibility"] == "public":
        print("Other people may see the brief, inputs, and outputs.")
    for index, option in enumerate(plan["options"], 1):
        skill = {"none": "Don’t Use Skills", "auto": "Auto"}.get(option["skill"], option["skill"])
        print(terminal_text(f"{index}. {option['name']} · {PAYER[option['route']]} · {skill}"))
    if plan["attachments"]:
        print("Inputs:", terminal_text(", ".join(plan["attachments"])))
    print("Gen AI: Don’t Use")
    if plan["paid_fallback"]:
        print("Eligible paid fallbacks can use your Evals balance.")
    print("Total cost is unknown before execution. Provider usage and Evals charges may apply.")
    return input("Start this comparison? [y/N] ").strip().lower() in {"y", "yes"}


def public_plan(plan: dict, site: str) -> dict:
    return {
        **{key: value for key, value in plan.items() if key != "envelope"},
        "review_url": site + "/runs/" + plan["run_id"],
        "total_cost": None,
        "generation": "none",
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version="evals 0.3.0")
    sub = parser.add_subparsers(dest="command", required=True)
    pairing = sub.add_parser("login", help="Connect your Evals account in the browser")
    pairing.add_argument("--no-browser", action="store_true")
    sub.add_parser("logout", help="Revoke this device")
    sub.add_parser("whoami", help="Show the connected account and private-run eligibility")
    sub.add_parser("models", help="List model IDs and payment routes for this account")
    find = sub.add_parser("search", help="Search public Evals records")
    find.add_argument("kind", choices=("skills", "tasks", "outputs"))
    find.add_argument("query")
    find.add_argument("--limit", type=int, default=5)
    compare = sub.add_parser("compare", help="Compare two to four setups on one brief")
    prompt = compare.add_mutually_exclusive_group(required=True)
    prompt.add_argument("prompt", nargs="?")
    prompt.add_argument("--prompt-file", help="Read the brief from a file, or use - for stdin")
    compare.add_argument("--visibility", choices=("public", "private"), required=True)
    compare.add_argument("--model", action="append", help="One model ID per option. Run evals models.")
    compare.add_argument("--skill", action="append", help="One per option: auto, none, or a skill ID")
    compare.add_argument("--attachment-id", action="append", help="An input already uploaded to your Evals account")
    compare.add_argument("--prepare-only", action="store_true", help="Print the plan without prompting to start")
    launch = sub.add_parser("start", help="Start a reviewed plan")
    launch.add_argument("comparison_id")
    launch.add_argument("--confirm-spend", action="store_true", help="Use only after reviewing this exact plan and authorizing its visibility and charges")
    status = sub.add_parser("status", help="Read attempts and recorded usage")
    status.add_argument("run_id")
    wait = sub.add_parser("wait", help="Wait for the current options to settle or need input")
    wait.add_argument("run_id")
    wait.add_argument("--timeout", type=int, choices=range(1, 601), metavar="SECONDS", default=120)
    args = parser.parse_args(argv)
    try:
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
            output(api(site, "/cli/models", token=token))
        elif args.command == "status":
            output(run_status(site, device, args.run_id))
        elif args.command == "wait":
            output(wait_for_run(site, device, args.run_id, args.timeout))
        elif args.command == "compare":
            plan = prepare(site, device, args)
            if not args.prepare_only and sys.stdin.isatty() and sys.stdout.isatty() and args.prompt_file != "-":
                if review(plan):
                    result = start(site, device, plan)
                    output(result)
                    return int(any(row["outcome"] != "accepted" for row in result["options"]))
                print("Comparison left unstarted.", file=sys.stderr)
            output(public_plan(plan, site))
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
