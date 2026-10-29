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
                     "servingLabel": str(food.get("householdServingFullText") or "")[:60],
                     "basis": "per 100 g", "nutrients": nutrients,
                     "source": f"https://fdc.nal.usda.gov/food-details/{food.get('fdcId')}/nutrients", "sourceName": "USDA FoodData Central",
                     "checkedAt": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    return {"query": query, "matches": hits, "source": "USDA FoodData Central", "checkedAt": datetime.now(timezone.utc).isoformat(timespec="seconds")}


_SUGGEST_CACHE: dict[str, tuple[float, dict]] = {}


def _tidy_title(title: str) -> str:
    """"Chobani Chobani Greek Yogurt" -> "Chobani Greek Yogurt" (the brand is often repeated in the product name)."""
    words = str(title or "").split()
    for size in (3, 2, 1):
        if len(words) >= 2 * size and [w.lower() for w in words[:size]] == [w.lower() for w in words[size:2 * size]]:
            return " ".join(words[size:])
    return " ".join(words)


def _off_matches(products: list, limit: int = 10) -> list[dict]:
    out = []
    for product in products[:limit]:
        if isinstance(product.get("brands"), list):
            product = {**product, "brands": ", ".join(str(b) for b in product["brands"])}
        if not product.get("product_name") or not product.get("code"):
            continue
        item = _off_product(product, f"https://world.openfoodfacts.org/product/{product['code']}")
        if item["nutrients"].get("calories") is None:
            continue
        out.append({"fdcId": None, "code": str(product["code"]), "title": _tidy_title(item["title"] or product["product_name"]), "dataType": "Product",
                    "servingSize": item["servingSize"] or "", "servingSizeUnit": "", "quantity": str(product.get("quantity") or ""),
                    "basis": "per 100 g", "nutrients": item["nutrients"], "source": item["source"], "sourceName": item["sourceName"],
                    "checkedAt": item["checkedAt"], "us": "en:united-states" in (product.get("countries_tags") or []),
                    "categories": [c for c in (product.get("categories_tags") or []) if isinstance(c, str)][:20],
                    "completeness": float(product.get("completeness") or 0)})
    return out


_OFF_FIELDS = "code,product_name,brands,quantity,nutriments,serving_size,serving_quantity,countries_tags,categories_tags,completeness"

# A typical serving by food category, used only when the label lists none (shown as "typical serving").
_CATEGORY_SERVINGS = (
    ("milks", "1 cup", 240), ("plant-based-milk", "1 cup", 240), ("juices", "1 cup", 240), ("dairy-drinks", "1 cup", 240),
    ("yogurts", "1 container", 170), ("cheeses", "1 oz", 28), ("breakfast-cereals", "1 cup", 40), ("breads", "1 slice", 40),
    ("peanut-butters", "2 tbsp", 32), ("nut-butters", "2 tbsp", 32), ("olive-oils", "1 tbsp", 14), ("vegetable-oils", "1 tbsp", 14),
    ("butters", "1 tbsp", 14), ("eggs", "1 large egg", 50), ("protein-powders", "1 scoop", 30), ("ice-creams", "2/3 cup", 95),
    ("sodas", "1 can", 355), ("carbonated-drinks", "1 can", 355), ("chips", "1 oz", 28), ("crisps", "1 oz", 28),
)


def _typical_serving(categories: list[str]) -> tuple[str, float] | None:
    tags = " ".join(categories)
    for key, label, grams in _CATEGORY_SERVINGS:
        if f":{key}" in tags:
            return label, grams
    return None


def _product_label(code: str) -> dict:
    """The full Open Food Facts record for one product: its real name and the serving size printed on the label
    (the search index leaves these out)."""
    data = _request(f"https://world.openfoodfacts.org/api/v2/product/{code}?fields=product_name,brands,quantity,serving_size,serving_quantity,categories_tags", timeout=6)
    return data.get("product") or {}


def _enrich_products(matches: list[dict], limit: int = 8) -> None:
    """Fill in name, size and serving for the top products from their full labels, at the same time."""
    from concurrent.futures import ThreadPoolExecutor
    todo = [m for m in matches if m.get("dataType") == "Product" and m.get("code")][:limit]
    if not todo:
        return
    with ThreadPoolExecutor(max_workers=6) as pool:
        labels = list(pool.map(lambda m: _safe(_product_label, m["code"]), todo))
    for match, label in zip(todo, labels):
        if not label:
            continue
        brand = ", ".join(label["brands"]) if isinstance(label.get("brands"), list) else str(label.get("brands") or "")
        name = str(label.get("product_name") or "").strip()
        if name:
            match["title"] = _tidy_title(f"{brand} {name}".strip() if brand and brand.lower() not in name.lower() else name)
        if label.get("quantity"):
            match["quantity"] = str(label["quantity"])
        if label.get("categories_tags"):
            match["categories"] = [c for c in label["categories_tags"] if isinstance(c, str)][:20]
        grams = label.get("serving_quantity")
        if label.get("serving_size"):
            match["servingSize"] = str(label["serving_size"])
            if isinstance(grams, (int, float)) and grams > 0 and not re.search(r"\d\s*(?:g|ml)\b", match["servingSize"], re.I):
                match["servingSize"] += f" ({grams:g} g)"
    for match in matches:
        if match.get("dataType") == "Product" and not match.get("servingSize"):
            typical = _typical_serving(match.get("categories") or [])
            if typical:
                match["servingSize"] = f"{typical[1]:g} g"
                match["servingLabel"] = f"{typical[0]} (typical serving)"


def _safe(fn, *args):
    try:
        return fn(*args)
    except Exception:
        return None


def _dedupe(matches: list[dict]) -> list[dict]:
    """The same product listed several times (other sizes, community copies): keep the most complete one."""
    best: dict[tuple, dict] = {}
    order = []
    for m in matches:
        cal = m["nutrients"].get("calories")
        key = (re.sub(r"[^a-z0-9]+", " ", str(m.get("title", "")).lower()).strip(), round(float(cal)) if cal is not None else None)
        if key not in best:
            order.append(key)
            best[key] = m
        elif (bool(m.get("servingSize")), m.get("completeness", 0)) > (bool(best[key].get("servingSize")), best[key].get("completeness", 0)):
            best[key] = m
    return [best[k] for k in order]


def _source_usda(query: str) -> list[dict]:
    return search_food(query)["matches"]


def _source_off_search(query: str) -> list[dict]:
    data = _request("https://search.openfoodfacts.org/search?" + urllib.parse.urlencode({"q": query, "page_size": 8, "fields": _OFF_FIELDS}))
    return _off_matches(data.get("hits") or [])


def _source_off_classic(query: str) -> list[dict]:
    data = _request("https://world.openfoodfacts.org/cgi/search.pl?" + urllib.parse.urlencode(
        {"search_terms": query, "search_simple": 1, "action": "process", "json": 1, "page_size": 8, "sort_by": "unique_scans_n", "fields": _OFF_FIELDS}))
    return _off_matches(data.get("products") or [])


def saved_ingredients(store, query: str) -> list[dict]:
    """Ingredients already used in saved recipes, with values per 100 g (picked from a source, or worked out from
    Grey's own amounts), so the usual foods come up first, even offline."""
    words = [w for w in re.findall(r"[a-z0-9]+", query.lower()) if len(w) > 1]
    if store is None or not words:
        return []
    seen, out = set(), []
    for recipe in store.list("fitness_recipe"):
        if recipe.get("archived"):
            continue
        for item in recipe.get("ingredients") or []:
            name = str(item.get("name") or "").strip()
            if not name or name.lower() in seen or not all(w in name.lower() for w in words):
                continue
            per100 = item.get("per100")
            if not per100 and item.get("grams") and isinstance(item.get("nutrients"), dict):
                grams = float(item["grams"])
                per100 = {k: (round(float(v) * 100 / grams, 2) if v is not None else None) for k, v in item["nutrients"].items()}
            if not per100 or per100.get("calories") is None:
                continue
            seen.add(name.lower())
            label = "Your recipe " + str(recipe.get("title", ""))
            out.append({"fdcId": None, "title": name, "dataType": "Yours", "servingSize": item.get("servingGrams"),
                        "servingSizeUnit": "g" if item.get("servingGrams") else "", "basis": "per 100 g", "nutrients": per100,
                        "source": str(item.get("source") or ""), "sourceName": label + (" · " + item["sourceName"] if item.get("sourceName") else "")})
    return out[:4]


def _rank(query: str, match: dict) -> tuple:
    """Your own ingredients first, then names with the most typed words (plurals folded), names starting with them,
    US products and ones with a serving size, generic foods before brands, shorter names first."""
    title = str(match.get("title") or "").lower()
    words = [w[:-1] if len(w) > 3 and w.endswith("s") else w for w in query.lower().split()]
    q = " ".join(words)
    kind = {"Yours": 0, "Common food": 1, "Foundation": 1, "SR Legacy": 1, "Survey (FNDDS)": 2}.get(match.get("dataType"), 3)
    missing = sum(1 for w in words if w not in title)
    starts = 0 if title.startswith(q) else 1 if any(w and title.startswith(w) for w in words) else 2
    product_bonus = (0 if match.get("us", True) else 1) + (0 if match.get("servingSize") else 1)
    return (0 if kind == 0 else 1, missing, starts, product_bonus, kind, len(title))


_SOURCES = (("USDA FoodData Central", "_source_usda"), ("Open Food Facts", "_source_off_search"), ("Open Food Facts (classic)", "_source_off_classic"))


def search_products(query: str, store=None) -> dict:
    """Recipe ingredient search as you type. Asked at the same time: Grey's saved recipe ingredients, Open Food Facts
    (the new search service and the classic one, which find different products) and USDA FoodData Central (generic and
    branded foods). Any source may be offline or rate-limited; whatever answered is returned. Values are per 100 g
    from the cited record, and every one stays editable."""
    import time
    from concurrent.futures import ThreadPoolExecutor
    query = " ".join(str(query or "").split())[:120]
    if len(query) < 2:
        raise ValueError("Type at least two letters of the ingredient.")
    key = query.lower()
    cached = _SUGGEST_CACHE.get(key)
    online = cached[1] if cached and time.time() - cached[0] < 3600 else None
    if online is None:
        found, failed = {}, []
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {name: pool.submit(globals()[fn], query) for name, fn in _SOURCES}
            for name, future in futures.items():
                try:
                    found[name] = future.result(timeout=15)
                except Exception:
                    failed.append(name)
        offline = ["USDA FoodData Central"] if "USDA FoodData Central" in failed else []
        if "Open Food Facts" in failed and "Open Food Facts (classic)" in failed:
            offline.append("Open Food Facts")
        merged, seen = [], set()
        for name, _ in _SOURCES:
            for match in found.get(name, []):
                ident = match.get("code") or match.get("fdcId") or str(match.get("title", "")).lower()
                if ident in seen:
                    continue
                seen.add(ident)
                merged.append(match)
        merged = _dedupe(merged)
        merged.sort(key=lambda m: _rank(query, m))
        _enrich_products(merged)
        merged = _dedupe(merged)
        online = {"matches": merged, "offline": offline}
        if merged:
            if len(_SUGGEST_CACHE) > 200:
                _SUGGEST_CACHE.clear()
            _SUGGEST_CACHE[key] = (time.time(), online)
    from core.assistant_platform.nutrition_common import common_foods
    mine = saved_ingredients(store, query)
    matches = sorted(mine + common_foods(query) + online["matches"], key=lambda m: _rank(query, m))[:10]
    used = sorted({"Your recipes" if m["dataType"] == "Yours" else "Common foods" if m["dataType"] == "Common food" else "Open Food Facts" if m["dataType"] == "Product" else "USDA" for m in matches})
    return {"query": query, "matches": matches, "offline": online["offline"], "sources": used}


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


# Weights for household units, so "1 cup of potatoes" or "4 strips of bacon" can be scaled (grams per unit).
_UNIT_GRAMS = {"oz": 28.3495, "ounce": 28.3495, "ounces": 28.3495, "lb": 453.592, "pound": 453.592, "pounds": 453.592,
               "g": 1, "gram": 1, "grams": 1, "kg": 1000, "ml": 1, "l": 1000, "liter": 1000, "liters": 1000,
               "cup": 240, "cups": 240, "tbsp": 15, "tablespoon": 15, "tablespoons": 15, "tsp": 5, "teaspoon": 5, "teaspoons": 5}
# Typical amount for an add-in ("eggs with tomatoes, onion, mushrooms and cheese") when no amount is given.
_ADD_IN_GRAMS = {"cheese": 28, "jelly": 20, "jam": 20, "granola": 30, "butter": 10, "syrup": 20, "honey": 14, "peanut butter": 16,
                 "cream cheese": 28, "sour cream": 30, "salsa": 30, "ketchup": 17, "mayo": 14, "dressing": 30}


def _serving_grams_of(match: dict) -> float | None:
    text = str(match.get("servingSize") or "")
    found = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:g|grams?|ml)\b", text, re.I)
    if found:
        return float(found.group(1).replace(",", "."))
    try:
        value = float(text)
    except ValueError:
        return None
    return value if value > 0 and str(match.get("servingSizeUnit") or "").lower() in ("g", "grm", "ml", "mlt") else None


def plan_meal(text: str) -> list[dict]:
    """Every food in a meal description: add-ins split out ("3 eggs with tomatoes, onion, mushrooms, and cheese" is five
    foods), the amount and unit Grey said, nutrients he stated ("a 25 g protein shake" = 25 g protein), and which items
    are add-ins (a smaller typical amount when none is said). Rule-based on purpose: the local model dropped amounts."""
    items = []
    for piece in parse_meal(text):
        # "3 eggs with tomatoes" -> eggs + tomatoes (an add-in).
        parts = re.split(r"\s+with\s+", piece["text"], maxsplit=1)
        first = parse_meal(parts[0])[0] if parts[0].strip() else piece
        protein = re.search(r"(\d+(?:\.\d+)?)\s*g\s+(?:of\s+)?protein", piece["text"], re.I)
        name = re.sub(r"^\d+(?:\.\d+)?\s*g\s+(?=protein)", "", first["name"], flags=re.I)
        said_amount = first["amount"] if not (protein and first["unit"] in ("g", "gram", "grams", "serving")) else None
        items.append({"text": parts[0].strip(), "name": name, "amount": said_amount,
                      "unit": None if first["unit"] in ("", "serving") or said_amount is None else first["unit"], "addIn": False,
                      "statedProteinG": float(protein.group(1)) if protein else None})
        if len(parts) > 1:
            items.append({"text": parts[1].strip(), "name": parts[1].strip(), "amount": None, "unit": None, "addIn": True, "statedProteinG": None,
                          "chainStart": True})
    # Short, amount-less pieces right after an add-in belong to the same food only when that list closes with
    # "and …" ("tomatoes, onion, mushrooms, and cheese"); otherwise they are foods of their own ("granola, apple sauce").
    i = 0
    while i < len(items):
        if items[i].pop("chainStart", False):
            j = i + 1
            while j < len(items) and items[j]["amount"] is None and items[j]["statedProteinG"] is None and len(items[j]["name"].split()) <= 2:
                j += 1
            closing = items[j - 1]["name"] if j - 1 > i else ""
            if closing and re.search(r"\band\s+(?:a\s+|an\s+|some\s+)?" + re.escape(closing) + r"\b", text, re.I):
                for k in range(i + 1, j):
                    items[k]["addIn"] = True
            i = j
        else:
            i += 1
    return items


def _portion(item: dict, match: dict) -> tuple[float | None, str]:
    """Grams for an item and how they were worked out (said by Grey, a household unit, the label serving, or a typical add-in)."""
    amount, unit, name = item.get("amount"), (item.get("unit") or "").rstrip("s") if item.get("unit") not in ("g", "ml") else item.get("unit"), item["name"].lower()
    serving = _serving_grams_of(match)
    if amount and unit in ("g", "ml", "kg", "oz", "ounce", "lb", "pound", "l", "liter"):
        return amount * _UNIT_GRAMS.get(unit, _UNIT_GRAMS.get(unit + "s", 1)), f"{amount:g} {item.get('unit')} as you said"
    if amount and unit in ("cup", "tbsp", "tablespoon", "tsp", "teaspoon"):
        label = str(match.get("servingLabel") or "").lower()
        if serving and label.startswith("1 cup") and unit == "cup":
            return amount * serving, f"{amount:g} cup ≈ {amount * serving:.0f} g (label serving)"
        grams = amount * _UNIT_GRAMS[unit if unit in _UNIT_GRAMS else unit + "s"]
        return grams, f"{amount:g} {item.get('unit')} ≈ {grams:.0f} g (estimate)"
    if amount and serving:
        return amount * serving, f"{amount:g} × {match.get('servingLabel') or 'serving'} ≈ {amount * serving:.0f} g"
    if amount:
        return None, ""
    if item.get("addIn"):
        grams = next((g for key, g in _ADD_IN_GRAMS.items() if key in name), 30)
        return grams, f"added in: about {grams} g (estimate)"
    if serving:
        return serving, f"1 serving: {match.get('servingLabel') or f'{serving:g} g'} (no amount said)"
    return None, ""


def preview_meal(text: str, store=None) -> dict:
    """A reviewable meal from one sentence: each food matched (your recipes, common foods, food labels, websites),
    scaled to the portion said or estimated, with every estimate marked so it can be checked and changed."""
    from concurrent.futures import ThreadPoolExecutor
    items = plan_meal(text)
    if not items:
        raise ValueError("Describe the food and how much you ate.")

    def look(item):
        try:
            matches = search_products(item["name"], store)["matches"]
        except Exception:
            matches = []
        if not any(m["nutrients"].get("fiber") is not None for m in matches[:3]):
            try:
                from core.assistant_platform.nutrition_web import web_lookup
                matches = matches + web_lookup(item["name"])["matches"]
            except Exception:
                pass
        return matches
    with ThreadPoolExecutor(max_workers=6) as pool:
        found = list(pool.map(look, items))
    result = []
    for item, matches in zip(items, found):
        # Prefer a match that reports calories, protein and fiber, so the meal can be logged.
        # When no amount (or only a count) was said, a match with a serving size is needed to know how much it was.
        needs_serving = not item.get("addIn") and (item.get("amount") is None or not item.get("unit"))
        ordered = sorted(matches, key=lambda m: (needs_serving and _serving_grams_of(m) is None,
                                                 not all(m["nutrients"].get(k) is not None for k in ("calories", "protein", "fiber"))))
        row = {"text": item["text"], "name": item["name"], "amount": item.get("amount"), "unit": item.get("unit") or "",
               "matches": ordered[:8], "nutrients": None, "grams": None, "source": "", "sourceName": "", "question": "", "note": ""}
        if not ordered:
            row["question"] = f"I couldn't find {item['name']}. Add a brand, try a simpler name, or enter its label."
            result.append(row)
            continue
        best = ordered[0]
        grams, how = _portion(item, best)
        row.update(selected=best, source=best["source"], sourceName=best["sourceName"], checkedAt=best.get("checkedAt"))
        if grams is None:
            row["question"] = f"How many grams of {item['name']} was it? (no serving size listed)"
        else:
            row["grams"] = round(grams, 1)
            row["nutrients"] = {k: (round(float(v) * grams / 100, 2) if v is not None else None) for k, v in best["nutrients"].items()}
            if item.get("statedProteinG") is not None:
                row["nutrients"]["protein"] = item["statedProteinG"]
                how += f" · protein {item['statedProteinG']:g} g as you said"
            row["note"] = how
            if any(row["nutrients"].get(k) is None for k in ("calories", "protein", "fiber")):
                row["question"] = "This record is missing calories, protein or fiber. Pick another match or enter the label value."
        result.append(row)
    complete = all(i["nutrients"] is not None and all(i["nutrients"].get(k) is not None for k in ("calories", "protein", "fiber")) for i in result)
    return {"description": text[:2000], "items": result, "complete": complete,
            "message": "Each food is matched and scaled to the portion you said; amounts you didn't give are estimated and marked. Change any match or weight, then log."}


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
