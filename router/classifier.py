class TaskClassifier:
    def __init__(self):
        self.coding_keywords = ["java", "python", "c#", "código", "programar", "crud", "docker", "html", "css", "sql", "script", "bug"]
        self.complex_keywords = ["arquitectura", "analiza este proyecto", "resumen detallado", "comparativa"]

    def classify(self, prompt: str) -> str:
        prompt_lower = prompt.lower()
        
        if any(keyword in prompt_lower for keyword in self.coding_keywords):
            return "coding"
        
        if any(keyword in prompt_lower for keyword in self.complex_keywords):
            return "complex"
        
        return "general"
