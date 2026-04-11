import pytest
from launcher import detect_provider

def test_detect_provider_raw_id():
    assert detect_provider("123456") == (None, "123456")

def test_detect_provider_nhentai():
    assert detect_provider("https://nhentai.net/g/123456/") == ("nhentai", "123456")
    assert detect_provider("nhentai.net/g/123") == ("nhentai", "123")

def test_detect_provider_hitomi_reader():
    assert detect_provider("https://hitomi.la/reader/123456.html#1") == ("hitomi", "123456")

def test_detect_provider_hitomi_galleries():
    assert detect_provider("https://hitomi.la/galleries/123456.html") == ("hitomi", "123456")

def test_detect_provider_hitomi_language():
    assert detect_provider("https://hitomi.la/manga/some-manga-english-123456.html") == ("hitomi", "123456")

def test_detect_provider_pururin():
    assert detect_provider("https://pururin.me/gallery/123456/some-name") == ("pururin", "123456")

def test_detect_provider_invalid():
    assert detect_provider("invalid_string") == (None, "invalid_string")
    assert detect_provider("https://example.com/gallery/123") == (None, "https://example.com/gallery/123")
