#!/usr/bin/env python3
"""
productstore.uz kategoriya/katalog sahifasidagi barcha mahsulotlarni topib,
har birining ichiga kirib ma'lumotlarini data_products.json ga saqlaydi.

scrape_product.py shu skript bilan bir papkada turishi kerak.

Ishlatish:
    python scrape_category.py "https://productstore.uz/category"
    python scrape_category.py "<url>" -o data_products.json --delay 1
"""
import argparse
import json
import sys
import time
from urllib.parse import urljoin, urlparse, urlencode, parse_qsl, urlunparse

import requests
from bs4 import BeautifulSoup

from scrape_product import BASE, fetch, scrape

DEFAULT_URL = "https://productstore.uz/katalog"
MAX_PAGES = 100  # xavfsizlik chegarasi


def with_page(url: str, page: int) -> str:
    p = urlparse(url)
    q = dict(parse_qsl(p.query))
    if page > 1:
        q["page"] = str(page)
    else:
        q.pop("page", None)
    return urlunparse(p._replace(query=urlencode(q, safe="/")))


def retry_fetch(url, tries=3, delay=2.0):
    last = None
    for i in range(tries):
        try:
            return fetch(url)
        except requests.RequestException as e:
            last = e
            time.sleep(delay * (i + 1))
    raise last


def collect_product_links(category_url: str, delay: float):
    """Barcha sahifalardan mahsulot havolalarini yig'adi (tartibni saqlagan holda)."""
    links, seen = [], set()
    for page in range(1, MAX_PAGES + 1):
        url = with_page(category_url, page)
        soup = BeautifulSoup(retry_fetch(url), "html.parser")
        new = 0
        for a in soup.find_all("a", href=True):
            path = urlparse(urljoin(BASE, a["href"])).path
            if not path.startswith("/product/"):
                continue
            full = urljoin(BASE, path)
            if full not in seen:
                seen.add(full)
                links.append(full)
                new += 1
        print(f"  sahifa {page}: {new} ta yangi mahsulot")
        if new == 0:  # yangi mahsulot yo'q -> oxirgi sahifa o'tib bo'lingan
            break
        # keyingi sahifaga havola bormi?
        next_page = f"page={page + 1}"
        if not any(next_page in (a["href"] or "") for a in soup.find_all("a", href=True)):
            break
        time.sleep(delay)
    return links


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url", nargs="?", default=DEFAULT_URL)
    ap.add_argument("-o", "--output", default="data_products.json")
    ap.add_argument("--delay", type=float, default=0.7, help="so'rovlar orasidagi kutish (soniya)")
    args = ap.parse_args()

    print(f"Ro'yxat yig'ilmoqda: {args.url}")
    try:
        links = collect_product_links(args.url, args.delay)
    except requests.RequestException as e:
        sys.exit(f"Ro'yxatni yuklashda xatolik: {e}")
    print(f"Jami {len(links)} ta mahsulot topildi\n")

    products, failed = [], []
    for i, link in enumerate(links, 1):
        try:
            data = scrape(link)
            # "O'xshash mahsulotlar" va keraksiz texnik ma'lumotlar saqlanmaydi
            for key in ("similar_products", "json_ld", "embedded_json"):
                data.pop(key, None)
            products.append(data)
            print(f"[{i}/{len(links)}] OK  {data['name']} — {data['price']['text']}")
        except Exception as e:  # bitta xato butun jarayonni to'xtatmasin
            failed.append({"url": link, "error": str(e)})
            print(f"[{i}/{len(links)}] XATO {link}: {e}")
        time.sleep(args.delay)

    result = {
        "source_url": args.url,
        "total": len(products),
        "failed": failed,
        "products": products,
    }
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\nSaqlandi: {args.output} ({len(products)} ta mahsulot, {len(failed)} ta xato)")


if __name__ == "__main__":
    main()