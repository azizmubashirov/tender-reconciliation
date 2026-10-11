from app.pipeline.quotes import locate

PAGES = [
    "General provisions of the tender.",
    "Warranty period shall be not less than 36 months from the date of delivery.",
    "The bidder must hold an ISO 9001 certificate.",
]


def test_quote_found_on_another_page() -> None:
    assert locate("Warranty period shall be not less than 36 months", PAGES, 3) == (2, True)


def test_quote_tolerates_whitespace_and_case() -> None:
    assert locate("the BIDDER must  hold an iso 9001\ncertificate", PAGES, None) == (3, True)


def test_invented_quote_is_not_verified() -> None:
    assert locate("Delivery within 10 days", PAGES, 2) == (2, False)


def test_scan_without_text_keeps_model_page() -> None:
    assert locate("anything", ["", ""], 2) == (2, False)
