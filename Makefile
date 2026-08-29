.PHONY: help install links scrape-links download-html html download-images images parse process gzip rank merge test clean

help:
	@echo "Available targets for 5-stage pipeline:"
	@echo "  install          Install python dependencies from requirements.txt"
	@echo "  links            Step 1: Scrape all accommodation URLs -> urls.txt"
	@echo "  download-html    Step 2: Download raw HTML pages -> html/*.html (supports sharding)"
	@echo "  download-images  Step 3: Download property photos -> imgs/ (supports sharding)"
	@echo "  parse            Step 4: Offline DOM parser & filter -> properties.json, out.csv, out.json"
	@echo "  rank             Step 5: Rank accommodations with Ollama (Gemma 2) -> ratings.json"
	@echo "  merge            Step 6: Merge LLM & manual ratings -> out-rated.csv"
	@echo "  test             Run all 36 unit tests"
	@echo "  clean            Remove temporary files and caches"

install:
	pip install -r requirements.txt

links: scrape-links

scrape-links:
	python3 scrape_links.py

download-html: html

html:
	python3 download_html.py

download-images: images

images:
	python3 download_images.py

parse:
	python3 parse_dom.py

process: parse

gzip:
	gzip -k -f properties.json

rank:
	python3 rank.py --model gemma2

merge:
	python3 merge_ratings.py

test:
	python3 -m unittest discover -s tests -v

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache


