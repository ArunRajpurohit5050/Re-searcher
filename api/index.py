import requests
from ddgs import DDGS
from fastapi import FastAPI
from google import genai
from google.genai import types

app = FastAPI()

client = genai.Client(api_key="key")


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
def gemini_search(q:str):
    response = client.models.generate_content(
        model = "gemini-3.5-flash",
        contents= q,
        config= types.GenerateContentConfig(
            system_instruction="use the user promt and search for top 5 websites about it",
            max_output_tokens= 100,
            temperature = 0.5,
        )

    )
    return response.text