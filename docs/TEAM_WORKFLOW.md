# Team workflow

## Repository and access

- Organization: https://github.com/echo-assistant-project
- Private repository: https://github.com/echo-assistant-project/Echo
- main is the stable branch. Use feature/<short-name> and fix/<short-name>.
- The founder account Akshaj-echo was previously verified as an Organization Owner.
- The co-founder's exact GitHub username is pending. Do not invite or claim access until the username is supplied, the invitation accepted, and access checked.
- Required reviews/rules for private repositories may depend on the GitHub plan. Treat peer review as the team's process unless the repository UI confirms enforcement. Owners/admins may change rules.

## Normal contribution

From a clean, up-to-date checkout:

    .\scripts\sync-project.ps1
    git switch -c feature/short-description

After editing:

    git status --short
    git diff
    git add path\to\changed-file
    git diff --cached
    git commit -m "Describe the change"
    git push -u origin feature/short-description

Open a pull request targeting main. The other developer reviews the diff and CI result. Merge only after review and checks pass. Do not force-push shared branches or resolve conflicts by discarding one side.

## Safe synchronization

The manual-first script is scripts/sync-project.ps1.

    .\scripts\sync-project.ps1

It fetches origin/main and fast-forwards local main only if it can do so safely:

- If main is checked out and clean, it refuses when a common editor/build is active or the history cannot fast-forward.
- If a feature branch is active and main is not checked out in another worktree, it advances only the local main ref; the current branch and working files stay untouched.
- If main is checked out in another worktree, it stops for manual action.
- It never switches branches, overwrites edits, resets, force-pushes, resolves conflicts, or merges an unreviewed PR.
- Fetch-only mode is safe for a scheduled check:

      .\scripts\sync-project.ps1 -FetchOnly

- -WhatIf assesses without applying the fast-forward.

Results go to %LOCALAPPDATA%\Echo\logs\sync-project.log. Remote URLs, raw Git output, and credentials are omitted.

Git transfers commits, not uncommitted edits. Save, commit, and push work before expecting it on another computer. A clean status matters before advancing an active main.

## Scheduling

No Task Scheduler job is installed or enabled. Manual sync is the default. A background fetch-only check can refresh remote-tracking metadata, but does not update a local branch. Automatic fast-forward can disturb open files, builds, or editor buffers, so do not schedule it without deliberate approval.

## Recovery

- Inspect git status --short and git diff before acting.
- Unstage while preserving file edits: git restore --staged <path>.
- Resolve merge conflicts by inspecting and editing both sides, then stage and commit the resolution.
- To undo an already shared commit, coordinate and use git revert <commit>.
- Before risky recovery, create a backup branch or copy. Do not use git reset --hard or force-push to hide a conflict.