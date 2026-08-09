#!/usr/bin/env bash
# Paste this script into the Setup script field of a Claude Code cloud environment.
# It provisions VM-level utilities only. Repository dependencies belong in the
# optional SessionStart hook shipped under project/.claude/cloud/.
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

log() { printf '[MAD-CLOUD] %s\n' "$*"; }

if [[ "$(id -u)" -ne 0 ]]; then
  log 'ERROR: cloud setup scripts are expected to run as root.'
  exit 1
fi

log 'Provisioning MAD Ventures cloud utilities...'
if ! apt-get update -qq || ! apt-get install -y --no-install-recommends gh shellcheck ca-certificates; then
  log 'WARNING: optional cloud utility provisioning was incomplete. The session may continue; mad-cloud-doctor will report missing tools.'
fi
rm -rf /var/lib/apt/lists/* || true

install -d -m 0755 /opt/madventures
cat > /opt/madventures/cloud-environment.env <<'STATE'
MADVENTURES_CLOUD_ENVIRONMENT_VERSION=4.4.1
STATE

cat > /usr/local/bin/mad-cloud-doctor <<'DOCTOR'
#!/usr/bin/env bash
set -euo pipefail
printf 'MAD Ventures cloud environment\n'
printf '  git:        %s\n' "$(git --version 2>/dev/null || echo missing)"
printf '  gh:         %s\n' "$(gh --version 2>/dev/null | head -1 || echo missing)"
printf '  node:       %s\n' "$(node --version 2>/dev/null || echo missing)"
printf '  npm:        %s\n' "$(npm --version 2>/dev/null || echo missing)"
printf '  python:     %s\n' "$(python3 --version 2>/dev/null || echo missing)"
printf '  shellcheck: %s\n' "$(shellcheck --version 2>/dev/null | awk '/version:/ {print $2}' || echo missing)"
printf '  remote:     %s\n' "${CLAUDE_CODE_REMOTE:-false}"
DOCTOR
chmod 0755 /usr/local/bin/mad-cloud-doctor

log 'Cloud utility provisioning complete.'
mad-cloud-doctor
