import threading


class ExecutionContext:
    _local = threading.local()

    @classmethod
    def push(cls, module):
        if not hasattr(cls._local, "stack"):
            cls._local.stack = []
            cls._local.tracing = False
        cls._local.stack.append(module)

    @classmethod
    def pop(cls):
        cls._local.stack.pop()

    @classmethod
    def get_current(cls):
        stack = getattr(cls._local, "stack", [])
        return stack[-1] if stack else None

    @classmethod
    def is_running(cls):
        return hasattr(cls._local, "stack") and len(cls._local.stack) > 0

    @classmethod
    def get_current_module(cls):
        return cls.get_current()

    @classmethod
    def set_tracing(cls, enabled: bool = True):
        cls._local.tracing = enabled

    @classmethod
    def is_tracing(cls) -> bool:
        return getattr(cls._local, "tracing", False)
