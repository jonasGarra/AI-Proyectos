from router.classifier import TaskClassifier

class SmartRouter:
    def __init__(self):
        self.default_model = "deepseek-chat"
        self.coding_model = "claude-3-5-sonnet"
        self.heavy_model = "gpt-4o"
        self.classifier = TaskClassifier()

    def route(self, prompt: str, task_type: str = "auto") -> str:
        # Si está en auto, el clasificador decide
        if task_type == "auto":
            task_type = self.classifier.classify(prompt)
            
        if task_type == "coding":
            return self.coding_model
        elif task_type == "complex":
            return self.heavy_model
        else:
            return self.default_model
