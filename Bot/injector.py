from injector import inject, Module, singleton


class AppModule(Module):
    # define services which will be injected
    def configure(self, binder):
        from .services import CustomerService
        from .website.statistics import Statistics

        binder.bind(CustomerService, to=CustomerService, scope=singleton)
        binder.bind(Statistics, to=Statistics, scope=singleton)