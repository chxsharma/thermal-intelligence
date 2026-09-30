from app.providers.live import FirmsDataProvider
from app.services import pipeline as pipeline_mod
from app.services.pipeline import STORE


def test_live_firms_failure_falls_back_to_demo(monkeypatch):
    live_settings = pipeline_mod.get_settings().model_copy(update={"app_mode": "live", "firms_map_key": "x"})

    def fake_settings():
        return live_settings

    fake_settings.cache_clear = lambda: None  # type: ignore[attr-defined]
    monkeypatch.setattr(pipeline_mod, "get_settings", fake_settings)
    monkeypatch.setattr(
        FirmsDataProvider,
        "fetch_observations",
        lambda self: (_ for _ in ()).throw(RuntimeError("FIRMS unavailable")),
    )
    STORE.reload()
    assert STORE.mode == "DEMO REPLAY MODE"
    assert STORE.data_provider_name == "DemoDataProvider (fallback)"
    assert STORE.observations
    assert STORE.live_error == "FIRMS unavailable"
    assert all(not str(o.id).startswith("FIRMS-") for o in STORE.observations)
