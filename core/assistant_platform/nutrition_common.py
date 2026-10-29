"""Common whole foods with typical values per 100 g (USDA SR Legacy / FoodData Central reference values).

Always available, even when the online catalogs are offline or rate-limited, so plain ingredients like
"eggs", "oats" or "olive oil" always have a match. Brands and preparations differ: the recipe editor shows
these as "typical values" and every number stays editable. None means the value isn't listed here.
Columns: calories, protein, carbs, fat, saturatedFat, fiber, sugars, sodiumMg, cholesterolMg.
"""
from __future__ import annotations

_ROWS = [
    # name, aliases, values
    ("Egg, whole, raw", "egg eggs whole egg", (143, 12.6, 0.7, 9.5, 3.1, 0, 0.4, 142, 372)),
    ("Egg white, raw", "egg white whites", (52, 10.9, 0.7, 0.2, 0, 0, 0.7, 166, 0)),
    ("Chicken breast, skinless, raw", "chicken breast chicken", (120, 22.5, 0, 2.6, 0.6, 0, 0, 45, 73)),
    ("Chicken breast, skinless, roasted", "chicken breast cooked grilled chicken", (165, 31.0, 0, 3.6, 1.0, 0, 0, 74, 85)),
    ("Ground beef, 85% lean, raw", "ground beef beef mince hamburger", (215, 18.6, 0, 15.0, 5.9, 0, 0, 66, 68)),
    ("Salmon, Atlantic, farmed, raw", "salmon fish", (208, 20.4, 0, 13.4, 3.1, 0, 0, 59, 55)),
    ("Oats, rolled, dry", "oats oatmeal rolled oats porridge", (389, 16.9, 66.3, 6.9, 1.2, 10.6, None, 2, 0)),
    ("Rice, white, long-grain, raw", "rice white rice uncooked", (365, 7.1, 80.0, 0.7, 0.2, 1.3, 0.1, 5, 0)),
    ("Rice, white, long-grain, cooked", "rice white rice cooked", (130, 2.7, 28.2, 0.3, 0.1, 0.4, 0.1, 1, 0)),
    ("Pasta, dry", "pasta spaghetti penne macaroni noodles", (371, 13.0, 74.7, 1.5, 0.3, 3.2, 2.7, 6, 0)),
    ("Flour, wheat, all-purpose", "flour all purpose white flour", (364, 10.3, 76.3, 1.0, 0.2, 2.7, 0.3, 2, 0)),
    ("Flour, whole wheat", "flour whole wheat wholemeal", (340, 13.2, 72.0, 2.5, 0.4, 10.7, 0.4, 2, 0)),
    ("Sugar, granulated", "sugar white sugar", (387, 0, 100.0, 0, 0, 0, 99.8, 1, 0)),
    ("Honey", "honey", (304, 0.3, 82.4, 0, 0, 0.2, 82.1, 4, 0)),
    ("Banana, raw", "banana bananas", (89, 1.1, 22.8, 0.3, 0.1, 2.6, 12.2, 1, 0)),
    ("Apple, raw, with skin", "apple apples", (52, 0.3, 13.8, 0.2, 0, 2.4, 10.4, 1, 0)),
    ("Blueberries, raw", "blueberries blueberry berries", (57, 0.7, 14.5, 0.3, 0, 2.4, 10.0, 1, 0)),
    ("Strawberries, raw", "strawberries strawberry berries", (32, 0.7, 7.7, 0.3, 0, 2.0, 4.9, 1, 0)),
    ("Avocado, raw", "avocado avocados", (160, 2.0, 8.5, 14.7, 2.1, 6.7, 0.7, 7, 0)),
    ("Broccoli, raw", "broccoli", (34, 2.8, 6.6, 0.4, 0, 2.6, 1.7, 33, 0)),
    ("Spinach, raw", "spinach", (23, 2.9, 3.6, 0.4, 0.1, 2.2, 0.4, 79, 0)),
    ("Potato, raw, with skin", "potato potatoes", (77, 2.0, 17.5, 0.1, 0, 2.2, 0.8, 6, 0)),
    ("Sweet potato, raw", "sweet potato yam", (86, 1.6, 20.1, 0.1, 0, 3.0, 4.2, 55, 0)),
    ("Onion, raw", "onion onions", (40, 1.1, 9.3, 0.1, 0, 1.7, 4.2, 4, 0)),
    ("Tomato, raw", "tomato tomatoes", (18, 0.9, 3.9, 0.2, 0, 1.2, 2.6, 5, 0)),
    ("Carrot, raw", "carrot carrots", (41, 0.9, 9.6, 0.2, 0, 2.8, 4.7, 69, 0)),
    ("Bell pepper, red, raw", "bell pepper red pepper peppers capsicum", (31, 1.0, 6.0, 0.3, 0, 2.1, 4.2, 4, 0)),
    ("Garlic, raw", "garlic", (149, 6.4, 33.1, 0.5, 0.1, 2.1, 1.0, 17, 0)),
    ("Black beans, cooked", "black beans beans", (132, 8.9, 23.7, 0.5, 0.1, 8.7, 0.3, 1, 0)),
    ("Chickpeas, cooked", "chickpeas chick peas garbanzo", (164, 8.9, 27.4, 2.6, 0.3, 7.6, 4.8, 7, 0)),
    ("Lentils, cooked", "lentils lentil", (116, 9.0, 20.1, 0.4, 0.1, 7.9, 1.8, 2, 0)),
    ("Olive oil", "olive oil oil", (884, 0, 0, 100.0, 13.8, 0, 0, 2, 0)),
    ("Butter, salted", "butter", (717, 0.9, 0.1, 81.1, 51.4, 0, 0.1, 643, 215)),
    ("Milk, whole (3.25%)", "milk whole milk", (61, 3.2, 4.8, 3.3, 1.9, 0, 5.1, 43, 10)),
    ("Milk, skim", "milk skim milk nonfat milk", (34, 3.4, 5.0, 0.1, 0.1, 0, 5.1, 42, 2)),
    ("Greek yogurt, plain, nonfat", "greek yogurt yoghurt yogurt", (59, 10.2, 3.6, 0.4, 0.1, 0, 3.2, 36, 5)),
    ("Cheddar cheese", "cheddar cheese", (403, 24.9, 1.3, 33.1, 21.1, 0, 0.5, 621, 105)),
    ("Peanut butter, smooth", "peanut butter pb", (588, 25.1, 19.6, 50.4, 10.1, 6.0, 9.2, 459, 0)),
    ("Almonds", "almonds almond nuts", (579, 21.2, 21.6, 49.9, 3.8, 12.5, 4.4, 1, 0)),
]
# Typical serving for each food (label, grams), so the recipe editor can work by serving instead of per 100 g.
SERVINGS = {
    "Egg, whole, raw": ("1 large egg", 50), "Egg white, raw": ("1 large egg white", 33),
    "Chicken breast, skinless, raw": ("4 oz", 113), "Chicken breast, skinless, roasted": ("3 oz", 85),
    "Ground beef, 85% lean, raw": ("4 oz", 113), "Salmon, Atlantic, farmed, raw": ("4 oz", 113),
    "Oats, rolled, dry": ("1/2 cup dry", 40), "Rice, white, long-grain, raw": ("1/4 cup dry", 46),
    "Rice, white, long-grain, cooked": ("1 cup", 158), "Pasta, dry": ("2 oz dry", 56),
    "Flour, wheat, all-purpose": ("1/4 cup", 31), "Flour, whole wheat": ("1/4 cup", 30),
    "Sugar, granulated": ("1 tsp", 4), "Honey": ("1 tbsp", 21), "Banana, raw": ("1 medium", 118),
    "Apple, raw, with skin": ("1 medium", 182), "Blueberries, raw": ("1 cup", 148), "Strawberries, raw": ("1 cup", 152),
    "Avocado, raw": ("1/2 avocado", 100), "Broccoli, raw": ("1 cup chopped", 91), "Spinach, raw": ("1 cup", 30),
    "Potato, raw, with skin": ("1 medium", 213), "Sweet potato, raw": ("1 medium", 130), "Onion, raw": ("1 medium", 110),
    "Tomato, raw": ("1 medium", 123), "Carrot, raw": ("1 medium", 61), "Bell pepper, red, raw": ("1 medium", 119),
    "Garlic, raw": ("1 clove", 3), "Black beans, cooked": ("1/2 cup", 86), "Chickpeas, cooked": ("1/2 cup", 82),
    "Lentils, cooked": ("1/2 cup", 99), "Olive oil": ("1 tbsp", 13.5), "Butter, salted": ("1 tbsp", 14),
    "Milk, whole (3.25%)": ("1 cup", 244), "Milk, skim": ("1 cup", 245), "Greek yogurt, plain, nonfat": ("1 container", 170),
    "Cheddar cheese": ("1 oz", 28), "Peanut butter, smooth": ("2 tbsp", 32), "Almonds": ("1 oz (about 23)", 28),
}
_KEYS = ("calories", "protein", "carbs", "fat", "saturatedFat", "fiber", "sugars", "sodiumMg", "cholesterolMg")
SOURCE = "https://fdc.nal.usda.gov/"


def common_foods(query: str, limit: int = 4) -> list[dict]:
    """Common foods whose name or aliases contain every word typed (plurals and partial words count)."""
    import re
    words = [w.rstrip("s") for w in re.findall(r"[a-z]+", str(query).lower()) if len(w) > 1]
    if not words:
        return []
    out = []
    for name, aliases, values in _ROWS:
        haystack = f"{name} {aliases}".lower()
        if all(w in haystack for w in words):
            label, grams = SERVINGS.get(name, ("", None))
            out.append({"fdcId": None, "title": name, "dataType": "Common food", "servingSize": grams, "servingSizeUnit": "g" if grams else "", "servingLabel": label,
                        "basis": "per 100 g", "nutrients": dict(zip(_KEYS, values)), "source": SOURCE,
                        "sourceName": "Typical values (USDA reference) · check your package"})
    return out[:limit]
