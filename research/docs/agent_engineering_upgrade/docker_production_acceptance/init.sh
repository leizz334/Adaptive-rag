#!/bin/sh
# Repeatable read-only checks; existing project initialization retained.
set -eu
docker version --format '{{.Server.Version}}'
docker compose version
docker ps --format '{{.Names}} {{.Status}} {{.Ports}}'
