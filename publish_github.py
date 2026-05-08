import argparse
import base64
import os

import requests
from dotenv import load_dotenv

load_dotenv()


API_ROOT = "https://api.github.com"


def _headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _get_current_file(owner, repo, path, branch, token):
    url = f"{API_ROOT}/repos/{owner}/{repo}/contents/{path}"
    response = requests.get(url, headers=_headers(token), params={"ref": branch}, timeout=20)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()


def publish_file(owner, repo, local_path, remote_path, branch, message, token):
    with open(local_path, "rb") as handle:
        encoded = base64.b64encode(handle.read()).decode("ascii")

    current = _get_current_file(owner, repo, remote_path, branch, token)
    payload = {
        "message": message,
        "content": encoded,
        "branch": branch,
    }
    if current and current.get("sha"):
        payload["sha"] = current["sha"]

    url = f"{API_ROOT}/repos/{owner}/{repo}/contents/{remote_path}"
    response = requests.put(url, headers=_headers(token), json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


def main():
    parser = argparse.ArgumentParser(description="Publish generated files through the GitHub Contents API.")
    parser.add_argument("--owner", default=os.getenv("GITHUB_OWNER"), help="GitHub user or organization.")
    parser.add_argument("--repo", default=os.getenv("GITHUB_REPO"), help="GitHub repository name.")
    parser.add_argument("--branch", default="main", help="Target branch.")
    parser.add_argument("--local-path", default="index.html", help="Local file to upload.")
    parser.add_argument("--remote-path", default="index.html", help="Path inside the repository.")
    parser.add_argument("--message", default="Update beverage news monitor", help="Commit message.")
    args = parser.parse_args()

    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise SystemExit("Falta GITHUB_TOKEN. Completalo en el archivo .env del proyecto.")
    if not args.owner:
        raise SystemExit("Falta GITHUB_OWNER. Completalo en el archivo .env del proyecto.")
    if not args.repo:
        raise SystemExit("Falta GITHUB_REPO. Completalo en el archivo .env del proyecto.")

    result = publish_file(args.owner, args.repo, args.local_path, args.remote_path, args.branch, args.message, token)
    commit = result.get("commit", {})
    print(f"Published {args.remote_path} to {args.owner}/{args.repo}@{args.branch}")
    if commit.get("html_url"):
        print(commit["html_url"])


if __name__ == "__main__":
    main()
