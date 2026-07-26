#!/usr/bin/env bash
set -euo pipefail

repo_url="${PROJECT_GIT_URL:-https://github.com/small-thinking/robotics-issac-learning.git}"
branch="${PROJECT_GIT_BRANCH:-codex/phase-0-1-bootstrap}"
project_dir="${REMOTE_PROJECT_DIR:-/workspace/robotics-issac-learning}"

printf -v quoted_repo_url '%q' "$repo_url"
printf -v quoted_branch '%q' "$branch"
printf -v quoted_project_dir '%q' "$project_dir"

remote_command="
set -euo pipefail
if [[ -d $quoted_project_dir/.git ]]; then
  git -C $quoted_project_dir fetch origin $quoted_branch
  git -C $quoted_project_dir checkout $quoted_branch
  git -C $quoted_project_dir pull --ff-only origin $quoted_branch
else
  git clone --branch $quoted_branch --single-branch $quoted_repo_url $quoted_project_dir
fi
git -C $quoted_project_dir rev-parse --short HEAD
"

exec "$(dirname "$0")/remote_exec.sh" "$remote_command"
