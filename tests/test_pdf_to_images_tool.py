import unittest
from pathlib import Path
from tools.PdfToImagesTool import PdfToImagesTool

class TestPdfToImagesTool(unittest.TestCase):
    def setUp(self):
        self.tool = PdfToImagesTool()

    def test_convert_pdf_to_images(self):
        # Create a sample PDF file for testing
        from fpdf import FPDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, txt="Sample PDF Page 1", ln=True, align='C')
        pdf.add_page()
        pdf.cell(200, 10, txt="Sample PDF Page 2", ln=True, align='C')
        test_pdf_path = "/tmp/sample_test.pdf"
        pdf.output(test_pdf_path)

        # Run the tool
        input_params = {"path": test_pdf_path}
        images = self.tool.run(input_params)

        # Check if the output is a list of images
        self.assertIsInstance(images, list)
        self.assertEqual(len(images), 2)
        for img in images:
            self.assertTrue(hasattr(img, 'save'))  # PIL Image objects have a 'save' method

        # Clean up
        Path(test_pdf_path).unlink()

if __name__ == '__main__':
    unittest.main()
