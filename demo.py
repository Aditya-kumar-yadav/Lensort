"""
Interactive Demo Script.
Creates a quick sample messy folder with various media types and runs LuminaSort.
"""

import shutil
from pathlib import Path
from PIL import Image, ImageDraw, ExifTags

from gallery_sorter.config import OrganizerConfig
from gallery_sorter.organizer import run_sort
from gallery_sorter.ui import TerminalUI

def create_sample_media(demo_dir: Path):
    if demo_dir.exists():
        shutil.rmtree(demo_dir)
    demo_dir.mkdir(parents=True)

    print("📁 Creating sample messy media files in:", demo_dir)

    # 1. Camera Original with EXIF & GPS in Manali
    img1 = Image.new("RGB", (1920, 1080), color=(100, 150, 200))
    draw1 = ImageDraw.Draw(img1)
    draw1.text((50, 50), "Manali Mountain View", fill=(255, 255, 255))
    exif = img1.getexif()
    exif[0x010F] = "Canon"
    exif[0x0110] = "EOS R5"
    exif_ifd = exif.get_ifd(ExifTags.IFD.Exif)
    exif_ifd[0x9003] = "2024:06:18 16:45:00"
    gps_ifd = exif.get_ifd(ExifTags.IFD.GPSInfo)
    gps_ifd[1] = "N"
    gps_ifd[2] = (32.2432, 0.0, 0.0)
    gps_ifd[3] = "E"
    gps_ifd[4] = (77.1892, 0.0, 0.0)
    img1.save(demo_dir / "IMG_4920_Manali.jpg", exif=exif)
    img1.close()

    # 2. WhatsApp Photo
    img2 = Image.new("RGB", (640, 480), color=(50, 180, 80))
    img2.save(demo_dir / "IMG-20231104-WA0005.jpg")
    img2.close()

    # 3. Mobile Screenshot
    img3 = Image.new("RGB", (1080, 2400), color=(40, 40, 40))
    img3.save(demo_dir / "Screenshot_20240512-143021.png")
    img3.close()

    # 4. WhatsApp Video
    with open(demo_dir / "VID-20240115-WA0010.mp4", "wb") as f:
        f.write(b"video_bytes_stream")

    # 5. Exact duplicate of WhatsApp photo
    shutil.copy2(demo_dir / "IMG-20231104-WA0005.jpg", demo_dir / "IMG-20231104-WA0005 - Copy.jpg")

    # 6. Perceptual duplicate of Manali photo (compressed version)
    with Image.open(demo_dir / "IMG_4920_Manali.jpg") as original:
        resized = original.resize((480, 270))
        resized.save(demo_dir / "Manali_shared_thumbnail.jpg", "jpeg")

    print("✨ Created 6 sample files (Camera, WhatsApp, Screenshot, Video, Exact Duplicate, Similar Photo)!\n")

def main():
    demo_dir = Path("./sample_messy_downloads").resolve()
    create_sample_media(demo_dir)

    print("🚀 Running LuminaSort in DRY-RUN mode on sample files...\n")
    config = OrganizerConfig(
        source_dir=demo_dir,
        dest_dir=demo_dir.parent / "sample_organized_output",
        mode="source-date",
        action="dry-run",
        detect_duplicates=True,
        detect_similar=True
    )

    report = run_sort(config)
    TerminalUI.render_report(report)

if __name__ == "__main__":
    main()
