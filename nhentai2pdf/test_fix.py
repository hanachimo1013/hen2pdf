import os
import unittest
from unittest.mock import patch, MagicMock
from nhentai2pdf import Nhentai2PDF
import asyncio

class TestSanitizeFix(unittest.TestCase):
    def test_sanitize_artist(self):
        pdf_maker = Nhentai2PDF()

        # Original artist string that might have caused a path traversal
        malicious_artist = "../../../etc/passwd"

        # Test just the sanitize function
        sanitized = pdf_maker._sanitize(malicious_artist)

        # Check that it doesn't contain traversal characters like / or \
        self.assertNotIn("/", sanitized)
        self.assertNotIn("\\", sanitized)

        # Ensure final sanitized string matches expectation
        self.assertEqual(sanitized, "......etcpasswd")

        # Test full filename generation directly logic (simulating the buggy line vs fixed line)
        code = "123456"
        data = {
            'artist': malicious_artist,
            'safe_title': 'Test_Title'
        }

        # Expected fix filename
        fixed_final_filename = os.path.join(pdf_maker.output_dir, f"{code}_[{pdf_maker._sanitize(data['artist'])}]_{data['safe_title']}.pdf")

        self.assertTrue("......etcpasswd" in fixed_final_filename)
        self.assertFalse("../../../" in fixed_final_filename)

if __name__ == '__main__':
    unittest.main()
