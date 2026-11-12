import json
import unittest

from core.research import links

TIKTOK_DATA = {"__DEFAULT_SCOPE__": {"webapp.video-detail": {"itemInfo": {"itemStruct": {
    "desc": "How to get the physique #gym", "author": {"uniqueId": "coach"}, "music": {"title": "original sound"},
    "video": {"duration": 39, "subtitleInfos": [{"LanguageCodeName": "eng-US", "Url": "https://cdn.example/sub.vtt"}]}}}}}}
TIKTOK_PAGE = ('<html><script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">'
               + json.dumps(TIKTOK_DATA) + "</script></html>")
VTT = "WEBVTT\n\n00:00:00.036 --> 00:00:02.795\nTrain every muscle group.\n\n00:00:02.796 --> 00:00:06.943\nNo skipping leg day.\nNo skipping leg day.\n"


class LinksTest(unittest.TestCase):
    def test_finds_links(self):
        self.assertEqual(links.find_links("see https://a.com/x, and (https://b.org/y)."), ["https://a.com/x", "https://b.org/y"])

    def test_tiktok_gives_caption_and_spoken_words(self):
        pages = {"https://www.tiktok.com/@coach/video/1": TIKTOK_PAGE, "https://cdn.example/sub.vtt": VTT}
        found = links.read_link("https://www.tiktok.com/@coach/video/1", get_text=pages.__getitem__)
        self.assertEqual(found["kind"], "TikTok video")
        self.assertIn("Caption: How to get the physique #gym", found["text"])
        self.assertIn("Train every muscle group. No skipping leg day.", found["text"])
        self.assertEqual(found["text"].count("No skipping leg day."), 1)

    def test_unreadable_link_says_so(self):
        def broken(url):
            raise ValueError("That address isn't a public web page.")
        [(name, body)] = links.links_as_files("read http://192.168.1.5/admin", reader=broken)
        self.assertIn("couldn't read this link", body.decode())
        self.assertTrue(name.endswith(".txt"))

    def test_page_falls_back_to_its_summary(self):
        page = '<html><head><meta property="og:title" content="Post"><meta property="og:description" content="Leg day tips"></head><body><script>x</script></body></html>'
        found = links.read_link("https://example.com/p", get_text=lambda url: page)
        self.assertEqual(found["text"], "Post Leg day tips")

    def test_clarify(self):
        self.assertTrue(links.wants_clarify("use this link to make me a fitness program https://x"))
        self.assertFalse(links.wants_clarify("what is this https://x"))
        self.assertFalse(links.wants_clarify("make me a fitness program\n\nMy answers to your questions:\n- a"))
        prompts = []
        reply = '```json\n{"questions": [{"question": "Your level?", "options": ["Beginner", "Advanced"]}, {"question": ""}]}\n```'
        questions = links.clarify_questions("make me a program https://t.co/x", "LINK: x\nWHAT IT IS: TikTok video: by @coach\n",
                                            lambda p: prompts.append(p) or reply)
        self.assertEqual(questions, [{"question": "Your level?", "options": ["Beginner", "Advanced"]}])
        self.assertIn("shared: TikTok video: by @coach", prompts[0])
        self.assertNotIn("https://t.co", prompts[0])
        self.assertEqual(links.clarify_questions("x", "", lambda p: "no json"), [])


if __name__ == "__main__":
    unittest.main()
