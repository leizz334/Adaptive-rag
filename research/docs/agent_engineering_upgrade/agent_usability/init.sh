#!/bin/sh
# Read-only recovery; never dispatches a model request.
set -eu
docker version --format '{{.Server.Version}}'
docker compose version
docker ps -a --format '{{.Names}} {{.Status}} {{.Ports}}'
