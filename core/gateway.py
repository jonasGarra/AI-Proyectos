"""Cliente del servidor de modelos (OmniRoute, API compatible con OpenAI).

Cada "modelo" que se pide aquí es un combo de OmniRoute (coding, fast, general...). OmniRoute
decide qué proveedor concreto lo atiende. Este módulo solo habla con él y traduce los fallos.
"""
import logging
from typing import List, Optional

import requests

log = logging.getLogger("kikos.gateway")

USER_MESSAGES = {
    "gateway_down": "No se puede conectar con el servidor de modelos (OmniRoute). Comprueba que está encendido.",
    "timeout": "El modelo ha tardado demasiado en responder. Inténtalo de nuevo o prueba el modo Rápido.",
    "provider_auth": "Un proveedor no tiene una API key válida o configurada. Revisa la configuración del servidor de modelos.",
    "rate_limited": "Se ha alcanzado el límite de uso del proveedor. Espera un momento e inténtalo otra vez.",
    "model_unavailable": "El modelo seleccionado no está disponible ahora mismo.",
    "provider_error": "El proveedor ha devuelto un error. Inténtalo de nuevo en unos segundos.",
    "invalid_response": "El modelo ha devuelto una respuesta que no se puede interpretar.",
    "too_long": "La conversación o los archivos son demasiado largos para el modelo.",
    "bad_request": "El modelo ha rechazado la petición.",
}


class GatewayError(Exception):
    """Fallo al pedir una respuesta. `fatal` = no tiene sentido probar otro modelo."""

    def __init__(self, code: str, detail: str = "", fatal: bool = False):
        super().__init__(code + ": " + detail)
        self.code = code
        self.detail = detail
        self.fatal = fatal

    @property
    def user_message(self) -> str:
        return USER_MESSAGES.get(self.code, USER_MESSAGES["provider_error"])


class Gateway:
    def __init__(self, url: str, api_key: str = "", connect_timeout: float = 5, read_timeout: float = 90):
        self.url = url
        self.api_key = api_key
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = "Bearer " + self.api_key
        return headers

    def complete(self, model: str, messages: List[dict], read_timeout: Optional[float] = None) -> str:
        payload = {"model": model, "messages": messages}
        try:
            response = requests.post(
                self.url,
                json=payload,
                headers=self._headers(),
                timeout=(self.connect_timeout, read_timeout or self.read_timeout),
            )
        except requests.exceptions.ConnectTimeout as exc:
            raise GatewayError("gateway_down", str(exc), fatal=True)
        except requests.exceptions.ConnectionError as exc:
            raise GatewayError("gateway_down", str(exc), fatal=True)
        except requests.exceptions.Timeout as exc:
            raise GatewayError("timeout", str(exc))
        except requests.exceptions.RequestException as exc:
            raise GatewayError("provider_error", str(exc))

        if response.status_code != 200:
            raise self._error_from_status(response)

        try:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise GatewayError("invalid_response", "respuesta sin 'choices': " + repr(exc))

        if isinstance(content, list):  # algunos proveedores devuelven la respuesta en partes
            content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
        if not isinstance(content, str) or not content.strip():
            raise GatewayError("invalid_response", "contenido vacío")
        return content

    @staticmethod
    def _error_from_status(response) -> GatewayError:
        status = response.status_code
        body = (response.text or "")[:500]
        if status in (401, 403):
            return GatewayError("provider_auth", "HTTP " + str(status) + " " + body)
        if status == 404:
            return GatewayError("model_unavailable", "HTTP 404 " + body)
        if status == 413:
            return GatewayError("too_long", "HTTP 413 " + body, fatal=True)
        if status == 429:
            return GatewayError("rate_limited", "HTTP 429 " + body)
        if status >= 500:
            return GatewayError("provider_error", "HTTP " + str(status) + " " + body)
        lowered = body.lower()
        if "model" in lowered or "combo" in lowered:
            return GatewayError("model_unavailable", "HTTP " + str(status) + " " + body)
        if "context" in lowered or "too long" in lowered or "token" in lowered:
            return GatewayError("too_long", "HTTP " + str(status) + " " + body, fatal=True)
        return GatewayError("bad_request", "HTTP " + str(status) + " " + body)

    def health(self) -> dict:
        """¿Responde OmniRoute? Intenta listar sus modelos (útil para comprobar que existen los combos)."""
        models_url = self.url.replace("/chat/completions", "/models")
        try:
            response = requests.get(models_url, headers=self._headers(), timeout=(2, 3))
        except requests.exceptions.RequestException as exc:
            log.info("Gateway no disponible: %s", exc)
            return {"reachable": False, "models": None}
        models = None
        if response.status_code == 200:
            try:
                models = sorted(m["id"] for m in response.json().get("data", []) if "id" in m)
            except (ValueError, AttributeError, TypeError, KeyError):
                models = None
        return {"reachable": True, "models": models}
