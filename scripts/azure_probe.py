from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

import httpx


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def classify(endpoint: str) -> dict[str, object]:
    parsed = urlparse(endpoint)
    return {
        "scheme": parsed.scheme,
        "host_suffix": ".".join(parsed.hostname.split(".")[-3:]) if parsed.hostname else None,
        "path": parsed.path or "/",
        "has_openai_path": "/openai" in parsed.path,
        "has_deployments_path": "/deployments" in parsed.path,
        "trailing_slash": endpoint.endswith("/"),
    }


def main() -> int:
    env = load_env(Path(".env"))
    endpoint = env.get("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
    key = env.get("AZURE_OPENAI_API_KEY", "")
    version = env.get("AZURE_OPENAI_API_VERSION", "2024-10-21")
    deployment = env.get("AZURE_OPENAI_DEPLOYMENT", "")
    print("classify", classify(env.get("AZURE_OPENAI_ENDPOINT", "")))
    print("deployment_len", len(deployment))
    print("version", version)

    headers = {"api-key": key}
    list_url = f"{endpoint}/openai/deployments?api-version={version}"
    with httpx.Client(timeout=30.0) as client:
        listed = client.get(list_url, headers=headers)
        print("list_status", listed.status_code)
        if listed.status_code == 200:
            names = [item.get("id") for item in listed.json().get("data", [])]
            print("deployments", names)
        else:
            content_type = listed.headers.get("content-type", "")
            if content_type.startswith("application/json"):
                print("list_error_code", listed.json().get("error", {}).get("code"))
            else:
                print("list_error_code", "non_json")

        ping = {
            "messages": [{"role": "user", "content": "Reply with the word pong only."}],
            "max_tokens": 8,
        }
        classic_url = (
            f"{endpoint.removesuffix('/openai/v1')}/openai/deployments/{deployment}"
            f"/chat/completions?api-version={version}"
        )
        candidates = [
            (
                "classic_deployments",
                classic_url,
                ping,
            ),
            (
                "v1_chat",
                f"{endpoint}/chat/completions",
                {
                    "model": deployment,
                    "messages": [{"role": "user", "content": "Reply with the word pong only."}],
                    "max_tokens": 8,
                },
            ),
        ]
        for name, chat_url, payload in candidates:
            chat = client.post(
                chat_url,
                headers={**headers, "Content-Type": "application/json"},
                json=payload,
            )
            print(name, "status", chat.status_code)
            if chat.status_code == 200:
                content = chat.json()["choices"][0]["message"]["content"]
                print(name, "ok", content.strip()[:40])
            else:
                body = chat.json() if "json" in chat.headers.get("content-type", "") else {}
                err = body.get("error", {}) if isinstance(body, dict) else {}
                print(name, "error_code", err.get("code"))
                print(name, "error_message", str(err.get("message", ""))[:180])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
