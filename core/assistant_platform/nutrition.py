"""Source-backed nutrition lookups and conservative meal parsing.

External catalog lookups are optional. The API remains usable offline; missing
or ambiguous nutrition is returned as a question instead of being estimated.
"""
from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone

NUTRIENTS = {
    "calories": ("Energy", "Energy (Atwater General Factors)", "Energy (Atwater Specific Factors)"),
    "protein": ("Protein",), "carbs": ("Carbohydrate, by difference",),
    "fat": ("Total lipid (fat)",), "saturatedFat": ("脂肪酸, total saturated", "Fatty acids, total saturated"),
    "fiber": ("Fiber, total dietary",), "sugars": ("Sugars, total including NLEA", "Sugars, total"),
    "sodiumMg": ("Sodium, Na",), "cholesterolMg": ("Cholesterol",),
}


def _request(url: str, timeout: float = 9) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "ZAENIA/1.0 (local personal nutrition lookup)", "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        if response.status != 200:
            raise ValueError("Nutrition source is unavailable.")
        return json.loads(response.read(2_000_000))


def _fdc_key() -> str:
    return os.environ.get("FDC_API_KEY", "DEMO_KEY").strip() or "DEMO_KEY"


def barcode_lookup(code: str) -> dict:
    code = re.sub(r"\D", "", str(code))
    if not 8 <= len(code) <= 14:
        raise ValueError("Enter a barcode with 8–14 digits.")
    payload = _request(f"https://world.openfoodfacts.org/api/v3.6/product/{code}.json?fields=code,product_name,brands,quantity,nutriments,serving_size,url")
    if payload.get("status") != "success":
        return {"found": False, "question": "That barcode is not in the catalog. Scan the nutrition label or enter the values manually."}
    product = payload.get("product") or {}
    return _off_product(product, f"https://world.openfoodfacts.org/product/{code}")


def _off_product(product: dict, source: str = "") -> dict:
    n = product.get("nutriments") or {}
    energy_kcal = n.get("energy-kcal_100g")
    if energy_kcal is None and n.get("energy-kj_100g") is not None:
        energy_kcal = round(float(n["energy-kj_100g"]) / 4.184, 2)
    sodium, cholesterol = n.get("sodium_100g"), n.get("cholesterol_100g")
    fields = {"calories": energy_kcal, "protein": n.get("proteins_100g"),
              "carbs": n.get("carbohydrates_100g"), "fat": n.get("fat_100g"), "saturatedFat": n.get("saturated-fat_100g"),
              "fiber": n.get("fiber_100g"), "sugars": n.get("sugars_100g"), "sodiumMg": float(sodium) * 1000 if sodium is not None else None,
              "cholesterolMg": float(cholesterol) * 1000 if cholesterol is not None else None}
    return {"found": True, "title": " ".join(x for x in (product.get("brands", ""), product.get("product_name", "")) if x).strip(),
            "quantity": product.get("quantity", ""), "servingSize": product.get("serving_size", ""), "basis": "per 100 g", "nutrients": fields,
            "source": source, "sourceName": "Open Food Facts · community-contributed; verify package label",
            "checkedAt": datetime.now(timezone.utc).isoformat(timespec="seconds")}


def search_food(query: str) -> dict:
    query = " ".join(str(query or "").split())[:120]
    if not query:
        raise ValueError("Enter a food name to search.")
    # One comma-separated dataType: FoodData Central answers 400 to the repeated-parameter form.
    params = urllib.parse.urlencode({"api_key": _fdc_key(), "query": query, "pageSize": 5,
                                    "dataType": "Foundation,SR Legacy,Survey (FNDDS),Branded"})
    data = _request("https://api.nal.usda.gov/fdc/v1/foods/search?" + params)
    hits = []
    for food in data.get("foods", [])[:5]:
        nutrients = {}
        for key, names in NUTRIENTS.items():
            match = next((n for n in food.get("foodNutrients", []) if n.get("nutrientName") in names), None)
            nutrients[key] = match.get("value") if match else None
            if key == "calories" and match and match.get("unitName", "").lower() == "kj":
                nutrients[key] = round(float(match["value"]) / 4.184, 2)
        hits.append({"fdcId": food.get("fdcId"), "title": food.get("description", "Food record"), "dataType": food.get("dataType", ""),
                     "servingSize": food.get("servingSize"), "servingSizeUnit": food.get("servingSizeUnit", "g"),
                     "basis": "per 100 g", "nutrients": nutrients,
                     "source": f"https://fdc.nal.usda.gov/food-details/{food.get('fdcId')}/nutrients", "sourceName": "USDA FoodData Central",
                     "checkedAt": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    return {"query": query, "matches": hits, "source": "USDA FoodData Central", "checkedAt": datetime.now(timezone.utc).isoformat(timespec="seconds")}


_SUGGEST_CACHE: dict[str, tuple[float, dict]] = {}


def search_products(query: str) -> dict:
    """Recipe ingredient search as you type: USDA FoodData Central (generic and branded foods) plus
    Open Food Facts (packaged products by name). Either source may be offline; whatever answered is
    returned. Values are per 100 g from the cited record, and Grey can edit any of them."""
    import time
    query = " ".join(str(query or "").split())[:120]
    if len(query) < 2:
        raise ValueError("Type at least two letters of the ingredient.")
    key = query.lower()
    cached = _SUGGEST_CACHE.get(key)
    if cached and time.time() - cached[0] < 3600:
        return cached[1]
    matches, offline = [], []
    try:
        matches.extend(search_food(query)["matches"])
    except Exception:
        offline.append("USDA FoodData Central")
    try:
        fields = "code,product_name,brands,quantity,nutriments,serving_size"
        try:
            data = _request("https://search.openfoodfacts.org/search?" + urllib.parse.urlencode({"q": query, "page_size": 6, "fields": fields}))
            products = data.get("hits") or []
        except Exception:
            data = _request("https://world.openfoodfacts.org/cgi/search.pl?" + urllib.parse.urlencode(
                {"search_terms": query, "search_simple": 1, "action": "process", "json": 1, "page_size": 6, "fields": fields}))
            products = data.get("products") or []
        for product in products[:6]:
            if isinstance(product.get("brands"), list):
                product = {**product, "brands": ", ".join(str(b) for b in product["brands"])}
            if not product.get("product_name") or not product.get("code"):
                continue
            item = _off_product(product, f"https://world.openfoodfacts.org/product/{product['code']}")
            if item["nutrients"].get("calories") is None:
                continue
            matches.append({"fdcId": None, "code": product["code"], "title": item["title"], "dataType": "Product",
                            "servingSize": item["servingSize"], "servingSizeUnit": "", "basis": "per 100 g", "nutrients": item["nutrients"],
                            "source": item["source"], "sourceName": item["sourceName"], "checkedAt": item["checkedAt"]})
    except Exception:
        offline.append("Open Food Facts")
    result = {"query": query, "matches": matches[:12], "offline": offline}
    if matches:
        if len(_SUGGEST_CACHE) > 200:
            _SUGGEST_CACHE.clear()
        _SUGGEST_CACHE[key] = (time.time(), result)
    return result


_NUMBER = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10", "a": "1", "an": "1"}
_ITEM = re.compile(r"^\s*(?P<amount>\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten|a|an)\s*(?P<unit>g|gram(?:s)?|kg|ml|mL|l|liter(?:s)?|cup(?:s)?|tbsp|tablespoon(?:s)?|tsp|teaspoon(?:s)?|slice(?:s)?|strip(?:s)?|piece(?:s)?|scoop(?:s)?|oz|ounce(?:s)?|lb|pound(?:s)?)?\s+(?P<food>.+?)\s*$", re.I)


def parse_meal(text: str) -> list[dict]:
    text = re.sub(r"^\s*(?:i (?:ate|had|just ate|just had)|log(?:\s+my)?\s+(?:food|meal)\s*:?|for (?:breakfast|lunch|dinner|snack)\s*:?\s*)", "", str(text), flags=re.I)
    pieces = [re.sub(r"^and\s+", "", p.strip(" ."), flags=re.I) for p in re.split(r",|;|\s+and\s+(?=(?:\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten|a|an)\b)", text, flags=re.I) if p.strip(" .")]
    items = []
    for piece in pieces[:30]:
        match = _ITEM.match(piece)
        if not match:
            items.append({"text": piece, "name": piece, "amount": None, "unit": "", "grams": None,
                          "question": f"How much of {piece!r} did you have, and what brand or type was it?"})
            continue
        amount = float(_NUMBER.get(match.group("amount").lower(), match.group("amount")))
        unit = (match.group("unit") or "serving").lower()
        food = re.sub(r"^of\s+", "", match.group("food"), flags=re.I).strip()
        food = re.sub(r"\b(?:for|at)\s+(?:breakfast|lunch|dinner|snack)\b", "", food, flags=re.I).strip()
        grams = amount if unit in ("g", "gram", "grams") else amount * 1000 if unit in ("kg", "l", "liter", "liters") else amount if unit in ("ml",) else amount * 28.3495 if unit in ("oz", "ounce", "ounces") else amount * 453.592 if unit in ("lb", "pound", "pounds") else None
        question = ""
        if unit in ("g", "gram", "grams") and re.match(r"protein shake\b", food, re.I):
            grams = None
            unit = "g protein"
            question = f"Does this mean a shake with {amount:g} g of protein? Confirm its brand and serving size from the package."
        items.append({"text": piece, "name": food, "amount": amount, "unit": unit, "grams": grams, "question": question})
    return items


def preview_meal(text: str) -> dict:
    items = parse_meal(text)
    if not items:
        raise ValueError("Describe the food and how much you ate.")
    result = []
    for item in items:
        row = {**item, "matches": [], "nutrients": None, "source": "", "sourceName": ""}
        if not item["question"]:
            try:
                row["matches"] = search_food(item["name"])["matches"]
                if not row["matches"]:
                    row["question"] = f"I couldn't find a nutrition record for {item['name']}. Enter a brand, choose a similar food, or read its label."
                elif item["grams"] is not None:
                    row["nutrients"] = {key: round(float(value or 0) * item["grams"] / 100, 3) if value is not None else None
                                        for key, value in row["matches"][0]["nutrients"].items()}
                    row["source"], row["sourceName"] = row["matches"][0]["source"], row["matches"][0]["sourceName"]
                    if any(row["nutrients"].get(key) is None for key in ("calories", "protein", "fiber")):
                        row["question"] = "This record does not report calories, protein, and fiber. Scan or enter the package label before logging."
                else:
                    row["question"] = f"Pick the closest food record and enter the portion weight in grams for {item['text']}."
            except Exception:
                row["question"] = f"I couldn't reach USDA FoodData Central for {item['name']}. Check the brand/label or retry when online."
        result.append(row)
    return {"description": text[:2000], "items": result, "complete": all(i["nutrients"] is not None and all(i["nutrients"].get(key) is not None for key in ("calories", "protein", "fiber")) for i in result),
            "message": "Check every match and serving weight before logging. Values are scaled from the cited catalog record per 100 g."}


def totals(items: list[dict]) -> dict:
    keys = tuple(NUTRIENTS)
    return {key: round(sum(float(item["nutrients"][key]) for item in items), 2)
            if items and all(isinstance(item.get("nutrients"), dict) and item["nutrients"].get(key) is not None for item in items) else None
            for key in keys}


def read_label(raw: bytes) -> dict:
    if not raw or len(raw) > 8_000_000:
        raise ValueError("Choose a nutrition-label photo under 8 MB.")
    from core.api.file_reader import describe_image
    text = describe_image(raw)
    found = {}
    patterns = {"calories": r"(?:calories|energy)\D{0,16}(\d+(?:\.\d+)?)\s*(?:kcal|cal)?", "protein": r"protein\D{0,12}(\d+(?:\.\d+)?)\s*g",
                "carbs": r"(?:total carbohydrate|carbohydrate)\D{0,12}(\d+(?:\.\d+)?)\s*g", "fat": r"(?:total fat|fat)\D{0,12}(\d+(?:\.\d+)?)\s*g",
                "saturatedFat": r"saturated fat\D{0,12}(\d+(?:\.\d+)?)\s*g", "fiber": r"(?:dietary fiber|fiber)\D{0,12}(\d+(?:\.\d+)?)\s*g",
                "sugars": r"(?:total sugars|sugars)\D{0,12}(\d+(?:\.\d+)?)\s*g", "sodiumMg": r"sodium\D{0,12}(\d+(?:\.\d+)?)\s*mg",
                "cholesterolMg": r"cholesterol\D{0,12}(\d+(?:\.\d+)?)\s*mg"}
    for key, pattern in patterns.items():
        match = re.search(pattern, text, re.I)
        if match:
            found[key] = float(match.group(1))
    return {"values": found, "text": text[:6000], "needsReview": True,
            "message": "Read locally with ZAE's vision model. Verify every value and serving size against the package before saving; the photo was not retained."}
