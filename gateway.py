import json
import os
import subprocess

import httpx
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
MY_CHAT_ID = int(os.environ["MY_CHAT_ID"])
OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "anthropic/claude-sonnet-4.5")

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
SYSTEM = (
    "You are a concise personal assistant running on the user's laptop. "
    "You have a `bash` tool that executes shell commands via /bin/bash. "
    "Briefly explain what a command will do before running it, especially "
    "anything that modifies files or system state."
)
DANGEROUS_PATTERNS = ["rm -rf", "sudo", "dd if=", "mkfs", "> /dev/", ":(){ :|:& };:"]

TOOLS = [{
    "type": "function",
    "function": {
        "name": "bash",
        "description": "Run a shell command and return stdout, stderr, and exit code.",
        "parameters": {
            "type": "object",
            "properties": {"command": {"type": "string", "description": "Shell command to run."}},
            "required": ["command"],
        },
    },
}]

client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_API_KEY)
history: dict[int, list] = {}
pending_confirmation: dict[int, tuple[str, str]] = {}


def send(text: str) -> None:
    httpx.post(f"{TELEGRAM_API}/sendMessage", json={"chat_id": MY_CHAT_ID, "text": text}, timeout=15)


def run_bash(command: str) -> str:
    try:
        r = subprocess.run(
            ["/bin/bash", "-c", command],
            capture_output=True, text=True, timeout=30,
        )
        return f"exit_code={r.returncode}\nstdout:\n{r.stdout}\nstderr:\n{r.stderr}"
    except subprocess.TimeoutExpired:
        return "exit_code=-1\nerror: command timed out after 30s"


def is_dangerous(command: str) -> bool:
    return any(p in command for p in DANGEROUS_PATTERNS)


def run_tool_loop(chat_id: int) -> None:
    msgs = history[chat_id]
    for _ in range(10):
        resp = client.chat.completions.create(model=OPENROUTER_MODEL, messages=msgs, tools=TOOLS)
        msg = resp.choices[0].message
        msgs.append(msg.model_dump(exclude_none=True))
        if not msg.tool_calls:
            send(msg.content or "(no content)")
            return
        for tc in msg.tool_calls:
            cmd = json.loads(tc.function.arguments)["command"]
            if is_dangerous(cmd):
                pending_confirmation[chat_id] = (cmd, tc.id)
                send(f"About to run: `{cmd}`. Reply yes to confirm.")
                return
            msgs.append({"role": "tool", "tool_call_id": tc.id, "content": run_bash(cmd)})
    send("(stopped: tool loop exceeded 10 iterations)")


def handle_message(chat_id: int, text: str) -> None:
    if chat_id in pending_confirmation:
        cmd, tool_call_id = pending_confirmation.pop(chat_id)
        if text.strip().lower() == "yes":
            result = run_bash(cmd)
        else:
            result = "User declined to run this command."
        history[chat_id].append({"role": "tool", "tool_call_id": tool_call_id, "content": result})
    else:
        msgs = history.setdefault(chat_id, [{"role": "system", "content": SYSTEM}])
        msgs.append({"role": "user", "content": text})
    run_tool_loop(chat_id)


def main() -> None:
    offset: int | None = None
    while True:
        try:
            params: dict = {"timeout": 30}
            if offset is not None:
                params["offset"] = offset
            r = httpx.get(f"{TELEGRAM_API}/getUpdates", params=params, timeout=60)
            for update in r.json().get("result", []):
                offset = update["update_id"] + 1
                msg = update.get("message")
                if not msg or "text" not in msg:
                    continue
                if msg["chat"]["id"] != MY_CHAT_ID:
                    continue
                handle_message(msg["chat"]["id"], msg["text"])
        except Exception as e:
            print(f"error: {e}")


if __name__ == "__main__":
    main()
