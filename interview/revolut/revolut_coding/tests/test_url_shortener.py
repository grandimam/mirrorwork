# Written by Bohdan Shtepan <bohdan@shtepan.com>, February 2025

import pytest
from lib.url_shortener import URLShortener, CounterStrategy, RandomStrategy, MD5Strategy, Base64Strategy

test_urls = [
    "https://example.com",
    "https://test.com/page1",
    "https://another-example.org/about"
]

def test_counter_strategy_uniqueness():
    shortener = URLShortener(CounterStrategy())
    short_urls = {shortener.shorten(url) for url in test_urls}

    assert len(short_urls) == len(test_urls)

def test_md5_strategy_uniqueness():
    shortener = URLShortener(MD5Strategy())
    short_urls = {shortener.shorten(url) for url in test_urls}

    assert  len(short_urls) == len(test_urls)

def test_random_strategy_collision():
    shortener = URLShortener(RandomStrategy())
    short_urls = [shortener.shorten("https://collision-test.com") for _ in range(1000)]

    assert 1 == len(set(short_urls))

def test_base64_strategy_valid_length():
    shortener = URLShortener(Base64Strategy())
    short_urls = [shortener.shorten(url) for url in test_urls]

    for short_url in short_urls:
        assert 1 <= len(short_url) <= 8

def test_unshorten_correctness():
    shortener = URLShortener(CounterStrategy())
    mapping = {url: shortener.shorten(url) for url in test_urls}

    for url, short in mapping.items():
        assert shortener.unshorten(short) == url

def test_invalid_url_handling():
    shortener = URLShortener(CounterStrategy())

    with pytest.raises(ValueError):
        shortener.shorten("invalid-url")
