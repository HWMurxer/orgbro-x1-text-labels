import unittest
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from x1_label import build_job, image_to_raster, load_saved_lines, render_label, save_lines


class X1LabelTests(unittest.TestCase):
    def test_last_text_is_saved_locally(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            self.assertEqual(load_saved_lines(path), ["", "", ""])
            save_lines(["erste", "zweite", "dritte"], path)
            self.assertEqual(load_saved_lines(path), ["erste", "zweite", "dritte"])

    def test_one_to_three_lines_have_exact_raster_size(self):
        for lines in (["Schlafzimmer"], ["Zähler", "Wohnung 1"], ["Kabel", "UV Keller", "L1"]):
            label = render_label(list(lines))
            self.assertEqual(label.size, (280, 96))
            self.assertEqual(len(image_to_raster(label)), 3360)

    def test_protocol_matches_captured_shape(self):
        hello, prepare, job = build_job(render_label(["Schlafzimmer"]))
        self.assertEqual(len(hello), 20)
        self.assertEqual(len(prepare), 11)
        self.assertEqual(len(hello + prepare + job), 3571)
        self.assertTrue(job.startswith(bytes.fromhex(
            "64 0a 04 01 00 19 00 00 00 00 9b"
            "64 09 05 01 00 09 00 00 00 00 9b"
            "64 03 06 03 00 02 20 03 00 00 00 00 9b"
            "64 02 07 02 00 11 00 00 00 00 00 9b"
        )))
        self.assertTrue((hello + prepare + job).endswith(bytes.fromhex("64 03 14 03 00 01 20 03 00 00 00 00 9b")))

    def test_long_text_keeps_safe_side_margins(self):
        label = render_label(["TEST WINDOWS"])
        black = label.point(lambda value: 255 - value)
        left, _top, right, _bottom = black.getbbox()
        self.assertGreaterEqual(left, 8)
        self.assertLessEqual(right, 272)
        self.assertAlmostEqual((left + right) / 2, 280 / 2, delta=2)


if __name__ == "__main__":
    unittest.main()
