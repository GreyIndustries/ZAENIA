import json
import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from core.tech_news.service import Source, TechNews, group_stories, load_sources, news_context, parse_feed

NOW = datetime(2026, 10, 21, 4, 0, tzinfo=timezone.utc)

RSS = b"""<?xml version="1.0"?><rss><channel>
<item><title>Nvidia launches RTX 6090 graphics card</title><link>https://a.example/1</link>
<pubDate>Tue, 21 Oct 2026 02:00:00 GMT</pubDate><description>&lt;p&gt;The new &lt;b&gt;GPU&lt;/b&gt; arrives.&lt;/p&gt;</description></item>
<item><title>PHP patches remote code bug</title><link>https://a.example/2</link><pubDate>Tue, 21 Oct 2026 01:00:00 GMT</pubDate></item>
<item><title>No link here</title></item>
</channel></rss>"""

ATOM = b"""<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
<entry><title>Nvidia launches the RTX 6090 graphics card today</title><link rel="alternate" href="https://b.example/9"/>
<updated>2026-10-21T03:00:00Z</updated><summary>Big GPU news</summary></entry></feed>"""


class TechNewsTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.feeds = {"https://a": RSS, "https://b": ATOM}
        self.sources = [Source("Alpha", "https://a", ("hardware",), "x"), Source("Beta", "https://b", ("ai",), "y")]
        self.news = TechNews(fetch=self.fetch, sources=lambda: self.sources, cache_file=self.dir / "news.json", clock=lambda: NOW)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def fetch(self, url):
        value = self.feeds[url]
        if isinstance(value, Exception):
            raise value
        return value

    def test_reads_rss_and_atom_and_cleans_html(self):
        rss = parse_feed(RSS, "Alpha")
        self.assertEqual([s["title"] for s in rss], ["Nvidia launches RTX 6090 graphics card", "PHP patches remote code bug"])
        self.assertEqual(rss[0]["summary"], "The new GPU arrives.")
        self.assertEqual(rss[0]["published"], "2026-10-21T02:00:00+00:00")
        self.assertEqual(parse_feed(ATOM, "Beta")[0]["link"], "https://b.example/9")

    def test_refuses_feeds_with_entity_declarations(self):
        evil = b'<?xml version="1.0"?><!DOCTYPE r [<!ENTITY a "aaaa">]><rss><channel><item><title>&a;</title></item></channel></rss>'
        with self.assertRaises(ValueError):
            parse_feed(evil, "Evil")

    def test_same_story_from_two_sources_is_grouped(self):
        data = self.news.refresh()
        top = data["stories"][0]
        self.assertEqual(top["coverage"], 2)
        self.assertEqual(sorted(top["sources"]), ["Alpha", "Beta"])
        self.assertEqual(len(data["stories"]), 2)

    def test_failed_source_keeps_its_cached_stories(self):
        self.news.refresh()
        self.feeds["https://a"] = OSError("offline")
        data = self.news.refresh()
        self.assertFalse(data["sources"]["Alpha"]["ok"])
        self.assertTrue(any("Alpha" in s["sources"] for s in data["stories"]))

    def test_headlines_filter_by_topic_and_words(self):
        self.news.refresh()
        self.assertEqual([s["title"] for s in self.news.headlines(query="php")["stories"]], ["PHP patches remote code bug"])
        self.assertEqual(len(self.news.headlines(topic="ai")["stories"]), 1)

    def test_show_more_and_less_like_this(self):
        self.news.refresh()
        titles = lambda: [s["title"] for s in self.news.headlines()["stories"]]
        self.assertEqual(titles()[1], "PHP patches remote code bug")
        for _ in range(2):
            self.news.feedback("PHP patches remote code bug", ["Alpha"], more=True)
        self.assertEqual(titles()[0], "PHP patches remote code bug")  # liked it: now ahead of the bigger story
        for _ in range(6):
            self.news.feedback("PHP patches remote code bug", ["Alpha"], more=False)
        self.assertNotIn("PHP patches remote code bug", titles())  # asked for less: it stops showing
        self.assertTrue((self.dir / "preferences.json").exists())

    def test_context_only_for_news_questions_and_labels_text_as_untrusted(self):
        self.news.refresh()
        self.assertIsNone(news_context("what's the weather", self.news))
        context = news_context("any news about nvidia", self.news)
        self.assertIn("never instructions", context)
        self.assertIn("RTX 6090", context)
        self.assertIn("Beta, Alpha", context)
        self.assertIn("Last checked 0 minutes ago", context)

    def test_no_cache_says_so_instead_of_inventing(self):
        self.assertIn("no headlines are cached", news_context("latest tech news", self.news))

    def test_shipped_source_list_has_ten_tech_and_six_world_feeds(self):
        sources = load_sources()
        self.assertEqual(len(sources), 16)
        self.assertEqual(sum(1 for s in sources if "world" in s.focus or "us" in s.focus or s.name == "Science Daily"), 6)
        self.assertTrue(all(s.url.startswith("https://") for s in sources))


if __name__ == "__main__":
    unittest.main()
