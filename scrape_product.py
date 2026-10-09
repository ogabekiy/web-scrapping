#!/usr/bin/env python3
"""
productstore.uz mahsulot sahifasidan barcha ma'lumotlarni olib, JSON faylga saqlaydi.

O'rnatish:
    pip install requests beautifulsoup4

Ishlatish:
    python scrape_product.py
    python scrape_product.py "<url>" -o iphone.json
"""
import argparse
import json
import re
import sys
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse, parse_qs, unquote

import requests
from bs4 import BeautifulSoup

BASE = "https://productstore.uz"
DEFAULT_URL = (
    "https://productstore.uz/category/apple"
    "?tur=iphone/product/449f7351-2b6b-495b-a455-7eb925ea2127"
)
UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "uz,ru;q=0.8,en;q=0.5",
}


def normalize_url(url: str) -> str:
    """
    '.../category/apple?tur=iphone/product/<id>' kabi noto'g'ri URLni
    to'g'ri '.../product/<id>' ko'rinishiga keltiradi.
    """
    decoded = unquote(url)
    m = re.search(r"/product/([^/?#&]+)", decoded)
    if m:
        return f"{BASE}/product/{m.group(1)}"
    return url


def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def parse_price(text):
    """'20 538 000 so'm' -> 20538000"""
    if not text:
        return None
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else None


def fetch(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    r.encoding = r.encoding or "utf-8"
    return r.text


def get_meta(soup):
    meta = {}
    for tag in soup.find_all("meta"):
        key = tag.get("property") or tag.get("name")
        if key and tag.get("content"):
            meta[key] = tag["content"]
    canonical = soup.find("link", rel="canonical")
    if canonical and canonical.get("href"):
        meta["canonical"] = canonical["href"]
    if soup.title:
        meta["title"] = clean(soup.title.string)
    return meta


def get_json_ld(soup):
    out = []
    for s in soup.find_all("script", type="application/ld+json"):
        try:
            out.append(json.loads(s.string or ""))
        except (json.JSONDecodeError, TypeError):
            pass
    return out


def get_embedded_json(soup):
    """__NEXT_DATA__ yoki boshqa ichki JSON bloklarini qidiradi (bo'lsa)."""
    out = {}
    for s in soup.find_all("script"):
        sid = s.get("id") or ""
        stype = s.get("type") or ""
        if sid == "__NEXT_DATA__" or stype == "application/json":
            try:
                out[sid or "application/json"] = json.loads(s.string or "")
            except (json.JSONDecodeError, TypeError):
                pass
    return out


def get_breadcrumbs(soup, h1):
    crumbs = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        path = urlparse(urljoin(BASE, href)).path
        if path == "/" or path.startswith("/category/"):
            txt = clean(a.get_text())
            if txt and txt not in ("Kategoriyalar",) and a.find_parent(["nav", "main"]) is not None:
                crumbs.append({"name": txt, "url": urljoin(BASE, href)})
        if len(crumbs) >= 4:
            break
    # birinchi uchta ko'pincha sarlavhadan oldin turadi
    seen, uniq = set(), []
    for c in crumbs:
        if c["url"] not in seen:
            seen.add(c["url"])
            uniq.append(c)
    if h1:
        uniq.append({"name": h1, "url": None})
    return uniq


def get_images(soup, h1):
    images, seen = [], set()
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src")
        if not src or "/images/products/" not in src:
            continue
        # "O'xshash mahsulotlar" ichidagi rasmlarni olib tashlaymiz
        alt = clean(img.get("alt"))
        if h1 and alt and not alt.startswith(h1):
            continue
        url = urljoin(BASE, src)
        if url not in seen:
            seen.add(url)
            images.append({"url": url, "alt": alt})
    return images


def get_specs(soup):
    """'Xususiyatlar' bo'limidan nom/qiymat juftliklarini oladi."""
    specs = {}
    heading = soup.find(lambda t: t.name in ("h2", "h3") and clean(t.get_text()) == "Xususiyatlar")
    if not heading:
        return specs
    container = heading.find_next_sibling() or heading.parent

    # 1) <dl><dt>/<dd>
    for dl in container.find_all("dl") if container else []:
        for dt in dl.find_all("dt"):
            dd = dt.find_next_sibling("dd")
            if dd:
                specs[clean(dt.get_text())] = clean(dd.get_text())
    if specs:
        return specs

    # 2) <tr><td>/<td>
    for tr in container.find_all("tr") if container else []:
        cells = [clean(c.get_text()) for c in tr.find_all(["th", "td"])]
        if len(cells) >= 2:
            specs[cells[0]] = cells[1]
    if specs:
        return specs

    # 3) har bir qator = ikki bola element (nom + qiymat)
    if container:
        for row in container.find_all(recursive=False):
            kids = [clean(k.get_text(" ")) for k in row.find_all(recursive=False)]
            kids = [k for k in kids if k]
            if len(kids) == 2:
                specs[kids[0]] = kids[1]
    if specs:
        return specs

    # 4) zaxira: matnni qatorlarga bo'lib, juft-juft olish
    lines = [clean(x) for x in container.get_text("\n").split("\n")] if container else []
    lines = [x for x in lines if x]
    for i in range(0, len(lines) - 1, 2):
        specs[lines[i]] = lines[i + 1]
    return specs


def get_labeled_value(soup, label):
    """'Yetkazib berish:' kabi yorliqdan keyingi matnni qaytaradi."""
    node = soup.find(string=lambda s: s and clean(s).rstrip(":") == label.rstrip(":"))
    if not node:
        return None
    el = node.parent
    nxt = el.find_next_sibling()
    if nxt and clean(nxt.get_text()):
        return clean(nxt.get_text())
    parent_text = clean(el.parent.get_text(" "))
    return clean(parent_text.replace(clean(node), "", 1)) or None


def get_description(soup):
    d = soup.find(
        lambda t: t.name in ("h2", "h3")
        and clean(t.get_text()).lower() in ("tavsif", "ta'rif", "mahsulot haqida", "описание")
    )
    if not d:
        return None
    parts = []
    for sib in d.find_next_siblings():
        if sib.name in ("h2", "h3"):
            break
        parts.append(clean(sib.get_text(" ")))
    return clean(" ".join(parts)) or None


def get_reviews(soup):
    h = soup.find(lambda t: t.name in ("h2", "h3") and clean(t.get_text()).startswith("Sharhlar"))
    if not h:
        return {"count": 0, "items": [], "note": None}
    texts = []
    for sib in h.find_next_siblings():
        if sib.name in ("h2", "h3"):
            break
        texts.append(clean(sib.get_text(" ")))
    note = clean(" ".join(texts)) or None
    empty = bool(note and "hali sharh yozilmagan" in note.lower())
    return {"count": 0 if empty else None, "items": [], "note": note}


def get_similar(soup, current_id):
    h = soup.find(lambda t: t.name in ("h2", "h3") and clean(t.get_text()) == "O'xshash mahsulotlar")
    if not h:
        return []
    items, seen = [], set()
    scope = h.find_parent() or soup
    for a in scope.find_all("a", href=True):
        href = a["href"]
        if "/product/" not in href:
            continue
        url = urljoin(BASE, href)
        if url in seen or (current_id and current_id in url):
            continue
        name = clean(a.get_text())
        if not name:
            continue
        seen.add(url)
        card = a.find_parent(["li", "article", "div"])
        card_text = clean(card.get_text(" ")) if card else ""
        pm = re.search(r"(\d[\d\s]*)\s*so'm", card_text)
        img = card.find("img") if card else None
        items.append(
            {
                "name": name,
                "url": url,
                "id": url.rstrip("/").split("/")[-1],
                "price": parse_price(pm.group(1)) if pm else None,
                "image": urljoin(BASE, img["src"]) if img and img.get("src") else None,
            }
        )
    return items


def scrape(url: str) -> dict:
    url = normalize_url(url)
    html = fetch(url)
    soup = BeautifulSoup(html, "html.parser")

    h1_tag = soup.find("h1")
    h1 = clean(h1_tag.get_text()) if h1_tag else None
    meta = get_meta(soup)

    pid_match = UUID_RE.search(url)
    product_id = pid_match.group(0) if pid_match else url.rstrip("/").split("/")[-1]

    # Narx: asosiy blokdan (h1 dan keyingi birinchi "so'm")
    price_text = None
    if h1_tag:
        for el in h1_tag.find_all_next(string=re.compile(r"so'm")):
            txt = clean(el)
            if re.search(r"\d", txt):
                price_text = txt
                break
    if not price_text and meta.get("og:description"):
        m = re.search(r"Narxi\s+([\d\s]+)\s*so'm", meta["og:description"])
        if m:
            price_text = clean(m.group(1)) + " so'm"

    # Holati va "Original" belgilar (h1 atrofida)
    condition = None
    badges = []
    if h1_tag:
        prev = h1_tag.find_previous(string=lambda s: s and clean(s) in ("Yangi", "Ishlatilgan"))
        condition = clean(prev) if prev else None
        nxt = h1_tag.find_next(string=lambda s: s and clean(s) in ("Original", "Tavsiya", "Aksiya"))
        if nxt:
            badges.append(clean(nxt))

    data = {
        "source_url": url,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "id": product_id,
        "name": h1 or meta.get("og:title"),
        "condition": condition,
        "badges": badges,
        "price": {
            "text": price_text,
            "amount": parse_price(price_text),
            "currency": "UZS",
        },
        "delivery": get_labeled_value(soup, "Yetkazib berish"),
        "warranty": get_labeled_value(soup, "Rasmiy kafolat"),
        "description": get_description(soup) or meta.get("description"),
        "specifications": get_specs(soup),
        "images": get_images(soup, h1),
        "breadcrumbs": get_breadcrumbs(soup, h1),
        "reviews": get_reviews(soup),
        "similar_products": get_similar(soup, product_id),
        "meta": meta,
        "json_ld": get_json_ld(soup),
        "embedded_json": get_embedded_json(soup),
    }
    return data


def main():
    ap = argparse.ArgumentParser(description="productstore.uz mahsulotini JSON ga saqlash")
    ap.add_argument("url", nargs="?", default=DEFAULT_URL, help="mahsulot URL manzili")
    ap.add_argument("-o", "--output", help="chiqish fayli (standart: product_<id>.json)")
    args = ap.parse_args()

    try:
        data = scrape(args.url)
    except requests.RequestException as e:
        sys.exit(f"Sahifani yuklashda xatolik: {e}")

    out = args.output or f"product_{data['id']}.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Saqlandi: {out}")
    print(f"Nomi: {data['name']} | Narxi: {data['price']['text']}")


if __name__ == "__main__":
    main()