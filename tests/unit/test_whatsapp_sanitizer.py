"""
Unit tests for Universal WhatsApp Phone Sanitizer Engine
"""

import unittest
from utils.whatsapp_sanitizer import format_whatsapp_number, build_whatsapp_link


class TestWhatsAppSanitizer(unittest.TestCase):

    def test_standard_10_digit_indian_number(self):
        self.assertEqual(format_whatsapp_number("9876543210"), "919876543210")

    def test_11_digit_with_leading_zero(self):
        self.assertEqual(format_whatsapp_number("09876543210"), "919876543210")

    def test_12_digit_with_country_code(self):
        self.assertEqual(format_whatsapp_number("919876543210"), "919876543210")

    def test_number_with_spaces_dashes_and_plus(self):
        self.assertEqual(format_whatsapp_number("+91 98765-43210"), "919876543210")

    def test_invalid_short_number(self):
        self.assertIsNone(format_whatsapp_number("12345"))

    def test_build_whatsapp_link_sanitized(self):
        link = build_whatsapp_link("9876543210", "Report Ready")
        self.assertIn("https://wa.me/919876543210?text=Report%20Ready", link)


if __name__ == "__main__":
    unittest.main()
