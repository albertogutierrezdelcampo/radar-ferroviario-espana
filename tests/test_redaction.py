from radar.redaction import REDACTED, sanitize_data, sanitize_text, sanitize_url

SIGNED = (
    "https://bucket.s3.eu-west-1.amazonaws.com/feed.zip?"
    "X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=AKIA/20261110/eu-west-1/s3/aws4_request&"
    "X-Amz-Date=20261110T110424Z&X-Amz-Expires=900&X-Amz-Signature=abcdef&visible=yes"
)


def test_signed_url_query_values_are_redacted_but_path_and_safe_query_remain():
    safe = sanitize_url(SIGNED)
    assert safe.startswith("https://bucket.s3.eu-west-1.amazonaws.com/feed.zip?")
    assert "abcdef" not in safe and "AKIA" not in safe and "20261110T110424Z" not in safe
    assert "X-Amz-Signature=%5BREDACTED%5D" in safe
    assert "visible=yes" in safe


def test_userinfo_fragment_and_common_sas_values_are_removed():
    safe = sanitize_url("https://user:pass@example.com/a.zip?sv=1&sig=SECRET&file=ok#fragment")
    assert "user" not in safe and "pass" not in safe and "fragment" not in safe
    assert "SECRET" not in safe and "file=ok" in safe


def test_recursive_diagnostic_redaction_preserves_shape():
    data = sanitize_data({
        "token": "top-secret",
        "attempts": [{"source": SIGNED, "http_status": 200}],
        "message": "ApiKey=abc Authorization:Bearer123",
    })
    assert data["token"] == REDACTED
    assert data["attempts"][0]["http_status"] == 200
    serialized = repr(data)
    assert "top-secret" not in serialized and "abcdef" not in serialized and "Bearer123" not in serialized


def test_arbitrary_text_sanitizes_embedded_url_and_assignments():
    text = sanitize_text(f"download failed {SIGNED} token=abc")
    assert "abcdef" not in text and "AKIA" not in text and "token=[REDACTED]" in text
