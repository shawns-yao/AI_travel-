from app.services.destination_resolver import resolve_destination


def test_gulangyu_resolves_to_xiamen_for_weather_but_keeps_focus():
    resolved = resolve_destination("鼓浪屿")

    assert resolved.display_name == "鼓浪屿（厦门）"
    assert resolved.weather_city == "厦门"
    assert resolved.search_city == "厦门"
    assert resolved.must_include == "鼓浪屿"


def test_common_xiamen_typo_resolves_to_xiamen():
    resolved = resolve_destination("夏门")

    assert resolved.display_name == "厦门"
    assert resolved.weather_city == "厦门"
    assert resolved.must_include == "厦门"
