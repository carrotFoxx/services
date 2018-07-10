from common.entities import App


def test_init_app():
    app = App(
        name='Some App',
        package='Matlab')

    assert app.uid is not None
    assert app.version is 0
