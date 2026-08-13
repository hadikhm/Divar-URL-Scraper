import argparse
import csv
import re
import time
from pathlib import Path
from urllib.parse import urljoin

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait

BASE_URL = "https://divar.ir"
SEARCH_RE = re.compile(r"https://divar\.ir/s/[^\s)\]>]+")
LISTING_RE = re.compile(r"^https://divar\.ir/v/[^?#]+")


def make_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1440,2000")
    options.add_argument("--lang=fa-IR")
    return webdriver.Chrome(options=options)


def normalize_search_url(url):
    url = url.strip().rstrip(".,;")
    if not url.startswith("https://divar.ir/s/"):
        return None
    return url


def read_search_urls(path):
    text = Path(path).read_text(encoding="utf-8")
    urls = []
    for match in SEARCH_RE.findall(text):
        url = normalize_search_url(match)
        if url:
            urls.append(url)
    if not urls:
        for line in text.splitlines():
            url = normalize_search_url(line)
            if url:
                urls.append(url)
    return list(dict.fromkeys(urls))


def extract_listing_urls_snapshot(driver):
    """Snapshot href strings from the current DOM without retaining WebElements."""
    hrefs = driver.execute_script("""
        return Array.from(document.querySelectorAll('a[href]'))
            .map(a => a.href)
            .filter(Boolean);
    """)

    found = set()
    for href in hrefs or []:
        url = urljoin(BASE_URL, href)
        url = url.split("?")[0].split("#")[0]
        if LISTING_RE.match(url):
            found.add(url)
    return found


def collect_urls(driver, search_url, max_scrolls=80):
    print("Opening:", search_url)
    driver.get(search_url)

    WebDriverWait(driver, 30).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )

    found = set()
    unchanged_cycles = 0
    previous_count = 0

    for scroll_number in range(max_scrolls):
        # Take a point-in-time snapshot of URL strings. Divar can re-render its
        # DOM asynchronously, so we deliberately do not keep Selenium elements.
        found.update(extract_listing_urls_snapshot(driver))

        current_count = len(found)
        print(
            f"Scroll {scroll_number + 1}/{max_scrolls} "
            f"- {current_count} unique listing URLs"
        )

        if current_count == previous_count:
            unchanged_cycles += 1
        else:
            unchanged_cycles = 0
            previous_count = current_count

        if unchanged_cycles >= 5:
            print("No new listings detected. Stopping.")
            break

        driver.execute_script(
            "window.scrollTo(0, document.body.scrollHeight);"
        )
        time.sleep(2)

    found.update(extract_listing_urls_snapshot(driver))
    return sorted(found)


def save_results(results):
    txt_path = Path("divar_listing_urls.txt")
    csv_path = Path("divar_listing_urls.csv")
    unique_urls = sorted(results)
    txt_path.write_text(
        "\n".join(unique_urls) + ("\n" if unique_urls else ""),
        encoding="utf-8"
    )

    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["url", "source_search_urls"])
        for url in unique_urls:
            writer.writerow([url, " | ".join(results[url])])

    print("\n===================================")
    print(f"Collected {len(unique_urls)} unique listing URLs")
    print("===================================")
    print("TXT:", txt_path)
    print("CSV:", csv_path)


def main():
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--url", help="One Divar search URL")
    source.add_argument("--url-file", help="Text/Markdown file containing Divar search URLs")
    parser.add_argument("--max-scrolls", type=int, default=80)
    parser.add_argument(
        "--delay-between-searches",
        type=float,
        default=5.0,
        help="Seconds to wait between consecutive Divar search URLs"
    )
    args = parser.parse_args()

    if args.url:
        search_urls = [normalize_search_url(args.url)]
        if not search_urls[0]:
            raise SystemExit("The URL must be a Divar search URL beginning with https://divar.ir/s/")
    else:
        search_urls = read_search_urls(args.url_file)
        if not search_urls:
            raise SystemExit("No valid Divar search URLs were found in the input file.")

    print(f"Loaded {len(search_urls)} unique search URLs")
    print(f"Delay between searches: {args.delay_between_searches} seconds")

    driver = make_driver()
    results = {}
    try:
        for index, search_url in enumerate(search_urls, start=1):
            print(f"\n========== Search {index}/{len(search_urls)} ==========")
            urls = collect_urls(driver, search_url, args.max_scrolls)
            for url in urls:
                results.setdefault(url, [])
                if search_url not in results[url]:
                    results[url].append(search_url)
            print(f"Search result: {len(urls)} unique listing URLs")
            print(f"Combined result so far: {len(results)} unique listing URLs")

            if index < len(search_urls):
                print(f"Waiting {args.delay_between_searches} seconds before the next search...")
                time.sleep(args.delay_between_searches)
    finally:
        driver.quit()

    save_results(results)


if __name__ == "__main__":
    main()
