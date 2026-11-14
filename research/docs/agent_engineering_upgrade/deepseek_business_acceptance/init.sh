#!/usr/bin/env bash
set -eu
git status --short
git log -5 --oneline
sudo docker ps --format "{{.Names}} {{.Status}}"
