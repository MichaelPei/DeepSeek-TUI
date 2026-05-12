#!/usr/bin/env node
/**
 * Git AI after-edit hook for DeepSeek TUI.
 * Called after edit_file / write_file / apply_patch tool completes.
 * Marks the just-written code as AI-authored via git-ai checkpoint agent-v1.
 *
 * Expects environment variables set by DeepSeek TUI's hook system:
 *   DEEPSEEK_TOOL_ARGS       — JSON of the tool call input
 *   DEEPSEEK_WORKSPACE       — git workspace root
 *   DEEPSEEK_MODEL           — model used (e.g. deepseek-v4-pro)
 *   DEEPSEEK_SESSION_ID      — current conversation/session id
 *   DEEPSEEK_TRANSCRIPT_PATH — path to transcript.json (optional)
 */

const { spawnSync } = require('child_process');
const fs = require('fs');

function extractFilePaths(toolArgsStr) {
  if (!toolArgsStr) return [];
  try {
    const args = JSON.parse(toolArgsStr);
    const paths = new Set();

    for (const key of ['path', 'file_path']) {
      const val = args[key];
      if (typeof val === 'string' && val) paths.add(val);
    }

    // apply_patch may have a "changes" array
    if (Array.isArray(args.changes)) {
      for (const change of args.changes) {
        if (change && typeof change === 'object') {
          const p = change.path || change.file_path;
          if (typeof p === 'string' && p) paths.add(p);
        }
      }
    }

    return [...paths];
  } catch {
    return [];
  }
}

function loadTranscript(transcriptPath) {
  if (!transcriptPath) return { messages: [] };
  try {
    const data = fs.readFileSync(transcriptPath, 'utf-8');
    const messages = JSON.parse(data);
    return { messages };
  } catch {
    return { messages: [] };
  }
}

function main() {
  const workspace = process.env.DEEPSEEK_WORKSPACE || '';
  const model = process.env.DEEPSEEK_MODEL || 'unknown';
  const sessionId = process.env.DEEPSEEK_SESSION_ID || 'unknown';
  const toolArgs = process.env.DEEPSEEK_TOOL_ARGS || '';
  const transcriptPath = process.env.DEEPSEEK_TRANSCRIPT_PATH;

  const filePaths = extractFilePaths(toolArgs);
  const transcript = loadTranscript(transcriptPath);

  const payload = JSON.stringify({
    type: 'ai_agent',
    repo_working_dir: workspace,
    agent_name: 'deepseek-tui',
    model,
    conversation_id: sessionId,
    edited_filepaths: filePaths,
    transcript,
  });

  const result = spawnSync('git-ai', ['checkpoint', 'agent-v1', '--hook-input', 'stdin'], {
    input: payload,
    encoding: 'utf-8',
    timeout: 30_000,
    stdio: ['pipe', 'inherit', 'inherit'],
  });

  if (result.error) {
    if (result.error.code === 'ENOENT') {
      process.stderr.write('git-ai: command not found\n');
    } else {
      process.stderr.write(`git-ai checkpoint failed: ${result.error.message}\n`);
    }
    process.exit(1);
  }
}

main();
