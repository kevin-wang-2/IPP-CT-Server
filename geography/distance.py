import math

RADIUS = 6378137
HALF_SIZE = math.pi * RADIUS


def epsg4326_distance(p1, p2):
    """
    计算epsg4326下的距离
    :param list p1:
    :param list p2:
    :return:
    """
    p1_lon = math.pi * p1[0] / HALF_SIZE
    p1_lat = 2 * math.atan(math.exp(p1[1] / RADIUS)) - math.pi / 2
    p2_lon = math.pi * p2[0] / HALF_SIZE
    p2_lat = 2 * math.atan(math.exp(p2[1] / RADIUS)) - math.pi / 2
    angle = math.cos(p1_lat) * math.cos(p2_lat) * math.cos(p1_lon - p2_lon) + math.sin(p1_lat) * math.sin(p2_lat)
    return RADIUS * math.acos(angle)


def epsg3857_distance(p1, p2):
    """
    计算epsg3857下的距离
    :param list p1:
    :param list p2:
    :return:
    """
    p1_lon = math.pi * p1[0] / 180
    p1_lat = math.pi * p1[1] / 180
    p2_lon = math.pi * p2[0] / 180
    p2_lat = math.pi * p2[1] / 180
    angle = math.cos(p1_lat) * math.cos(p2_lat) * math.cos(p1_lon - p2_lon) + math.sin(p1_lat) * math.sin(p2_lat)
    return RADIUS * math.acos(angle)
