import unittest

from core.assistant_platform import nutrition_web as w

FAIRLIFE = ("Serving Size 1 cup (240ml)\nServings Per Container About 6\nAmount Per Serving\nCalories\n150\n% Daily Value*\nTotal Fat\n8g\n10%\n"
            "Saturated Fat 5g\n25%\nTrans Fat 0g\nCholesterol\n30mg\n10%\nSodium\n120mg\n5%\nTotal Carbohydrate\n6g\n2%\nDietary Fiber 0g\n0%\n"
            "Total Sugars 6g\nProtein\n13g\n26%")
FS_SEARCH = ('<a class="prominent" href="/calories-nutrition/fairlife/whole-ultra-filtered-milk">Whole Ultra-Filtered Milk</a>&nbsp;&nbsp;'
             '<a class="brand" href="/calories-nutrition/fairlife">(Fairlife)</a>\n<div class="smallText greyText greyLink">\n'
             'Per 1 cup - Calories: 150kcal | Fat: 8.00g | Carbs: 6.00g | Protein: 13.00g\n</div>')
FS_ITEM = '<meta name="description" content="There are 150 calories in 1 cup (240 ml) of Fairlife Whole Ultra-Filtered Milk. Calorie breakdown: 49% fat"/>'


class NutritionWebTest(unittest.TestCase):
    def test_reads_a_label_panel(self):
        found = w.label_from_text(FAIRLIFE)
        self.assertEqual(found["servingSize"], "1 cup (240ml)")
        self.assertEqual((found["values"]["calories"], found["values"]["protein"], found["values"]["sodiumMg"], found["values"]["fiber"]), (150, 13, 120, 0))

    def test_serving_grams(self):
        self.assertEqual(w.serving_grams("1 cup (240ml)"), 240)
        self.assertEqual(w.serving_grams("2 tbsp (32 g)"), 32)
        self.assertEqual(w.serving_grams("1 cup (8 oz)"), 226.8)
        self.assertIsNone(w.serving_grams("1 bar"))

    def test_json_ld(self):
        html = ('<script type="application/ld+json">{"@type":"Product","name":"Oat Bar","nutrition":{"@type":"NutritionInformation",'
                '"servingSize":"1 bar (40 g)","calories":"160 calories","proteinContent":"4 g","fiberContent":"3 g"}}</script>')
        found = w._json_ld(html)
        self.assertEqual((found["title"], found["servingSize"], found["values"]["calories"], found["values"]["fiber"]), ("Oat Bar", "1 bar (40 g)", 160, 3))

    def test_fatsecret(self):
        pages = {"search": FS_SEARCH, "item": FS_ITEM}
        out = w.fatsecret_products("fairlife whole milk", lambda url: pages["search"] if "/search?" in url else pages["item"])
        self.assertEqual(len(out), 1)
        m = out[0]
        self.assertEqual((m["title"], m["servingLabel"], m["servingSize"]), ("Fairlife Whole Ultra-Filtered Milk", "1 cup (240 ml)", "240 g"))
        self.assertEqual((m["perServing"]["calories"], m["perServing"]["protein"], m["perServing"]["fiber"]), (150, 13, None))
        self.assertAlmostEqual(m["nutrients"]["calories"], 62.5)

    def test_page_reader_skips_pages_without_a_label(self):
        def search(query, limit=10):
            return [{"url": "https://brand.example/milk", "title": "Milk"}, {"url": "https://www.youtube.com/watch?v=1", "title": "video"},
                    {"url": "https://blog.example/post", "title": "Blog"}]
        pages = {"https://brand.example/milk": "<html><body><div>" + FAIRLIFE.replace("\n", "<br>") + "</div></body></html>",
                 "https://blog.example/post": "<p>We love milk.</p>"}
        result = w.web_products("fairlife whole milk", search=search, get_text=lambda url: pages[url])
        self.assertEqual(result["read"], ["brand.example", "blog.example"])
        self.assertEqual(len(result["matches"]), 1)
        self.assertEqual(result["matches"][0]["perServing"]["calories"], 150)


if __name__ == "__main__":
    unittest.main()
