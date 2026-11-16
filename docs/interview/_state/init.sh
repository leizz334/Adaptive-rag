#!/usr/bin/env bash
set -eu
git status --short
git log -5 --oneline
python docs/interview/_state/validate.py
