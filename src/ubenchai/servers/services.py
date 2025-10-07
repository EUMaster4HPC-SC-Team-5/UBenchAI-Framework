from enum import Enum


class ServiceRegistery:
    pass


class ServiceInstance:
    pass


class ServiceStatus(Enum):
    RUNNING = 0
    STARTING = 1
    PENDING = 2
    STOPPING = 3
    STOPPED = 4
    ERROR = 5
    UNKNOWN = 6


class ServiceRecipe:
    pass
