import cv2
import numpy as np
import os
import uuid

def save_bgr_im(bgr_img, directory, original_path=None): # сохраняет bgr изображение
    ext = '.jpg'
    if original_path and os.path.exists(original_path):
        _, ext = os.path.splitext(original_path) # разбиваем путь на имя без расширения и расширение
        if ext.lower() not in ['.jpg', '.jpeg', '.png', '.bmp']:
            ext = '.jpg'

    filename = f"{uuid.uuid4().hex}{ext}" # cлучайный uuid без дефисов
    filepath = os.path.join(directory, filename) # правильный путь для всех ос
    cv2.imwrite(filepath, bgr_img)          # без конвертации
    return filepath

def load_image_bgr(filepath): # загрузка bgr изображение
    img = cv2.imread(filepath, cv2.IMREAD_COLOR)   # всегда 3 канала
    if img is None:
        raise ValueError("Не удалось загрузить изображение")
    return img


# Фильтры
def apply_filter(filepath, filter_name):
    img = load_image_bgr(filepath)

    if filter_name == 'grayscale':
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        result = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

    elif filter_name == 'sepia':
        kernel = np.array([[0.272, 0.534, 0.131],
                           [0.349, 0.686, 0.168],
                           [0.393, 0.769, 0.189]], dtype=np.float32)
        result = cv2.transform(img, kernel)
        result = np.clip(result, 0, 255).astype(np.uint8)

    elif filter_name == 'invert':
        result = cv2.bitwise_not(img)

    elif filter_name == 'blur':
        result = cv2.GaussianBlur(img, (99, 99), 0)

    elif filter_name == 'sharpen':
        kernel = np.array([[0, -1, 0],
                           [-1, 5.2, -1],
                           [0, -1, 0]])
        result = cv2.filter2D(img, -1, kernel)
        result = np.clip(result, 0, 255).astype(np.uint8)

    elif filter_name == 'edges':
        edges = cv2.Canny(img, 100, 200)
        result = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)

    elif filter_name == 'emboss':
        kernel = np.array([[-2, -1, 0],
                           [-1, 1, 1],
                           [0, 1, 2]])
        result = cv2.filter2D(img, -1, kernel) + 128
        result = np.clip(result, 0, 255).astype(np.uint8)


    elif filter_name == 'cartoon':
        color = cv2.bilateralFilter(img, 9, 250, 250)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.medianBlur(gray, 5)
        edges = cv2.adaptiveThreshold(gray, 255,
                                      cv2.ADAPTIVE_THRESH_MEAN_C,
                                      cv2.THRESH_BINARY, 9, 7)
        edges_inv = cv2.bitwise_not(edges)
        result = cv2.bitwise_and(color, color, mask=edges_inv)

    return result


# Трансформации
def apply_transform(filepath, transform_type):
    img = load_image_bgr(filepath)

    if transform_type == 'rotate_90_ccw':
        result = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
    elif transform_type == 'rotate_90_cw':
        result = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
    elif transform_type == 'flip_horizontal':
        result = cv2.flip(img, 1)
    elif transform_type == 'flip_vertical':
        result = cv2.flip(img, 0)

    return result


# Коррекции
def apply_correction(filepath, brightness=0, contrast=0, saturation=0):
    img = load_image_bgr(filepath)

    if brightness != 0:
        img = np.clip(img.astype(np.int16) + brightness, 0, 255).astype(np.uint8)

    if contrast != 0:
        a = 1 + contrast / 100.0
        img_float = img.astype(np.float32)
        img_float = al * (img_float - 128) + 128
        img = np.clip(img_float, 0, 255).astype(np.uint8)

    if saturation != 0:
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(np.float32)
        factor = 1 + saturation / 100.0
        hsv[:, :, 1] *= factor
        hsv[:, :, 1] = np.clip(hsv[:, :, 1], 0, 255)
        hsv = hsv.astype(np.uint8)
        img = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)

    return img