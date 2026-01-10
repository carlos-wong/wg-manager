#!/usr/bin/env bash
set -euo pipefail

LOG_FILE="/home/gitlab-runner/cron_gitlab.log"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"
}

# 第一个参数：GitLab project ID
PROJECT_ID="${1:-}"

if [[ -z "$PROJECT_ID" ]]; then
  log "ERROR: PROJECT_ID is empty. Usage: trigger_pipeline.sh <project_id>"
  exit 1
fi

log "trigger_pipeline.sh started for project_id=${PROJECT_ID}"

# 加载环境变量
# 用 bash 跑脚本，这里用 source 是安全的
if [[ -f /home/gitlab-runner/.bash_env ]]; then
  # shellcheck source=/home/gitlab-runner/.bash_env
  source /home/gitlab-runner/.bash_env
else
  log "ERROR: /home/gitlab-runner/.bash_env not found"
  exit 1
fi

# 打印一下关键环境变量（防止为空）
log "ENV: URL=${GITLAB_PERSONAL_URL:-EMPTY}, TOKEN_SET=$([[ -n "${GITLAB_PERSONAL_TOKEN:-}" ]] && echo yes || echo no)"

# 调 GitLab API 触发 pipeline
curl --request POST \
  --header "PRIVATE-TOKEN: ${GITLAB_PERSONAL_TOKEN}" \
  --header "Content-Type: application/json" \
  --data '{"ref": "master", "variables": [{"key": "CARLOS_RUN_MODE", "value": "agent-iter"}]}' \
  "${GITLAB_PERSONAL_URL%/}/api/v4/projects/${PROJECT_ID}/pipeline" >> "$LOG_FILE" 2>&1

EXIT_CODE=$?
log "curl finished for project_id=${PROJECT_ID}, exit_code=${EXIT_CODE}"
exit "$EXIT_CODE"
