from html import escape

QR_VERSION = 5
QR_SIZE = 17 + QR_VERSION * 4
DATA_CODEWORDS = 108
ECC_CODEWORDS = 26


def _gf_multiply(x: int, y: int) -> int:
    result = 0
    for _ in range(8):
        result = ((result << 1) ^ (0x11D if result & 0x80 else 0)) & 0xFF
        if y & 0x80:
            result ^= x
        y <<= 1
    return result


def _reed_solomon_divisor(degree: int) -> list[int]:
    result = [0] * (degree - 1) + [1]
    root = 1
    for _ in range(degree):
        for index in range(degree):
            result[index] = _gf_multiply(result[index], root)
            if index + 1 < degree:
                result[index] ^= result[index + 1]
        root = _gf_multiply(root, 2)
    return result


def _reed_solomon_remainder(data: list[int], divisor: list[int]) -> list[int]:
    result = [0] * len(divisor)
    for value in data:
        factor = value ^ result[0]
        result = result[1:] + [0]
        for index, coefficient in enumerate(divisor):
            result[index] ^= _gf_multiply(coefficient, factor)
    return result


def _data_codewords(text: str) -> list[int]:
    payload = text.encode("utf-8")
    if len(payload) > 104:
        raise ValueError("QR content is too long")
    bits: list[int] = [0, 1, 0, 0]
    bits.extend((len(payload) >> shift) & 1 for shift in range(7, -1, -1))
    for value in payload:
        bits.extend((value >> shift) & 1 for shift in range(7, -1, -1))
    capacity = DATA_CODEWORDS * 8
    bits.extend([0] * min(4, capacity - len(bits)))
    bits.extend([0] * ((-len(bits)) % 8))
    codewords = [
        sum(bits[offset + bit] << (7 - bit) for bit in range(8))
        for offset in range(0, len(bits), 8)
    ]
    padding = (0xEC, 0x11)
    while len(codewords) < DATA_CODEWORDS:
        codewords.append(padding[(len(codewords) - len(payload)) % 2])
    return codewords


def qr_matrix(text: str) -> list[list[bool]]:
    data = _data_codewords(text)
    codewords = data + _reed_solomon_remainder(data, _reed_solomon_divisor(ECC_CODEWORDS))
    modules = [[False] * QR_SIZE for _ in range(QR_SIZE)]
    functions = [[False] * QR_SIZE for _ in range(QR_SIZE)]

    def set_function(x: int, y: int, dark: bool) -> None:
        modules[y][x] = dark
        functions[y][x] = True

    for index in range(8, QR_SIZE - 8):
        dark = index % 2 == 0
        set_function(6, index, dark)
        set_function(index, 6, dark)

    def finder(center_x: int, center_y: int) -> None:
        for dy in range(-4, 5):
            for dx in range(-4, 5):
                x, y = center_x + dx, center_y + dy
                if 0 <= x < QR_SIZE and 0 <= y < QR_SIZE:
                    distance = max(abs(dx), abs(dy))
                    set_function(x, y, distance not in {2, 4})

    finder(3, 3)
    finder(QR_SIZE - 4, 3)
    finder(3, QR_SIZE - 4)
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            set_function(30 + dx, 30 + dy, max(abs(dx), abs(dy)) != 1)

    def draw_format(mask: int) -> None:
        value = (1 << 3) | mask  # Error correction level L.
        remainder = value
        for _ in range(10):
            remainder = (remainder << 1) ^ ((remainder >> 9) * 0x537)
        bits = ((value << 10) | remainder) ^ 0x5412
        bit = lambda index: ((bits >> index) & 1) != 0  # noqa: E731
        for index in range(6):
            set_function(8, index, bit(index))
        set_function(8, 7, bit(6))
        set_function(8, 8, bit(7))
        set_function(7, 8, bit(8))
        for index in range(9, 15):
            set_function(14 - index, 8, bit(index))
        for index in range(8):
            set_function(QR_SIZE - 1 - index, 8, bit(index))
        for index in range(8, 15):
            set_function(8, QR_SIZE - 15 + index, bit(index))
        set_function(8, QR_SIZE - 8, True)

    draw_format(0)
    all_bits = [(value >> shift) & 1 for value in codewords for shift in range(7, -1, -1)]
    bit_index = 0
    upward = True
    right = QR_SIZE - 1
    while right >= 1:
        if right == 6:
            right = 5
        for vertical in range(QR_SIZE):
            y = QR_SIZE - 1 - vertical if upward else vertical
            for offset in range(2):
                x = right - offset
                if not functions[y][x]:
                    dark = bit_index < len(all_bits) and all_bits[bit_index] == 1
                    bit_index += 1
                    modules[y][x] = dark ^ ((x + y) % 2 == 0)
        upward = not upward
        right -= 2
    draw_format(0)
    return modules


def qr_svg(text: str) -> str:
    matrix = qr_matrix(text)
    border = 4
    size = len(matrix) + border * 2
    path = "".join(
        f"M{x + border},{y + border}h1v1h-1z"
        for y, row in enumerate(matrix)
        for x, dark in enumerate(row)
        if dark
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" '
        f'role="img" aria-label="{escape(text, quote=True)}" shape-rendering="crispEdges">'
        f'<rect width="100%" height="100%" fill="#fff"/><path d="{path}" fill="#000"/>'
        "</svg>"
    )
