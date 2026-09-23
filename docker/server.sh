#!/bin/bash
set -euo pipefail
cd /opt/dst_server/bin64
exec ./dontstarve_dedicated_server_nullrenderer_x64 "$@"
