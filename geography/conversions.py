import math

RADIUS = 6378137
HALF_SIZE = math.pi * RADIUS


def epsg3857_to_epsg4326(coords):
    """
    将EPSG:3857坐标转换为EPSG4326坐标
    :param list coords:
    :return:
    """
    output = coords.copy()
    output[0] = 180 * coords[0] / HALF_SIZE
    output[1] = (360 * math.atan(math.exp(coords[1] / RADIUS))) / math.pi - 90
    return output


def epsg4326_to_epsg3857(coords):
    """
    将EPSG4326坐标转换为EPSG3857坐标
    :param list coords:
    :return:
    """
    output = coords.copy()
    output[0] = coords[0] * HALF_SIZE / 180
    y = RADIUS * math.log(math.tan(math.pi * (coords[1] + 90) / 360))
    if y > HALF_SIZE:
        y = HALF_SIZE
    elif y < -HALF_SIZE:
        y = -HALF_SIZE
    output[1] = y
    return output
