# Echo collaboration guide

The intended arrangement is equal Organization Owner access for founder Akshaj-echo and co-founder praviramc-web. The co-founder GitHub account is verified, but no invitation has been sent and no access is active yet. Do not describe the account as an Owner until the invitation is accepted and both organization role and private repository access are verified.

## Branch and review workflow

- main is the stable shared line.
- Use feature/<short-name> for features and fix/<short-name> for bug fixes.
- Open a pull request for normal changes. The other developer reviews; authors do not approve their own PR.
- Merge after review and checks pass. Do not force-push shared branches.
- The private repo is on GitHub Free. Required branch protection/reviews for private repos need a paid plan; on Free this review policy is a team agreement, not an enforced rule. See [GitHub protected branch plan availability](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches).

## Safe manual synchronization

From the repository root in PowerShell:

    .\scripts\sync-project.ps1

It fetches origin/main then fast-forwards local main only when safe. It never switches branches. With a feature branch active, it updates only local main's ref, leaving the feature branch and working files untouched. When main is checked out, it refuses to update if the tree is dirty, a common editor/build is open, or history cannot fast-forward. Diverged history or uncertainty requires manual review.

Fetch only, without advancing local main:

    .\scripts\sync-project.ps1 -FetchOnly

Assess without applying a fast-forward:

    .\scripts\sync-project.ps1 -WhatIf

The default log is %LOCALAPPDATA%\Echo\logs\sync-project.log. It records timestamps, branch, and outcome only. It omits remote URLs, Git output, and credentials.

Git does not synchronize uncommitted edits. Save, commit, and push changes before expecting them on another PC. Save/close editors before updating their active main.

### Optional Windows Task Scheduler

No task is installed or enabled. Manual synchronization is recommended because background updates can change files under active development.

For a future fetch-only check, configure Task Scheduler to run only while the developer is logged in, start after an idle delay, and invoke:

    pwsh.exe -NoProfile -ExecutionPolicy Bypass -File "C:\path\to\Echo\scripts\sync-project.ps1" -FetchOnly

Replace the path with that PC's clone. Fetch-only updates remote-tracking metadata but never changes a local branch or working file. Avoid scheduled fast-forwards because an open editor may retain stale buffers. The script never merges PRs.

## Everyday Git workflow

From a clean tree:

    .\scripts\sync-project.ps1
    git switch -c feature/short-description

After editing:

    git status --short
    git diff
    git add path\to\changed-file
    git diff --cached
    git commit -m "Describe the change"
    git push -u origin feature/short-description

Create a pull request with base main. After the other founder reviews it and checks pass, merge on GitHub and synchronize local main.

Resolve conflicts by inspecting and editing both sides intentionally:

    git status --short
    # Edit each conflict by hand.
    git add path\to\resolved-file
    git commit
    git push

If unsure, stop and coordinate. Do not use git reset --hard or force-push to resolve conflicts.

## Recover safely

- Inspect git diff before changing unstaged edits.
- Unstage while keeping files: git restore --staged path\to\file.
- Undo a pushed change with a revert commit: git revert <commit>.
- Before recovery, make a backup branch/copy and coordinate.

## Equal ownership and co-founder access

Akshaj-echo is verified as an active organization Owner. `praviramc-web` is the verified co-founder account. Current state (2026-10-29): no organization membership, no pending invitation, and repository permission `none`. The invitation has not been sent; obtain founder confirmation immediately before sending it with the Owner role.

Distinguish the stages: (1) invitation sent = pending acceptance, not active access; (2) invitation accepted = verify organization membership role `admin` (GitHub API representation of Owner) and repository permission `admin`; (3) only after both checks pass, record equal Owner access as verified. If GitHub requires an initial Member invitation, explain that constraint, wait for acceptance, then promote `praviramc-web` to Owner and verify again. Owners can change permissions, settings, visibility, or delete repos; branch rules cannot absolutely constrain Owners.

Follow [docs/DEVELOPER_SETUP.md](DEVELOPER_SETUP.md). Credentials, SDK paths, models, signing keys, pairing material, and APKs stay outside Git.
