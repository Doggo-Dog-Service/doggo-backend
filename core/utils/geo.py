from django.db.models import ExpressionWrapper, F, FloatField, Value
from django.db.models.functions import ASin, Cos, Least, Radians, Sin, Sqrt


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
