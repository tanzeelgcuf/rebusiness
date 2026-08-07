---
name: merge-main
description: Merges verified work from a feature branch back to Main and opens a PR. Use when a branch's changes are tested and ready to ship.
tools: Bash, Read, Grep
---

# Merge to Main

Ships completed, verified work to `Main` via PR.

## Workflow

1. **Check the branch is clean** — `git status`; nothing uncommitted except intentional artifacts.
2. **Run the sanity check** — the pipeline-runner's verification, or the project's test/self-check if one exists. If it fails, STOP and hand back to the fixer — never merge broken work.
3. **Push the branch** — `git push origin <branch>`.
4. **Open a PR** against `Main` — use `gh pr create --draft --base Main --head <branch>`. If `gh` is unavailable, print the PR URL (`https://github.com/tanzeelgcuf/rebusiness/pull/new/<branch>`) and say the PR is manual.
5. **Report**: branch, commit SHA, verification result, PR URL.

## Rules

- Never push directly to `Main`. Never force-push. Never merge unverified work.
- PR body states what changed + how it was verified.
- Wait for the PR to be merged (or hand the link to the user) — do not merge yourself unless the user explicitly said to.
- If merge conflicts would arise, resolve them in the feature branch first and re-verify.
