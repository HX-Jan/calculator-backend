"""Errors safe to expose to API clients."""


class CalculatorError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status: int = 400,
        *,
        position=None,
        end_position=None,
        argument=None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.position = position
        self.end_position = end_position
        self.argument = argument
