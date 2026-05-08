import unittest

from beverage_news.extraction import extract_title_summary_body
from beverage_news.filtering import filter_candidates, match_companies, match_keyword_categories
from beverage_news.models import Candidate, Company
from beverage_news.text import normalize_text, term_in_text
from beverage_news.urls import normalize_url


class CoreTest(unittest.TestCase):
    def setUp(self):
        self.companies = [
            Company(
                name="The Coca-Cola Company",
                country="United States",
                segments=["soft_drinks", "water"],
                aliases=["Coca-Cola", "Coke", "Sprite"],
            ),
            Company(
                name="Heineken",
                country="Netherlands",
                segments=["beer"],
                aliases=["Heineken NV", "Amstel"],
            ),
        ]
        self.keywords = {
            "beer": ["beer", "brewer", "cerveza"],
            "soft_drinks": ["soft drinks", "soda", "gaseosas"],
            "packaging_regulation": ["sugar tax", "deposit return", "regulation"],
        }

    def test_normalize_url_removes_tracking_and_fragment(self):
        url = normalize_url("https://example.com/news/", "/article?utm_source=x&id=7#comments")
        self.assertEqual(url, "https://example.com/article?id=7")

    def test_term_matching_is_word_based_and_accent_insensitive(self):
        self.assertTrue(term_in_text("cerveza", "La cervecera lanzo una cerveza sin alcohol"))
        self.assertTrue(term_in_text("sugar tax", "New Sugar Tax rules hit soft drinks"))
        self.assertFalse(term_in_text("rum", "rumors about unrelated markets"))

    def test_match_companies_uses_aliases(self):
        matches = match_companies("Sprite sales rose in Mexico", self.companies)
        self.assertEqual([company.name for company in matches], ["The Coca-Cola Company"])

    def test_match_keywords_multilanguage(self):
        matches = match_keyword_categories("Nueva regulation para cerveza y sugar tax", self.keywords)
        self.assertEqual(sorted(matches), ["beer", "packaging_regulation"])

    def test_filter_accepts_company_match_and_deduplicates(self):
        candidates = [
            Candidate(title="Coca-Cola FEMSA invests in bottling", url="https://example.com/a?utm_campaign=x"),
            Candidate(title="Coca-Cola FEMSA invests in bottling", url="https://example.com/a"),
        ]
        accepted, diagnostics = filter_candidates(candidates, self.companies, self.keywords)
        self.assertEqual(len(accepted), 1)
        self.assertEqual(diagnostics["duplicates"], 1)
        self.assertEqual(accepted[0]["reason"], "company_match")

    def test_filter_accepts_two_sector_keywords_without_company(self):
        candidates = [
            Candidate(title="Sugar tax regulation targets soft drinks", url="https://example.com/tax"),
        ]
        accepted, _diagnostics = filter_candidates(candidates, self.companies, self.keywords)
        self.assertEqual(len(accepted), 1)
        self.assertEqual(accepted[0]["reason"], "strong_keyword_match")

    def test_filter_rejects_weak_generic_article(self):
        candidates = [Candidate(title="Retail market opens higher", url="https://example.com/market")]
        accepted, diagnostics = filter_candidates(candidates, self.companies, self.keywords)
        self.assertEqual(accepted, [])
        self.assertEqual(diagnostics["discarded"]["weak_match"], 1)

    def test_extracts_json_ld_article_body_summary_and_title(self):
        html = """
        <html><head>
            <script type="application/ld+json">
            {
              "@type": "NewsArticle",
              "headline": "Brewer reports higher sales",
              "description": "The company posted stronger beer revenue.",
              "datePublished": "2026-05-07T10:00:00Z",
              "articleBody": "The brewer said demand improved across several markets. The article body includes enough detail for extraction and continues with operational context, pricing and volume data."
            }
            </script>
        </head><body></body></html>
        """
        extracted = extract_title_summary_body(html)
        self.assertEqual(extracted["title"], "Brewer reports higher sales")
        self.assertEqual(extracted["summary"], "The company posted stronger beer revenue.")
        self.assertIn("demand improved", extracted["body"])
        self.assertEqual(extracted["published"], "2026-05-07T10:00:00Z")

    def test_extracts_meta_summary_and_article_paragraphs(self):
        html = """
        <html>
            <head>
                <meta property="og:title" content="Soft drinks group faces new rules">
                <meta name="description" content="Regulators are reviewing labels and packaging.">
            </head>
            <body>
                <nav>Menu item</nav>
                <article>
                    <p>Short.</p>
                    <p>The soft drinks company said it would adapt its packaging strategy after regulators introduced new requirements for labels and deposit return systems.</p>
                    <p>Executives added that the changes may affect bottlers, retailers and logistics partners during the next financial year.</p>
                </article>
            </body>
        </html>
        """
        extracted = extract_title_summary_body(html)
        self.assertEqual(extracted["title"], "Soft drinks group faces new rules")
        self.assertEqual(extracted["summary"], "Regulators are reviewing labels and packaging.")
        self.assertIn("packaging strategy", extracted["body"])
        self.assertNotIn("Short.", extracted["body"])

    def test_normalize_text_removes_punctuation_and_accents(self):
        self.assertEqual(normalize_text("Bebidas energéticas: regulación"), "bebidas energeticas regulacion")

    def test_extract_ignores_common_subscription_boilerplate(self):
        html = """
        <article>
            <p>The brewer said demand improved across several markets and that the new packaging plan would support growth in premium channels.</p>
            <p>Stay ahead with unbiased news, expert commentary, and in-depth features on global topics.</p>
            <p>Executives added that new capacity would be used for beer and soft drinks production in the next financial year.</p>
        </article>
        """
        extracted = extract_title_summary_body(html)
        self.assertIn("demand improved", extracted["body"])
        self.assertIn("new capacity", extracted["body"])
        self.assertNotIn("Stay ahead", extracted["body"])


if __name__ == "__main__":
    unittest.main()
