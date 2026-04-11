import asyncio
import os
from unittest.mock import AsyncMock, patch

from nhentai2pdf import Nhentai2PDF

async def test_download_page_sanitization():
    # Setup
    pdf_generator = Nhentai2PDF(output_dir="test_outputs", concurrency_limit=1)

    # Mocking the _fetch_image method so we don't actually download
    pdf_generator._fetch_image = AsyncMock(return_value=True)

    session = AsyncMock()
    media_id = "123456"
    page_num = 1

    # Test cases with normal and malicious extensions
    test_cases = [
        ("jpg", "0001.jpg"),
        ("../malicious", "0001.malicious"),
        ("..\\malicious", "0001.malicious"),
        ("/etc/passwd", "0001.etcpasswd"),
        ("png", "0001.png"),
        ("png?foo=bar", "0001.pngfoobar")
    ]

    temp_path = "temp_test"
    os.makedirs(temp_path, exist_ok=True)

    try:
        for ext, expected_filename in test_cases:
            await pdf_generator.download_page(session, media_id, page_num, ext, temp_path)

            # Get the arguments passed to _fetch_image
            pdf_generator._fetch_image.assert_called()
            call_args = pdf_generator._fetch_image.call_args[0]

            file_path = call_args[2]

            expected_path = os.path.join(temp_path, expected_filename)
            assert file_path == expected_path, f"Path Traversal detected! Expected: {expected_path}, Got: {file_path}"
            print(f"PASS: {ext} -> {os.path.basename(file_path)}")

            # Reset mock for next iteration
            pdf_generator._fetch_image.reset_mock()

        print("All sanitization tests passed successfully!")

    finally:
        # Cleanup
        if os.path.exists(temp_path):
            os.rmdir(temp_path)
        if os.path.exists("test_outputs"):
            os.rmdir("test_outputs")

if __name__ == "__main__":
    asyncio.run(test_download_page_sanitization())
