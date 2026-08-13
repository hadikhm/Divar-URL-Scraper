
import argparse
import csv
import re
import time
from pathlib import Path
from urllib.parse import urljoin

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait


BASE_URL = "https://divar.ir"
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

        # Collect every rendered link.
        elements = driver.find_elements(By.CSS_SELECTOR, "a[href]")

        for element in elements:
            href = element.get_attribute("href")

            if not href:
                continue

            url = urljoin(BASE_URL, href)
            url = url.split("?")[0].split("#")[0]

            if LISTING_RE.match(url):
                found.add(url)

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

        # Five consecutive scroll cycles with no new listings.
        if unchanged_cycles >= 5:
            print("No new listings detected. Stopping.")
            break

        driver.execute_script(
            "window.scrollTo(0, document.body.scrollHeight);"
        )

        time.sleep(2)

    # Final scan.
    elements = driver.find_elements(By.CSS_SELECTOR, "a[href]")

    for element in elements:
        href = element.get_attribute("href")

        if href:
            url = urljoin(BASE_URL, href)
            url = url.split("?")[0].split("#")[0]

            if LISTING_RE.match(url):
                found.add(url)

    return sorted(found)


def save_results(urls):
    txt_path = Path("divar_listing_urls.txt")
    csv_path = Path("divar_listing_urls.csv")

    txt_path.write_text(
        "\n".join(urls) + ("\n" if urls else ""),
        encoding="utf-8"
    )

    with csv_path.open(
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as f:

        writer = csv.writer(f)
        writer.writerow(["url"])

        for url in urls:
            writer.writerow([url])

    print()
    print("===================================")
    print(f"Collected {len(urls)} unique URLs")
    print("===================================")
    print("TXT:", txt_path)
    print("CSV:", csv_path)


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--url",
        required=True,
        help="Divar search URL"
    )

    parser.add_argument(
        "--max-scrolls",
        type=int,
        default=80
    )

    args = parser.parse_args()

    if not args.url.startswith("https://divar.ir/s/"):
        raise SystemExit(
            "The URL must be a Divar search URL beginning with https://divar.ir/s/"
        )

    driver = make_driver()

    try:
        urls = collect_urls(
            driver,
            args.url,
            args.max_scrolls
        )
    finally:
        driver.quit()

    save_results(urls)


if __name__ == "__main__":
    main()
