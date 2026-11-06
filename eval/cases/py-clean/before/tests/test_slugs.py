from slugs import slugify


def test_slugify():
    assert slugify("Hello, World!") == "hello-world"
