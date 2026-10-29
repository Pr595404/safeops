from __future__ import annotations

import unittest

from safeops.__main__ import parse_tool_arguments


class CliArgTests(unittest.TestCase):
    def test_json_object(self) -> None:
        self.assertEqual(parse_tool_arguments('{"resource":"web-api-prod"}', []), {"resource": "web-api-prod"})

    def test_single_quoted_json(self) -> None:
        self.assertEqual(
            parse_tool_arguments("{'resource':'web-api-prod'}", []),
            {"resource": "web-api-prod"},
        )

    def test_set_pairs(self) -> None:
        self.assertEqual(
            parse_tool_arguments("{}", ["resource=web-api-prod"]),
            {"resource": "web-api-prod"},
        )

    def test_invalid_json_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            parse_tool_arguments("not-json", [])

    def test_non_dict_json_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            parse_tool_arguments('["not", "a", "dict"]', [])

    def test_invalid_set_pair_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            parse_tool_arguments("{}", ["no_equals_sign"])


if __name__ == "__main__":
    unittest.main()
