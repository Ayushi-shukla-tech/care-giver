import httpx

import app.weather_provider as weather_provider_module


class _FakeResponse:
    def __init__(self, json_data, raise_error=None):
        self._json_data = json_data
        self._raise_error = raise_error

    def raise_for_status(self):
        if self._raise_error:
            raise self._raise_error

    def json(self):
        return self._json_data


def _patch_httpx_get(fake_response_or_raiser):
    original = weather_provider_module.httpx.get
    weather_provider_module.httpx.get = fake_response_or_raiser
    return original


def _restore_httpx_get(original):
    weather_provider_module.httpx.get = original


def test_reverse_geocode_returns_city_when_present():
    original = _patch_httpx_get(
        lambda *args, **kwargs: _FakeResponse({"address": {"city": "Mumbai", "state": "Maharashtra"}})
    )
    try:
        label = weather_provider_module._reverse_geocode_location_label(19.076, 72.8777)
    finally:
        _restore_httpx_get(original)

    assert label == "Mumbai"


def test_reverse_geocode_falls_back_to_town_then_village_then_suburb():
    original = _patch_httpx_get(
        lambda *args, **kwargs: _FakeResponse({"address": {"suburb": "Kurla West"}})
    )
    try:
        label = weather_provider_module._reverse_geocode_location_label(19.076, 72.8777)
    finally:
        _restore_httpx_get(original)

    assert label == "Kurla West"


def test_reverse_geocode_falls_back_to_your_area_when_no_address_fields():
    original = _patch_httpx_get(lambda *args, **kwargs: _FakeResponse({"address": {}}))
    try:
        label = weather_provider_module._reverse_geocode_location_label(0.0, 0.0)
    finally:
        _restore_httpx_get(original)

    assert label == "your area"


def test_reverse_geocode_falls_back_to_your_area_on_http_error():
    def _raise(*args, **kwargs):
        raise httpx.ConnectError("network unreachable")

    original = _patch_httpx_get(_raise)
    try:
        label = weather_provider_module._reverse_geocode_location_label(19.076, 72.8777)
    finally:
        _restore_httpx_get(original)

    assert label == "your area"
