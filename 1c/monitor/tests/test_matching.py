"""Name matching (case, word boundaries, aliases) and citation domain matching."""
import tempfile
import unittest
from pathlib import Path

from tests import _util  # noqa: F401  (puts the bundle on sys.path)
from matching import Watched, domain_matches, effective_url, find_mentions, load_names

RD = "https://vertexaisearch.cloud.google.com/grounding-api-redirect/ABC"


class NameMatching(unittest.TestCase):
    def setUp(self):
        self.bay = Watched("Bay Light Day Cruises", ["Bay Light"], ["baylight.example"])
        self.kayak = Watched("Harbor Kayak Co.", [], ["harborkayak.example"])
        self.kennel = Watched("Mile 12 Kennel", [], ["mile12kennel.example"])

    def named(self, text, w=None):
        w = w or self.bay
        return find_mentions(text, [w], [])[w.name]

    def test_case_insensitive(self):
        self.assertTrue(self.named("We loved BAY LIGHT DAY CRUISES.").appears)
        self.assertTrue(self.named("try bay light").appears)

    def test_word_boundaries(self):
        for text in ("Bay Lightning Tours is new", "Baylight is a domain", "SuperBay Light Co", "the Bay Lights"):
            self.assertFalse(self.named(text).appears, text)

    def test_possessive_markdown_and_punctuation(self):
        for text in ("Bay Light's cabin is warm", "**Bay Light Day Cruises**", "(Bay Light)", "Bay Light, then"):
            self.assertTrue(self.named(text).appears, text)

    def test_curly_apostrophe_hyphen_and_line_break(self):
        self.assertTrue(self.named("Bay Light’s crew").appears)
        self.assertTrue(self.named("Bay-Light runs in rain").appears)
        self.assertTrue(self.named("Bay\nLight runs in rain").appears)

    def test_alias_inside_full_name_counts_once(self):
        m = self.named("Bay Light Day Cruises is good. Later, Bay Light again.")
        self.assertEqual(m.mention_count, 2)
        self.assertEqual(m.first_offset, 0)

    def test_trailing_period_optional(self):
        self.assertTrue(self.named("Harbor Kayak Co offers paddles", self.kayak).appears)
        self.assertTrue(self.named("Book Harbor Kayak Co. today", self.kayak).appears)
        self.assertFalse(self.named("Harbor Kayak Company", self.kayak).appears)  # needs an alias

    def test_rank_among_watched(self):
        res = find_mentions("Harbor Kayak Co. first, then Bay Light.", [self.bay, self.kayak, self.kennel], [])
        self.assertEqual(res["Harbor Kayak Co."].rank_among_watched, 1)
        self.assertEqual(res["Bay Light Day Cruises"].rank_among_watched, 2)
        self.assertIsNone(res["Mile 12 Kennel"].rank_among_watched)
        self.assertIsNone(res["Mile 12 Kennel"].first_offset)
        self.assertEqual(res["Mile 12 Kennel"].mention_count, 0)

    def test_number_in_name_needs_whole_word(self):
        self.assertFalse(self.named("Mile 120 Kennel", self.kennel).appears)
        self.assertTrue(self.named("mile 12 kennel", self.kennel).appears)


class DomainMatching(unittest.TestCase):
    def test_subdomain_and_www(self):
        self.assertTrue(domain_matches("https://www.baylight.example/cruise", "baylight.example"))
        self.assertTrue(domain_matches("https://book.baylight.example/x", "baylight.example"))
        self.assertTrue(domain_matches("https://baylight.example/?utm_source=openai", "www.baylight.example"))

    def test_lookalikes_rejected(self):
        self.assertFalse(domain_matches("https://notbaylight.example/", "baylight.example"))
        self.assertFalse(domain_matches("https://baylight.example.evil.example/", "baylight.example"))
        self.assertFalse(domain_matches("", "baylight.example"))

    def test_path_prefix_for_one_listing(self):
        entry = "ota.example/tours/bay-light"
        self.assertTrue(domain_matches("https://ota.example/tours/bay-light-cruise?x=1", entry))
        self.assertFalse(domain_matches("https://ota.example/tours/other", entry))

    def test_cited_means_watched_domain_in_citations(self):
        w = Watched("Bay Light Day Cruises", ["Bay Light"], ["baylight.example"])
        cits = [{"url": "https://visitseward.example/rain", "title": "x"}]
        m = find_mentions("Bay Light runs in rain", [w], cits)[w.name]
        self.assertTrue(m.appears)
        self.assertFalse(m.cited)
        cits.append({"url": "https://baylight.example/cruise", "title": "y"})
        m = find_mentions("Bay Light runs in rain", [w], cits)[w.name]
        self.assertTrue(m.cited)
        self.assertEqual(m.cited_urls, ["https://baylight.example/cruise"])

    def test_cited_without_being_named(self):
        w = Watched("Bay Light Day Cruises", [], ["baylight.example"])
        m = find_mentions("A cruise company.", [w], [{"url": "https://baylight.example/"}])[w.name]
        self.assertFalse(m.appears)
        self.assertTrue(m.cited)

    def test_gemini_redirect_falls_back_to_title(self):
        w = Watched("Bay Light Day Cruises", [], ["baylight.example"])
        self.assertTrue(find_mentions("", [w], [{"url": RD, "title": "baylight.example"}])[w.name].cited)
        self.assertTrue(find_mentions("", [w], [{"url": RD, "title": "www.BayLight.example"}])[w.name].cited)
        # A title that is not a domain cannot be matched
        self.assertFalse(find_mentions("", [w], [{"url": RD, "title": "Bay Light Day Cruises"}])[w.name].cited)

    def test_resolved_redirect_wins_over_title(self):
        c = {"url": RD, "title": "baylight.example", "resolved_url": "https://ota.example/bay"}
        self.assertEqual(effective_url(c), "https://ota.example/bay")
        w = Watched("Bay Light Day Cruises", [], ["baylight.example"])
        self.assertFalse(find_mentions("", [w], [c])[w.name].cited)

    def test_cited_urls_show_the_resolved_address(self):
        c = {"url": RD, "title": "x", "resolved_url": "https://baylight.example/cruise"}
        w = Watched("Bay Light Day Cruises", [], ["baylight.example"])
        self.assertEqual(find_mentions("", [w], [c])[w.name].cited_urls, ["https://baylight.example/cruise"])


class LoadNames(unittest.TestCase):
    def test_aliases_domains_and_member_flag(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "names.csv"
            p.write_text("name,aliases,domains,is_member\n"
                         "Bay Light Day Cruises,Bay Light| Bay Light Cruises ,baylight.example|ota.example/x,1\n"
                         "Sample Fjord Tours,,samplefjord.example,0\n"
                         "# comment row,,,\n", encoding="utf-8")
            names = load_names(p)
        self.assertEqual([n.name for n in names], ["Bay Light Day Cruises", "Sample Fjord Tours"])
        self.assertEqual(names[0].aliases, ["Bay Light", "Bay Light Cruises"])
        self.assertEqual(names[0].domains, ["baylight.example", "ota.example/x"])
        self.assertTrue(names[0].is_member)
        self.assertFalse(names[1].is_member)

    def test_bundled_names_file_loads(self):
        names = load_names(_util.HERE / "names.csv")
        self.assertGreaterEqual(len(names), 1)


if __name__ == "__main__":
    unittest.main()
