import os
from PIL import Image

sizes = [16, 32, 48, 64, 128, 256]
src = os.path.join('bin', 'windows', 'icon.png')
ico = os.path.join('bin', 'windows', 'icon.ico')
preview = os.path.join('bin', 'windows', 'icon_preview.png')

if not os.path.exists(src):
    print(f'ERROR: {src} not found — place your icon here first')
    exit(1)

img = Image.open(src).convert('RGBA')
img.save(ico, format='ICO', sizes=[(s, s) for s in sizes])
img.resize((512, 512), Image.LANCZOS).save(preview)

print(f'ICO: {ico} ({os.path.getsize(ico)//1024} KB)')
print(f'Preview: {preview}')
