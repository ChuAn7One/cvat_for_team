"""CVAT uses dense cropped masks for detectors, RLE for interactor shapes."""


def mask_payload(rows, *, rle=False):
    height = len(rows)
    width = len(rows[0]) if height else 0
    if any(len(row) != width for row in rows):
        raise ValueError('Mask rows must have equal width')
    left, top, right, bottom = width, height, -1, -1
    for y, row in enumerate(rows):
        for x, value in enumerate(row):
            if value:
                left, top = min(left, x), min(top, y)
                right, bottom = max(right, x), max(bottom, y)
    if right < 0:
        return None
    pixels = [int(bool(rows[y][x])) for y in range(top, bottom + 1)
              for x in range(left, right + 1)]
    if rle:
        counts = [0]
        previous = 0
        for pixel in pixels:
            if pixel == previous:
                counts[-1] += 1
            else:
                counts.append(1)
                previous = pixel
        pixels = counts
    return pixels + [left, top, right, bottom]


def validate_names(declared, actual):
    actual = {str(key): str(value) for key, value in actual.items()}
    expected = {str(index): name for index, name in enumerate(declared)}
    if expected != actual:
        raise ValueError(f'labels.json differs from checkpoint class names: {actual}')
