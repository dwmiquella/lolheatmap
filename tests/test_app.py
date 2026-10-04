from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def demo():
    app = AppTest.from_file(APP, default_timeout=30).run()
    assert not app.exception
    next(b for b in app.button if b.label == "Explore demo").click().run()
    assert not app.exception
    return app


def view(app, name):
    next(r for r in app.radio if r.label == "View").set_value(name).run()
    assert not app.exception


def test_demo_filters_champions_and_reset():
    app = demo()
    app.selectbox(key="champ").set_value("Ahri").run()
    view(app, "Champions")
    assert app.dataframe[0].value["Champion"].tolist() == ["Ahri"]
    assert app.dataframe[0].value["Games"].sum() == 4
    next(b for b in app.button if b.label == "Reset filters").click().run()
    assert app.dataframe[0].value["Games"].sum() == 12


def test_comparison_is_independent_of_explore_filters_and_handles_equal_bounds():
    app = demo()
    app.radio(key="result").set_value("Win").run()
    view(app, "Compare")
    assert app.dataframe[0].value.loc["Games", "You"] == 4
    app.select_slider(key="compare_window").set_value((5, 5)).run()
    assert not app.exception
    assert any("end time" in w.value for w in app.warning)


def test_invalid_explore_window_shows_warning():
    app = demo()
    app.slider(key="window").set_value((5, 5)).run()
    assert not app.exception
    assert any("end time" in w.value for w in app.warning)


def test_host_secret_is_not_sent_to_a_widget(monkeypatch):
    monkeypatch.setenv("RIOT_API_KEY", "test-host-secret")
    app = AppTest.from_file(APP).run()
    assert not app.exception
    assert all(w.label != "Riot API key" for w in app.text_input)
