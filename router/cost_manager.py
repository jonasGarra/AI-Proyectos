class CostManager:
    def __init__(self):
        # Presupuesto ficticio (luego lo leeremos de una base de datos o API)
        self.monthly_budget = 5.0
        self.current_spend = 5.2  # Imagina que ya casi hemos gastado todo
        
        self.model_costs = {
            "claude-3-5-sonnet": "high",
            "gpt-4o": "high",
            "deepseek-chat": "low"
        }

    def can_afford(self, model: str) -> bool:
        """Devuelve False si el modelo es caro y estamos al límite del presupuesto"""
        cost_tier = self.model_costs.get(model, "low")
        if cost_tier == "high" and self.current_spend >= self.monthly_budget:
            return False
        return True
