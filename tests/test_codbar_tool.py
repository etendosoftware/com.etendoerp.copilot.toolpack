import unittest

from tools.CodbarTool import CodbarTool


class TestCodbarTool(unittest.TestCase):
    def setUp(self):
        self.tool = CodbarTool()

    def test_decode_single_barcode(self):
        input_params = {"filepath": ["./resources/images/barcode1.png"]}
        result = self.tool.run(input_params)
        expected_output = {
            "message": ["123456789012"]
        }  # Replace with the actual barcode value
        self.assertEqual(result, expected_output)

    def test_decode_multiple_barcodes(self):
        input_params = {
            "filepath": [
                "./resources/images/barcode1.png",
                "./resources/images/barcode2.png",
            ]
        }
        result = self.tool.run(input_params)
        expected_output = {
            "message": ["123456789012", "987654321098"]
        }  # Replace with the actual barcode values
        self.assertEqual(result, expected_output)

    def test_decode_no_barcodes(self):
        input_params = {"filepath": ["./resources/images/no_barcode.png"]}
        result = self.tool.run(input_params)
        expected_output = {"message": []}
        self.assertEqual(result, expected_output)


if __name__ == "__main__":
    unittest.main()
