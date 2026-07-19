import requests
from ddgs import DDGS
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def index():
    return{"name":"how are you"}
@app.get("/get")
def get_res(q:str):
    with DDGS() as ddgs:
        search_got = list(ddgs.text(q,max_results=5))
        links = [item["href"] for item in search_got]
    return{"query": q,
           "result": search_got
           
           }