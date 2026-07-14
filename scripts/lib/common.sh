#!/usr/bin/env bash

# ==============================================================================
# Shared Bash Utilities and Verification Logic
# ==============================================================================

# Terminal Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging Helpers
log_info() {
  echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
  echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
  echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
  echo -e "${RED}[ERROR]${NC} $1" >&2
}

# Verify .env exists in docker/
verify_env_file() {
  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  local project_root
  project_root="$(cd "${script_dir}/../.." && pwd)"
  
  if [ ! -f "${project_root}/docker/.env" ]; then
    log_error "The configuration file 'docker/.env' is missing!"
    log_error "Please copy 'docker/.env.example' to 'docker/.env' and configure your secrets before proceeding."
    exit 1
  fi
}

# Load .env variables
load_env() {
  verify_env_file
  
  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  local project_root
  project_root="$(cd "${script_dir}/../.." && pwd)"
  
  # Export non-commented lines from .env
  set -a
  # shellcheck disable=SC1090
  source "${project_root}/docker/.env"
  set +a
}

# Verify Docker command availability
verify_docker() {
  if ! command -v docker &> /dev/null; then
    log_error "Docker is not installed or not in PATH. Please install Docker first."
    exit 1
  fi
  
  # Check if docker compose works (v2+)
  if ! docker compose version &> /dev/null; then
    log_error "Docker Compose v2+ is required but 'docker compose' was not found."
    exit 1
  fi
}

# Verify utility dependencies (curl, etc.)
verify_dependency() {
  local dep=$1
  if ! command -v "$dep" &> /dev/null; then
    log_error "Required CLI dependency '$dep' is missing. Please install it."
    exit 1
  fi
}
