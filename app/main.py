from fastapi import FastAPI

app = FastAPI(title="Scribe POC py")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}