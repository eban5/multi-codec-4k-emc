from io import BytesIO

import cairosvg
from PIL import Image

codecs = ["AVC", "HEVC", "VP9", "AV1"]
framesizes = [234, 360, 432, 640, 720, 960, 1080, 1440, 2160]

for codec in codecs:
    for framesize in framesizes:
        svg = (
            '<svg width="360" height="240" viewBox="0 0 360 240" fill="none" xmlns="http://www.w3.org/2000/svg">'
            '<rect width="360" height="240" rx="20" fill="#050505"/>'
            '<rect x="24" y="24" width="312" height="136" fill="#F5F5F5"/>'
            f'<text x="50%" y="100" dominant-baseline="middle" text-anchor="middle" fill="#050505" font-family="Roboto" font-size="120" font-weight="bold">{framesize}</text>'
            f'<text x="50%" y="200" dominant-baseline="middle" text-anchor="middle" fill="#F5F5F5" font-family="Roboto" font-size="64">{codec}</text>'
            "</svg>"
        )

        png = cairosvg.svg2png(bytestring=svg)

        # use Pillow to create a 1920x1080 image with the png badge in the upper right corner with padding of 10 pixels then scale the image (keeping the aspect ration) to the height of the current framesize and save it make the image transparent
        # use Pillow 10.4.0
        image = Image.new("RGBA", (3840, 2160), (0, 0, 0, 0))
        image.paste(Image.open(BytesIO(png)), (3840 - 360 - 20, 20))
        # resize the image using Image.Resampling.LANCZOS keeping the aspect ratio and using the framesize variable as the height do not use the thumbnail method
        image2 = image.resize(
            (int(framesize / 9 * 16), int(framesize)), resample=Image.Resampling.LANCZOS
        )
        image2.save(f"framesizebadge/{codec.lower()}-{framesize}p.png")
