#!/usr/bin/env bash
# Manual trigger — activate env and post immediately
set -e
cd "$( dirname "${BASH_SOURCE[0]}" )/.."
/opt/miniconda3/envs/linkedin-autoposter/bin/python -m src.main "$@"
