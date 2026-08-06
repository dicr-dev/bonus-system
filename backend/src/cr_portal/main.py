from fastapi import FastAPI

app = FastAPI(
    title="CR Integration Portal",
    version="0.1.0",
    description="Internal portal for CARGO.RUN integration department",
)


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "application": "CR Integration Portal",
        "status": "running",
        "version": "0.1.0",
    }