import unittest

from tools.CodeRunTool import CodeRunTool


class TestCodeRunTool(unittest.TestCase):
    def setUp(self):
        self.tool = CodeRunTool()

    def test_execute_valid_code(self):
        command = "print(1+1)"
        expected_output = {"output":"2\n"}
        output = self.tool.run({"command": command})
        self.assertEqual(expected_output, output)

    def test_execute_invalid_code(self):
        command = "print(1 / 0)"
        expected_output = {"output":"ZeroDivisionError('division by zero')"}
        output = self.tool.run({"command": command})
        self.assertEqual(expected_output, output)

    def test_execute_syntax_error(self):
        command = "result = 1 +"
        output = self.tool.run({"command": command})
        self.assertIn("SyntaxError", output["output"])

    def test_execute_code_with_print(self):
        command = "print('Hello, World!')"
        output = self.tool.run({"command": command})
        self.assertIn( 'Hello, World!', output["output"])


if __name__ == '__main__':
    unittest.main()
