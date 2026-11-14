#!/bin/sh
# Read-only recovery checks; never starts paid work.
set -eu
docker version --format '{{.Server.Version}}'
docker compose version
docker ps -a --format '{{.Names}} {{.Status}} {{.Ports}}'
