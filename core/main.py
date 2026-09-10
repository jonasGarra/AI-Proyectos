from fastapi import FastAPI

app = FastAPI(title="Kikos AI Core", version="0.1.0")

@app.get("/health")
def health():
    return {"status": "ok", "service": "kikos-ai-core"}
