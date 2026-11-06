"""Word statistics for plain-text reports."""


def tokenize(text):
    return [w.strip(".,!?;:").lower() for w in text.split() if w.strip(".,!?;:")]
