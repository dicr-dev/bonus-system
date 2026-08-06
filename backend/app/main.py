from fastapi import FastAPI


app = FastAPI(
    title="CRMicro Integration Portal API",
    version="0.1.0",
)


@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "service": "bonus-system-backend",
    }