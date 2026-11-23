"""
Comprehensive Test Suite for Lensort.
Creates mock photos, screenshots, WhatsApp media, EXIF/GPS tags, and tests the entire pipeline:
1. Metadata & EXIF extraction
2. Offline reverse geocoding
3. Category classification (WhatsApp, Screenshots, Camera, Videos)
4. Duplicate detection (Exact & Perceptual)
5. Execution (Copy mode) & 1-Click Rollback (Undo)
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from PIL import Image, ImageDraw, ExifTags

from gallery_sorter.config import OrganizerConfig
from gallery_sorter.organizer import GallerySorter, run_sort, run_undo
from gallery_sorter.classifier import MediaClassifier
from gallery_sorter.geocoder import reverse_geocode
from gallery_sorter.metadata import FileMetadata
from gallery_sorter.duplicates import DuplicateDetector

class TestLensort(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="lensort_test_"))
        self.source_dir = self.test_dir / "Source_Messy"
        self.source_dir.mkdir(parents=True)
        self.dest_dir = self.test_dir / "Organized_Gallery"

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _create_mock_image(
        self,
        filepath: Path,
        size=(800, 600),
        pattern_id=1,
        camera_make=None,
        camera_model=None,
        date_str=None, # "2024:03:15 10:20:00"
        gps_lat=None,
        gps_lon=None
    ):
        img = Image.new("RGB", size, color=(30 * pattern_id % 255, 60 * pattern_id % 255, 90 * pattern_id % 255))
        draw = ImageDraw.Draw(img)
        # Draw distinctive geometric shapes so perceptual hash is non-trivial and unique
        draw.rectangle([10 * pattern_id, 10, 200, 200], fill=(200, 50, 100))
        draw.line([(0, 0), size], fill=(255, 255, 255), width=3)
        draw.ellipse([50, 50, 150, 150], fill=(50, 200, 50))

        exif = img.getexif()

        if camera_make:
            exif[0x010F] = camera_make # Make
        if camera_model:
            exif[0x0110] = camera_model # Model

        if date_str:
            exif_ifd = exif.get_ifd(ExifTags.IFD.Exif)
            exif_ifd[0x9003] = date_str # DateTimeOriginal

        if gps_lat is not None and gps_lon is not None:
            gps_ifd = exif.get_ifd(ExifTags.IFD.GPSInfo)
            gps_ifd[1] = "N" if gps_lat >= 0 else "S"
            gps_ifd[2] = (abs(gps_lat), 0.0, 0.0)
            gps_ifd[3] = "E" if gps_lon >= 0 else "W"
            gps_ifd[4] = (abs(gps_lon), 0.0, 0.0)

        img.save(filepath, "jpeg", exif=exif)
        img.close()

    def test_geocoder(self):
        """Verify offline reverse geocoder for Goa and Delhi."""
        loc_goa = reverse_geocode(15.54, 73.75)
        self.assertIsNotNone(loc_goa)
        self.assertTrue(loc_goa.city in ("Goa", "Calangute", "Panaji") or loc_goa.region == "Goa")

        loc_delhi = reverse_geocode(28.61, 77.20)
        self.assertIsNotNone(loc_delhi)
        self.assertEqual(loc_delhi.city, "Delhi")

    def test_end_to_end_pipeline(self):
        """Create a full messy folder, sort it, and test undo."""
        # 1. Camera Original with EXIF & GPS in Goa
        camera_file = self.source_dir / "DSC_0042.jpg"
        self._create_mock_image(
            camera_file,
            size=(2000, 1500),
            pattern_id=1,
            camera_make="Sony",
            camera_model="ILCE-7M4",
            date_str="2024:03:15 10:20:00",
            gps_lat=15.4989,
            gps_lon=73.8278 # Goa
        )

        # 2. WhatsApp Photo
        wa_file = self.source_dir / "IMG-20231104-WA0002.jpg"
        self._create_mock_image(wa_file, size=(800, 600), pattern_id=2)

        # 3. Screenshot (Aspect ratio 19.5:9, PNG format, no EXIF)
        screenshot_file = self.source_dir / "Screenshot_20240512-143021.png"
        img_screen = Image.new("RGB", (1080, 2400), color=(50, 50, 200))
        draw_ss = ImageDraw.Draw(img_screen)
        draw_ss.rectangle([50, 50, 500, 500], fill=(200, 200, 200))
        img_screen.save(screenshot_file, "png")
        img_screen.close()

        # 4. Video file (dummy binary)
        video_file = self.source_dir / "VID-20240115-WA0010.mp4"
        with open(video_file, "wb") as f:
            f.write(b"fake_mp4_video_data_stream_content")

        # 5. Exact duplicate of WhatsApp photo
        exact_dup_file = self.source_dir / "copy_of_wa.jpg"
        shutil.copy2(wa_file, exact_dup_file)

        # 6. Perceptual duplicate of camera photo (slightly resized copy)
        similar_file = self.source_dir / "DSC_0042_compressed.jpg"
        with Image.open(camera_file) as original:
            resized = original.resize((600, 450))
            resized.save(similar_file, "jpeg")

        # -------------------------------------------------------------
        # STEP 1: Dry Run Verification
        # -------------------------------------------------------------
        config_dry = OrganizerConfig(
            source_dir=self.source_dir,
            dest_dir=self.dest_dir,
            mode="source-date",
            action="dry-run",
            detect_duplicates=True,
            detect_similar=True
        )
        report_dry = run_sort(config_dry)
        self.assertEqual(report_dry.total_scanned, 6)
        self.assertEqual(report_dry.exact_duplicates_count, 1)
        self.assertEqual(report_dry.similar_duplicates_count, 1)
        self.assertFalse(self.dest_dir.exists())

        # -------------------------------------------------------------
        # STEP 2: Actual Execution (Copy Mode)
        # -------------------------------------------------------------
        config_copy = OrganizerConfig(
            source_dir=self.source_dir,
            dest_dir=self.dest_dir,
            mode="source-date",
            action="copy",
            detect_duplicates=True,
            detect_similar=True,
            duplicate_action="isolate"
        )
        report_copy = run_sort(config_copy)

        self.assertTrue(self.dest_dir.exists())
        self.assertIsNotNone(report_copy.manifest_path)
        self.assertTrue(report_copy.manifest_path.exists())

        # 1. Camera file -> Camera Originals / 2024 / 03 - March /
        expected_camera_dest = self.dest_dir / "Camera Originals" / "2024" / "03 - March" / "DSC_0042.jpg"
        self.assertTrue(expected_camera_dest.exists(), f"Missing: {expected_camera_dest}")

        # 2. WhatsApp file -> WhatsApp & Social / 2023 / 11 - November /
        expected_wa_dest = self.dest_dir / "WhatsApp & Social" / "2023" / "11 - November" / "IMG-20231104-WA0002.jpg"
        self.assertTrue(expected_wa_dest.exists(), f"Missing: {expected_wa_dest}")

        # 3. Screenshot file -> Screenshots / 2024 /
        expected_ss_dest = self.dest_dir / "Screenshots" / "2024" / "Screenshot_20240512-143021.png"
        self.assertTrue(expected_ss_dest.exists(), f"Missing: {expected_ss_dest}")

        # 4. Video file -> Videos / 2024 /
        expected_vid_dest = self.dest_dir / "Videos" / "2024" / "VID-20240115-WA0010.mp4"
        self.assertTrue(expected_vid_dest.exists(), f"Missing: {expected_vid_dest}")

        # 5. Duplicates folder exists with exact & similar subfolders
        dups_dir = self.dest_dir / "_Duplicates"
        self.assertTrue(dups_dir.exists())
        self.assertTrue((dups_dir / "Exact").exists())
        self.assertTrue((dups_dir / "Similar").exists())

        # -------------------------------------------------------------
        # STEP 3: Undo / Rollback Verification
        # -------------------------------------------------------------
        manifest_file = report_copy.manifest_path
        success, fail, errors = run_undo(manifest_file)
        self.assertGreater(success, 0)
        self.assertEqual(fail, 0)

        # Copied destination files should be removed
        self.assertFalse(expected_camera_dest.exists())
        self.assertFalse(expected_wa_dest.exists())

        # Source files should be 100% intact
        self.assertTrue(camera_file.exists())
        self.assertTrue(wa_file.exists())
        self.assertTrue(screenshot_file.exists())

    def test_trips_mode(self):
        """Verify trips mode groups GPS photos into Trips/City_Year."""
        photo = self.source_dir / "GoaVacation.jpg"
        self._create_mock_image(
            photo,
            pattern_id=5,
            date_str="2024:04:10 12:00:00",
            gps_lat=15.2993,
            gps_lon=74.1240 # Goa
        )
        dest = self.test_dir / "Trips_Gallery"
        config = OrganizerConfig(
            source_dir=self.source_dir,
            dest_dir=dest,
            mode="trips",
            action="copy",
            detect_duplicates=False
        )
        report = run_sort(config)
        trips_folder = dest / "Trips"
        self.assertTrue(trips_folder.exists())
        # Find folder with Goa_2024
        goa_folders = list(trips_folder.glob("*Goa*"))
        self.assertTrue(len(goa_folders) > 0)

if __name__ == "__main__":
    unittest.main()
