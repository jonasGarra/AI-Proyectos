class SmartRouter:
    def __init__(self):
        # Aquí definiremos los modelos disponibles y sus pesos/prioridades
        self.default_model = "deepseek-chat"
        self.coding_model = "claude-3-5-sonnet"
        self.heavy_model = "gpt-4o"

    def route(self, prompt: str, task_type: str = "general") -> str:
        """
        Decide qué modelo utilizar basándose en el tipo de tarea
        """
        if task_type == "coding":
            return self.coding_model
        elif task_type == "complex":
            return self.heavy_model
        else:
            return self.default_model
