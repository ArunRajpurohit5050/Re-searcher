import requests
from ddgs import DDGS
from fastapi import FastAPI

app = FastAPI()

JINA_API_KEY = "key"

@app.get("/")
def index():
    return{"name":"how are you"}
@app.get("/get")
def get_res(q:str):
    with DDGS() as ddgs:
        search_got = list(ddgs.text(q,max_results=5))
        link = [item["href"] for item in search_got]
    return{"query": q,
           "links": link
           }

@app.get("/search")
def jina_search(link:str):
    url = f"https://s.jina.ai/{link}"

    headers = {
        "Authorization" : f"Bearer {JINA_API_KEY}",
        "accept": "application/json"
    }

    response = requests.get(url,headers=headers)
    data = response.json()

    return{
        "query": link,
        "resp" : data
    }