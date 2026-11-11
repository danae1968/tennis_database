# Tennis analyses: one entry point per analysis, shared code in src/tennis.
#   make data     download raw data (idempotent)      make test   run all tests
#   make all      rebuild every analysis from raw data (caches cleared first)
#   make <name>   rebuild one analysis: serve_first | birth_months | match_length_trends
#   make clean    remove caches and build artefacts (never touches data, results or figures)

PY ?= .venv/bin/python
ANALYSES := serve_first birth_months match_length_trends

.PHONY: all data test install clean clean-cache $(ANALYSES)

all: clean-cache $(ANALYSES)

$(ANALYSES):
	$(PY) analyses/$@/run.py

test:
	$(PY) -m pytest

data:
	bash scripts/download_data.sh

install:
	$(PY) -m pip install -e ".[dev]"

clean-cache:
	rm -rf analyses/*/cache

clean: clean-cache
	rm -rf .pytest_cache src/*.egg-info build dist
	find . -path ./.venv -prune -o -type d -name __pycache__ -prune -exec rm -rf {} +
	find analyses -name "*.tmp.png" -delete

# --- SONNET: top10_profiles ---------------------------------------------------
.PHONY: top10_profiles
top10_profiles:
	$(PY) analyses/top10_profiles/run.py
# --- end SONNET block ---------------------------------------------------------

# --- OPUS: new analyses -----------------------------------------------------------
.PHONY: serve_return_trends height_predicts_winner
serve_return_trends:
	$(PY) analyses/serve_return_trends/run.py

height_predicts_winner:
	$(PY) analyses/height_predicts_winner/run.py

all: serve_return_trends height_predicts_winner
# --- end OPUS block ----------------------------------------------------------------
