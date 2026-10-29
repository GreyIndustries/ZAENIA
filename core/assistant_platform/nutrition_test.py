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
        record = {"fdcId": 123, "description": "Egg, whole, raw, fresh", "dataType": "Foundation", "foodNutrients": [
            {"nutrientName": "Energy", "unitName": "kcal", "value": 143},
            {"nutrientName": "Protein", "unitName": "g", "value": 12.6},
            {"nutrientName": "Fiber, total dietary", "unitName": "g", "value": 0},
            {"nutrientName": "Carbohydrate, by difference", "unitName": "g", "value": 0.72}]}
        with patch.object(nutrition, "_request", return_value={"foods": [record]}):
            result = nutrition.preview_meal("I ate 100g eggs")
        item = result["items"][0]
        self.assertEqual(item["nutrients"]["calories"], 143)
        self.assertEqual(item["nutrients"]["protein"], 12.6)
        self.assertIsNone(item["nutrients"]["fat"])
        self.assertTrue(result["complete"])

    def test_lookup_failure_becomes_question_without_estimation(self):
        with patch.object(nutrition, "_request", side_effect=OSError("offline")):
            result = nutrition.preview_meal("I ate 100g eggs")
        self.assertFalse(result["complete"])
        self.assertIn("couldn't reach USDA", result["items"][0]["question"])
        self.assertIsNone(result["items"][0]["nutrients"])

    def test_barcode_requires_digits(self):
        with self.assertRaises(ValueError):
            nutrition.barcode_lookup("not a barcode")

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
        self.assertEqual([m["title"] for m in result["matches"]], ["Yogurt, Greek, plain", "Chobani Greek Yogurt"])
        self.assertEqual(result["matches"][1]["nutrients"]["calories"], 53)

        self.nutrition._SUGGEST_CACHE.clear()

        def usda_down(url, timeout=9):
            if "nal.usda.gov" in url:
                raise OSError("429")
            return off
        with mock.patch.object(self.nutrition, "_request", side_effect=usda_down):
            result = self.nutrition.search_products("greek yogurt")
        self.assertEqual(result["offline"], ["USDA FoodData Central"])
        self.assertEqual(len(result["matches"]), 1)

    def test_needs_two_letters(self):
        with self.assertRaises(ValueError):
            self.nutrition.search_products("a")
