from ..scanner import ScanRule

easy = "easy: `test`"
not_easy = "not_easy: not `xyz`"
and_rule = "and_rule: `abc` and `xyz`"
or_rule = "or_rule: `abc` or `xyz`"
trivial_group = "tg: (`test`)"


def test_trivial_group():
    assert ScanRule.parse(trivial_group)("this is a test.")
    assert not ScanRule.parse(trivial_group)("this is something else.")


def test_or():
    r = ScanRule.parse(or_rule)
    assert r("this is abc; after, we have xyz.")
    assert r("this is abc; after, we have wxy.")
    assert r("this is abd; after, we have xyz.")
    assert not r("this is abd; after, we have wxy.")


def test_and():
    r = ScanRule.parse(and_rule)
    assert r("this is abc; after, we have xyz.")
    assert not r("this is abc; after, we have wxy.")


def test_not_easy():
    r = ScanRule.parse(not_easy)
    assert r("this is a test.")
    assert not r("this is xyz a test.")


def test_easy():
    r = ScanRule.parse(easy)
    assert r("this is a test.")
    assert not r("this is a pickle.")


