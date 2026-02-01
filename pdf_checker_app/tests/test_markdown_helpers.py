from django.test import SimpleTestCase as TestCase

from pdf_checker_app.lib import markdown_helpers


class MarkdownHelpersTest(TestCase):
    """
    Checks markdown helper behavior.
    """

    def test_render_markdown_text_outputs_html(self) -> None:
        """
        Checks render_markdown_text() returns HTML output.
        """
        html = markdown_helpers.render_markdown_text('# Title')
        self.assertIn('<h1', html)
        self.assertIn('Title', html)

    def test_load_markdown_from_lib_reads_info_file(self) -> None:
        """
        Checks load_markdown_from_lib() reads and renders the info.md file.
        """
        html = markdown_helpers.load_markdown_from_lib('info.md')
        self.assertIn('About the PDF Accessibility Checker', html)
        self.assertIn('Something here.', html)
