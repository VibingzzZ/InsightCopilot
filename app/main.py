from fastapi import FastAPI
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str


app = FastAPI(title="InsightCopilot")


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


if __name__ == "__main__":
    import uvicorn

    # 直接 `python app/main.py` 即可启动；reload 在 Windows 下易起子进程，Demo 场景关闭。
    uvicorn.run(app, host="127.0.0.1", port=8000)
