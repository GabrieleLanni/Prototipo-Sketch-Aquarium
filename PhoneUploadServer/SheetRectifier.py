from __future__ import annotations

import argparse
from itertools import combinations
from pathlib import Path

import cv2
import numpy as np


# Foglio A4 prodotto per il prototipo.
A4_WIDTH_MM = 210.0
A4_HEIGHT_MM = 297.0
MARKER_MARGIN_MM = 13.0
MARKER_SIZE_MM = 12.0

# Risoluzione del foglio raddrizzato (circa 150 DPI).
OUTPUT_WIDTH = 1240
OUTPUT_HEIGHT = 1754

# Dimensioni in punti del PDF A4 usato per creare FISH_01.
PDF_PAGE_WIDTH = 595.2755905511812
PDF_PAGE_HEIGHT = 841.8897637795277

# Un piccolo margine conserva interamente il contorno nero del pesce.
FISH_MASK_MARGIN_PIXELS = 5
FISH_CROP_PADDING_PIXELS = 12

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def find_latest_image(folder: Path) -> Path:
    if not folder.exists():
        raise FileNotFoundError(f"La cartella non esiste: {folder}")

    images = [
        path
        for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    ]

    if not images:
        raise FileNotFoundError(f"Nessuna fotografia trovata in: {folder}")

    return max(images, key=lambda path: path.stat().st_mtime)


def order_points(points: np.ndarray) -> np.ndarray:
    """Ordina quattro punti: alto-sinistra, alto-destra, basso-destra, basso-sinistra."""
    points = np.asarray(points, dtype=np.float32)
    sums = points.sum(axis=1)
    differences = points[:, 0] - points[:, 1]

    return np.array(
        [
            points[np.argmin(sums)],
            points[np.argmax(differences)],
            points[np.argmax(sums)],
            points[np.argmin(differences)],
        ],
        dtype=np.float32,
    )


def has_nested_square_pattern(hierarchy: np.ndarray, contour_index: int) -> bool:
    """Verifica la struttura nero-bianco-nero presente nei marcatori stampati."""
    child_index = hierarchy[contour_index][2]

    while child_index != -1:
        if hierarchy[child_index][2] != -1:
            return True
        child_index = hierarchy[child_index][0]

    return False


def detect_marker_centres(image: np.ndarray) -> np.ndarray:
    original_height, original_width = image.shape[:2]
    max_dimension = max(original_width, original_height)
    detection_scale = min(1.0, 2000.0 / max_dimension)

    if detection_scale < 1.0:
        detection_image = cv2.resize(
            image,
            None,
            fx=detection_scale,
            fy=detection_scale,
            interpolation=cv2.INTER_AREA,
        )
    else:
        detection_image = image.copy()

    gray = cv2.cvtColor(detection_image, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    binary = cv2.threshold(
        gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )[1]

    contours, hierarchy_data = cv2.findContours(
        binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE
    )

    if hierarchy_data is None:
        raise RuntimeError("Non sono stati trovati i quattro marcatori.")

    hierarchy = hierarchy_data[0]
    image_area = float(detection_image.shape[0] * detection_image.shape[1])
    candidates: list[tuple[np.ndarray, float]] = []

    for index, contour in enumerate(contours):
        area = cv2.contourArea(contour)

        if area < image_area * 0.00015 or area > image_area * 0.03:
            continue

        perimeter = cv2.arcLength(contour, True)
        if perimeter <= 0:
            continue

        polygon = cv2.approxPolyDP(contour, 0.045 * perimeter, True)
        if len(polygon) != 4 or not cv2.isContourConvex(polygon):
            continue

        x, y, width, height = cv2.boundingRect(polygon)
        aspect_ratio = width / float(height)
        if not 0.60 <= aspect_ratio <= 1.45:
            continue

        hull_area = cv2.contourArea(cv2.convexHull(contour))
        if hull_area <= 0 or area / hull_area < 0.72:
            continue

        if not has_nested_square_pattern(hierarchy, index):
            continue

        moments = cv2.moments(polygon)
        if moments["m00"] == 0:
            continue

        centre = np.array(
            [
                moments["m10"] / moments["m00"],
                moments["m01"] / moments["m00"],
            ],
            dtype=np.float32,
        )
        candidates.append((centre, area))

    if len(candidates) < 4:
        raise RuntimeError(
            "Vedo meno di quattro marcatori. Fotografa l'intero foglio, "
            "con buona luce e senza coprire i quadrati neri."
        )

    # I veri marcatori formano il quadrilatero più grande tra i candidati.
    # Limitiamo il confronto ai candidati più grandi per mantenere il test rapido.
    candidates.sort(key=lambda item: item[1], reverse=True)
    candidate_points = [item[0] for item in candidates[:16]]

    best_points: np.ndarray | None = None
    best_area = 0.0

    for group in combinations(candidate_points, 4):
        ordered = order_points(np.array(group, dtype=np.float32))

        if len({tuple(point) for point in ordered}) != 4:
            continue

        polygon_area = abs(cv2.contourArea(ordered))
        if polygon_area > best_area and cv2.isContourConvex(ordered.astype(np.int32)):
            best_area = polygon_area
            best_points = ordered

    minimum_page_area = image_area * 0.12
    if best_points is None or best_area < minimum_page_area:
        raise RuntimeError(
            "I marcatori sono stati trovati, ma la foto non mostra bene l'intero foglio."
        )

    return best_points / detection_scale


def rectify_sheet(image: np.ndarray, marker_centres: np.ndarray) -> np.ndarray:
    marker_centre_mm = MARKER_MARGIN_MM + MARKER_SIZE_MM / 2.0

    left = marker_centre_mm / A4_WIDTH_MM * OUTPUT_WIDTH
    right = (A4_WIDTH_MM - marker_centre_mm) / A4_WIDTH_MM * OUTPUT_WIDTH
    top = marker_centre_mm / A4_HEIGHT_MM * OUTPUT_HEIGHT
    bottom = (A4_HEIGHT_MM - marker_centre_mm) / A4_HEIGHT_MM * OUTPUT_HEIGHT

    destination_points = np.array(
        [
            [left, top],
            [right, top],
            [right, bottom],
            [left, bottom],
        ],
        dtype=np.float32,
    )

    transform = cv2.getPerspectiveTransform(marker_centres, destination_points)
    return cv2.warpPerspective(
        image,
        transform,
        (OUTPUT_WIDTH, OUTPUT_HEIGHT),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(255, 255, 255),
    )


def cubic_bezier(
    start: np.ndarray,
    control_1: np.ndarray,
    control_2: np.ndarray,
    end: np.ndarray,
    steps: int = 64,
) -> np.ndarray:
    """Restituisce i punti di una curva di Bezier cubica."""
    t = np.linspace(0.0, 1.0, steps, dtype=np.float32)[:, None]
    one_minus_t = 1.0 - t

    return (
        one_minus_t**3 * start
        + 3.0 * one_minus_t**2 * t * control_1
        + 3.0 * one_minus_t * t**2 * control_2
        + t**3 * end
    )


def pdf_points_to_image(points: np.ndarray, scale: int = 1) -> np.ndarray:
    """Converte le coordinate del PDF, con origine in basso, in pixel OpenCV."""
    converted = np.asarray(points, dtype=np.float32).copy()
    converted[:, 0] = converted[:, 0] / PDF_PAGE_WIDTH * OUTPUT_WIDTH * scale
    converted[:, 1] = (
        (PDF_PAGE_HEIGHT - converted[:, 1])
        / PDF_PAGE_HEIGHT
        * OUTPUT_HEIGHT
        * scale
    )
    return converted


def create_fish_mask() -> np.ndarray:
    """Crea la maschera trasparente usando la sagoma esatta di FISH_01."""
    # Sono le stesse coordinate vettoriali usate per generare il foglio A4.
    outline_parts = [
        np.array(
            [
                [165.0, 500.0],
                [75.0, 555.0],
                [105.0, 440.0],
                [75.0, 325.0],
                [165.0, 380.0],
            ],
            dtype=np.float32,
        )
    ]

    lower_body = cubic_bezier(
        np.array([165.0, 380.0], dtype=np.float32),
        np.array([250.0, 315.0], dtype=np.float32),
        np.array([410.0, 325.0], dtype=np.float32),
        np.array([490.0, 440.0], dtype=np.float32),
    )
    upper_body = cubic_bezier(
        np.array([490.0, 440.0], dtype=np.float32),
        np.array([410.0, 555.0], dtype=np.float32),
        np.array([250.0, 565.0], dtype=np.float32),
        np.array([165.0, 500.0], dtype=np.float32),
    )

    outline_parts.extend([lower_body[1:], upper_body[1:]])
    outline_pdf = np.vstack(outline_parts)

    # Il supersampling rende il bordo trasparente più morbido e pulito.
    supersampling = 4
    outline_pixels = pdf_points_to_image(outline_pdf, supersampling)
    large_mask = np.zeros(
        (OUTPUT_HEIGHT * supersampling, OUTPUT_WIDTH * supersampling),
        dtype=np.uint8,
    )
    cv2.fillPoly(
        large_mask,
        [np.rint(outline_pixels).astype(np.int32)],
        color=255,
        lineType=cv2.LINE_AA,
    )

    margin = FISH_MASK_MARGIN_PIXELS * supersampling
    if margin > 0:
        kernel_size = margin * 2 + 1
        kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (kernel_size, kernel_size)
        )
        large_mask = cv2.dilate(large_mask, kernel, iterations=1)

    return cv2.resize(
        large_mask,
        (OUTPUT_WIDTH, OUTPUT_HEIGHT),
        interpolation=cv2.INTER_AREA,
    )


def crop_fish_with_transparency(rectified: np.ndarray) -> np.ndarray:
    """Ritaglia FISH_01 e rende trasparente tutto ciò che è fuori dalla sagoma."""
    alpha = create_fish_mask()
    visible_points = cv2.findNonZero(alpha)

    if visible_points is None:
        raise RuntimeError("Impossibile creare la maschera della sagoma FISH_01.")

    x, y, width, height = cv2.boundingRect(visible_points)
    padding = FISH_CROP_PADDING_PIXELS
    left = max(0, x - padding)
    top = max(0, y - padding)
    right = min(OUTPUT_WIDTH, x + width + padding)
    bottom = min(OUTPUT_HEIGHT, y + height + padding)

    fish = cv2.cvtColor(rectified, cv2.COLOR_BGR2BGRA)
    fish[:, :, 3] = alpha
    return fish[top:bottom, left:right]


def process_photo(input_path: Path, output_folder: Path) -> tuple[Path, Path]:
    image = cv2.imread(str(input_path), cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError(f"Impossibile aprire l'immagine: {input_path}")

    marker_centres = detect_marker_centres(image)
    rectified = rectify_sheet(image, marker_centres)
    cropped_fish = crop_fish_with_transparency(rectified)

    output_folder.mkdir(parents=True, exist_ok=True)
    rectified_path = output_folder / f"rectified_{input_path.stem}.png"
    fish_path = output_folder / f"fish_{input_path.stem}.png"

    if not cv2.imwrite(str(rectified_path), rectified):
        raise RuntimeError(f"Impossibile salvare il risultato: {rectified_path}")

    if not cv2.imwrite(str(fish_path), cropped_fish):
        raise RuntimeError(f"Impossibile salvare il risultato: {fish_path}")

    return rectified_path, fish_path


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Raddrizza la fotografia del foglio FISH_01, ritaglia il pesce "
            "e rende trasparente lo sfondo esterno."
        )
    )
    parser.add_argument(
        "--input",
        type=Path,
        help="Fotografia da elaborare. Se omessa, viene usata l'ultima in Uploads.",
    )
    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()
    base_folder = Path(__file__).resolve().parent
    input_path = arguments.input or find_latest_image(base_folder / "Uploads")
    rectified_path, fish_path = process_photo(
        input_path.resolve(), base_folder / "Processed"
    )

    print()
    print("FOGLIO RADDRIZZATO E PESCE RITAGLIATO CORRETTAMENTE")
    print(f"Foto usata: {input_path}")
    print(f"Foglio raddrizzato: {rectified_path}")
    print(f"Pesce PNG trasparente: {fish_path}")
    print()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print()
        print(f"ERRORE: {error}")
        print()
        raise SystemExit(1)
