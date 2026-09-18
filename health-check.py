@app.get("/health")
async def health():
    return {"status": "ok"}