# ベースイメージ
FROM python:3.12-slim

# 環境変数の設定
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# 作業ディレクトリ
WORKDIR /app

# システムパッケージを先にインストール
COPY install-packages.sh /tmp/install-packages.sh
RUN chmod +x /tmp/install-packages.sh
RUN /tmp/install-packages.sh

# Pythonパッケージをインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Djangoのプロジェクトを作成
RUN django-admin startproject hackathon .

# アプリケーションの全ファイルをコピー
COPY . .

# ポートを公開
EXPOSE 8000

CMD [ "python","manage.py","runserver","0.0.0.0:8000" ]