"""Orquestador: decide el modelo (Smart Router), lo llama y, si falla, prueba el siguiente."""
import logging
import time
from dataclasses import dataclass, field
from typing import List, Optional

from core.gateway import Gateway, GatewayError, USER_MESSAGES
from router.smart_router import SmartRouter

log = logging.getLogger("kikos.orchestrator")

# Si fallan todos los modelos, se muestra el error más útil para el usuario
_ERROR_PRIORITY = [
    "gateway_down", "provider_auth", "rate_limited", "too_long", "timeout",
    "model_unavailable", "invalid_response", "bad_request", "provider_error",
]


@dataclass
class Generation:
    reply: str
    model: str
    task: str
    confidence: float
    mode: str
    latency_ms: int
    fallback: bool
    attempts: List[dict] = field(default_factory=list)
    scores: dict = field(default_factory=dict)


class AllModelsFailed(Exception):
    def __init__(self, code: str, attempts: List[dict]):
        super().__init__(code)
        self.code = code
        self.attempts = attempts

    @property
    def user_message(self) -> str:
        text = USER_MESSAGES.get(self.code, USER_MESSAGES["provider_error"])
        tried = len(self.attempts)
        if tried > 1:
            text += " (Se probaron " + str(tried) + " modelos.)"
        return text


class Orchestrator:
    def __init__(self, router: SmartRouter, gateway: Gateway, total_timeout: float = 150):
        self.router = router
        self.gateway = gateway
        self.total_timeout = total_timeout

    def generate(self, classify_text: str, messages: list, mode: str, has_image: bool = False,
                 input_length: int = 0, previous_task: Optional[str] = None,
                 has_attachments: bool = False) -> Generation:
        decision = self.router.plan(
            classify_text, mode=mode, input_length=input_length, has_image=has_image,
            previous_task=previous_task, has_attachments=has_attachments,
        )
        log.info(
            "Ruta: tarea=%s confianza=%.2f modo=%s cadena=%s (%s)",
            decision.task, decision.confidence, decision.mode, decision.chain, decision.reason,
        )

        started = time.monotonic()
        deadline = started + self.total_timeout
        attempts: List[dict] = []
        errors: List[GatewayError] = []

        for combo in decision.chain:
            remaining = deadline - time.monotonic()
            if attempts and remaining <= 1:
                log.warning("Se agotó el tiempo total antes de probar '%s'", combo)
                break
            try:
                reply = self.gateway.complete(combo, messages, read_timeout=max(remaining, 1))
            except GatewayError as exc:
                log.warning("Falla el modelo '%s': %s (%s)", combo, exc.code, exc.detail)
                attempts.append({"model": combo, "ok": False, "error": exc.code})
                errors.append(exc)
                if exc.fatal:
                    break
                continue
            attempts.append({"model": combo, "ok": True})
            if len(attempts) > 1:
                log.info("Fallback correcto: respondió '%s' tras %d fallo(s)", combo, len(attempts) - 1)
            return Generation(
                reply=reply, model=combo, task=decision.task, confidence=decision.confidence,
                mode=decision.mode, latency_ms=int((time.monotonic() - started) * 1000),
                fallback=len(attempts) > 1, attempts=attempts, scores=decision.scores,
            )

        codes = {e.code for e in errors} or {"timeout"}
        code = next((c for c in _ERROR_PRIORITY if c in codes), "provider_error")
        raise AllModelsFailed(code, attempts)
