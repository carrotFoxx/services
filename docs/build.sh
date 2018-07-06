#!/usr/bin/env bash
export FB_APP_ID=1 TYK_DASHBOARD_TOKEN=1 TYK_GATEWAY_TOKEN=1

# generate code reference
sphinx-apidoc --ext-autodoc --ext-todo --ext-coverage --ext-viewcode -M -e -o ./apidocs ../src/
# build sphinx doc in html
make html
