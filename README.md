# 文京区「今月の当番医」をStarSeekerに描画する

## 作業ディレクトリを作成

作業ディレクトリ(例: work)を作成する。

```
~/bunkyo-iryo-kyujitsutoban$ mkdir work
~/bunkyo-iryo-kyujitsutoban$ cd work
```
## PDFからデータを抽出

Excelのデータ取得機能でpdfからデータを抽出する。

* 文京区の[「今月の当番医」ページ](https://www.city.bunkyo.lg.jp/hoken/iryo/kyujithutouban/5gatsubun.html)からpdfをダウンロード
* Excelを開き、「データ」→「データの取得」→「ファイルから」→「PDFから」で該当するPDFを選択
* ナビゲーターで「Table<番号>」のうちデータの入っているテーブルを選択し「データ変換」を押す
* Power Queryエディターが開くので、メニューから「閉じて読み込む」を実行しexcelに読み込む
* 日付(A列)の行がほぼズレているので、PDFと比較しつつ、同じ日付となる最初の行に手で移動する。(元PDFがExcelセル結合をしていることによる限界)
* Excelを保存し、作業ディレクトリに移動

## データCSVを作成

[xlsx2csv](https://github.com/dilshod/xlsx2csv)でxlsxをcsvに変換する。

```
~/bunkyo-iryo-kyujitsutoban/work$ xlsx2csv -s 1 toban-ikashika2301.xlsx toban-ikashika2301.csv
```

## StarSeekerデータを作成

`convert.py`を使って[StarSeeker](https://github.com/c-3lab/StarSeeker)のoperatorで登録するデータを作成する。
なお、作業ディレクトリにできる`.geocode.cache`ファイルは同じ住所で何度もジオコーディングAPIを呼び出さないためのキャッシュであり、残しておくと次に実行するときの処理速度が速くなる。

```
~/bunkyo-iryo-kyujitsutoban/work$ ../convert.py --dir work --month 2301 toban-ikashika2301.csv
```

`point.csv`と`point_data.csv`が生成されているので適宜名前を変更する。

```
~/bunkyo-iryo-kyujitsutoban/work$ mv point.csv point.toban-ikashika2301.csv
~/bunkyo-iryo-kyujitsutoban/work$ mv point_data.csv point_data.toban-ikashika2301.csv
```
## `convert.py`コマンドラインオプション

### --encoding

`--encoding`はCSVファイルのエンコーディングを指定する。
デフォルト値は`utf-8`。

### --month

`--month`は年月を指定する。指定方法は以下のいずれかである。

* 月のみ: 1～2桁の数字の場合は、その年の月を表す。年末に近い場合に小さい月数を指定した場合は翌年になる。
* 年月(YYMMまたはYYYYMM): 4桁または6桁の数字の場合は、指定したとおりの年(先頭2桁または4桁)と月(末尾2桁)となる。

デフォルト値は現在の年月。

### --dir

`--dir`は作業ディレクトリを表す。作業ディレクトリには入力ファイルや出力ファイル、ジオコーディングのキャッシュファイルなどがおかれる。

### --tenant, --servicepath, --category

`--tenant`、`--servicepath`、`--category`はそれぞれStarSeekerのtenant (FIWAREのfiware-serviceヘッダ)、servicepath (FIWAREのfiware-servicepathヘッダ)、categoryを表す。デフォルト値はそれぞれ以下の通り。

* tenant: `NULL` ※英数字、アンダースコア('_')のみ
* servicepath: `NULL` ※英数字、アンダースコア('_')のみ、絶対パス指定('/'から始める)
* category: `文京区医療休日当番` ※メニューに出る文字列(日本語可)

## ライセンス

[MIT License](https://github.com/mkyutani/bunkyo-iryo-kyujitsutoban/blob/main/LICENSE)
