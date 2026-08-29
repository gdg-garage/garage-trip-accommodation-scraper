import argparse
import email
from email import policy
import glob
import os
import re
import sys
import urllib.parse
from bs4 import BeautifulSoup

DEFAULT_OUTPUT_FILE = "urls.txt"
BASE_URL = "https://www.e-chalupy.cz"


def extract_html_from_file(file_path: str) -> str:
    """Extract HTML text from either pure .html or .mhtml files."""
    if file_path.endswith('.mhtml'):
        try:
            with open(file_path, 'rb') as f:
                raw = f.read(8 * 1024 * 1024)
            # Find boundary
            boundary_match = re.search(rb'boundary=\"?([^\";\r\n]+)\"?', raw)
            if boundary_match:
                parts = raw.split(b'--' + boundary_match.group(1))
                for part in parts:
                    if b'text/html' in part.lower():
                        header_end = part.find(b'\r\n\r\n')
                        if header_end == -1:
                            header_end = part.find(b'\n\n')
                        body = part[header_end+4:] if header_end != -1 else part
                        import quopri
                        if b'quoted-printable' in part.lower():
                            body = quopri.decodestring(body)
                        return body.decode('utf-8', errors='ignore')
        except Exception as e:
            print(f"Warning parsing MHTML {file_path}: {e}", file=sys.stderr)

    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def extract_accommodation_links(html_content: str, base_url: str = BASE_URL) -> list:
    """Extract all unique accommodation links from HTML content."""
    soup = BeautifulSoup(html_content, 'html.parser')
    links = set()

    for a in soup.find_all('a', href=True):
        href = a['href'].strip()
        if href and not href.startswith('#') and not href.startswith('javascript:'):
            full_url = urllib.parse.urljoin(base_url, href)
            if is_property_url(full_url):
                links.add(clean_property_url(full_url))

    return sorted(list(links))


def is_property_url(url: str) -> bool:
    """Check if URL matches accommodation property pattern."""
    excluded = [
        'chaty-chalupy-pronajem.php', 'index.php', 'hledam/', 'vyhledavani',
        'last-minute', 'vikendove-pobyty', 'registrace', 'prihlaseni',
        'oblibene', 'podminky', 'kontakt', 'bazen', 'sauna', 'virivk',
        'detska-postylka', 'ohniste', 'terasa', 'internet', 'spolecenska-mistnost'
    ]
    if any(ex in url for ex in excluded):
        return False

    if re.search(r'-o\d+(?:[/?#]|$)', url):
        return True

    if url.endswith('.php') and url.count('/') >= 4:
        return True

    return False


def clean_property_url(url: str) -> str:
    """Strip query parameters and anchors from property URL."""
    parsed = urllib.parse.urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


def parse_args():
    parser = argparse.ArgumentParser(description="Extract and deduplicate accommodation links from saved HTML/MHTML files.")
    parser.add_argument("inputs", nargs="*", default=["vyhledavani_index.html", "raw_regions/"], help="Files or directory containing saved pages")
    parser.add_argument("--output", "-o", type=str, default=DEFAULT_OUTPUT_FILE, help=f"Output URLs file (default: {DEFAULT_OUTPUT_FILE})")
    parser.add_argument("--preview", "-p", type=int, default=15, help="Number of sample links to show (default: 15)")
    return parser.parse_args()


def collect_files(input_paths):
    files = []
    for path in input_paths:
        if os.path.isdir(path):
            files.extend(glob.glob(os.path.join(path, "*.html")))
            files.extend(glob.glob(os.path.join(path, "*.mhtml")))
            files.extend(glob.glob(os.path.join(path, "*.htm")))
        elif os.path.isfile(path):
            files.append(path)
        else:
            # check glob
            matched = glob.glob(path)
            if matched:
                files.extend(matched)
    return sorted(list(set(files)))


def main():
    args = parse_args()
    files = collect_files(args.inputs)

    if not files:
        print(f"No valid HTML/MHTML files found in: {args.inputs}", file=sys.stderr)
        sys.exit(1)

    print(f"Processing {len(files)} files...")
    all_urls = set()

    for fpath in files:
        html = extract_html_from_file(fpath)
        urls = extract_accommodation_links(html)
        print(f"  • {os.path.basename(fpath):35s} -> {len(urls):4d} links")
        all_urls.update(urls)

    sorted_urls = sorted(list(all_urls))

    with open(args.output, "w", encoding="utf-8") as f:
        for u in sorted_urls:
            f.write(u + "\n")

    print(f"============================================================")
    print(f" Extraction Summary")
    print(f"============================================================")
    print(f"Files processed:               {len(files)}")
    print(f"Total unique Czech properties: {len(sorted_urls):,}")
    print(f"Output saved to:               {args.output}")
    print(f"------------------------------------------------------------")
    print(f"Sample of {min(args.preview, len(sorted_urls))} extracted links:")
    for idx, u in enumerate(sorted_urls[:args.preview], 1):
        print(f"  {idx:2d}. {u}")
    print(f"============================================================")


if __name__ == '__main__':
    main()

