from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from openai import OpenAI
import os
import re

def index(request):
    return HttpResponse("Hello World! これはトップページです。")

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def generate_question_4choice(request):
    word = request.GET.get("word", None)
    if not word:
        return JsonResponse({"error": "word is required"}, status=400)

    # 明確なフォーマット指示を与える（モデルが必ず A/B/C/D を別行で出すように）
    prompt = f"""
次の単語を使った教育用の問題を1つ作ってください。
問題の形式は四択問題にしてください。
答えが「{word}」となるようにしてください（正解の選択肢の本文が {word} になること）。
選択肢は必ず **4つ** 用意し、次のように**別々の行**でラベルを付けて出力してください：

選択肢:
A: ...
B: ...
C: ...
D: ...

正解はラベル（A/B/C/D）で示してください（例: 正解: A）。
また最後に解説を1〜3行で書いてください。

出力フォーマットの例（厳守してください）:
問題: ...
選択肢:
A: ...
B: ...
C: ...
D: ...
正解: A
解説: ...
"""

    # API 呼び出し（必要に応じて temperature=0, max_tokens を調整）
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "あなたは教育用の問題作成アシスタントです。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.0,
        max_tokens=400,
    )

    content = response.choices[0].message.content.strip()

    # --- パース処理（堅牢にする） ---
    lines = content.splitlines()
    current = None
    sections = {"question": [], "options": [], "answer": [], "explanation": []}

    for raw in lines:
        s = raw.strip()
        if not s:
            continue

        # ヘッダ検出（問題, 選択肢, 正解, 解説）
        if re.match(r'^(問題|問|Q)[:：\s]', s):
            current = "question"
            parts = re.split(r'[:：]', s, 1)
            if len(parts) > 1 and parts[1].strip():
                sections[current].append(parts[1].strip())
        elif re.match(r'^(選択肢)[:：]?', s):
            current = "options"
            # 選択肢ヘッダに続いて同じ行に選択肢群があるかチェック
            parts = re.split(r'[:：]', s, 1)
            if len(parts) > 1 and parts[1].strip():
                sections[current].append(parts[1].strip())
        elif re.match(r'^[A-D][\)\.\）．:：\s]', s) or re.match(r'^[Ａ-Ｄ][\)\.\．:：\s]', s):
            # 直接 "A: りんご" などの行
            current = "options"
            sections[current].append(s)
        elif re.match(r'^(正解)[:：]', s):
            current = "answer"
            parts = re.split(r'[:：]', s, 1)
            if len(parts) > 1:
                sections[current].append(parts[1].strip())
        elif re.match(r'^(解説)[:：]', s):
            current = "explanation"
            parts = re.split(r'[:：]', s, 1)
            if len(parts) > 1:
                sections[current].append(parts[1].strip())
        else:
            # ヘッダが直前に出ていた場合は続き行として格納
            if current:
                sections[current].append(s)
            else:
                # ヘッダがない場合に備えて最初の行を問題と見做す（フォールバック）
                if not sections["question"]:
                    sections["question"].append(s)
                else:
                    # それ以外は無視または raw に残す
                    sections.setdefault("raw_tail", []).append(s)

    # 選択肢の正規化関数
    def normalize_options(opt_lines):
        opts = []
        for item in opt_lines:
            # 分割：改行、スラッシュ、カンマ、全角読点などで分ける
            parts = re.split(r'\n|/|、|,', item)
            for p in parts:
                tok = p.strip()
                if not tok:
                    continue
                # 先頭のラベル（A:, A. など）を取り除く
                tok = re.sub(r'^[A-DＡ-Ｄ][\)\.\）．:：\s]*', '', tok).strip()
                # さらに "A:りんご B:みかん" のような一行塊があれば A/B/C/D で分割
                subparts = re.split(r'(?=[A-D][\)\.\．:：\s])', tok)
                for sp in subparts:
                    sp2 = sp.strip()
                    if not sp2:
                        continue
                    # 削除したラベルが残る場合さらに除去
                    sp2 = re.sub(r'^[A-D][\)\.\）．:：\s]*', '', sp2).strip()
                    if sp2 and sp2 not in opts:
                        opts.append(sp2)
        return opts

    options = normalize_options(sections["options"])

    # フォールバック：content 全体から "A: ... B: ... C: ... D: ..." を抽出してみる
    if len(options) < 4:
        matches = re.findall(r'(?:A|B|C|D)[\)\.\．:：\s]*([^A-D]+)(?=(?:[A-D][\)\.\．:：\s]*|$))', content)
        matches = [m.strip() for m in matches if m.strip()]
        if len(matches) >= 4:
            options = matches[:4]

    # question, answer, explanation を整形
    question = " ".join(sections["question"]).strip()
    explanation = " ".join(sections["explanation"]).strip()
    answer_raw = " ".join(sections["answer"]).strip()

    # answer が A/B/C/D 以外（選択肢の本文＝wordになっている）場合は対応するラベルに変換
    answer = ""
    if answer_raw:
        # 既にラベルなら使う
        m = re.match(r'^[A-D]$', answer_raw.strip().upper())
        if m:
            answer = answer_raw.strip().upper()
        else:
            # 本文で与えられた可能性：options の何番目か探す
            for idx, opt in enumerate(options):
                if answer_raw == opt or answer_raw in opt or opt in answer_raw:
                    answer = ["A", "B", "C", "D"][idx]
                    break

    # さらにフォールバック：answer 空でも word が options にあるなら自動でセット
    if not answer and word and options:
        for idx, opt in enumerate(options):
            if word == opt or word in opt or opt in word:
                answer = ["A", "B", "C", "D"][idx]
                break

    result = {
        "word": word,
        "question": question,
        "options": options,            # 配列で返す
        "answer": word,
        "explanation": explanation,
        #"raw_model": content           # デバッグ用に生テキストも返す
    }

    return JsonResponse(result)


def generate_question(request):
    word = request.GET.get("word", None)
    if not word:
        return JsonResponse({"error": "word is required"}, status=400)

    prompt = f"""
    次の単語を使った教育用の問題を1つ作ってください。
    問題の形式は一問一答問題にしてください。
    さらに、その問題は{word}が答えとなるようにしてください。
    簡単な解説も出力してください。

    単語: {word}

    出力フォーマット:
    問題: ...
    正解: ...
    解説: ...
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",  # 軽量モデル
        messages=[
            {"role": "system", "content": "あなたは教育用の問題作成アシスタントです。"},
            {"role": "user", "content": prompt},
        ],
    )

    content = response.choices[0].message.content.strip()

    # 念のため改行で分割してJSONに整理
    lines = content.split("\n")
    result = {"word": word}
    for line in lines:
        if line.startswith("問題:"):
            result["question"] = line.replace("問題:", "").strip()
        elif line.startswith("正解:"):
            result["answer"] = line.replace("正解:", "").strip()
        elif line.startswith("解説:"):
            result["explanation"] = line.replace("解説:", "").strip()

    return JsonResponse(result)

def generate_question_hole(request):
    word = request.GET.get("word", None)
    if not word:
        return JsonResponse({"error": "word is required"}, status=400)

    prompt = f"""
    次の単語を使った教育用の問題を1つ作ってください。
    問題の形式は穴埋め問題にしてください。
    さらに、その問題の正解と簡単な解説も出力してください。

    単語: {word}

    出力フォーマット:
    問題: ...
    正解: ...
    解説: ...
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",  # 軽量モデル
        messages=[
            {"role": "system", "content": "あなたは教育用の問題作成アシスタントです。"},
            {"role": "user", "content": prompt},
        ],
    )

    content = response.choices[0].message.content.strip()

    # 念のため改行で分割してJSONに整理
    lines = content.split("\n")
    result = {"word": word}
    for line in lines:
        if line.startswith("問題:"):
            result["question"] = line.replace("問題:", "").strip()
        elif line.startswith("正解:"):
            result["answer"] = line.replace("正解:", "").strip()
        elif line.startswith("解説:"):
            result["explanation"] = line.replace("解説:", "").strip()

    return JsonResponse(result)
