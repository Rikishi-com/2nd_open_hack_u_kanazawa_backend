#!/bin/sh
# スクリプトの途中でエラーが発生したら、処理を中断するための設定（推奨）
set -e

# --- ここから実行したいコマンドを記述 ---

apt-get update

apt-get install -y curl git tree build-essential default-libmysqlclient-dev pkg-config

rm -rf /var/lib/apt/lists/*

pip install --upgrade pip

apt update

apt install tree



# --- ここまで ---

echo "パッケージのインストールが完了しました。"