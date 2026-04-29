from app.services.information_cache import InformationCache


def test_information_cache_key_is_stable_and_namespaced():
    weather_cache = InformationCache("qweather_forecast", ttl_seconds=3600)
    poi_cache = InformationCache("amap_poi", ttl_seconds=3600)

    assert weather_cache._cache_key("杭州:3d") == weather_cache._cache_key("杭州:3d")
    assert weather_cache._cache_key("杭州:3d") != poi_cache._cache_key("杭州:3d")
    assert weather_cache._cache_key("杭州:3d").startswith("info:qweather_forecast:")
