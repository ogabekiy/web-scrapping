# ProductStore ma'lumotlarini yig'ish va tayyorlash

Ushbu loyiha `productstore.uz` katalogidagi mahsulot ma'lumotlarini sahifalardan yig'adi, tozalaydi va qidiruv yoki AI tizimlarida ishlatish uchun JSONL formatida tayyorlaydi. Scraping jarayonida saytga ortiqcha so'rov yubormaslik uchun so'rovlar orasida kutish va xatolik bo'lganda qayta urinish qo'llanadi.

## Jarayon

1. `scrape_category.py` katalog sahifalarini ketma-ket ko'rib chiqadi va `/product/` havolalarini takrorlanmasdan yig'adi.
2. `scrape_product.py` har bir mahsulot sahifasidan nom, narx, tavsif, xususiyatlar, rasm, kategoriya yo'li, yetkazib berish, kafolat va sharhlar haqidagi ma'lumotlarni ajratadi.
3. Natija `data_products.json` fayliga yoziladi. Faylda manba katalog URL'i, muvaffaqiyatli yig'ilgan mahsulotlar va xatoga uchragan URL'lar bo'ladi.
4. `clean.ipynb` yoki `prepare_chunks.py` mahsulotlarni keyingi ishlov uchun JSONL yozuvlariga aylantiradi.

## Pandas notebooki

`clean.ipynb`da pandas xom JSON ma'lumotini jadval ko'rinishiga keltirish va har bir mahsulot uchun qidiruvga qulay matn tayyorlashda ishlatiladi:

- `pd.json_normalize(data["products"])` mahsulotlar ro'yxatini `DataFrame`ga aylantiradi va ichma-ich narx maydonlarini `price.text`, `price.amount`, `price.currency` kabi ustunlarga yoyadi.
- `fillna`, `str.replace` va `str.strip` tavsifdagi bo'sh qiymatlarni hamda ortiqcha interfeys matnini tozalaydi.
- Breadcrumb ma'lumotlaridan `category` olinadi, ichma-ich narx qiymatlari esa alohida ustunlarga ko'chiriladi.
- `df.apply(..., axis=1)` har bir qator uchun mahsulot nomi, kategoriya, narx, yetkazib berish, kafolat va tavsifni birlashtirgan `content` matnini yasaydi.
- Kerakli ustunlar `df_chunks`ga tanlanib, `to_json(orient="records", lines=True, force_ascii=False)` bilan `product-chunks-pandas.jsonl` fayliga chiqariladi. Har bir satr alohida JSON obyekt, ya'ni bitta mahsulot bitta yozuv bo'ladi; o'zbekcha belgilar saqlanadi.

Bu notebookdagi “chunk” har bir mahsulot uchun tayyorlangan alohida hujjatni anglatadi. Matn token yoki belgi chegarasiga qarab mayda bo'laklarga ajratilmaydi va bo'laklar orasida overlap hosil qilinmaydi.

## `prepare_chunks.py` varianti

`prepare_chunks.py` shu vazifani alohida Python skripti bilan bajaradi. U `data_products.json` ichidagi `products` ro'yxatini o'qib, har bir mahsulot uchun `id`, `type`, `title`, `keywords`, `source`, `updated`, `metadata`, `text` va `content` maydonlariga ega yozuvni `product-chunks.jsonl`ga chiqaradi. Bu format notebook yaratadigan maydonlar to'plamidan farq qiladi; kerakli iste'molchi formatiga mos variantni tanlang.

## O'rnatish

Scraping skriptlari uchun `requests` va `beautifulsoup4`, pandas notebooki uchun `pandas` kerak:

```bash
python -m pip install requests beautifulsoup4 pandas
```

## Ishlatish

Katalogni yig'ish (standart manzil `https://productstore.uz/katalog`):

```bash
python scrape_category.py
```

Muayyan katalog, chiqish fayli yoki so'rovlar orasidagi kutish vaqtini berish:

```bash
python scrape_category.py "https://productstore.uz/katalog" --output data_products.json --delay 1
```

Bitta mahsulot sahifasini yig'ish:

```bash
python scrape_product.py "https://productstore.uz/product/PRODUCT_ID" --output product.json
```

Skript orqali chunk fayl yaratish:

```bash
python prepare_chunks.py --input data_products.json --output product-chunks.jsonl
```

Pandas varianti uchun `clean.ipynb`ni Jupyter yoki VS Code'da yuqoridan pastga ishga tushiring. Notebook `data_products.json`ni shu papkadan o'qib, `product-chunks-pandas.jsonl`ni shu yerga yozadi.

## Fayllar

| Fayl | Vazifasi |
| --- | --- |
| `scrape_category.py` | Katalog bo'ylab yuradi va mahsulot sahifalarini yig'adi |
| `scrape_product.py` | Bitta mahsulot sahifasidan maydonlarni ajratadi |
| `clean.ipynb` | Pandas bilan tozalaydi va pandas JSONL formatini yaratadi |
| `prepare_chunks.py` | Alternativ JSONL formatini Python skripti bilan yaratadi |
| `data_products.json` | Scraping natijasi; qayta yaratiladigan ma'lumot fayli |
| `product-chunks-pandas.jsonl` | Notebook yaratadigan mahsulot yozuvlari |
| `dokon-info.jsonl` | Do'kon haqida tayyorlangan qo'shimcha JSONL ma'lumotlari |

Scrapingni ishlatishdan oldin saytning foydalanish shartlari va `robots.txt` qoidalarini tekshiring. So'rov tezligini saytga ortiqcha yuk tushirmaydigan darajada saqlang; skriptning standart kutish vaqti 0.7 soniya.