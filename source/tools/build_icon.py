from pathlib import Path

from PIL import Image, ImageDraw


def build_icon(destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    scale = 4
    image = Image.new('RGBA', (512 * scale, 512 * scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    def points(values):
        return [(horizontal * scale, vertical * scale) for horizontal, vertical in values]
    draw.rounded_rectangle((8 * scale, 8 * scale, 504 * scale, 504 * scale), radius=112 * scale, fill='#007f68')
    draw.line(points([(102, 326), (102, 148), (204, 148), (238, 188), (402, 188), (402, 326)]), fill='white', width=27 * scale, joint='curve')
    draw.ellipse((189 * scale, 215 * scale, 337 * scale, 363 * scale), fill='#007f68', outline='#f2b352', width=29 * scale)
    draw.line(points([(318, 345), (393, 420)]), fill='#f2b352', width=32 * scale)
    for horizontal, vertical in [(318, 345), (393, 420)]:
        radius = 16 * scale
        draw.ellipse((horizontal * scale - radius, vertical * scale - radius, horizontal * scale + radius, vertical * scale + radius), fill='#f2b352')
    image = image.resize((512, 512), Image.Resampling.LANCZOS)
    image.save(destination / 'app-icon.png')
    image.save(destination / 'app-icon.ico', sizes=[(size, size) for size in (16, 20, 24, 32, 48, 64, 128, 256)])
    return destination / 'app-icon.ico'


if __name__ == '__main__':
    build_icon(Path(__file__).resolve().parents[1] / 'assets')
