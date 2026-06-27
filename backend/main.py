from fastapi import FastAPI

app = FastAPI(title="AI Broadcast OS Backend")


@app.get("/health")
def health():
    return {"status": "ok"}
