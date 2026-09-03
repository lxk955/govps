from unittest.mock import patch
import httpx
from app.services.indexnow import submit_to_indexnow


def test_submit_to_indexnow_success():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://api.indexnow.org/indexnow"
        data = httpx.Response(200, json={"message": "ok"})
        return data

    with patch("httpx.Client") as mock_client:
        mock_client.return_value.__enter__.return_value.post.return_value = httpx.Response(200)
        res = submit_to_indexnow(["https://govps.xyz/vps/1-test"])
        assert res["ok"] is True
        assert res["submitted"] == 1


def test_submit_to_indexnow_empty():
    res = submit_to_indexnow([])
    assert res["ok"] is True
    assert res["submitted"] == 0
