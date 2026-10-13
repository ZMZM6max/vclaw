"""DockerSandbox - high-level Docker sandbox lifecycle management.

Backward-compatible wrapper around SandboxManager for existing tests
and consumers that expect the DockerSandbox interface.
"""

from src.l6.docker_controller import DockerController  # noqa: F401 - imported for test patching
from src.l6.sandbox_manager import SandboxManager
from src.l6.config import SandboxConfig


class DockerSandbox(SandboxManager):
    """High-level Docker sandbox.

    Delegates all operations to SandboxManager while exposing a
    ``controller`` attribute for test mocking.
    """

    def __init__(self, config: SandboxConfig = None) -> None:
        super().__init__()
        self.config = config or SandboxConfig()
        # Re-assign controller using the module-level DockerController
        # so that tests patching ``src.l6.docker_sandbox.DockerController``
        # intercept this instantiation.
        self._controller = DockerController()

    @property
    def controller(self):
        """Expose the internal DockerController for mocking."""
        return self._controller

    @controller.setter
    def controller(self, value):
        self._controller = value
