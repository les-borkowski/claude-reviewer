from wordstats import tokenize


def test_tokenize_strips_punctuation():
    assert tokenize("Hello, world!") == ["hello", "world"]
