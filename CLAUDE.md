@AGENTS.md

## Claude Code
- Use Opus for planning, architecture, implementation, and review.
- Always verify changes with tests/typecheck/lint/build where available.
- Keep final responses short: changed files, commands run, result, risks.

## Security rules
- Work only inside this repository unless explicitly instructed.
- Do not access production credentials, kubeconfig, cloud credentials, SSH keys, or secret files.
- Do not run destructive infrastructure commands.
