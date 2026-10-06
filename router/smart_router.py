from dataclasses import dataclass, field
from typing import Dict, List, Optional

from router.classifier import TaskClassifier

MODES = ("rapido", "pensativo", "ultra")
LOW_CONFIDENCE = 0.3


@dataclass
class RouteDecision:
    task: str
    confidence: float
    mode: str
    chain: List[str]                  # combos a probar, en orden (el primero es el elegido)
    reason: str = ""
    scores: Dict[str, float] = field(default_factory=dict)

    @property
    def model(self) -> str:
        return self.chain[0]


class SmartRouter:
    def __init__(self):
        # Combos de OmniRoute que ya usaba Kikos AI (no se inventa ninguno)
        self.combos = {
            "coding": "coding",
            "coding_agent": "coding-agent",
            "reasoning": "reasoning",
            "research": "research",
            "documents": "documents",
            "vision": "vision",
            "writing": "writing",
            "translation": "translation",
            "data": "data",
            "creative": "creative",
            "long_context": "long-context",
            "agent_tools": "agent-tools",
            "audio": "audio",
            "safety": "safety",
            "premium": "premium",
            "fast": "fast",
            "general": "general",
        }
        # Qué combo atiende cada intención cuando se busca calidad (modo Pensativo)
        self.intent_to_combo = {
            "chat": "fast",
            "coding": "coding",
            "data": "data",
            "math": "reasoning",
            "translation": "translation",
            "summary": "documents",
            "documents": "documents",
            "writing": "writing",
            "creative": "creative",
            "reasoning": "reasoning",
            "technical": "research",
            "research": "research",
            "general": "general",
        }
        self.classifier = TaskClassifier()
        self.long_context_chars = 20000

    def _combo_for(self, task: str) -> str:
        if task in self.combos:           # nombres antiguos: "coding", "fast", "long_context"...
            return self.combos[task]
        return self.combos[self.intent_to_combo.get(task, "general")]

    def _chain(self, quality: str, mode: str) -> List[str]:
        fast, general, premium = self.combos["fast"], self.combos["general"], self.combos["premium"]
        if mode == "rapido":
            chain = [fast, quality, general]
        elif mode == "ultra":
            chain = [premium, quality, general, fast]
        else:  # pensativo
            chain = [quality, general, fast]
        seen, unique = set(), []
        for combo in chain:
            if combo not in seen:
                seen.add(combo)
                unique.append(combo)
        return unique

    def plan(self, prompt: str, mode: str = "pensativo", task_type: str = "auto", input_length: int = 0,
             has_image: bool = False, previous_task: Optional[str] = None,
             has_attachments: bool = False) -> RouteDecision:
        mode = mode if mode in MODES else "pensativo"

        # Reglas duras: dependen de la capacidad, no de la preferencia del usuario
        if has_image:
            return RouteDecision("vision", 1.0, mode, [self.combos["vision"]], "imagen adjunta")
        if input_length > self.long_context_chars:
            return RouteDecision("long_context", 1.0, mode, [self.combos["long_context"]], "entrada muy larga")

        scores: Dict[str, float] = {}
        if task_type == "auto":
            result = self.classifier.analyze(prompt, previous_task, has_attachments)
            task, confidence, reason, scores = result.task, result.confidence, result.reason, result.scores
            if confidence < LOW_CONFIDENCE and task not in ("chat",):
                task, reason = "general", "confianza baja"
        else:
            task, confidence, reason = task_type, 1.0, "tarea indicada"

        chain = self._chain(self._combo_for(task), mode)
        return RouteDecision(task, confidence, mode, chain, reason, scores)

    def route(self, prompt: str, task_type: str = "auto", input_length: int = 0) -> str:
        """Compatibilidad con la versión anterior: devuelve solo el combo elegido."""
        return self.plan(prompt, "pensativo", task_type, input_length).model
