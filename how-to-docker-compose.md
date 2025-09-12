# DockerCompose

---

## 使い方
ymlファイルがあるディレクトリにいることを前提とする
まず初めに`.env`ファイルを同一ディレクトリに格納する
以下のコマンドを順番にコピペでok


```bash
docker compose build
docker compose up -d
docker compose exec web python manage.py migrate
```
- これだけでOK
  
## DATABASEの使用方法
上のコマンドを順に打つと，以下の２つのコンテナができる
- `django_app`
- `mysql_db`
このうち`mysql_db`がデータベースを司るコンテナなので，データベースではこちらを使う．

### コンテナに対話形式で入る方法
以下のコマンドを入力する

```bash
docker exec -it mysql_db bash
```
- こうするとコマンドラインでDBを扱うことができる

#### 補足
パスワードなど必要な情報は`.env`に書いてあるので参照すること

```bash
mysql -u user -p 
```
- DBコンテナのコマンドラインでこのコードを入力し，その後パスワードを入力することで**MySQL**に入ることができる

---

## Djangoの開発方法
`django_app`が**Django**を司るコンテナなので，データベースではこちらを使う．

### コンテナに対話形式で入る方法
以下のコマンドを入力する

```bash
docker exec -it django_app bash
```
- これで通常のように開発ができる

## コンテナの終了方法
以下のコマンド１つですべてのコンテナを終了させることができる．
しかし開発データなども飛ぶので，使い所があるかは自分次第

```bash
docker compose down
```
