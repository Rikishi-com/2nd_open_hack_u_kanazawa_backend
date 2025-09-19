from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from openai import OpenAI
import os
import re
import json
from django.views.decorators.csrf import csrf_exempt

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


def generate_question(request, word, question_texts=None):
    base_question = question_texts[0] if question_texts else None
    

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
    # result = {"word": word}
    # for line in lines:
    #     if line.startswith("問題:"):
    #         result["question"] = line.replace("問題:", "").strip()
    #     elif line.startswith("正解:"):
    #         result["answer"] = line.replace("正解:", "").strip()
    #     elif line.startswith("解説:"):
    #         result["explanation"] = line.replace("解説:", "").strip()

    result = {}
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("問題:") or line.startswith("問題："):
            result["問題文"] = line.split(":", 1)[1].strip()
        elif line.startswith("解説:") or line.startswith("解説："):
            result["解説"] = line.split(":", 1)[1].strip()

    return JsonResponse(result)

def generate_question_hole(request, word, question_texts=None):

    base_question = question_texts[0] if question_texts else None
    
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
    # result = {"word": word}
    # for line in lines:
    #     if line.startswith("問題:"):
    #         result["question"] = line.replace("問題:", "").strip()
    #     elif line.startswith("正解:"):
    #         result["answer"] = line.replace("正解:", "").strip()
    #     elif line.startswith("解説:"):
    #         result["explanation"] = line.replace("解説:", "").strip()

    result = {}
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("問題:") or line.startswith("問題："):
            result["問題文"] = line.split(":", 1)[1].strip()
        elif line.startswith("解説:") or line.startswith("解説："):
            result["解説"] = line.split(":", 1)[1].strip()

    return JsonResponse(result)

@csrf_exempt
def generate_workbook_for_q_and_a(request):
    if request.method !="POST":
        return JsonResponse({"error":"POST method is not allowed"},status=405)
    
    try:
        data = json.loads(request.body)
        # "解答"キーの値（単語リスト）を取得。存在しない場合は空のリストを返す
        answer_list = data.get("解答", [])
        pattern = data.get("pattern",None)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    
    if not answer_list:
        return JsonResponse({"error": "`解答` key with a list of words is required"}, status=400)
    
    prompt = f"""
    次の複数の単語に関する問題文，及び解説を作成してください．
    解答形式は以下のようにしてください．それ以外の文字は完全に必要ありません．
    パターンによって問題の種別を変えてください．パターンには”1問1答”,”穴埋め”の2種類が存在します．

    単語群：{answer_list}
    パターン:{pattern}

    ```
    問題文:[生成文]
    解説:[生成文]
    ---
    問題文:[生成文]
    解説:[生成文]
    ```

    例(パターン:1問1問)
    送信される単語群
    ["光合成","関ヶ原の戦い","平等院鳳凰堂"]

    生成する解答
    ```
    問題文:植物が二酸化炭素と水から有機物をつくる反応を何という？
    解説:主に葉緑体で行われ、光エネルギーを化学エネルギーに変換する。副産物として酸素を放出する。
    ---
    問題文:1600年に東軍と西軍が激突し、江戸幕府成立の契機となった戦いは何？
    解説:徳川家康率いる東軍が勝利し、1603年の征夷大将軍就任へとつながった。
    ---
    問題文:京都・宇治にある、藤原頼通が建立した阿弥陀堂建築の代表は何？
    解説:阿弥陀如来像と極楽浄土を表現した庭園で知られる。10円硬貨のデザインでも有名。
    ```

    例(パターン:穴埋め)
    送信される単語群
    ["鎖国","朱印船貿易"]

    生成する解答
    ```
    問題文:江戸幕府が対外関係を厳しく制限した政策は（ ）と呼ばれる。
    解説:例外としてオランダ・中国との交易は長崎出島で継続。
    ---
    問題文:江戸初期、幕府が発行した公的な許可状を持つ船によって行われた海外交易を（ ）という。
    解説:東南アジア方面との貿易で活発だった。
    ```
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",  # 軽量モデル
        messages=[
            {"role": "system", "content": "あなたは教育用の問題作成アシスタントです。"},
            {"role": "user", "content": prompt},
        ],
    )

    content = response.choices[0].message.content.strip()

    return_array = []

    qa_blocks = content.split('---')

    # 2. 分割した各ブロックを処理する
    for block in qa_blocks:
        block = block.strip()  # 前後の余分な空白や改行を削除
        if not block:
            continue  # 空のブロックはスキップ

        question = ""
        explanation = ""

        # 3. ブロックをさらに改行で分割し、問題文と解説を探す
        lines = block.split('\n')
        for line in lines:
            if line.startswith("問題文:"):
                question = line.replace("問題文:", "").strip()
            elif line.startswith("解説:"): # プロンプトの指示通り「解説:」で探す
                explanation = line.replace("解説:", "").strip()

        # 4. 問題文と解説の両方が見つかった場合のみリストに追加
        if question and explanation:
            # 値を { } で囲まず、直接指定する
            return_array.append({
                "問題文": question,
                "解説": explanation
            })

    # 5. safe=False をつけて、リストをJSON配列として返す
    return JsonResponse(return_array, safe=False)

    






@csrf_exempt
def generate_question_4choice_api(request):
    if request.method !="POST":
        return JsonResponse({"error":"POST method is not allowed"},status=405)
    
    try:
        body = json.loads(request.body.decode("utf-8"))
        answer = body.get("解答")
        existing_questions = body.get("問題文",[])
        pattern = body.get("pattern")
    except Exception:
        return JsonResponse({"error":"Invalid JSON"},status=400)
    
    if not answer or not pattern:
        return JsonResponse({"error":"Answer and pattern are required"},status=400)
    prompt = f"""
あなたは教育用の問題作成アシスタントです。
与えられた単語を答えとする問題を1つ作成してください。

条件:
- 答えは必ず「{answer}」になること。
- 選択肢は必ず4つ用意してください（1つは正解、3つは誤答）。
- 問題文から答えが一意になるようにしてください。
- 出力フォーマットは厳守してください。
- 既存の問題文とは異なる新しい問題文を生成してください。
既存の問題文: {existing_questions}

問題形式の指定:
- {pattern} に従って問題を作成してください。
  - "1問1答" の場合: 通常の四択問題形式。
  - "穴埋め" の場合: 問題文の中に空欄（（ ））を入れて四択問題を作成。

出力フォーマット（必ず守ってください）:
問題: ...
選択肢:
A: ...
B: ...
C: ...
D: ...
正解: A
解説: ...
"""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": "あなたは教育用の問題作成アシスタントです。"},
                  {"role": "user", "content": prompt},
                  ],
    )

    raw_output = response.choices[0].message.content.strip()
    try:
        lines = raw_output.splitlines()
        question = next(line.replace("問題:", "").strip() for line in lines if line.startswith("問題:"))
        choices = [line.split(":")[1].strip() for line in lines if line.startswith(("A:", "B:", "C:", "D:"))]
        explanation = next(line.replace("解説:", "").strip() for line in lines if line.startswith("解説:"))
    except Exception:
        return JsonResponse({"error": "出力解析に失敗しました", "raw": raw_output}, status=500)

    return JsonResponse([
        {
            "問題文": question,
            "選択肢": choices,
            "解説": explanation
        }
    ], safe=False)
    
@csrf_exempt   
def generate_problem(request):
    
    if request.method != "POST":
        return JsonResponse({"error":" POST method is not allowed"}, status=405)
    
    try:
        body = json.loads(request.body)
        answer = body.get("解答")
        question_texts = body.get("問題文",[])
        pattern = body.get("pattern")
    except Exception:
        return JsonResponse({"error":"Invalid JSON"}, status=400)
        
    if not answer or not question_texts or not pattern:
        return JsonResponse({"error":"解答, 問題文, patternは必須です。"}, status=400)
    
    if pattern == "1問1答":
        return generate_question(request, word = answer, question_texts = question_texts)
    elif pattern == "穴埋め":
        return generate_question_hole(request, word = answer, question_texts = question_texts)
    else:
        return JsonResponse({"error":"Invalid pattern"}, status=400)

@csrf_exempt
def generate_4_choice_workbook_for_q_and_a(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST method is not allowed"}, status=405)

    try:
        body = json.loads(request.body.decode("utf-8"))
        answers = body.get("解答")  
        pattern = body.get("pattern") 
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    if not answers or not pattern:
        return JsonResponse({"error": "解答とpatternは必須です"}, status=400)

    results = []

    for answer in answers:
        prompt = f"""
あなたは教育用の問題作成アシスタントです。
与えられた単語を答えとする四択問題を1つ作成してください。

条件:
- 答えは必ず「{answer}」になること。
- 選択肢は必ず4つ用意してください（1つは正解、3つは誤答）。
- 問題文から答えが一意になるようにしてください。
- 出力フォーマットは厳守してください。

問題形式の指定:
- {pattern} に従って問題を作成してください。
  - "1問1答" の場合: 通常の四択問題形式。
  - "穴埋め" の場合: 問題文の中に空欄（（ ））を入れて四択問題を作成。

出力フォーマット（必ず守ってください）:
問題: ...
選択肢:
A: ...
B: ...
C: ...
D: ...
正解: A
解説: ...
"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "あなたは教育用の問題作成アシスタントです。"},
                {"role": "user", "content": prompt},
            ],
        )

        raw_output = response.choices[0].message.content.strip()

        try:
            lines = raw_output.splitlines()
            question = next(line.replace("問題:", "").strip() for line in lines if line.startswith("問題:"))
            choices = [line.split(":", 1)[1].strip() for line in lines if line.startswith(("A:", "B:", "C:", "D:"))]
            explanation = next(line.replace("解説:", "").strip() for line in lines if line.startswith("解説:"))
        except Exception:
            return JsonResponse({"error": "出力解析に失敗しました", "raw": raw_output}, status=500)

        results.append({
            "問題文": question,
            "選択肢": choices,
            "解説": explanation
        })

    return JsonResponse(results, safe=False)
