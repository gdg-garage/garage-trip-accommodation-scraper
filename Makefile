.PHONY: help install download scrape process gzip images get-images rank merge test clean

help:
	@echo "Available targets:"
	@echo "  install      Install python dependencies from requirements.txt"
	@echo "  scrape       Scrape accommodation properties from e-chalupy.cz -> properties.json"
	@echo "  process      Process, enrich, and filter properties -> out.csv, out.json"
	@echo "  gzip         Compress properties.json to properties.json.gz"
	@echo "  images       Download property photos to imgs/ directory"
	@echo "  rank         Rank filtered properties using Ollama LLM -> ratings.json"
	@echo "  merge        Merge LLM & manual ratings with CSV dataset -> out-rated.csv"
	@echo "  test         Run unit test suite"
	@echo "  clean        Remove temporary files and caches"

install:
	pip install -r requirements.txt

download: scrape

scrape:
	python3 download.py

process:
	python3 process.py

gzip:
	gzip -k -f properties.json

get-images: images

images:
	python3 get_images.py

rank:
	python3 rank.py

merge:
	python3 merge_ratings.py

test:
	python3 -m unittest discover -s tests -v

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache

