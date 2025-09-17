from django.shortcuts import render
from django.http import JsonResponse
from openai import OpenAI
import os
from django.http import HttpResponse

def index(request):
    return HttpResponse("Hello World! これはトップページです。")

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def generate_question(request):
    word = request.GET.get("word", None)
    if not word:
        return JsonResponse({"error": "word is required"}, status=400)

    prompt = f"次の単語を使った問題文を1つ作ってください: {word}"

    response = client.chat.completions.create(
        model="gpt-4o-mini",  # 軽量モデルで十分
        messages=[
            {"role": "system", "content": "あなたは教育用の問題作成アシスタントです。"},
            {"role": "user", "content": prompt},
        ],
    )

    question = response.choices[0].message.content.strip()
    return JsonResponse({"word": word, "question": question})
