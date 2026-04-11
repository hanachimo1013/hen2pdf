import pytest
from unittest.mock import MagicMock
from nhentai2pdf import Nhentai2PDF

@pytest.fixture
def nhentai():
    # Use a dummy output directory so it doesn't pollute
    # Note: we should patch cloudscraper to avoid making it actually download things
    # but the constructor creates a scraper. We'll let it create it then mock its `get`
    return Nhentai2PDF(output_dir="test_outputs", concurrency_limit=1)

def test_fetch_metadata_success(nhentai):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "title": {
            "pretty": "Pretty Title",
            "english": "English Title",
            "japanese": "Japanese Title"
        },
        "media_id": "123456",
        "num_pages": 3,
        "tags": [
            {"type": "tag", "name": "big breasts"},
            {"type": "artist", "name": "shindol"},
            {"type": "language", "name": "english"}
        ],
        "pages": [
            {"path": "1.jpg"},
            {"path": "2.png"},
            {"t": "w"}  # missing path, using 't' -> webp
        ]
    }

    nhentai.scraper.get = MagicMock(return_value=mock_resp)

    result = nhentai.fetch_metadata("123")

    nhentai.scraper.get.assert_called_once_with("https://nhentai.net/api/v2/galleries/123")

    assert result["title"] == "Pretty Title"
    assert result["safe_title"] == "Pretty_Title"
    assert result["media_id"] == "123456"
    assert result["total_pages"] == 3
    assert result["artist"] == "shindol"
    assert result["tags"] == ["big breasts"]
    assert result["language"] == "English"
    assert result["pages_ext"] == ["jpg", "png", "webp"]

def test_fetch_metadata_success_fallback_title_and_images(nhentai):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "title": {
            # missing pretty
            "english": "Fallback English Title",
            "japanese": "Japanese Title"
        },
        "media_id": "7890",
        "num_pages": 1,
        "tags": [
            {"type": "language", "name": "translated"}  # shouldn't affect language if 'translated'
        ],
        "images": {
            "pages": [
                {"path": "foo/bar.gif"}
            ]
        }
    }

    nhentai.scraper.get = MagicMock(return_value=mock_resp)
    result = nhentai.fetch_metadata("456")

    assert result["title"] == "Fallback English Title"
    assert result["artist"] == "Unknown"
    assert result["language"] == "Unknown"
    assert result["pages_ext"] == ["gif"]

def test_fetch_metadata_403(nhentai):
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    nhentai.scraper.get = MagicMock(return_value=mock_resp)

    with pytest.raises(Exception, match=r"Access Denied \(Cloudflare\)"):
        nhentai.fetch_metadata("123")

def test_fetch_metadata_404(nhentai):
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    nhentai.scraper.get = MagicMock(return_value=mock_resp)

    with pytest.raises(Exception, match=r"Gallery 123 not found"):
        nhentai.fetch_metadata("123")

def test_fetch_metadata_other_error(nhentai):
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    nhentai.scraper.get = MagicMock(return_value=mock_resp)

    with pytest.raises(Exception, match=r"HTTP 500: Error fetching metadata"):
        nhentai.fetch_metadata("123")

def test_fetch_metadata_invalid_json(nhentai):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.side_effect = ValueError("Invalid JSON")
    nhentai.scraper.get = MagicMock(return_value=mock_resp)

    with pytest.raises(Exception, match=r"Failed to parse API response"):
        nhentai.fetch_metadata("123")

def test_fetch_metadata_empty_pages_error(nhentai):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "num_pages": 5,
        "pages": [],
        "images": {"pages": []}
    }
    nhentai.scraper.get = MagicMock(return_value=mock_resp)

    with pytest.raises(Exception, match=r"Gallery found but could not fetch image list"):
        nhentai.fetch_metadata("123")
