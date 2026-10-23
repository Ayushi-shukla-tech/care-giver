#!/usr/bin/env bash
# commit-metric.sh — Cursor AI Commit Metric Collector (Bash port of commit-metric.go)
#
# Architecture: Two-phase execution triggered by post-commit git hook.
#
# Phase 1 ("start") — Runs synchronously in the hook (fast):
#   1. Checks if this is a normal commit (skips rebase/merge).
#   2. Gets the latest commit hash from git.
#   3. Writes commit info to a temp file.
#   4. Spawns itself as "continue" in a detached background process.
#
# Phase 2 ("continue") — Runs in background:
#   1. Polls Cursor DB until commit hash appears (500ms interval, 3 min max).
#   2. On match: builds request payload, sends to API.
#   3. On timeout: calls /error endpoint with commit hash.
#   4. Uploads dangling prompt metrics for repos matching the commit.
#   5. Retries failed requests from previous runs.
#
# Dependencies: bash 4+, sqlite3, jq, curl, git

set -euo pipefail

# ============================================================
# Dependency check
# ============================================================

check_dependencies() {
  mkdir -p ~/bin

  # Detect CPU architecture (Intel vs Apple Silicon)
  ARCH=$(uname -m)
  if [[ "$ARCH" == "arm64" ]]; then
    JQ_URL="https://github.com/stedolan/jq/releases/latest/download/jq-macos-arm64"
  elif [[ "$ARCH" == "x86_64" ]]; then
    JQ_URL="https://github.com/stedolan/jq/releases/latest/download/jq-osx-amd64"
  else
    log_warn "Unsupported architecture: $ARCH"
    return 1
  fi

  # Download jq if not installed
  if ! command -v jq >/dev/null 2>&1; then
    curl -fsSL -o ~/bin/jq "$JQ_URL"
    chmod +x ~/bin/jq
  fi

  # Add to PATH
  export PATH="$HOME/bin:$PATH"

  # These should always be present on macOS/Linux
  local missing=()
  for cmd in sqlite3 curl git; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
      missing+=("$cmd")
    fi
  done
  if [ ${#missing[@]} -gt 0 ]; then
    log_warn "Missing required dependencies: ${missing[*]}"
    return 1
  fi
}
# check_dependencies is called from main after parsing the command

# ============================================================
# Configuration
# ============================================================

# API endpoint to send commit metrics
API_ENDPOINT="https://cursor-server.meeshogcp.in/api/v1/add-commit-metrics"

# Error API endpoint (called on polling timeout)
ERROR_API_ENDPOINT="https://cursor-server.meeshogcp.in/api/v1/error"

# Set to true to skip API call and only save locally (for testing)
DRY_RUN=false

# Database configuration
DB_RELATIVE_PATH="Library/Application Support/Cursor/User/globalStorage/state.vscdb"
TABLE_NAME="ItemTable"
KEY_NAME="aiCodeTracking.recentCommit"

# SQLite configuration
BUSY_TIMEOUT_MS=3000
MAX_RETRIES=3
INITIAL_RETRY_DELAY_MS=500
MAX_RETRY_DELAY_MS=2000

# API retry configuration
API_MAX_ATTEMPTS=3
API_INITIAL_RETRY_DELAY_MS=1000
API_MAX_RETRY_DELAY_MS=5000

# DB polling configuration (post-commit: wait for Cursor to update DB)
COMMIT_POLL_INTERVAL_MS=10000
COMMIT_MAX_WAIT_S=120

# Storage paths (relative to $HOME)
FAILED_COMMITS_FILE=".cursor-metrics/commit-metric/failed.json"
METRICS_OUTPUT_DIR=".cursor-metrics/commit-metric/data"
TEMP_DIR=".cursor-metrics/commit-metric/tmp"
LOG_DIR_RELATIVE=".cursor-metrics/commit-metric/logs"
REBASE_MAP_FILE=".cursor-metrics/commit-metric/rebase-map.json"

# ---- Dangling prompt metrics configuration ----
PROMPT_API_ENDPOINT="https://cursor-server.meeshogcp.in/api/v1/add-prompt-metrics"
PROMPT_DB_TABLE="cursorDiskKV"
PROMPT_PERSISTENT_STORAGE_DIR=".cursor-metrics/prompt-metric/composer-partialDiffFates"
PROMPT_FAILED_REQUESTS_FILE=".cursor-metrics/prompt-metric/failed.json"

# ============================================================
# Logging
# ============================================================

LOG_FILE=""

setup_logging() {
  local log_dir="${HOME}/${LOG_DIR_RELATIVE}"
  mkdir -p "$log_dir" 2>/dev/null || true
  LOG_FILE="${log_dir}/commit-metric.log"
}

# logWarn writes a timestamped warning to the log file with [commit-metric] prefix.
# Falls back to stderr if the log file is not available.
log_warn() {
  local fmt_str="$1"; shift
  local msg
  # shellcheck disable=SC2059
  msg=$(printf "$fmt_str" "$@")
  local line
  line="[commit-metric] $(date -u +"%Y-%m-%dT%H:%M:%S%z") ${msg}"
  if [ -n "$LOG_FILE" ]; then
    echo "$line" >> "$LOG_FILE" 2>/dev/null || echo "$line" >&2
  else
    echo "$line" >&2
  fi
}

# ============================================================
# Utility functions
# ============================================================

# min_val returns the smaller of two integers
min_val() {
  local a=$1 b=$2
  if [ "$a" -lt "$b" ]; then echo "$a"; else echo "$b"; fi
}

# sleep_ms sleeps for N milliseconds
sleep_ms() {
  local ms=$1
  local secs
  secs=$(awk "BEGIN { printf \"%.3f\", $ms / 1000 }")
  sleep "$secs"
}

# get_db_path returns the full path to the Cursor state database
get_db_path() {
  echo "${HOME}/${DB_RELATIVE_PATH}"
}

# ============================================================
# Value decoding
# ============================================================

# is_hex_string checks if a string is hex-encoded (even length, only hex chars)
is_hex_string() {
  local s="$1"
  local len=${#s}
  if [ "$len" -eq 0 ] || [ $(( len % 2 )) -ne 0 ]; then
    return 1
  fi
  # Check all characters are hex
  if [[ "$s" =~ ^[0-9a-fA-F]+$ ]]; then
    return 0
  fi
  return 1
}

# hex_decode reads hex from stdin and outputs raw bytes.
# Uses xxd, perl, or python3 (whichever is available).
hex_decode() {
  if command -v xxd >/dev/null 2>&1; then
    xxd -r -p
  elif command -v perl >/dev/null 2>&1; then
    perl -pe 's/(..)/chr(hex($1))/ge'
  elif command -v python3 >/dev/null 2>&1; then
    python3 -c "import sys,binascii; sys.stdout.buffer.write(binascii.unhexlify(sys.stdin.read().strip()))"
  else
    return 1
  fi
}

# decode_value decodes a raw DB value (could be JSON or hex-encoded) to JSON bytes.
# Mirrors Go's decodeValue function.
decode_value() {
  local raw="$1"
  if [ -z "$raw" ]; then
    return 1
  fi
  # Check if valid JSON
  if echo "$raw" | jq empty 2>/dev/null; then
    echo "$raw"
    return 0
  fi
  # Check if hex-encoded
  if is_hex_string "$raw"; then
    local decoded
    if decoded=$(echo "$raw" | hex_decode 2>/dev/null) && [ -n "$decoded" ]; then
      # Verify it's valid JSON (UTF-8 check implicit)
      if echo "$decoded" | jq empty 2>/dev/null; then
        echo "$decoded"
        return 0
      fi
    fi
  fi
  return 1
}

# ============================================================
# DB helpers
# ============================================================

# read_db_value reads a single value from the DB by exact key.
# Uses typeof() to handle BLOB values safely (returns hex for BLOBs).
# PRAGMAs output is suppressed via .output /dev/null so it doesn't mix with query results.
read_db_value() {
  local db_path="$1"
  local table="$2"
  local key="$3"

  sqlite3 -readonly "$db_path" 2>/dev/null <<SQL
.output /dev/null
PRAGMA busy_timeout=${BUSY_TIMEOUT_MS};
.output
SELECT CASE typeof(value) WHEN 'blob' THEN hex(value) ELSE value END FROM ${table} WHERE key = '${key}';
SQL
}

# read_db_value_with_retry wraps read_db_value with exponential-backoff retries.
read_db_value_with_retry() {
  local db_path="$1"
  local table="$2"
  local key="$3"
  local retry_delay=$INITIAL_RETRY_DELAY_MS

  for attempt in $(seq 1 $MAX_RETRIES); do
    local raw
    raw=$(read_db_value "$db_path" "$table" "$key") && {
      echo "$raw"
      return 0
    }

    if [ "$attempt" -lt "$MAX_RETRIES" ]; then
      log_warn "DB read attempt %d/%d failed for key '%s', retrying in %dms..." \
        "$attempt" "$MAX_RETRIES" "$key" "$retry_delay"
      sleep_ms "$retry_delay"
      retry_delay=$(min_val $(( retry_delay * 2 )) $MAX_RETRY_DELAY_MS)
    fi
  done
  return 1
}

# read_commit_data reads and parses the commit metric from the DB with retries.
# Returns empty/fails when no commit data exists.
read_commit_data() {
  local db_path="$1"
  local raw
  raw=$(read_db_value_with_retry "$db_path" "$TABLE_NAME" "$KEY_NAME")
  if [ -z "$raw" ]; then
    return 1
  fi
  decode_value "$raw"
}

# read_repo_tracker_paths reads the repositoryTracker.paths key from the Cursor DB with retries.
read_repo_tracker_paths() {
  local db_path="$1"
  local raw
  raw=$(read_db_value_with_retry "$db_path" "$TABLE_NAME" "repositoryTracker.paths")
  if [ -z "$raw" ]; then
    echo "{}"
    return 0
  fi
  local decoded
  decoded=$(decode_value "$raw") || { echo "{}"; return 0; }
  echo "$decoded"
}

# ============================================================
# Temp file helpers
# ============================================================

# write_temp_file writes commit info to a temp JSON file for the background process.
# Prints the file path.
write_temp_file() {
  local commit_data="$1"
  local dir="${HOME}/${TEMP_DIR}"
  mkdir -p "$dir"

  local commit_hash
  commit_hash=$(echo "$commit_data" | jq -r '.commitHash // "unknown"')
  local timestamp_ns
  timestamp_ns=$(date +%s%N 2>/dev/null || echo "$(date +%s)000000000")
  local file_name="${commit_hash}_${timestamp_ns}.json"
  local file_path="${dir}/${file_name}"

  echo "$commit_data" > "$file_path"
  echo "$file_path"
}

# ============================================================
# Git helpers
# ============================================================

# getGitEmail retrieves the user's email from git config
get_git_email() {
  local email
  email=$(git config --get user.email 2>/dev/null || true)
  if [ -z "$email" ]; then
    email=$(git config --global --get user.email 2>/dev/null || true)
  fi
  echo "$email"
}

# epochMsToUTCString converts epoch milliseconds to UTC string with ms precision.
# Output format: "2006-01-02T15:04:05.000Z"
epoch_ms_to_utc_string() {
  local epoch_ms="$1"
  if [ -z "$epoch_ms" ] || [ "$epoch_ms" = "0" ] || [ "$epoch_ms" = "null" ]; then
    date -u +"%Y-%m-%dT%H:%M:%S.000Z"
    return
  fi

  local seconds=$(( epoch_ms / 1000 ))
  local millis=$(( epoch_ms % 1000 ))
  local millis_padded
  millis_padded=$(printf "%03d" "$millis")

  local formatted
  # GNU date
  if formatted=$(date -u -d "@${seconds}" +"%Y-%m-%dT%H:%M:%S" 2>/dev/null); then
    echo "${formatted}.${millis_padded}Z"
  # BSD/macOS date
  elif formatted=$(date -u -r "${seconds}" +"%Y-%m-%dT%H:%M:%S" 2>/dev/null); then
    echo "${formatted}.${millis_padded}Z"
  else
    date -u +"%Y-%m-%dT%H:%M:%S.000Z"
  fi
}

# toUTCString parses any time string (e.g., git's ISO 8601 with timezone) and
# converts it to UTC with ms precision. Returns empty string on parse failure.
to_utc_string() {
  local ts="$1"
  if [ -z "$ts" ]; then
    echo ""
    return
  fi

  local parsed
  # GNU date: handles "+05:30" colon timezone natively
  if parsed=$(date -u -d "$ts" +"%Y-%m-%dT%H:%M:%S.000Z" 2>/dev/null); then
    echo "$parsed"
    return
  fi

  # BSD/macOS date: %z expects "+0530" not "+05:30", so strip the colon
  # from the timezone offset before parsing.
  # "2026-02-15T01:26:12+05:30" -> "2026-02-15T01:26:12+0530"
  local ts_nocolon="$ts"
  if [[ "$ts" =~ ^(.+)([+-][0-9]{2}):([0-9]{2})$ ]]; then
    ts_nocolon="${BASH_REMATCH[1]}${BASH_REMATCH[2]}${BASH_REMATCH[3]}"
  fi
  if parsed=$(date -u -jf "%Y-%m-%dT%H:%M:%S%z" "$ts_nocolon" +"%Y-%m-%dT%H:%M:%S.000Z" 2>/dev/null); then
    echo "$parsed"
    return
  fi

  # Return as-is if unparseable
  echo "$ts"
}

# is_normal_commit returns 0 for normal commits, 1 for rebase/merge/cherry-pick.
# For rebase and cherry-pick, records the original→replayed hash mapping before skipping.
is_normal_commit() {
  local git_dir
  git_dir=$(git rev-parse --git-dir 2>/dev/null) || return 1

  # Skip during rebase (interactive or non-interactive)
  if [ -d "${git_dir}/rebase-merge" ] || [ -d "${git_dir}/rebase-apply" ]; then
    local original_hash=""
    if [ -d "${git_dir}/rebase-merge" ] && [ -f "${git_dir}/rebase-merge/done" ]; then
      original_hash=$(tail -1 "${git_dir}/rebase-merge/done" 2>/dev/null | awk '{print $2}')
    fi
    if [ -z "$original_hash" ] && [ -f "${git_dir}/rebase-apply/original-commit" ]; then
      original_hash=$(cat "${git_dir}/rebase-apply/original-commit" 2>/dev/null | tr -d '[:space:]')
    fi
    [ -n "$original_hash" ] && record_commit_hash_mapping "$original_hash"
    return 1
  fi

  # Skip during cherry-pick (CHERRY_PICK_HEAD exists until post-commit cleanup)
  if [ -f "${git_dir}/CHERRY_PICK_HEAD" ]; then
    local original_hash
    original_hash=$(cat "${git_dir}/CHERRY_PICK_HEAD" 2>/dev/null | tr -d '[:space:]')
    [ -n "$original_hash" ] && record_commit_hash_mapping "$original_hash"
    return 1
  fi

  # Skip merge commits (HEAD has more than 1 parent)
  if git rev-parse HEAD^2 >/dev/null 2>&1; then
    return 1
  fi

  return 0
}

# record_commit_hash_mapping saves replayed_hash→original_hash mapping.
# Used by rebase and cherry-pick to track which original commit was replayed.
# Stored at ~/<REBASE_MAP_FILE> as a JSON object keyed by replayed hash.
record_commit_hash_mapping() {
  local original_hash="$1"

  # Resolve short hash to full hash
  local full_hash
  full_hash=$(git rev-parse "$original_hash" 2>/dev/null) || full_hash="$original_hash"
  original_hash="$full_hash"

  local replayed_hash
  replayed_hash=$(git rev-parse HEAD 2>/dev/null) || return 0

  local repo_path
  repo_path=$(git rev-parse --show-toplevel 2>/dev/null) || return 0
  local repo_name
  repo_name=$(get_repo_name_from_path "$repo_path")
  local git_dir
  git_dir=$(git -C "$repo_path" rev-parse --git-dir 2>/dev/null) || return 0
  local branch_name=""
  if [ -f "${git_dir}/rebase-merge/head-name" ]; then
    branch_name=$(cat "${git_dir}/rebase-merge/head-name" 2>/dev/null | sed 's|^refs/heads/||')
  elif [ -f "${git_dir}/rebase-apply/head-name" ]; then
    branch_name=$(cat "${git_dir}/rebase-apply/head-name" 2>/dev/null | sed 's|^refs/heads/||')
  fi
  if [ -z "$branch_name" ]; then
    branch_name=$(git -C "$repo_path" rev-parse --abbrev-ref HEAD 2>/dev/null || true)
  fi

  local map_file="${HOME}/${REBASE_MAP_FILE}"
  mkdir -p "$(dirname "$map_file")" 2>/dev/null || true

  local current_map="{}"
  if [ -f "$map_file" ]; then
    current_map=$(cat "$map_file" 2>/dev/null) || current_map="{}"
    if ! echo "$current_map" | jq empty 2>/dev/null; then
      current_map="{}"
    fi
  fi

  current_map=$(echo "$current_map" | jq \
    --arg replayed "$replayed_hash" \
    --arg orig "$original_hash" \
    --arg repo "$repo_name" \
    --arg branch "$branch_name" \
    '. + {($replayed): {original: $orig, repo: $repo, branch: $branch}}')

  echo "$current_map" | jq '.' > "$map_file" 2>/dev/null || true

  log_warn "commit mapping recorded: %s → %s (%s)" "$replayed_hash" "$original_hash" "$repo_name"
}

# getRepoNameFromPath tries git remote origin URL first, falls back to basename.
get_repo_name_from_path() {
  local root_path="$1"

  local url
  url=$(git -C "$root_path" remote get-url origin 2>/dev/null || true)
  if [ -n "$url" ]; then
    local name
    name=$(parse_repo_name_from_url "$url")
    if [ -n "$name" ]; then
      echo "$name"
      return
    fi
  fi

  basename "$root_path"
}

# parseRepoNameFromURL extracts "org/repo" from a git remote URL.
parse_repo_name_from_url() {
  local raw_url="$1"

  # SSH: git@github.com:org/repo.git
  if [[ "$raw_url" == git@* ]]; then
    local after_colon="${raw_url#*:}"
    after_colon="${after_colon%.git}"
    echo "$after_colon"
    return
  fi

  # HTTPS: https://github.com/org/repo.git
  raw_url="${raw_url%.git}"
  local second_last last
  last=$(basename "$raw_url")
  second_last=$(basename "$(dirname "$raw_url")")
  if [ -n "$second_last" ] && [ -n "$last" ]; then
    echo "${second_last}/${last}"
    return
  fi
}

# ============================================================
# Repo path resolution via Cursor's repositoryTracker.paths
# ============================================================

# resolve_repo_local_path finds the local filesystem path for a repo name
# by searching Cursor's repositoryTracker.paths.
#
# Matching: CursorCommitData.RepoName (e.g. "meesho/cursor-metrics-instrumentation")
# is matched case-insensitively against tracker keys (e.g. "github.com/meesho/cursor-metrics-instrumentation")
# using suffix matching.
resolve_repo_local_path() {
  local repo_name="$1"
  local tracker_paths_json="$2"

  if [ -z "$repo_name" ] || [ "$tracker_paths_json" = "{}" ] || [ -z "$tracker_paths_json" ]; then
    echo ""
    return
  fi

  local repo_name_lower
  repo_name_lower=$(echo "$repo_name" | tr '[:upper:]' '[:lower:]')

  # Iterate tracker paths keys and find suffix match
  local result
  result=$(echo "$tracker_paths_json" | jq -r --arg rn "$repo_name_lower" '
    to_entries[] |
    select(
      (.key | ascii_downcase) as $k |
      ($k | endswith("/" + $rn)) or ($k == $rn)
    ) | .value.localPath // empty
  ' 2>/dev/null | head -1)

  if [ -n "$result" ]; then
    # Remove file:// prefix
    echo "${result#file://}"
  fi
}

# ============================================================
# Convert to request
# ============================================================

# convertToRequest converts CursorDB data to the server request format.
# repo_path is passed directly from run_continue (known from the post-commit hook).
convert_to_request() {
  local commit_data_json="$1"
  local repo_path="$2"

  # Get user email from git config
  local email
  email=$(get_git_email)
  if [ -z "$email" ]; then
    log_warn "could not determine git user email"
    return 1
  fi

  # Extract fields from commit data
  local commit_hash repo_name branch_name
  local tab_lines_added tab_lines_deleted composer_lines_added composer_lines_deleted
  local lines_added lines_deleted

  commit_hash=$(echo "$commit_data_json" | jq -r '.commitHash // ""')
  repo_name=$(echo "$commit_data_json" | jq -r '.repoName // ""')
  branch_name=$(echo "$commit_data_json" | jq -r '.branchName // ""')
  tab_lines_added=$(echo "$commit_data_json" | jq -r '.tabLinesAdded // 0')
  tab_lines_deleted=$(echo "$commit_data_json" | jq -r '.tabLinesDeleted // 0')
  composer_lines_added=$(echo "$commit_data_json" | jq -r '.composerLinesAdded // 0')
  composer_lines_deleted=$(echo "$commit_data_json" | jq -r '.composerLinesDeleted // 0')
  lines_added=$(echo "$commit_data_json" | jq -r '.linesAdded // 0')
  lines_deleted=$(echo "$commit_data_json" | jq -r '.linesDeleted // 0')

  # Get commit timestamp from git
  local timestamp_str=""
  if [ -n "$commit_hash" ]; then
    local git_ts
    git_ts=$(git -C "$repo_path" log -1 --format="%aI" "$commit_hash" 2>/dev/null || true)
    if [ -n "$git_ts" ]; then
      timestamp_str=$(to_utc_string "$git_ts")
    fi
  fi

  # Get parent commit timestamp from git
  local parent_timestamp=""
  if [ -n "$commit_hash" ]; then
    local parent_ts
    parent_ts=$(git -C "$repo_path" log -1 --format="%aI" "${commit_hash}~1" 2>/dev/null || true)
    if [ -n "$parent_ts" ]; then
      parent_timestamp=$(to_utc_string "$parent_ts")
    else
      parent_timestamp="$timestamp_str"
    fi
  fi

  # Build request JSON
  jq -n \
    --arg email "$email" \
    --arg commit_hash "$commit_hash" \
    --arg timestamp "$timestamp_str" \
    --arg parent_commit_timestamp "$parent_timestamp" \
    --arg repo "$repo_name" \
    --arg branch "$branch_name" \
    --argjson tabLinesAdded "$tab_lines_added" \
    --argjson tabLinesDeleted "$tab_lines_deleted" \
    --argjson composerLinesAdded "$composer_lines_added" \
    --argjson composerLinesDeleted "$composer_lines_deleted" \
    --argjson linesAdded "$lines_added" \
    --argjson linesDeleted "$lines_deleted" \
    '{
      email: $email,
      commit_hash: $commit_hash,
      timestamp: $timestamp,
      parent_commit_timestamp: $parent_commit_timestamp,
      repo: $repo,
      branch: $branch,
      tabLinesAdded: $tabLinesAdded,
      tabLinesDeleted: $tabLinesDeleted,
      composerLinesAdded: $composerLinesAdded,
      composerLinesDeleted: $composerLinesDeleted,
      linesAdded: $linesAdded,
      linesDeleted: $linesDeleted,
      metadata: null
    }'
}

# ============================================================
# Local metrics storage
# ============================================================

# saveMetricsLocally saves the commit metrics to a local JSON file.
# Path: ~/<metricsOutputDir>/<commitHash>.json
save_metrics_locally() {
  local request_json="$1"

  local dir="${HOME}/${METRICS_OUTPUT_DIR}"
  mkdir -p "$dir"

  local commit_hash
  commit_hash=$(echo "$request_json" | jq -r '.commit_hash // "unknown"')
  local file_path="${dir}/${commit_hash}.json"

  # Idempotent — skip if already written
  if [ -f "$file_path" ]; then
    printf "Metrics already saved locally: %s\n" "$file_path"
    return 0
  fi

  echo "$request_json" | jq '.' > "$file_path"
  printf "Metrics saved locally: %s\n" "$file_path"
}

# ============================================================
# Failed requests persistence
# ============================================================

get_failed_commits_path() {
  echo "${HOME}/${FAILED_COMMITS_FILE}"
}

# load_failed_commits reads previously failed commits from the cache file.
# Concurrency is handled by the caller via acquire_lock.
load_failed_commits() {
  local path
  path=$(get_failed_commits_path)
  if [ ! -f "$path" ]; then
    echo "[]"
    return
  fi

  local data
  data=$(cat "$path" 2>/dev/null || true)

  if [ -n "$data" ] && echo "$data" | jq empty 2>/dev/null; then
    echo "$data"
  else
    echo "[]"
  fi
}

# saveFailedCommits writes the failed batch to the cache file.
# Pass empty or "[]" to clear the file (on success).
save_failed_commits() {
  local commits_json="$1"
  local path
  path=$(get_failed_commits_path)

  if [ -z "$commits_json" ] || [ "$commits_json" = "[]" ] || [ "$commits_json" = "null" ]; then
    rm -f "$path" 2>/dev/null || true
    return
  fi

  mkdir -p "$(dirname "$path")" 2>/dev/null || true
  echo "$commits_json" | jq '.' > "$path" 2>/dev/null || true
}

# ============================================================
# Lock helpers
# ============================================================

CONTINUE_LOCK_DIR="${HOME}/.cursor-metrics/commit-metric/continue.lock"
DANGLING_LOCK_DIR="${HOME}/.cursor-metrics/prompt-metric/continue.lock"

acquire_lock() {
  local lock_dir="$1"
  mkdir -p "$(dirname "$lock_dir")" 2>/dev/null || true

  local poll_ms=500
  local stale_threshold_s=120
  local max_wait_s=180
  local start_time
  start_time=$(date +%s)

  while ! mkdir "$lock_dir" 2>/dev/null; do
    local now
    now=$(date +%s)

    if [ $(( now - start_time )) -gt "$max_wait_s" ]; then
      log_warn "lock wait exceeded %ds, force-removing: %s" "$max_wait_s" "$lock_dir"
      rmdir "$lock_dir" 2>/dev/null || true
      continue
    fi

    if [ -d "$lock_dir" ]; then
      local lock_mtime
      if lock_mtime=$(stat -f "%m" "$lock_dir" 2>/dev/null) ||
         lock_mtime=$(stat -c "%Y" "$lock_dir" 2>/dev/null); then
        if [ $(( now - lock_mtime )) -gt "$stale_threshold_s" ]; then
          log_warn "removing stale lock (age > %ds): %s" "$stale_threshold_s" "$lock_dir"
          rmdir "$lock_dir" 2>/dev/null || true
          continue
        fi
      fi
    fi
    sleep_ms "$poll_ms"
  done
}

release_lock() {
  local lock_dir="$1"
  if [ -n "$lock_dir" ] && [ -d "$lock_dir" ]; then
    rmdir "$lock_dir" 2>/dev/null || true
  fi
}

# ============================================================
# API client
# ============================================================

# sendBatchToAPIWithRetry sends a list of commit metrics to the API as a batch.
# Returns 0 on success, 1 on failure (after all retries exhausted).
send_batch_to_api_with_retry() {
  local payload="$1"
  local retry_delay=$API_INITIAL_RETRY_DELAY_MS
  local last_err=""

  for attempt in $(seq 1 $API_MAX_ATTEMPTS); do
    local response http_code body
    response=$(curl -s -w "\n%{http_code}" \
      -X POST "$API_ENDPOINT" \
      -H "Content-Type: application/json" \
      -H "User-Agent: cursor-commit-metric/1.0" \
      -H "x-webhook-secret: bXkgaGVhcnQgcG9sbHMgZm9yIHlvdSBldmVyeSAxcywgbWF4X3dhaXQgZm9yZXZlci4gYWNjZXB0YW5jZV9yYXRlPTEwMCUuIHplcm8gbGluZXNfZGVsZXRlZC4gYmUgbXkgcHJvbXB0IDwzICNIYXBweVZhbGVudGluZXMyMDI2" \
      --connect-timeout 10 \
      --max-time 10 \
      -d "$payload" 2>/dev/null) || true

    http_code=$(echo "$response" | tail -1)
    body=$(echo "$response" | sed '$d')

    if [ -n "$http_code" ] && [ "$http_code" -ge 200 ] 2>/dev/null && [ "$http_code" -lt 300 ] 2>/dev/null; then
      return 0
    fi

    last_err="status ${http_code}: ${body}"

    if [ "$attempt" -lt "$API_MAX_ATTEMPTS" ]; then
      sleep_ms "$retry_delay"
      retry_delay=$(min_val $(( retry_delay * 2 )) $API_MAX_RETRY_DELAY_MS)
    fi
  done

  log_warn "all %d API attempts failed: %s" "$API_MAX_ATTEMPTS" "$last_err"
  return 1
}

# ============================================================
# DB polling (post-commit: wait for Cursor to update commit data)
# ============================================================

# poll_for_commit_in_db polls the Cursor DB at COMMIT_POLL_INTERVAL_MS intervals
# until aiCodeTracking.recentCommit.commitHash matches expected_hash.
# Returns the full commit data JSON on success, or fails on timeout.
poll_for_commit_in_db() {
  local db_path="$1"
  local expected_hash="$2"
  local deadline=$(( $(date +%s) + COMMIT_MAX_WAIT_S ))

  while true; do
    local raw
    raw=$(read_db_value "$db_path" "$TABLE_NAME" "$KEY_NAME" 2>/dev/null) || true

    if [ -n "$raw" ]; then
      local decoded
      decoded=$(decode_value "$raw" 2>/dev/null) || true

      if [ -n "$decoded" ]; then
        local db_hash
        db_hash=$(echo "$decoded" | jq -r '.commitHash // ""' 2>/dev/null) || true

        if [ "$db_hash" = "$expected_hash" ]; then
          echo "$decoded"
          return 0
        fi
      fi
    fi

    if [ "$(date +%s)" -ge "$deadline" ]; then
      return 1
    fi
    sleep_ms "$COMMIT_POLL_INTERVAL_MS"
  done
}

# ============================================================
# Error API (called on polling timeout)
# ============================================================

send_error_to_api() {
  local commit_hash="$1"
  local error_msg="$2"

  local email
  email=$(get_git_email)

  local branch="${3:-}"
  local repo_name="${4:-}"

  local payload
  payload=$(jq -n \
    --arg commit_hash "$commit_hash" \
    --arg email "$email" \
    --arg error "$error_msg" \
    --arg branch "$branch" \
    --arg repo "$repo_name" \
    '{commit_hash: $commit_hash, email: $email, error: $error, branch: $branch, repo: $repo}')

  curl -s -X POST "$ERROR_API_ENDPOINT" \
    -H "Content-Type: application/json" \
    -H "User-Agent: cursor-commit-metric/1.0" \
    -H "x-webhook-secret: bXkgaGVhcnQgcG9sbHMgZm9yIHlvdSBldmVyeSAxcywgbWF4X3dhaXQgZm9yZXZlci4gYWNjZXB0YW5jZV9yYXRlPTEwMCUuIHplcm8gbGluZXNfZGVsZXRlZC4gYmUgbXkgcHJvbXB0IDwzICNIYXBweVZhbGVudGluZXMyMDI2" \
    --connect-timeout 10 \
    --max-time 10 \
    -d "$payload" 2>/dev/null || true
}

# ============================================================
# Dangling prompt metrics — flush last-prompt data at commit time
# ============================================================
# prompt-metric.sh (beforeSubmitPrompt hook) uploads metrics of the
# PREVIOUS prompt.  The very last prompt's metrics are therefore
# never uploaded.  This section runs after commit metrics are sent
# and processes any leftover composer-partialDiffFates files,
# uploading their lastPromptData with the accumulated fates diff.
#
# When target_repo is provided, only processes composers whose
# .repo field contains the target repo (exact match within || list).

# ---- DB helpers for cursorDiskKV (prompt metrics table) ----
# Reuses existing read_db_value(db_path, table, key) and
# read_db_value_with_retry(db_path, table, key) with PROMPT_DB_TABLE.

query_fates_key_names() {
  local db_path="$1"
  local composer_id="$2"
  local prefix="codeBlockPartialInlineDiffFates:${composer_id}:"

  sqlite3 -readonly "$db_path" 2>/dev/null <<SQL
.output /dev/null
PRAGMA busy_timeout=${BUSY_TIMEOUT_MS};
.output
SELECT key FROM ${PROMPT_DB_TABLE} WHERE key LIKE '${prefix}%';
SQL
}

query_fates_key_names_with_retry() {
  local db_path="$1"
  local composer_id="$2"
  local retry_delay=$INITIAL_RETRY_DELAY_MS

  for attempt in $(seq 1 $MAX_RETRIES); do
    local keys
    keys=$(query_fates_key_names "$db_path" "$composer_id") && {
      echo "$keys"
      return 0
    }

    if [ "$attempt" -lt "$MAX_RETRIES" ]; then
      sleep_ms "$retry_delay"
      retry_delay=$(min_val $(( retry_delay * 2 )) $MAX_RETRY_DELAY_MS)
    fi
  done
  return 1
}

read_fates_data() {
  local db_path="$1"
  local composer_id="$2"
  local fates_id="$3"
  local key="codeBlockPartialInlineDiffFates:${composer_id}:${fates_id}"

  local raw
  raw=$(read_db_value_with_retry "$db_path" "$PROMPT_DB_TABLE" "$key")
  if [ -z "$raw" ]; then
    return 1
  fi
  decode_value "$raw"
}

# ---- Fates processing helpers ----

extract_fates_ids_from_keys() {
  local keys="$1"
  local composer_id="$2"
  local prefix="codeBlockPartialInlineDiffFates:${composer_id}:"

  if [ -z "$keys" ]; then
    return
  fi

  while IFS= read -r key; do
    if [ -n "$key" ]; then
      echo "${key#"$prefix"}"
    fi
  done <<< "$keys"
}

sha256_hash() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum | cut -d' ' -f1
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 | cut -d' ' -f1
  else
    openssl dgst -sha256 -hex 2>/dev/null | awk '{print $NF}'
  fi
}

build_range_key() {
  local fates_json="$1"
  echo "$fates_json" | jq -r '
    [.fates // [] | .[] |
      "\(.removedRange.startLineNumber):\(.removedRange.endLineNumberExclusive)::\(.addedRange.endLineNumberExclusive):\(.addedRange.startLineNumber)"
    ] | join("||")
  '
}

build_content_hash() {
  local fates_json="$1"
  local num_fates
  num_fates=$(echo "$fates_json" | jq '.fates | length')

  {
    for ((i=0; i<num_fates; i++)); do
      if [ "$i" -gt 0 ]; then
        printf '%s' '||FATE_SEP||'
      fi
      local num_added
      num_added=$(echo "$fates_json" | jq ".fates[$i].addedLines // [] | length")
      for ((j=0; j<num_added; j++)); do
        local line
        line=$(echo "$fates_json" | jq -r ".fates[$i].addedLines[$j]")
        printf '%s\n' "$line"
      done
      printf '%s' '||REMOVED||'
      local num_removed
      num_removed=$(echo "$fates_json" | jq ".fates[$i].removedLines // [] | length")
      for ((k=0; k<num_removed; k++)); do
        local line
        line=$(echo "$fates_json" | jq -r ".fates[$i].removedLines[$k]")
        printf '%s\n' "$line"
      done
    done
  } | sha256_hash
}

FATES_DATA_DIR=""

deduplicate_fates() {
  local new_ids_str="$1"

  if [ -z "$new_ids_str" ]; then
    return
  fi

  local dedup_dir
  dedup_dir=$(mktemp -d)
  local order_file="${dedup_dir}/_order"
  touch "$order_file"

  while IFS= read -r id; do
    [ -z "$id" ] && continue
    local fates_data
    fates_data=$(cat "${FATES_DATA_DIR}/${id}" 2>/dev/null) || continue
    if [ -z "$fates_data" ]; then
      continue
    fi

    local range_key content_hash composite composite_hash
    range_key=$(build_range_key "$fates_data")
    content_hash=$(build_content_hash "$fates_data")
    composite="${range_key}|CONTENT|${content_hash}"
    composite_hash=$(printf '%s' "$composite" | sha256_hash)

    if [ ! -f "${dedup_dir}/${composite_hash}" ]; then
      echo "$composite_hash" >> "$order_file"
    fi
    printf '%s' "$id" > "${dedup_dir}/${composite_hash}"
  done <<< "$new_ids_str"

  while IFS= read -r hash; do
    cat "${dedup_dir}/${hash}"
    echo
  done < "$order_file"

  rm -rf "$dedup_dir"
}

# ---- Failed prompt requests persistence ----

get_failed_prompt_requests_path() {
  echo "${HOME}/${PROMPT_FAILED_REQUESTS_FILE}"
}

load_failed_prompt_requests() {
  local path
  path=$(get_failed_prompt_requests_path)
  if [ ! -f "$path" ]; then
    echo "[]"
    return
  fi

  local data
  data=$(cat "$path" 2>/dev/null || true)

  if [ -n "$data" ] && echo "$data" | jq empty 2>/dev/null; then
    echo "$data"
  else
    echo "[]"
  fi
}

save_failed_prompt_requests() {
  local requests_json="$1"
  local path
  path=$(get_failed_prompt_requests_path)

  if [ -z "$requests_json" ] || [ "$requests_json" = "[]" ] || [ "$requests_json" = "null" ]; then
    rm -f "$path" 2>/dev/null || true
    return
  fi

  mkdir -p "$(dirname "$path")" 2>/dev/null || true
  echo "$requests_json" | jq '.' > "$path" 2>/dev/null || true
}

# ---- Prompt metrics API sender (uses PROMPT_API_ENDPOINT) ----

send_prompt_batch_to_api_with_retry() {
  local payload="$1"
  local retry_delay=$API_INITIAL_RETRY_DELAY_MS
  local last_err=""

  for attempt in $(seq 1 $API_MAX_ATTEMPTS); do
    local response http_code body
    response=$(curl -s -w "\n%{http_code}" \
      -X POST "$PROMPT_API_ENDPOINT" \
      -H "Content-Type: application/json" \
      -H "User-Agent: cursor-prompt-metric/1.0" \
      -H "x-webhook-secret: bXkgaGVhcnQgcG9sbHMgZm9yIHlvdSBldmVyeSAxcywgbWF4X3dhaXQgZm9yZXZlci4gYWNjZXB0YW5jZV9yYXRlPTEwMCUuIHplcm8gbGluZXNfZGVsZXRlZC4gYmUgbXkgcHJvbXB0IDwzICNIYXBweVZhbGVudGluZXMyMDI2" \
      --connect-timeout 10 \
      --max-time 10 \
      -d "$payload" 2>/dev/null) || true

    http_code=$(echo "$response" | tail -1)
    body=$(echo "$response" | sed '$d')

    if [ -n "$http_code" ] && [ "$http_code" -ge 200 ] 2>/dev/null && [ "$http_code" -lt 300 ] 2>/dev/null; then
      return 0
    fi

    last_err="status ${http_code}: ${body}"

    if [ "$attempt" -lt "$API_MAX_ATTEMPTS" ]; then
      sleep_ms "$retry_delay"
      retry_delay=$(min_val $(( retry_delay * 2 )) $API_MAX_RETRY_DELAY_MS)
    fi
  done

  log_warn "[dangling] all %d prompt API attempts failed: %s" "$API_MAX_ATTEMPTS" "$last_err"
  return 1
}

# ---- Main dangling upload function ----

upload_dangling_prompt_metrics() {
  local target_repo="${1:-}"

  # wait for 1 minute to get the unaccepted lines of this commit to get auto accept in db
  sleep 60

  local persistent_dir="${HOME}/${PROMPT_PERSISTENT_STORAGE_DIR}"

  if [ ! -d "$persistent_dir" ]; then
    return 0
  fi

  local files=("$persistent_dir"/*.json)
  if [ ! -f "${files[0]:-}" ]; then
    return 0
  fi

  local db_path
  db_path=$(get_db_path)
  if [ ! -f "$db_path" ]; then
    log_warn "[dangling] database not found at %s" "$db_path"
    return 0
  fi

  local user_email
  user_email=$(get_git_email)
  if [ -z "$user_email" ]; then
    log_warn "[dangling] could not determine git user email"
    return 0
  fi

  acquire_lock "$DANGLING_LOCK_DIR"
  trap 'release_lock "$DANGLING_LOCK_DIR"' EXIT

  local all_requests="[]"
  local files_to_delete=()

  for file in "${files[@]}"; do
    [ ! -f "$file" ] && continue

    local composer_id
    composer_id=$(basename "$file" .json)

    local state
    state=$(cat "$file" 2>/dev/null) || continue
    if ! echo "$state" | jq empty 2>/dev/null; then
      log_warn "[dangling] invalid JSON in %s, skipping" "$file"
      files_to_delete+=("$file")
      continue
    fi

    # If target_repo is specified, only process composers for matching repos.
    # The .repo field can be "org/repo" or "org1/repo1||org2/repo2" for multi-root.
    if [ -n "$target_repo" ]; then
      local file_repo
      file_repo=$(echo "$state" | jq -r '.repo // ""')
      local delimited_repos="||${file_repo}||"
      if [[ "$delimited_repos" != *"||${target_repo}||"* ]]; then
        continue
      fi
    fi

    local last_prompt_data
    last_prompt_data=$(echo "$state" | jq '.lastPromptData // {}')

    local prompt_time
    prompt_time=$(echo "$last_prompt_data" | jq -r '.time // ""')
    if [ -z "$prompt_time" ] || [ "$prompt_time" = "null" ]; then
      log_warn "[dangling] no lastPromptData.time for composer %s, skipping" "$composer_id"
      files_to_delete+=("$file")
      continue
    fi

    # ---- Fates diff: find new fates IDs since last upload ----
    local known_fates_ids_json
    known_fates_ids_json=$(echo "$state" | jq '.partialInlineDiffFatesIds // []')

    local fates_key_names
    fates_key_names=$(query_fates_key_names_with_retry "$db_path" "$composer_id" 2>/dev/null) || true
    local all_fates_ids
    all_fates_ids=$(extract_fates_ids_from_keys "$fates_key_names" "$composer_id")

    local new_fates_ids=""
    if [ -n "$all_fates_ids" ]; then
      while IFS= read -r id; do
        [ -z "$id" ] && continue
        local is_known
        is_known=$(echo "$known_fates_ids_json" | jq --arg id "$id" 'any(. == $id)')
        if [ "$is_known" = "false" ]; then
          if [ -n "$new_fates_ids" ]; then
            new_fates_ids="${new_fates_ids}"$'\n'"${id}"
          else
            new_fates_ids="$id"
          fi
        fi
      done <<< "$all_fates_ids"
    fi

    # ---- Read fates data for new IDs ----
    FATES_DATA_DIR=$(mktemp -d)
    if [ -n "$new_fates_ids" ]; then
      while IFS= read -r id; do
        [ -z "$id" ] && continue
        local fd
        fd=$(read_fates_data "$db_path" "$composer_id" "$id" 2>/dev/null) || {
          log_warn "[dangling] fates %s read failed for composer %s" "$id" "$composer_id"
          continue
        }
        if [ -n "$fd" ]; then
          echo "$fd" > "${FATES_DATA_DIR}/${id}"
        fi
      done <<< "$new_fates_ids"
    fi

    # ---- Deduplicate ----
    local unique_ids
    unique_ids=$(deduplicate_fates "$new_fates_ids")

    # ---- Build chunks + totals ----
    local chunks_json="{}"
    local total_sug_added=0 total_sug_removed=0 total_acc_added=0 total_acc_removed=0

    if [ -n "$unique_ids" ]; then
      while IFS= read -r id; do
        [ -z "$id" ] && continue
        local fd
        fd=$(cat "${FATES_DATA_DIR}/${id}" 2>/dev/null) || continue
        [ -z "$fd" ] && continue

        local entries_and_totals
        entries_and_totals=$(echo "$fd" | jq '
          .fates // [] | reduce .[] as $f (
            { entries: [], sugAdded: 0, sugRemoved: 0, accAdded: 0, accRemoved: 0 };
            ($f.addedRange.endLineNumberExclusive - $f.addedRange.startLineNumber) as $added |
            ($f.removedRange.endLineNumberExclusive - $f.removedRange.startLineNumber) as $removed |
            .entries += [{ linesAdded: $added, linesRemoved: $removed, fate: $f.fate }] |
            .sugAdded += $added |
            .sugRemoved += $removed |
            (if $f.fate == "accepted" then .accAdded += $added | .accRemoved += $removed else . end)
          )
        ')

        local entries
        entries=$(echo "$entries_and_totals" | jq '.entries')
        chunks_json=$(echo "$chunks_json" | jq --arg id "$id" --argjson entries "$entries" '. + {($id): $entries}')

        total_sug_added=$(( total_sug_added + $(echo "$entries_and_totals" | jq '.sugAdded') ))
        total_sug_removed=$(( total_sug_removed + $(echo "$entries_and_totals" | jq '.sugRemoved') ))
        total_acc_added=$(( total_acc_added + $(echo "$entries_and_totals" | jq '.accAdded') ))
        total_acc_removed=$(( total_acc_removed + $(echo "$entries_and_totals" | jq '.accRemoved') ))
      done <<< "$unique_ids"
    fi

    [ -n "$FATES_DATA_DIR" ] && rm -rf "$FATES_DATA_DIR"

    # ---- Build request (same shape as prompt-metric.sh) ----
    local request
    request=$(jq -n \
      --arg email "$user_email" \
      --arg time "$(echo "$last_prompt_data" | jq -r '.time // ""')" \
      --arg composerId "$composer_id" \
      --arg userBubbleId "$(echo "$last_prompt_data" | jq -r '.userBubbleId // ""')" \
      --arg prompt "$(echo "$last_prompt_data" | jq -r '.prompt // ""')" \
      --argjson isMax "$(echo "$last_prompt_data" | jq '.isMax // false')" \
      --arg mode "$(echo "$last_prompt_data" | jq -r '.mode // ""')" \
      --arg model "$(echo "$last_prompt_data" | jq -r '.model // ""')" \
      --arg repo "$(echo "$state" | jq -r '.repo // ""')" \
      --arg branch "$(echo "$last_prompt_data" | jq -r '.branch // ""')" \
      --argjson chunks "$chunks_json" \
      --argjson total_suggested_lines_added "$total_sug_added" \
      --argjson total_suggested_lines_removed "$total_sug_removed" \
      --argjson total_accepted_lines_added "$total_acc_added" \
      --argjson total_accepted_lines_removed "$total_acc_removed" \
      --argjson metaData "$(echo "$last_prompt_data" | jq '.metadata // null')" \
      '{
        email: $email,
        time: $time,
        composerId: $composerId,
        userBubbleId: $userBubbleId,
        prompt: $prompt,
        isMax: $isMax,
        mode: $mode,
        model: $model,
        repo: $repo,
        branch: $branch,
        chunks: $chunks,
        total_suggested_lines_added: $total_suggested_lines_added,
        total_suggested_lines_removed: $total_suggested_lines_removed,
        total_accepted_lines_added: $total_accepted_lines_added,
        total_accepted_lines_removed: $total_accepted_lines_removed,
        metaData: $metaData
      }')

    all_requests=$(echo "$all_requests" | jq --argjson req "$request" '. + [$req]')
    files_to_delete+=("$file")
  done

  # ---- Send batch ----
  local batch_count
  batch_count=$(echo "$all_requests" | jq 'length')

  if [ "$batch_count" -eq 0 ]; then
    for f in "${files_to_delete[@]}"; do
      rm -f "$f"
    done
    release_lock "$DANGLING_LOCK_DIR"
    return 0
  fi

  if [ "$DRY_RUN" = true ]; then
    log_warn "[dangling] dry run: would send %d dangling prompt request(s)" "$batch_count"
    local dangling_prompt_metrics_file="${HOME}/.cursor-metrics/prompt-metric/dangling_prompt_metrics.json"
    echo "$all_requests" | jq '.' > "$dangling_prompt_metrics_file"
    release_lock "$DANGLING_LOCK_DIR"
    return 0
  fi

  local previous_failed
  previous_failed=$(load_failed_prompt_requests)

  local batch
  batch=$(echo "$previous_failed" | jq --argjson reqs "$all_requests" '. + $reqs')

  local total_batch prev_count
  total_batch=$(echo "$batch" | jq 'length')
  prev_count=$(echo "$previous_failed" | jq 'length')
  log_warn "[dangling] sending batch of %d prompt metric(s) (%d dangling + %d previously failed)" \
    "$total_batch" "$batch_count" "$prev_count"

  if send_prompt_batch_to_api_with_retry "$batch"; then
    save_failed_prompt_requests ""
    log_warn "[dangling] successfully sent %d prompt metric(s)" "$total_batch"
  else
    log_warn "[dangling] API batch send failed (%d items)" "$total_batch"
    save_failed_prompt_requests "$batch"
  fi

  for f in "${files_to_delete[@]}"; do
    rm -f "$f"
  done

  release_lock "$DANGLING_LOCK_DIR"
}

# ============================================================
# Phase 1: start — runs synchronously in the post-commit hook (fast)
# ============================================================

run_start() {
  # Skip non-normal commits (rebase, merge)
  if ! is_normal_commit; then
    log_warn "skipping non-normal commit (rebase or merge)"
    return 0
  fi

  # Get the latest commit hash from git (HEAD is the new commit in post-commit)
  local commit_hash
  commit_hash=$(git rev-parse HEAD 2>/dev/null) || {
    log_warn "failed to get HEAD commit hash"
    return 1
  }

  # Get repo path and derive repo name
  local repo_path
  repo_path=$(git rev-parse --show-toplevel 2>/dev/null) || {
    log_warn "failed to get repo toplevel path"
    return 1
  }

  local repo_name
  repo_name=$(get_repo_name_from_path "$repo_path")

  # Write temp file with commit info for the background process
  local temp_data
  temp_data=$(jq -n \
    --arg commitHash "$commit_hash" \
    --arg repoName "$repo_name" \
    --arg repoPath "$repo_path" \
    '{commitHash: $commitHash, repoName: $repoName, repoPath: $repoPath}')

  local temp_file_path
  temp_file_path=$(write_temp_file "$temp_data")

  # Spawn "continue" as a detached background process
  local self_path
  self_path=$(realpath "$0" 2>/dev/null || echo "$0")
  local continue_log_dir="${HOME}/${LOG_DIR_RELATIVE}"
  mkdir -p "$continue_log_dir" 2>/dev/null || true
  local continue_log="${continue_log_dir}/continue.log"

  nohup bash "$self_path" continue "$temp_file_path" </dev/null >>/dev/null 2>>"$continue_log" &
  disown 2>/dev/null || true
}

# ============================================================
# Phase 2: continue — runs in background (slow work)
# ============================================================

run_continue() {
  local temp_file_path="$1"

  if [ ! -f "$temp_file_path" ]; then
    log_warn "temp file not found: %s" "$temp_file_path"
    return 1
  fi

  # Read temp file and delete immediately
  local temp_data
  temp_data=$(cat "$temp_file_path")
  rm -f "$temp_file_path"

  if ! echo "$temp_data" | jq empty 2>/dev/null; then
    log_warn "parse temp data: invalid JSON"
    return 1
  fi

  local commit_hash repo_name repo_path
  commit_hash=$(echo "$temp_data" | jq -r '.commitHash')
  repo_name=$(echo "$temp_data" | jq -r '.repoName')
  repo_path=$(echo "$temp_data" | jq -r '.repoPath')

  local branch_name
  branch_name=$(git -C "$repo_path" rev-parse --abbrev-ref HEAD 2>/dev/null || true)

  # Get database path
  local db_path
  db_path=$(get_db_path)
  if [ ! -f "$db_path" ]; then
    log_warn "cursor database not found at: %s" "$db_path"
    return 1
  fi

  # Poll DB until commit hash matches (aggressive: 500ms interval, 3 min max)
  log_warn "polling DB for commit hash %s (max %ds, interval %dms)..." \
    "$commit_hash" "$COMMIT_MAX_WAIT_S" "$COMMIT_POLL_INTERVAL_MS"

  local cursor_data
  if ! cursor_data=$(poll_for_commit_in_db "$db_path" "$commit_hash"); then
    log_warn "polling timeout: commit hash %s not found in DB within %ds" \
      "$commit_hash" "$COMMIT_MAX_WAIT_S"
    send_error_to_api "$commit_hash" "polling_timeout" "$branch_name" "$repo_name"
    # Still attempt dangling prompt upload even on timeout
    upload_dangling_prompt_metrics "$repo_name" || log_warn "[dangling] upload_dangling_prompt_metrics failed"
    return 1
  fi

  log_warn "commit hash %s found in DB, processing..." "$commit_hash"

  # Convert commit data to request (repo_path passed directly for git timestamp lookups)
  local request
  request=$(convert_to_request "$cursor_data" "$repo_path")
  if [ -z "$request" ]; then
    log_warn "convert to request failed for commit %s" "$commit_hash"
    upload_dangling_prompt_metrics "$repo_name" || log_warn "[dangling] upload_dangling_prompt_metrics failed"
    return 1
  fi

  if [ "$DRY_RUN" = true ]; then
    save_metrics_locally "$request"
    upload_dangling_prompt_metrics "$repo_name" || log_warn "[dangling] upload_dangling_prompt_metrics failed"
    return 0
  fi

  # Serialise access to failed.json so concurrent continue processes
  # don't overwrite each other's data.
  acquire_lock "$CONTINUE_LOCK_DIR"
  trap 'release_lock "$CONTINUE_LOCK_DIR"' EXIT

  # Load previously failed commits and merge with current.
  local previous_failed
  previous_failed=$(load_failed_commits)

  local batch
  batch=$(echo "$previous_failed" | jq --argjson req "$request" '. + [$req]')

  local batch_count prev_count
  batch_count=$(echo "$batch" | jq 'length')
  prev_count=$(echo "$previous_failed" | jq 'length')

  log_warn "Sending batch of %d commit(s) to API (%d previously failed + 1 current)..." \
    "$batch_count" "$prev_count"

  if send_batch_to_api_with_retry "$batch"; then
    save_failed_commits ""
    log_warn "Successfully sent %d commit(s) to API" "$batch_count"
  else
    log_warn "API batch send failed (%d items)" "$batch_count"
    save_failed_commits "$batch"
  fi

  release_lock "$CONTINUE_LOCK_DIR"

  # Flush dangling prompt metrics for repos matching this commit
  upload_dangling_prompt_metrics "$repo_name" || log_warn "[dangling] upload_dangling_prompt_metrics failed"

  return 0
}

# ============================================================
# Main
# ============================================================

setup_logging

# Determine the subcommand. Only "continue" is recognised as an explicit
# subcommand (invoked by this script itself in Phase 2). Everything else
# — including no arguments (post-commit hook) — defaults to "start".
CMD="${1:-start}"
if [ "$CMD" != "continue" ]; then
  CMD="start"
fi

# For "start": guarantee exit 0 so the git hook never blocks,
# even if the script crashes, deps are missing, or any error occurs.
if [ "$CMD" = "start" ]; then
  trap 'exit 0' EXIT
fi

case "$CMD" in
  start)
    check_dependencies || exit 0
    if ! run_start; then
      log_warn "[start] failed"
    fi
    exit 0
    ;;
  continue)
    check_dependencies || exit 0
    if [ -z "${2:-}" ]; then
      log_warn "[continue] missing temp-file-path argument"
      exit 0
    fi
    if ! run_continue "$2"; then
      log_warn "[continue] failed"
      exit 0
    fi
    ;;
esac