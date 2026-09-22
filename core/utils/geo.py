from math import asin, cos, radians, sin, sqrt

from django.db.models import ExpressionWrapper, F, FloatField, Value
from django.db.models.functions import ASin, Cos, Least, Radians, Sin, Sqrt


def haversine(latitude_1, longitude_1, latitude_2, longitude_2):
    """
    Calcula a distância em metros entre dois pontos geográficos.
    """
    earth_radius = 6371000.0

    latitude_1 = radians(latitude_1)
    latitude_2 = radians(latitude_2)

    delta_latitude = radians(latitude_2 - latitude_1)
    delta_longitude = radians(longitude_2 - longitude_1)

    a = (
        sin(delta_latitude / 2) ** 2
        + cos(latitude_1) * cos(latitude_2) * sin(delta_longitude / 2) ** 2
    )

    c = 2 * asin(sqrt(a))

    return earth_radius * c


def haversine_annotation(lat, lon, lat_field='fixed_latitude', lon_field='fixed_longitude'):
    radius = Value(6371.0, output_field=FloatField())
    user_lat = Radians(Value(lat))
    user_lon = Radians(Value(lon))
    provider_lat = Radians(F(lat_field))
    provider_lon = Radians(F(lon_field))

    a = ExpressionWrapper(
        Sin((provider_lat - user_lat) / 2) ** 2
        + Cos(user_lat) * Cos(provider_lat) * Sin((provider_lon - user_lon) / 2) ** 2,
        output_field=FloatField(),
    )

    return ExpressionWrapper(
        2 * ASin(Sqrt(Least(a, Value(1.0)))) * radius,
        output_field=FloatField(),
    )
