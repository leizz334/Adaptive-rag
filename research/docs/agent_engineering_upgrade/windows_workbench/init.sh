#!/usr/bin/env bash
# Read-only recovery; never initialize data or select a paid provider.
set -u
git status --short
git log -4 --oneline
git stash list
docker compose -f compose.showcase.yml ps -a
docker version
docker compose version
