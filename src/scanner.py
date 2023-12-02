import re


class TargetRule:
    def __init__(self, regex):
        self.regex = regex

    def __call__(self, path):
        return self.regex.match(path)


class ScanRule:
    """
    The goal of a ScanRule is to look at content and decide whether it is interesting.
    If yes, we say that the ScanRule "matches" the content. The text within the content
    that triggered the match is called the "evidence" (that the match is interesting).

    The __call__ method on this class allows a rule to be treated like a function. When
    called on content, a rule returns a regex Match object that identifies the
    subset of the content that justifies interest, or None if it doesn't match.

    ScanRules have a formal syntax. They are defined as a single line of text which consists
    of a name (alphanumerics or _-. characters) followed a colon, followed by an
    expression. Whitespace is trimmed and ignored on either side of the colon:

        NAME: EXPRESSION

    The static ScanRule.parse() method constructs a ScanRule object from one of these lines; a
    file with rule definitions and invocations is easy to use to build a family of related rules
    and then run them.

    The nature of EXPRESSION determines how the rule decides whether text is interesting. There
    are three possible syntax variants.

    1. simple regex

        If EXPRESSION is a simple regex, then it is a string enclosed in backticks, and the string
        inside the backticks obeys python regex syntax. (If the regex needs to reference a backtick,
        it writes it as \\u0060. This makes parsing easy for us, since we don't have to support
        an escaped backtick.)

        For example:

           `[Gg]et[Mm]apping`

        ...is a rule that considers text interesting if it contains the string GetMapping
        or variations that capitalize differently. (Another way to write this rule would be
        to make the regex case-insensitive by embedding a flag: `(?i)getmapping`.)

        If regular expressions contain capture groups, then it becomes possible to distinguish between
        the text that was matched and the text that is "evidence": the value of group 1 is considered
        the evidence. Otherwise the full matched text is considered the evidence.

    2. boolean expression

        If EXPRESSION is built by using the AND, OR, and NOT operators, plus optional
        parentheses, to combine and group other expressions together, then it matches according
        to boolean logic against regular expressions. Operators are case-sensitive. For example:

           `public override` AND NOT (`pickle` OR `serialize`)

        ...is a rule that considers text interesting if it contains the first phrase and neither
        of the second pair of words.

    3. IN expression

        If EXPRESSION uses the IN or NOT IN operator, then it tests whether interesting text from
        the regex that's on the left side of the operator appears (or does not appear) inside evidence
        of interesting text matched by the operand on the right. The operand on the right can
        be an expression, but it can also be the name of a rule that's already defined.

        Typically, this kind of rule is used to identify a chunk of text that might be interesting
        (the operand on the right, which contains evidence), and then to use a more refined rule
        (the operand on the left) to either match or exclude it. For example:

            `public` IN `^\s*class\s+[a-zA-Z0-9]+.*\{([^}\n]{1,8})`

        ...first searches for the right operand -- a class declaration (possibly interesting) with
        a capture group around the text that immediately follows the open curly brace. Up to 8 lines
        of text are selected, but less if the content ends or a close curly brace is found. This text
        is the evidence which is then searched by the left operand, which wants to find the key word
        "public".

        We could also write this same rule as:

            `public` IN first-few-lines-of-class-body

        ...if we had previously defined a rule of that name:

            first-few-lines-of-class-body `^\s*class\s+[a-zA-Z0-9]+.*\{([^}\n]{1,8})`
    """

    ALL = {}
    BINARY_OPERATORS = ['AND', 'OR']
    UNARY_OPERATORS = ['NOT', 'FROM']
    OPERATORS = BINARY_OPERATORS + UNARY_OPERATORS
    NAME_EXPR_PAT = re.compile(r'\s*([-_.a-z0-9]+)\s*:\s*(.+)', re.I)
    OPERATOR_PAT = re.compile('(' + '|'.join(OPERATORS) + r')\W', re.I)

    @staticmethod
    def parse(definition):

        def _lex(txt):
            i = 0
            j = len(txt)
            while True:
                # skip current whitespace
                while i < j and txt[i].isspace():
                    i += 1
                # if we have anything left...
                if i >= j:
                    return
                if txt[i] == '`':
                    end = txt.find('`', i + 1)
                    if end > -1:
                        yield txt[i:end + 1]
                        i = end + 1
                    else:
                        raise ValueError(f'The backtick expression that started at offset {i} was not terminated.')
                elif txt[i] in '()':
                    yield txt[i]
                    i += 1
                else:
                    m = ScanRule.OPERATOR_PAT.match(txt, i)
                    if m:
                        yield m.group(1).upper()
                        i = m.end()
                    else:
                        raise ValueError(f"At offset {i}, expected boolean operator but did not see one.")

        def _parse(expr, nest=0):
            stack = []
            rule = ScanRule()
            stack.append(rule)
            for token in _lex(expr):
                if token in ScanRule.OPERATORS:
                    rule.set_operator(token)
                elif token.startswith('`'):
                    rule.set_next_operand(re.compile(token[1:-1]))
                elif token == '(':
                    if rule.right or rule.needs_operator:
                        raise ValueError("Group must be preceded by an operator.")
                    rule = ScanRule()
                    stack.append(rule)
                elif token == ')':
                    child = stack.pop()
                    rule = stack[-1]
                    if not rule.left:
                        # This condition is caused by unnecessary parens. Remove any rule
                        # that does nothing but hold a child.
                        stack.pop()
                        stack.append(child)
                        rule = child
                    else:
                        rule.set_next_operand(child)
            if len(stack) > 1:
                raise ValueError("Unclosed group.")
            if rule.needs_operator:
                assert isinstance(rule.left, re.Pattern)
            return rule

        m = ScanRule.NAME_EXPR_PAT.match(definition.strip())
        if m:
            result = _parse(m.group(2))
            ScanRule.ALL[m.group(1).lower()] = result
            return result
        else:
            raise ValueError("The rule didn't consist of a name followed by an expression.")

    def __init__(self):
        self.left = None
        self.operator = None
        self.right = None

    def set_next_operand(self, operand):
        if self.operator:
            if not self.right:
                self.right = operand
            else:
                raise ValueError(f"Extra operand, {operand}, in expression.")
        else:
            self.left = operand

    def set_operator(self, operator):
        if self.operator:
            raise ValueError(f"Extra operator, {operator}, in expression.")
        if not self.left and operator in ScanRule.BINARY_OPERATORS:
            raise ValueError(f"Can't have {operator} before left operand.")
        self.operator = operator

    @property
    def needs_operator(self):
        return self.left and self.operator

    def __str__(self):
        def format(operand):
            return f"({operand})" if isinstance(operand, ScanRule) else f"`{operand.pattern}`"

        l = format(self.left) + ' ' if self.left else ''
        r = format(self.right)
        return f"{l}{self.operator} {r}"

    def __call__(self, content):
        def call_or_match(regex_or_rule, content):
            return regex_or_rule.search(content) if isinstance(regex_or_rule, re.Pattern) else regex_or_rule(content)

        o = self.operator
        if o is None or o == 'AND' or o == 'OR':
            l = call_or_match(self.left, content)
        if o is None:
            return l
        if o == 'OR':
            if l:
                return l
        r = call_or_match(self.right, content)
        if o == 'NOT':
            return not r
        elif o == 'FROM':
            if r:
                g = r.groups()
                return g[1] if len(g) > 1 else g[0]
        else:
            return r