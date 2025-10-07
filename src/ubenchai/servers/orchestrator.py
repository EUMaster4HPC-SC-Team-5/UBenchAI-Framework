from enum import Enum
from abc import ABC, abstractmethod


class OrchestratorType(Enum):
    SLURM = 0
    K8S = 1


class Orchestrator(ABC):
    pass
