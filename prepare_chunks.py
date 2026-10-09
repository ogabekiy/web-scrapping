import argparse
import json
from pathlib import Path


def clean_text(value):
    if value is None:
        return ""
    return " ".join(str(value).split())


def category_from_breadcrumbs(product):
    breadcrumbs = product.get("breadcrumbs") or []
    names = [item.get("name") for item in breadcrumbs if item.get("name")]
    if len(names) >= 2:
        return names[-2]
    return None


def build_product_chunk(product):
    product_id = clean_text(product.get("id"))
    name = clean_text(product.get("name"))
    category = category_from_breadcrumbs(product)
    price = product.get("price") or {}
    specifications = product.get("specifications") or {}
    badges = product.get("badges") or []
    reviews = product.get("reviews") or {}

    lines = [
        f"Mahsulot: {name}",
        f"Kategoriya: {category}" if category else "",
        f"Holati: {clean_text(product.get('condition'))}" if product.get("condition") else "",
        f"Narxi: {clean_text(price.get('text'))}" if price.get("text") else "",
        f"Valyuta: {clean_text(price.get('currency'))}" if price.get("currency") else "",
        f"Yetkazib berish: {clean_text(product.get('delivery'))}" if product.get("delivery") else "",
        f"Kafolat: {clean_text(product.get('warranty'))}" if product.get("warranty") else "",
        f"Belgilar: {', '.join(map(clean_text, badges))}" if badges else "",
        "",
        "Tavsif:",
        clean_text(product.get("description")),
    ]

    if specifications:
        lines.extend(["", "Xususiyatlar:"])
        for key, value in specifications.items():
            lines.append(f"- {clean_text(key)}: {clean_text(value)}")

    if reviews.get("count") is not None:
        lines.extend(["", f"Sharhlar soni: {reviews.get('count')}"])

    content = "\n".join(line for line in lines if line != "")

    keywords = [name]
    if category:
        keywords.append(category)
    keywords.extend(clean_text(badge) for badge in badges)
    keywords.extend(clean_text(value) for value in specifications.values())
    keywords = [keyword for keyword in keywords if keyword]

    return {
        "id": f"product-{product_id}",
        "type": "product",
        "title": name,
        "keywords": ", ".join(dict.fromkeys(keywords)),
        "source": product.get("source_url"),
        "updated": (product.get("scraped_at") or "")[:10],
        "metadata": {
            "product_id": product_id,
            "category": category,
            "price_amount": price.get("amount"),
            "price_currency": price.get("currency"),
            "condition": product.get("condition"),
            "badges": badges,
            "image": (product.get("images") or [{}])[0].get("url"),
        },
        "text": clean_text(product.get("description")),
        "content": content,
    }


def convert_products(input_path, output_path):
    data = json.loads(input_path.read_text(encoding="utf-8"))
    products = data.get("products", [])

    with output_path.open("w", encoding="utf-8") as file:
        for product in products:
            chunk = build_product_chunk(product)
            file.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    return len(products)


def main():
    parser = argparse.ArgumentParser(
        description="Prepare productstore.uz products as JSONL chunks for an AI assistant."
    )
    parser.add_argument("--input", default="data_products.json")
    parser.add_argument("--output", default="product-chunks.jsonl")
    args = parser.parse_args()

    count = convert_products(Path(args.input), Path(args.output))
    print(f"Prepared {count} product chunks -> {args.output}")


if __name__ == "__main__":
    main()
