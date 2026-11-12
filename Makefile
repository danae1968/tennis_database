# Tennis analyses: one entry point per analysis, shared code in src/tennis.
#   make data     download raw data (idempotent)      make test   run all tests
#   make all      rebuild every analysis from raw data (caches cleared first)
#   make <name>   rebuild one analysis (see ANALYSES below)
#   make site     build the website into _site/       make preview  live preview of the site
#   make clean    remove caches and build artefacts (never touches data, results or figures)

PY ?= .venv/bin/python
ANALYSES := serve_first birth_months match_length_trends \
            serve_return_trends height_predicts_winner top10_profiles

.PHONY: all data test install clean clean-cache site preview $(ANALYSES)

all: clean-cache $(ANALYSES)

$(ANALYSES):
	$(PY) analyses/$@/run.py

test:
	$(PY) -m pytest

data:
	bash scripts/download_data.sh

install:
	$(PY) -m pip install -e ".[dev]"

site:
	bash scripts/render_site.sh   # = quarto render (mirrored to a Linux folder on WSL /mnt drives)

preview:
	bash scripts/render_site.sh preview   # = quarto preview --no-browser

clean-cache:
	rm -rf analyses/*/cache

clean: clean-cache
	rm -rf .pytest_cache src/*.egg-info build dist
	find . -path ./.venv -prune -o -type d -name __pycache__ -prune -exec rm -rf {} +
	find analyses -name "*.tmp.png" -delete
