import requests
from ddgs import DDGS
from fastapi import FastAPI
from openai import OpenAI

app = FastAPI()

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key= "key"
)


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
def open_search(q:str):
    selected_model = "~openai/gpt-latest"

    response = client.chat.completions.create(
        model= selected_model,
        messages=[
            {
                "role" : "system",
                "content": "provide a consise response under 100 tokens"
            },
            {
                "role": "user",
                "content": q
            }
        ],
        max_tokens=100,
        temperature=0.5
    )
    return{"response": response.choices[0].message.content}
