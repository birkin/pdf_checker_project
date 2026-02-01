from bs4 import BeautifulSoup
from django.test import SimpleTestCase as TestCase

from pdf_checker_app.management.commands import update_pattern_header


class PatternHeaderSplitTest(TestCase):
    """
    Checks split_pattern_header parsing.
    """

    def test_split_pattern_header_extracts_link_tag(self) -> None:
        """
        Checks split_pattern_header() extracts the bul_patterns.css link tag.
        """
        link_tag = '<link rel="stylesheet" href="https://dlibwwwcit.services.brown.edu/common/css/bul_patterns.css" />'
        content = '\n'.join(
            [
                '<!-- begin bul_pl_header -->',
                link_tag,
                '<div id="bul_pl_header_begin">',
                'header content',
                '</div>',
            ]
        )

        head_content, body_content = update_pattern_header.split_pattern_header(content)

        head_soup = BeautifulSoup(head_content, 'html.parser')
        parsed_link = head_soup.find('link')
        self.assertIsNotNone(parsed_link)
        self.assertEqual(
            parsed_link.get('href'),
            'https://dlibwwwcit.services.brown.edu/common/css/bul_patterns.css',
        )
        self.assertEqual(parsed_link.get('rel'), ['stylesheet'])
        self.assertNotIn('bul_patterns.css', body_content)
        self.assertIn('header content', body_content)
