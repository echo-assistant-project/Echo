# Echo Collaboration Guide

This guide is for a two-person team with equal organization ownership. It assumes the future repository is private and `main` is the stable shared branch.

## Recommended branch policy

- `main`: stable, shared release line.
- `feature/<short-name>`: a feature or enhancement.
- `fix/<short-name>`: a bug fix.
- Use pull requests for normal work. The other developer reviews and approves; the author does not approve their own pull request.
- Keep changes focused. Add required CI checks only after the Android and Windows build workflows exist and run reliably.
- Do not force-push shared branches. Avoid history-rewriting recovery commands unless the other developer has coordinated with you.

Suggested `main` protection for a two-person team: require a pull request, one approval from the other developer, resolve conversations, block force-push and deletion, and dismiss stale approvals when new commits are pushed. Do not require status checks until those checks have been configured and verified.

### GitHub plan limitation

GitHub Free organizations support private repositories. GitHub documents protected branches for Free organizations on public repositories; private repository branch protection and rulesets require a paid plan such as GitHub Team. GitHub Team currently lists at USD $4 per user per month, so two billed members would be about USD $8/month before taxes or billing adjustments. Verify the plan and pricing again before purchase. If staying on Free, use the same PR/review convention manually, but GitHub cannot enforce it on a private repository through those protections. See [GitHub plans and pricing](https://github.com/pricing), [protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches), and [ruleset availability](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/creating-rulesets-for-a-repository).

Organization owners have full administrative access. Even when a rule says PR/review required, owners or admins may have bypass paths depending on configuration; an owner can also change the rules. Rules reduce accidents, they do not create an absolute lock against both owners.

## Everyday Git workflow (PowerShell)

Run these commands from the local Echo repository root after the private remote has been configured.

### Start or update work

```powershell
git switch main
git pull --ff-only origin main
git switch -c feature/short-description
```

Use `fix/short-description` for a bug fix. Choose a unique, lowercase branch name with hyphens.

### Review and commit your changes

```powershell
git status --short
git diff
git add path\to\changed-file
git diff --cached
git commit -m "Describe the change"
```

Check `git diff` before staging. Check `git diff --cached` before committing. Do not add local configuration, API keys, certificates, model files, APKs, Gradle caches, or machine-specific SDK paths containing private information.

### Push your branch and open a pull request

```powershell
git push -u origin feature/short-description
gh pr create --base main --head feature/short-description --fill
```

`gh` is optional; you can create the pull request in the GitHub website instead. Never paste passwords or personal access tokens into chat. Authenticate with the official browser/device flow from GitHub CLI or Git Credential Manager.

### Review and merge

```powershell
gh pr checkout 123
gh pr diff 123
gh pr review 123 --approve
```

Replace `123` with the pull request number. For review, inspect the changed files and build/test evidence, then approve or request changes. The reviewer should not approve their own changes. After approval and successful checks, merge in GitHub or with `gh pr merge 123`.

### Resolve conflicts safely

First update your feature branch from `main`:

```powershell
git fetch origin
git switch feature/short-description
git merge origin/main
```

Open each conflicted file, decide the intended combined content, then:

```powershell
git status --short
git add path\to\resolved-file
git commit
git push
```

If the result is unclear, stop before committing and ask the other developer. Do not use `git reset --hard` or force-push as a conflict shortcut.

### Update the local main branch

```powershell
git switch main
git pull --ff-only origin main
```

### Recover from common mistakes

- Wrong branch, no changes yet: `git switch main` and create the intended branch.
- Accidentally staged a file but did not commit: inspect `git status`, then unstage it with `git restore --staged path\to\file`. The working copy remains.
- Need to discard unstaged edits: inspect `git diff` first. `git restore path\to\file` permanently discards those edits; use only when you are certain.
- A commit was made but not pushed: make a correcting commit. If removing the commit is necessary, coordinate first and preserve a backup branch before changing history.
- A bad commit was already pushed/shared: use `git revert <commit>` to make a new undo commit, then push normally. Do not reset or force-push shared history.
- Unsure what Git will do: stop and inspect `git status`, `git log --oneline --decorate -8`, and `git diff` before running a mutating command.

## Equal ownership and invitations

Both founders should be organization Owners and verify the accepted invitation before treating access as active. GitHub describes Owners as having complete administrative access and recommends at least two owners for continuity ([organization roles](https://docs.github.com/en/organizations/managing-peoples-access-to-your-organization-with-roles/roles-in-an-organization), [ownership continuity](https://docs.github.com/en/organizations/managing-peoples-access-to-your-organization-with-roles/maintaining-ownership-continuity-for-your-organization)). Owners have equal administrative access, including the ability to change organization settings, repository rules, roles, visibility, or delete repositories. Keep recovery codes and account security under each person's control; never share sign-in credentials.

## Setup remains pending

No organization, repository, remote, invitations, or upload has been created. The organization name/slug, repository name, co-founder login, and approved upload scope must be confirmed first. This local GitHub connection can inspect accessible repositories but has no organization creation, repository creation, or owner-invitation operation. GitHub CLI is not installed on this PC at audit time.
