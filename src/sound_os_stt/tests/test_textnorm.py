from textnorm import normalize


def test_alef_and_punctuation():
    assert normalize("إفتح المتصفح،") == "افتح المتصفح"


def test_english_lowercase_and_punct():
    assert normalize("Open the browser.") == "open the browser"


def test_diacritics_and_arabic_digits():
    assert normalize("وطّي الصوت ٥٠") == "وطي الصوت 50"


def test_ya_and_ta_marbuta():
    assert normalize("الحاسبة") == normalize("الحاسبه")
    assert normalize("على") == normalize("علي")


def test_empty_and_none():
    assert normalize("") == ""
    assert normalize(None) == ""


def test_normalization_does_not_fix_missing_letters():
    # documented limitation: this is the parser's fuzzy-matching job
    assert normalize("افتح المتصف") != normalize("افتح المتصفح")
