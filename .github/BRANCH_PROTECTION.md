# Branch Protection Setup

Configure branch protection rules on GitHub for the `main` (or `master`) branch.

## Recommended Settings

Go to: **Repository Settings > Branches > Add branch protection rule**

### Branch name pattern
```
main
```
(or `master` if that's your default branch)

### Protection Rules

Enable the following:

- [x] **Require a pull request before merging**
  - [x] Require approvals: 1 (optional for solo projects)
  - [ ] Dismiss stale pull request approvals when new commits are pushed
  - [ ] Require review from Code Owners

- [x] **Require status checks to pass before merging**
  - [x] Require branches to be up to date before merging
  - Status checks required:
    - `Lint`
    - `Test`

- [x] **Require conversation resolution before merging**

- [ ] **Require signed commits** (optional)

- [ ] **Require linear history** (optional - prevents merge commits)

- [x] **Do not allow bypassing the above settings**

### For Administrators

- [ ] Allow force pushes (keep disabled)
- [ ] Allow deletions (keep disabled)

## Quick Setup via GitHub CLI

```bash
# Enable branch protection (requires gh CLI)
gh api repos/{owner}/{repo}/branches/main/protection \
  -X PUT \
  -H "Accept: application/vnd.github+json" \
  -f required_status_checks='{"strict":true,"contexts":["Lint","Test"]}' \
  -f enforce_admins=true \
  -f required_pull_request_reviews='{"required_approving_review_count":0}' \
  -f restrictions=null
```

## Verification

After setup, you should see a lock icon next to the branch name on GitHub, and direct pushes to `main` should be blocked.
