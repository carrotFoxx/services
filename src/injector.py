import inject


def configuration(binder: inject.Binder):
    pass


def configure_injector():
    inject.configure(configuration)
