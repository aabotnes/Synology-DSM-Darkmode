"""Unit tests for gen_dark.py. Usage: python3 tools/test_gen.py"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src", "package", "bin"))
import gen_dark  # noqa: E402


def run(css, base="/webman/app"):
    out = []
    gen_dark.convert(gen_dark.strip_comments(css), out, base)
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

    def test_vars_resolved_to_real_colours(self):
        gen_dark.VARS.clear()
        css = ":root{--white:#fff;--ink:var(--dark);--dark:#414b55} .search{background-color:var(--white);color:var(--ink)} .x{color:var(--unknown, #000)} .y{color:var(--nope)}"
        gen_dark.collect_vars(css)
        out = run(css)
        gen_dark.VARS.clear()
        search = out.split("html .search {")[1].split("}")[0]
        self.assertLess(lightness(search.split("background-color: ")[1].split(" ")[0]), 0.2)
        self.assertGreater(lightness(search.split("color: ")[2].split(" ")[0]), 0.7)
        x = out.split("html .x {")[1].split("}")[0]
        self.assertGreater(lightness(x.split("color: ")[1].split(" ")[0]), 0.7)
        self.assertIn("color: var(--nope) !important", out)

    def test_grey_buttons_go_dark(self):
        for grey in ("#8a949e", "#b6c0c9", "#4a5056", "#6b7277"):
            out = run(".btn{background-color:%s}" % grey)
            col = out.split("background-color: ")[1].split(" ")[0]
            self.assertLess(lightness(col), 0.22, grey)

    def test_light_text_and_dark_background_kept(self):
        out = run(".tip{color:#fff;background:#222}")
        self.assertIn("color: #fff !important", out)
        self.assertIn("background-color: #222 !important", out)

    def test_brand_button_keeps_colour_and_still_wins(self):
        # Emitted unchanged so the boosted .btn rule can't override it.
        out = run(".btn{background:#eef1f3} .btn-blue{background-color:#057feb;color:#fff}")
        self.assertIn("html .btn-blue {\n  background-color: #057feb !important;\n  color: #fff !important;", out)

    def test_web_dir(self):
        self.assertEqual(gen_dark.web_dir("/usr/syno/synoman/webman/modules/Pkg/style.css"), "/webman/modules/Pkg")
        self.assertEqual(gen_dark.web_dir("/var/packages/Foo/target/ui/css/a.css"), "/webman/3rdparty/Foo/css")
        self.assertIsNone(gen_dark.web_dir("/tmp/a.css"))

    def test_border_shorthand_maps_to_side_colour(self):
        out = run(".row{border-bottom:1px solid #e5e5e5}")
        self.assertIn("border-bottom-color:", out)
        self.assertNotIn("solid", out)

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

    def test_images_and_gradients_never_emitted(self):
        out = run(".icon{background:#fff url(a.png) no-repeat 0 -32px} .btn:hover{background:linear-gradient(#fff,#eee)} .s{box-shadow:0 0 0 1px #eee}")
        self.assertIn("background-color:", out)
        self.assertNotIn("url(", out)
        self.assertNotIn("gradient", out)
        self.assertNotIn("background-image", out)
        self.assertNotIn("box-shadow", out)

    def test_layout_only_rules_dropped(self):
        self.assertEqual(run(".a{width:10px;background-position:0 -16px}"), "")

    def test_rgba_and_hsl(self):
        out = run(".a{background-color:rgba(255,255,255,.8)} .b{color:hsl(0,0%,20%)}")
        self.assertIn("rgba(", out)
        self.assertIn("html .b", out)

    def test_important_and_strings(self):
        out = run('.a{content:"}";color:#000 !important}')
        self.assertIn("html .a", out)
        self.assertEqual(out.count("!important"), 1)


class RealDsmSample(unittest.TestCase):
    """Rules copied from DSM 7's desktop.css."""

    @classmethod
    def setUpClass(cls):
        here = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(here, "fixtures", "dsm-desktop-sample.css")) as fh:
            cls.out = run(fh.read(), base="/webman/resources/css")

    def test_parses_minified_media_and_keyframes(self):
        self.assertIn("html .syno-sds-dropdown-menu {", self.out)
        self.assertNotIn("rotate(", self.out)

    def test_main_menu_goes_dark_with_light_labels(self):
        menu = self.out.split("html .syno-sds-dropdown-menu {")[1].split("}")[0]
        col = menu.split("background-color: ")[1].split(" ")[0]
        self.assertLess(lightness(col), 0.2)
        label = self.out.split("html .launch-icon.app-item-icon.dropdown-item-icon .text {")[1].split("}")[0]
        self.assertGreater(lightness(label.split("color: ")[1].split(" ")[0]), 0.7)

    def test_selection_highlight_stays_see_through_white(self):
        self.assertIn("html .launch-icon.sds-desktop-icon-selected {\n  background-color: rgba(255, 255, 255, 0.15) !important;", self.out)

    def test_brand_badge_kept(self):
        self.assertIn("background-color: #057feb !important", self.out)


if __name__ == "__main__":
    unittest.main()
