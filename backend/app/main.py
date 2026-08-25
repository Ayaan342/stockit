from fastapi import FastAPI

app = FastAPI()


@app.get("/")
def root():
    return {"message": "StockIt API is running"}