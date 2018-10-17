#!/usr/bin/env bash

# generate code reference
# sphinx-apidoc --ext-autodoc --ext-todo --ext-coverage --ext-viewcode -M -e -o ./apidocs ../src/
# generate gettext
make gettext
# generate po files updates
sphinx-intl update -p _build/gettext -l ru
# build lang specific docs
# make -e SPHINXOPTS="-D language='ru'" html

# build sphinx doc in html
make html
