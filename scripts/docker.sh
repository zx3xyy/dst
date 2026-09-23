#!/usr/bin/env bash
# Use current Docker access, or the already-authorized docker group.
set -euo pipefail
if docker info --format '{{.ServerVersion}}' >/dev/null 2>&1; then
    exec docker "$@"
fi
if id -nG "$USER" | tr ' ' '\n' | grep -qx docker; then
    docker_command=$(python3 -c 'import shlex,sys; print(shlex.join(["docker", *sys.argv[1:]]))' "$@")
    exec sg docker -c "$docker_command"
fi
echo 'Docker is not accessible. Start Docker and give this account access, then retry.' >&2
exit 1
