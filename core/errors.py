class ApiError(Exception):
    """Error controlado: lleva un código HTTP y un mensaje que el usuario puede leer."""

    def __init__(self, status: int, code: str, message: str, extra: dict = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.extra = extra or {}

    def to_dict(self) -> dict:
        body = {"status": "error", "code": self.code, "message": self.message}
        body.update(self.extra)
        return body
