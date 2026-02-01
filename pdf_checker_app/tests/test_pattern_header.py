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

        self.assertEqual(head_content, f'{link_tag}\n')
        self.assertNotIn(link_tag, body_content)
        self.assertIn('header content', body_content)
