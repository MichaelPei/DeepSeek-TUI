#!/usr/bin/env python3
"""
Git AI after-edit hook for DeepSeek TUI.
Called after edit_file / write_file / apply_patch tool completes.
Marks the just-written code as AI-authored via git-ai checkpoint agent-v1.

Expects environment variables set by DeepSeek TUI's hook system:
  DEEPSEEK_TOOL_ARGS       — JSON of the tool call input
  DEEPSEEK_WORKSPACE       — git workspace root
  DEEPSEEK_MODEL           — model used (e.g. deepseek-v4-pro)
  DEEPSEEK_SESSION_ID      — current conversation/session id
  DEEPSEEK_TRANSCRIPT_PATH — path to transcript.json (optional)
"""

import json
import os
import subprocess
import sys


def extract_file_paths(tool_args_str: str) -> list[str]:
    """Extract edited file paths from the tool call arguments."""
    if not tool_args_str:
        return []
    try:
        args = json.loads(tool_args_str)
    except json.JSONDecodeError:
        return []

    # Common field names for file paths across different tools
    paths = []
    for key in ("path", "file_path"):
        val = args.get(key)
        if val and isinstance(val, str):
            paths.append(val)

    # apply_patch may have a "changes" array or a "patch" string
    if "changes" in args and isinstance(args["changes"], list):
        for change in args["changes"]:
            if isinstance(change, dict):
                p = change.get("path") or change.get("file_path")
                if p and isinstance(p, str):
                    paths.append(p)

    return list(dict.fromkeys(paths))  # dedup preserving order


def load_transcript(transcript_path):
    """Load conversation transcript from the file path, if available."""
    if not transcript_path:
        return {"messages": []}
    if not os.path.isfile(transcript_path):
        return {"messages": []}
    try:
        with open(transcript_path, "r") as f:
            messages = json.load(f)
        # messages is already filtered (no tool results) by DeepSeek TUI
        return {"messages": messages}
    except (json.JSONDecodeError, OSError):
        return {"messages": []}


def main():
    workspace = os.environ.get("DEEPSEEK_WORKSPACE", "")
    model = os.environ.get("DEEPSEEK_MODEL", "unknown")
    session_id = os.environ.get("DEEPSEEK_SESSION_ID", "unknown")
    tool_args = os.environ.get("DEEPSEEK_TOOL_ARGS", "")
    transcript_path = os.environ.get("DEEPSEEK_TRANSCRIPT_PATH")

    file_paths = extract_file_paths(tool_args)
    transcript = load_transcript(transcript_path)

    payload = {
        "type": "ai_agent",
        "repo_working_dir": workspace,
        "agent_name": "deepseek-tui",
        "model": model,
        "conversation_id": session_id,
        "edited_filepaths": file_paths,
        "transcript": transcript,
    }

    try:
        proc = subprocess.run(
            ["git-ai", "checkpoint", "agent-v1", "--hook-input", "stdin"],
            input=json.dumps(payload),
            capture_output=False,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        print("git-ai not found on PATH", file=sys.stderr, flush=True)
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print("git-ai checkpoint timed out after 30s", file=sys.stderr, flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
