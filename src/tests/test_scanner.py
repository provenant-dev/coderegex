from ..scanner import ScanRule

easy = "easy: `.*test`"
not_easy = "not_easy: not `.*xyz`"
and_rule = "and_rule: `.*abc` and `.*xyz`"


def test_and():
    assert ScanRule.parse(and_rule)("this is abc; after, we have xyz.")


def test_not_easy():
    assert ScanRule.parse(not_easy)("this is a test.")


def test_easy():
    assert ScanRule.parse(easy)("this is a test.")


