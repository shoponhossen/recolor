import numpy as np
from PIL import Image, ImageOps
import io

def load_rgba(path) -> np.ndarray:
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im)  # fix phone photo rotation
        return np.asarray(im.convert("RGBA"))  # (H, W, 4) uint8

def save_rgba(arr: np.ndarray, path) -> None:
    Image.fromarray(arr).save(path, "PNG")

def arr_to_bytes(arr):
    pil_img = Image.fromarray(arr, mode="RGBA")
    img_byte_arr = io.BytesIO()
    pil_img.save(img_byte_arr, format='PNG')
    img_bytes = img_byte_arr.getvalue()
    return img_bytes