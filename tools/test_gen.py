"""Unit tests for gen_dark.py. Usage: python3 tools/test_gen.py"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src", "package", "bin"))
import gen_dark  # noqa: E402


def run(css):
    out = []
    gen_dark.convert(gen_dark.strip_comments(css), out)
    return "".join(out)


def lightness(hex_color):
    return gen_dark.hls(gen_dark.parse_color(hex_color))[1]


class Convert(unittest.TestCase):
    def test_white_background_becomes_dark(self):
        out = run(".panel{background-color:#fff}")
        self.assertIn("html .panel", out)
        col = out.split("background-color: ")[1].split(" ")[0]
        self.assertLess(lightness(col), 0.2)

    def test_dark_text_becomes_light(self):
        out = run(".title{color:#414b55}")
        col = out.split("color: ")[1].split(" ")[0]
        self.assertGreater(lightness(col), 0.7)

    def test_light_text_and_dark_background_kept(self):
        out = run(".tip{color:#fff;background:#222}")
        self.assertIn("color: #fff !important", out)
        self.assertIn("background-color: #222 !important", out)

    def test_brand_button_keeps_colour_and_still_wins(self):
        # Emitted unchanged so the boosted .btn rule can't override it.
        out = run(".btn{background:#eef1f3} .btn-blue{background-color:#057feb;color:#fff}")
        self.assertIn("html .btn-blue {\n  background-color: #057feb !important;\n  color: #fff !important;", out)

    def test_shorthand_keeps_sprite(self):
        out = run(".icon{background:#fff url(a.png) no-repeat 0 -32px}")
        self.assertIn("background-color:", out)
        self.assertNotIn("url(", out)
        self.assertNotIn("no-repeat", out)

    def test_border_shorthand_maps_to_side_colour(self):
        out = run(".row{border-bottom:1px solid #e5e5e5}")
        self.assertIn("border-bottom-color:", out)
        self.assertNotIn("solid", out)

    def test_gradient_recoloured(self):
        out = run(".bar{background-image:linear-gradient(#fff,#f0f0f0)}")
        self.assertIn("linear-gradient(", out)
        self.assertNotIn("#fff,", out)

    def test_media_queries_kept_keyframes_dropped(self):
        out = run("@media (max-width:800px){.a{color:#000}} @keyframes k{from{color:#000}to{color:#111}}")
        self.assertIn("@media (max-width:800px)", out)
        self.assertNotIn("from", out)

    def test_selector_list_and_root(self):
        out = run("body, .a:hover, html .b{background:#fafafa}")
        self.assertIn("html body, html .a:hover, html .b", out)

    def test_custom_properties(self):
        out = run(":root{--syno-bg-color:#ffffff;--text-color:#333;--radius:4px}")
        self.assertIn("--syno-bg-color", out)
        self.assertIn("--text-color", out)
        self.assertNotIn("--radius", out)

    def test_keywords_and_vars_passed_through(self):
        out = run(".a{color:var(--x);background:none;border-color:transparent}")
        self.assertIn("color: var(--x) !important", out)
        self.assertIn("background-color: transparent !important", out)
        self.assertIn("border-color: transparent !important", out)

    def test_layout_only_rules_dropped(self):
        self.assertEqual(run(".a{width:10px;background:url(a.png) 0 0}"), "")

    def test_rgba_and_hsl(self):
        out = run(".a{background-color:rgba(255,255,255,.8)} .b{color:hsl(0,0%,20%)}")
        self.assertIn("rgba(", out)
        self.assertIn("html .b", out)

    def test_important_and_strings(self):
        out = run('.a{content:"}";color:#000 !important}')
        self.assertIn("html .a", out)
        self.assertEqual(out.count("!important"), 1)


if __name__ == "__main__":
    unittest.main()
