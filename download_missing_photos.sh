#!/usr/bin/env bash
# Quick-start script to download missing accommodation photos
# Usage:
#   ./download_missing_photos.sh --cf-clearance "<CF_CLEARANCE_COOKIE_FROM_BROWSER>"
#   or
#   CF_CLEARANCE="<TOKEN>" ./download_missing_photos.sh
#
# To get CF_CLEARANCE:
# 1. Open https://www.e-chalupy.cz in your browser
# 2. Open DevTools (F12) -> Application/Storage -> Cookies -> copy value of 'cf_clearance'
# 3. Run: ./download_missing_photos.sh --cf-clearance "<PASTE_HERE>"

set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$DIR"

# Ensure URL manifest is up to date
python3 export_missing_photos_urls.py

# Run downloader
python3 download_missing_photos.py "$@"
