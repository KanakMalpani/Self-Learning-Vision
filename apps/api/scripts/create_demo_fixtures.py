from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw


def draw_face(path: Path, *, skin: tuple[int, int, int], shirt: tuple[int, int, int], dx: int = 0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (512, 512), (24, 28, 36))
    draw = ImageDraw.Draw(image)
    draw.ellipse((156 + dx, 96, 356 + dx, 296), fill=skin)
    draw.rectangle((150 + dx, 292, 362 + dx, 452), fill=shirt)
    draw.ellipse((210 + dx, 175, 232 + dx, 197), fill=(20, 20, 20))
    draw.ellipse((280 + dx, 175, 302 + dx, 197), fill=(20, 20, 20))
    draw.arc((225 + dx, 190, 295 + dx, 250), start=20, end=160, fill=(80, 40, 40), width=4)
    draw.arc((225 + dx, 220, 295 + dx, 270), start=15, end=165, fill=(120, 50, 60), width=5)
    image.save(path)


def main() -> None:
    out = Path("data/demo-fixtures")
    draw_face(out / "demo-person-a-1.png", skin=(218, 172, 130), shirt=(45, 126, 185), dx=0)
    draw_face(out / "demo-person-a-2.png", skin=(218, 172, 130), shirt=(48, 132, 188), dx=8)
    draw_face(out / "demo-person-b-1.png", skin=(150, 101, 78), shirt=(168, 84, 96), dx=-6)
    draw_face(out / "demo-person-b-2.png", skin=(150, 101, 78), shirt=(170, 90, 100), dx=6)
    print(f"Wrote demo fixtures to {out}")


if __name__ == "__main__":
    main()
