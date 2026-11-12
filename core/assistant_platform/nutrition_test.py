import unittest
from unittest.mock import patch

from core.assistant_platform import nutrition


class NutritionTest(unittest.TestCase):
    def test_meal_parser_keeps_each_amount_and_food(self):
        items = nutrition.parse_meal("I ate three eggs, 4 waffles, 4 strips of bacon, 1 cup of sauteed potatoes, 1 cup of orange juice, and 25g protein shake for breakfast.")
        self.assertEqual(len(items), 6)
        self.assertEqual([(item["amount"], item["unit"], item["name"]) for item in items], [
            (3.0, "serving", "eggs"), (4.0, "serving", "waffles"), (4.0, "strips", "bacon"),
            (1.0, "cup", "sauteed potatoes"), (1.0, "cup", "orange juice"), (25.0, "g protein", "protein shake")])
        self.assertIsNone(items[0]["grams"])
        self.assertIsNone(items[5]["grams"])
        self.assertIn("Confirm its brand", items[5]["question"])

    def test_meal_uses_catalog_values_and_keeps_unknown_nutrients_unknown(self):
        record = {"fdcId": 123, "description": "Kale, raw", "dataType": "Foundation", "foodNutrients": [
            {"nutrientName": "Energy", "unitName": "kcal", "value": 143},
            {"nutrientName": "Protein", "unitName": "g", "value": 12.6},
            {"nutrientName": "Fiber, total dietary", "unitName": "g", "value": 0},
            {"nutrientName": "Carbohydrate, by difference", "unitName": "g", "value": 0.72}]}
        nutrition._SUGGEST_CACHE.clear()
        with patch.object(nutrition, "_request", return_value={"foods": [record]}):
            result = nutrition.preview_meal("I ate 100g kale")
        item = result["items"][0]
        self.assertEqual(item["nutrients"]["calories"], 143)
        self.assertEqual(item["nutrients"]["protein"], 12.6)
        self.assertIsNone(item["nutrients"]["fat"])
        self.assertTrue(result["complete"])

    def test_lookup_failure_becomes_question_without_estimation(self):
        nutrition._SUGGEST_CACHE.clear()
        with patch.object(nutrition, "_request", side_effect=OSError("offline")),              patch("core.assistant_platform.nutrition_web.web_lookup", side_effect=OSError("offline")):
            result = nutrition.preview_meal("I ate 100g kale")
        self.assertFalse(result["complete"])
        self.assertIn("couldn't find kale", result["items"][0]["question"])
        self.assertIsNone(result["items"][0]["nutrients"])

    def test_one_sentence_breakfast_is_split_and_portioned(self):
        nutrition._SUGGEST_CACHE.clear()
        text = ("I ate 1 cup of potatoes, 3 eggs with tomatoes, onion, mushrooms, and cheese, 4 strips of bacon, bagel with jelly, "
                "10 oz of apple juice, Chobani yogurt with granola, apple sauce, and a 25 G protein shake.")
        plan = nutrition.plan_meal(text)
        self.assertEqual([i["name"] for i in plan], ["potatoes", "eggs", "tomatoes", "onion", "mushrooms", "cheese", "bacon", "bagel", "jelly",
                                                     "apple juice", "Chobani yogurt", "granola", "apple sauce", "protein shake"])
        self.assertEqual([i["name"] for i in plan if i["addIn"]], ["tomatoes", "onion", "mushrooms", "cheese", "jelly", "granola"])
        self.assertEqual(plan[-1]["statedProteinG"], 25)
        with patch.object(nutrition, "_request", side_effect=OSError("offline")),              patch("core.assistant_platform.nutrition_web.web_lookup", side_effect=OSError("offline")):
            result = nutrition.preview_meal(text)
        rows = {i["name"]: i for i in result["items"]}
        self.assertEqual(rows["eggs"]["grams"], 150)            # 3 × 1 large egg
        self.assertEqual(rows["bacon"]["grams"], 32)            # 4 × 1 strip
        self.assertAlmostEqual(rows["apple juice"]["grams"], 283.5, places=1)
        self.assertEqual(rows["cheese"]["grams"], 28)           # add-in estimate
        self.assertEqual(rows["protein shake"]["nutrients"]["protein"], 25)
        self.assertIn("estimate", rows["onion"]["note"])

    def test_barcode_requires_digits(self):
        with self.assertRaises(ValueError):
            nutrition.barcode_lookup("not a barcode")

    def test_barcode_reads_a_us_upc_with_its_nutrition(self):
        product = {"code": "0028400090896", "brands": "Doritos", "product_name": "Nacho Cheese",
                   "nutriments": {"energy-kcal_100g": 536, "proteins_100g": 7.1, "sodium_100g": 0.75}}
        with patch.object(nutrition, "_request", return_value={"code": "0028400090896", "product": product}) as request:
            found = nutrition.barcode_lookup("028400090896")
        self.assertIn("/api/v2/product/028400090896.json", request.call_args[0][0])
        self.assertTrue(found["found"])
        self.assertEqual(found["nutrients"]["calories"], 536)
        self.assertEqual(found["nutrients"]["sodiumMg"], 750)

    def test_barcode_retries_with_a_leading_zero_and_reports_a_miss(self):
        import urllib.error
        missing = urllib.error.HTTPError("u", 404, "not found", {}, None)
        product = {"code": "0049000028911", "product_name": "Diet Coke", "nutriments": {"energy-kcal_100g": 0}}
        with patch.object(nutrition, "_request", side_effect=[missing, {"status": 1, "product": product}]):
            self.assertTrue(nutrition.barcode_lookup("049000028911")["found"])
        with patch.object(nutrition, "_request", return_value={"status": 0, "status_verbose": "product not found"}):
            miss = nutrition.barcode_lookup("12345670")
        self.assertFalse(miss["found"])
        self.assertIn("12345670", miss["question"])

    def test_totals_mark_missing_facts_instead_of_counting_them_as_zero(self):
        self.assertEqual(nutrition.totals([{"nutrients": {"calories": 140, "protein": 12, "fiber": 0, "fat": None}},
                                           {"nutrients": {"calories": 100, "protein": 4, "fiber": 2, "fat": 5}}]),
                         {"calories": 240, "protein": 16, "carbs": None, "fat": None, "saturatedFat": None,
                          "fiber": 2, "sugars": None, "sodiumMg": None, "cholesterolMg": None})

    def test_nutrition_routes_keep_existing_read_write_authority_split(self):
        from core.api.platform_routes import operation_for
        self.assertEqual(operation_for("POST", "/api/platform/personal/nutrition/meal-preview"), "memory.read")
        self.assertEqual(operation_for("POST", "/api/platform/personal/nutrition/barcode"), "memory.read")
        self.assertEqual(operation_for("POST", "/api/platform/personal/nutrition/log"), "memory.write")
        self.assertEqual(operation_for("GET", "/api/platform/personal/recipes"), "memory.read")


if __name__ == "__main__":
    unittest.main()


class SearchProductsTest(__import__("unittest").TestCase):
    def setUp(self):
        from core.assistant_platform import nutrition
        nutrition._SUGGEST_CACHE.clear()
        self.nutrition = nutrition

    def test_combines_sources_and_survives_one_offline(self):
        from unittest import mock
        usda = {"foods": [{"fdcId": 1, "description": "Yogurt, Greek, plain", "dataType": "Foundation", "foodNutrients": [
            {"nutrientName": "Energy", "value": 59, "unitName": "KCAL"}, {"nutrientName": "Protein", "value": 10.3}]}]}
        off = {"hits": [{"code": "123", "product_name": "Greek Yogurt", "brands": ["Chobani"], "serving_size": "170 g",
                         "nutriments": {"energy-kcal_100g": 53, "proteins_100g": 9.4}}]}

        def fake(url, timeout=9):
            if "nal.usda.gov" in url:
                self.assertIn("dataType=Foundation%2CSR+Legacy", url)
                return usda
            return off
        with mock.patch.object(self.nutrition, "_request", side_effect=fake):
            result = self.nutrition.search_products("greek yogurt")
        self.assertEqual(result["offline"], [])
        titles = [m["title"] for m in result["matches"]]
        self.assertEqual(titles[0], "Greek yogurt, plain, nonfat")  # built-in common food ranks first among generic foods
        self.assertIn("Yogurt, Greek, plain", titles)
        self.assertEqual(titles.count("Chobani Greek Yogurt"), 1)  # the two Open Food Facts searches are merged
        self.assertEqual(next(m for m in result["matches"] if m["title"] == "Chobani Greek Yogurt")["nutrients"]["calories"], 53)
        self.assertEqual(result["sources"], ["Common foods", "Open Food Facts", "USDA"])

        self.nutrition._SUGGEST_CACHE.clear()

        def usda_down(url, timeout=9):
            if "nal.usda.gov" in url:
                raise OSError("429")
            return off
        with mock.patch.object(self.nutrition, "_request", side_effect=usda_down):
            result = self.nutrition.search_products("greek yogurt")
        self.assertEqual(result["offline"], ["USDA FoodData Central"])
        self.assertEqual([m["dataType"] for m in result["matches"]], ["Common food", "Product"])

    def test_common_foods_work_offline_and_saved_ingredients_come_first(self):
        from unittest import mock
        from core.assistant_platform.store import PlatformStore
        import tempfile, pathlib
        with tempfile.TemporaryDirectory() as folder:
            store = PlatformStore(pathlib.Path(folder) / "state.sqlite3")
            store.put("fitness_recipe", {"title": "Overnight oats", "archived": False, "category": "Meal", "servings": 1, "instructions": "", "source": "Owner",
                                         "createdAt": "2026-10-29T00:00:00+00:00",
                                         "ingredients": [{"name": "Oats, my brand", "amount": "50", "unit": "g", "grams": 50, "source": "label",
                                                          "nutrients": {"calories": 190, "protein": 6.5, "fiber": 5}}]}, None, revision=0)
            with mock.patch.object(self.nutrition, "_request", side_effect=OSError("offline")):
                result = self.nutrition.search_products("oats", store)
        self.assertEqual(result["offline"], ["USDA FoodData Central", "Open Food Facts"])
        self.assertEqual([m["dataType"] for m in result["matches"]], ["Yours", "Common food"])
        self.assertEqual(result["matches"][0]["nutrients"]["calories"], 380.0)

    def test_needs_two_letters(self):
        with self.assertRaises(ValueError):
            self.nutrition.search_products("a")


class ProductLabelTest(__import__("unittest").TestCase):
    def test_full_label_gives_real_name_and_serving_and_duplicates_merge(self):
        from unittest import mock
        from core.assistant_platform import nutrition
        nutrition._SUGGEST_CACHE.clear()
        hits = {"hits": [
            {"code": "1", "product_name": "Fairlife Whole", "brands": ["Fairlife"], "quantity": "52 fl oz", "countries_tags": ["en:united-states"],
             "completeness": .7, "nutriments": {"energy-kcal_100g": 62.5, "proteins_100g": 5.4}},
            {"code": "2", "product_name": "Fairlife Whole", "brands": ["Fairlife"], "countries_tags": ["en:united-states"],
             "completeness": .3, "nutriments": {"energy-kcal_100g": 62.5, "proteins_100g": 5.4}},
            {"code": "3", "product_name": "Greek Yogurt", "brands": ["Chobani"], "categories_tags": ["en:yogurts"],
             "nutriments": {"energy-kcal_100g": 74, "proteins_100g": 10}}]}
        labels = {"1": {"product": {"product_name": "Whole ultra-filtered milk", "brands": "fairlife", "quantity": "52 fl oz", "serving_size": "1 portion (240 ml)", "serving_quantity": 240}}}

        def fake(url, timeout=9):
            if "nal.usda.gov" in url:
                raise OSError("busy")
            if "/api/v2/product/" in url:
                return labels.get(url.split("/api/v2/product/")[1].split("?")[0], {"product": {}})
            return hits if "search.openfoodfacts.org" in url else {"products": []}
        with mock.patch.object(nutrition, "_request", side_effect=fake):
            result = nutrition.search_products("fairlife whole milk")
        products = [m for m in result["matches"] if m["dataType"] == "Product"]
        self.assertEqual(products[0]["title"], "fairlife Whole ultra-filtered milk")
        self.assertEqual(products[0]["servingSize"], "1 portion (240 ml)")
        self.assertEqual(sum(1 for m in products if "fairlife" in m["title"].lower()), 1)  # the duplicate merged
        yogurt = next(m for m in products if "Yogurt" in m["title"])
        self.assertEqual((yogurt["servingSize"], yogurt["servingLabel"]), ("170 g", "1 container (typical serving)"))

    def test_tidy_title(self):
        from core.assistant_platform.nutrition import _tidy_title
        self.assertEqual(_tidy_title("Chobani Chobani Greek Yogurt"), "Chobani Greek Yogurt")
