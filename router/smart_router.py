from router.classifier import TaskClassifier
from router.cost_manager import CostManager

class SmartRouter:
    def __init__(self):
        self.default_model = "deepseek-chat"
        self.coding_model = "claude-3-5-sonnet"
        self.heavy_model = "gpt-4o"
        self.classifier = TaskClassifier()
        self.cost_manager = CostManager()

    def route(self, prompt: str, task_type: str = "auto") -> str:
        if task_type == "auto":
            task_type = self.classifier.classify(prompt)
            
        if task_type == "coding":
            selected = self.coding_model
        elif task_type == "complex":
            selected = self.heavy_model
        else:
            selected = self.default_model

        # FALLBACK: Si no nos lo podemos permitir, usamos el barato
        if not self.cost_manager.can_afford(selected):
            print(f"⚠️ AVISO: Presupuesto agotado para {selected}. Fallback a {self.default_model}")
            return self.default_model
            
        return selected
