# From http://groups.google.com/group/comp.lang.python/msg/ce3fc3330cbbac0a
# "How do you htmlentities in Python", 6/6/2007 by John J. Lee

import htmlentitydefs
import re
import unittest

def unescape_charref(ref):
    name = ref[2:-1]
    base = 10
    if name.startswith("x"):
        name = name[1:]
        base = 16
    return unichr(int(name, base))

def replace_entities(match):
    ent = match.group()
    if ent[1] == "#":
        return unescape_charref(ent)

    repl = htmlentitydefs.name2codepoint.get(ent[1:-1])
    if repl is not None:
        repl = unichr(repl)
    else:
        repl = ent
    return repl

def unescape(data):
    return re.sub(r"&#?[A-Za-z0-9]+?;", replace_entities, data) 

class UnescapeTests(unittest.TestCase):

    def test_unescape_charref(self):
        self.assertEqual(unescape_charref(u"&#38;"), u"&")
        self.assertEqual(unescape_charref(u"&#x2014;"), u"\N{EM DASH}")
        self.assertEqual(unescape_charref(u"&#8212;"), u"\N{EM DASH}")

    def test_unescape(self):
        self.assertEqual(
            unescape(u"&amp; &lt; &mdash; &#8212; &#x2014;"),
            u"& < %s %s %s" % tuple(u"\N{EM DASH}"*3)
            )
        self.assertEqual(unescape(u"&a&amp;"), u"&a&")
        self.assertEqual(unescape(u"a&amp;"), u"a&")
        self.assertEqual(unescape(u"&nonexistent;"), u"&nonexistent;")
