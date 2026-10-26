# -*- coding: utf-8 -*-
"""bim_taiken.ipynb（BIM 体験ノートブック）を生成するスクリプト"""
import os
import sys

import nbformat
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "bim_taiken.ipynb")

with open(os.path.join(HERE, "minibim.py"), encoding="utf-8") as fh:
    LIB = fh.read()

cells = []
md = lambda s: cells.append(new_markdown_cell(s.strip("\n")))
code = lambda s: cells.append(new_code_cell(s.strip("\n")))

# ------------------------------------------------------------------
md(r"""
# BIM を体験しよう — コードで建物をつくる

このノートブックは、**BIM（Building Information Modeling）** の考え方を
「自分の手で動かして」理解するための体験教材です。
Revit や ArchiCAD のような本物の BIM ソフトは使わず、
Python で書いた **ミニ BIM**（部材 = 直方体 + 情報）で BIM の本質を体験します。

## 使い方
1. メニュー **「ランタイム」→「すべてのセルを実行」** を押す（初回は 1 分ほどかかります）
2. 上から順に読み進め、コードセルを実行しながら ▶ 3D モデルをマウスで回してみる
3. 「🧪 やってみよう」の指示に従ってコードを書き換えて再実行する

## この教材で体験すること

| 章 | テーマ | BIM のキーワード |
|---|---|---|
| 1 | CAD と BIM は何が違う？ | 線 vs オブジェクト、属性情報 |
| 2 | コードで建物をつくる | 部材（オブジェクト）、3D モデル |
| 3 | 「I」= 情報を使う | 属性検索、数量拾い、概算コスト（5D） |
| 4 | パラメトリック | 変更が全体に自動で伝わる |
| 5 | 干渉チェック | 設計調整、クラッシュディテクション |
| 6 | 4D シミュレーション | 工程 × 3D モデル |
| 7 | IFC で書き出す | 国際標準フォーマット、相互運用性 |

> **注意:** このノートブックの単価・原単位・工程日数はすべて **教材用の仮の数値** です。実務の数値ではありません。
""")

# ------------------------------------------------------------------
md(r"""
## 0. 準備

最初の 2 つのセルは、ライブラリのインストールと「ミニ BIM ライブラリ」の定義です。
中身を読まなくても授業は進められます（興味のある人は後で覗いてみてください）。
""")

code(r"""
# IFC ファイルを扱うライブラリ IfcOpenShell をインストール（Google Colab には入っていないため）
try:
    import ifcopenshell
except ImportError:
    import subprocess, sys
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "ifcopenshell"], check=True)
    import ifcopenshell
print("IfcOpenShell", ifcopenshell.version, "の準備ができました")
""")

code("# ▼ ミニ BIM ライブラリ（このセルを実行すると Wall, Slab, Window ... などの部材クラスが使えるようになります）\n" + LIB + "\nprint('ミニ BIM ライブラリを読み込みました ✅')")

# ------------------------------------------------------------------
md(r"""
---
## 第 1 章　CAD と BIM は何が違う？

まず、従来の **2D CAD** の図面を描いてみます。コンピュータから見ると、CAD 図面は「線の集まり」です。
""")

code(r"""
import plotly.graph_objects as go

fig = go.Figure()
# 外壁の線（CAD では "線" でしかない）
for (x1, y1, x2, y2) in [(0, 0, 8, 0), (8, 0, 8, 6), (8, 6, 0, 6), (0, 6, 0, 0)]:
    fig.add_trace(go.Scatter(x=[x1, x2], y=[y1, y2], mode="lines", line=dict(color="black", width=3), showlegend=False))
# 水色の太い線 … これは窓？ それとも扉？ 人間は読み取れるが、コンピュータには「水色の線」でしかない
fig.add_trace(go.Scatter(x=[2.5, 4], y=[0, 0], mode="lines", line=dict(color="deepskyblue", width=10), name="水色の線（？）"))
fig.update_layout(title="2D CAD の図面：ここにあるのは『線』だけ", width=520, height=420,
                  xaxis=dict(scaleanchor="y", title="X [m]"), yaxis=dict(title="Y [m]"))
fig.show()
""")

md(r"""
この図面に対して、コンピュータに次の質問をしても答えられません。

- 「この建物に窓はいくつある？」
- 「コンクリートは何 m³ 必要？」
- 「南向きの窓の面積の合計は？」

人間が図面を読んで数えるしかありません。線には **意味（情報）** がないからです。

### BIM では「壁」というオブジェクトを置く

BIM では線ではなく、**壁・窓・床などの部材（オブジェクト）** を置きます。
部材は「形」だけでなく「情報」を持っています。
""")

code(r"""
# BIM 的に「壁」を 1 枚つくる： 始点 (0,0) → 終点 (8,0)、高さ 3m、厚さ 0.2m
wall = Wall("南の壁", start=(0, 0), end=(8, 0), height=3.0, thickness=0.2,
            material="コンクリート", 方位="南", 耐火="1時間", 仕上げ="塗装")

# この壁に、窓を 1 つ取り付ける（壁の始点から 3m の位置に、幅 1.5m × 高さ 1.2m、床から 0.9m）
window = Window("リビングの窓", wall, offset=3.0, width=1.5, height=1.2, sill=0.9, メーカー="A社")

# 壁が持っている「情報」を見てみる
wall.info()
print()
window.info()
""")

md(r"""
### 同じ壁を 3D で見てみる

CAD では「線」だったものが、BIM では **厚みと高さを持った「もの」** として置かれています。
窓は壁に取り付いていて、壁の体積からは窓の分が自動で差し引かれています。

> 3D ビューは **マウスのドラッグで回転・ホイールでズーム** できます。
> 壁や窓に **カーソルを乗せる** と、さっき `info()` で見た情報がそのまま表示されます。
""")

code(r"""
demo = Building("壁 1 枚のモデル")
demo.add(wall, window)
demo.show(title="BIM の壁：形と情報を持ったオブジェクト（カーソルを乗せると情報が出ます）", height=450).show()

print("壁の体積（窓の分を差し引いた正味）:", round(wall.volume, 3), "m3")
print("壁の見付面積（窓の分を差し引いた正味）:", round(wall.area, 2), "m2")
""")

md(r"""
> 🧪 **やってみよう**
> - 2 つ上のセルで `thickness=0.2` を `0.3` に変えて再実行し、このセルも再実行 → 3D の壁が厚くなり、体積・重量・費用も変わる
> - `材料="木材"` にしてみる（登録済みの材料: コンクリート / 鉄骨 / 木材 / ガラス / 鋼板）
> - `耐火="2時間"` のように、自分で好きな属性を追加できる（キーワード引数は何でも OK）
>
> **ポイント:** 壁は「形（幾何）」と「情報（属性）」の両方を持ちます。体積や費用は形から **自動で計算** されます。
> これが BIM の "I"（Information）です。
""")

# ------------------------------------------------------------------
md(r"""
---
## 第 2 章　コードで建物をつくる

部材を組み合わせて建物をつくります。ここでは `build_house()` という関数で
「基礎スラブ + 4 枚の壁 + 窓 4 つ + 玄関扉 + 屋根」の小さな家を自動生成します。

> 3D ビューは **マウスのドラッグで回転・ホイールでズーム** できます。部材にカーソルを乗せると情報が表示されます。
""")

code(r"""
house = build_house(length=8, width=6, floors=1)   # 間口 8m × 奥行 6m の平屋
print(f"部材数: {len(house)}")
house.show(title="BIM 体験ハウス（マウスで回転できます）").show()
""")

md(r"""
### 建物は「部材のデータベース」

BIM モデルの正体は、**部材の一覧表（データベース）** です。表にして眺めてみましょう。
""")

code(r"""
df = house.to_dataframe()
df
""")

md(r"""
部材一覧は普通の表なので、**CSV に書き出して Excel で開く** こともできます。
BIM ソフトの「集計表を Excel に出す」機能と同じことをしています。
""")

code(r"""
csv_path = "bim_taiken_house.csv"
df.to_csv(csv_path, encoding="utf-8-sig")   # utf-8-sig にすると Excel で開いても文字化けしない
print(f"{csv_path} に {len(df)} 行を書き出しました")

# Google Colab なら、自分の PC にダウンロードできます（画面左のフォルダアイコンからも取り出せます）
try:
    from google.colab import files
    files.download(csv_path)
except ImportError:
    print("（Colab 以外の環境ではダウンロードはスキップされます）")
""")

md(r"""
> 🧪 **やってみよう**
> - `build_house(length=12, width=8, floors=2)` のように引数を変えて、2 階建てや大きな家にしてみる
> - CSV を Excel で開き、「種別」でフィルタして窓だけを表示したり、「概算費用[円]」の合計を出したりしてみる
> - 自分で部材を追加してみる（例: `house.add(Column("柱1", x=4, y=3, height=3.0, width=0.4))` → `house.show().show()`）
""")

# ------------------------------------------------------------------
md(r"""
---
## 第 3 章　「I」= 情報を使う（数量拾い・概算コスト）

部材が情報を持っているので、第 1 章でできなかった質問に **コンピュータが答えられます**。
pandas の `query()` を使って、モデルに質問してみましょう。
""")

code(r"""
df = house.to_dataframe()

print("Q1. 窓はいくつある？")
print("  →", len(df[df["種別"] == "窓"]), "個")

print("Q2. 南向きの窓の面積の合計は？（日射・省エネ検討に使う）")
print("  →", df.query('種別 == "窓" and 方位 == "南"')["面積[m2]"].sum(), "m2")

print("Q3. 耐火 1 時間が求められる壁はどれ？")
print("  →", df.query('種別 == "壁" and 耐火 == "1時間"')["名前"].tolist())

print("Q4. A 社製の窓はいくつ？（発注・メンテナンスに使う）")
print("  →", len(df.query('メーカー == "A社"')), "個")
""")

md(r"""
### 数量拾い（Quantity Takeoff）と概算コスト（5D）

従来は図面から人が手で拾っていた **コンクリート量・型枠面積・鉄筋量** が、モデルから一瞬で集計できます。
さらに単価を掛ければ概算コストになります（これを 3D + 工程 + コスト で **5D BIM** と呼びます）。
""")

code(r"""
import plotly.express as px

print("■ 種別・材料ごとの数量")
display(house.quantity_takeoff())

print("\n■ コンクリート工事の概算数量（型枠・鉄筋は原単位による概算）")
display(house.concrete_summary())

print(f"\n■ 概算工事費（教材用の仮単価）: {house.total_cost():,.0f} 円")

qt = house.quantity_takeoff().reset_index()
px.bar(qt, x="種別", y="概算費用[円]", color="材料", title="種別ごとの概算費用", height=380).show()
""")

md(r"""
> 🧪 **やってみよう**
> - `MATERIALS["コンクリート"]["unit_price"] = 50_000` と単価を変えてから上のセルを再実行 → 総額はいくら増える？
> - 窓を 1 つ追加して（`house.add(Window("追加窓", house.find("1F 西壁"), offset=3, width=1.0, height=1.0))`）、ガラスの数量が増えることを確認する
""")

# ------------------------------------------------------------------
md(r"""
---
## 第 4 章　パラメトリック — 変更が全体に伝わる

2D CAD では「壁の厚さを変える」と、平面図・断面図・数量表・見積を **人が一つずつ直す** 必要があります。
BIM では部材のパラメータを変えると、**モデル・数量・コストが自動で更新** されます。

まず、設計案をいくつか並べて比較してみましょう。
""")

code(r"""
import pandas as pd

cases = {
    "案A: 平屋 8×6m 壁厚20cm": dict(length=8, width=6, floors=1, wall_thickness=0.2),
    "案B: 平屋 8×6m 壁厚30cm": dict(length=8, width=6, floors=1, wall_thickness=0.3),
    "案C: 2階建 8×6m":          dict(length=8, width=6, floors=2, wall_thickness=0.2),
    "案D: 平屋 12×8m":          dict(length=12, width=8, floors=1, wall_thickness=0.2),
}
models, rows = {}, []
for name, kw in cases.items():
    b = build_house(**kw)
    models[name] = b
    s = b.concrete_summary()
    rows.append({"設計案": name, "部材数": len(b), "コンクリート[m3]": s["コンクリート[m3]"],
                 "型枠[m2]": s["型枠[m2]"], "概算費用[万円]": round(b.total_cost() / 1e4)})
comparison = pd.DataFrame(rows).set_index("設計案")
comparison
""")

md(r"""
表だけでは分かりにくいので、4 つの案を **同じ縮尺で 3D に並べ**、数量とコストを **グラフで比較** してみます。
""")

code(r"""
# 4 案を同じ縮尺で並べて表示（それぞれ回転できます）
show_side_by_side(models).show()
""")

code(r"""
import plotly.graph_objects as go
from plotly.subplots import make_subplots

fig = make_subplots(rows=1, cols=2, subplot_titles=("コンクリート量 [m3]", "概算費用 [万円]"))
fig.add_trace(go.Bar(x=comparison.index, y=comparison["コンクリート[m3]"], text=comparison["コンクリート[m3]"],
                     marker_color="#8d9aa5"), row=1, col=1)
fig.add_trace(go.Bar(x=comparison.index, y=comparison["概算費用[万円]"], text=comparison["概算費用[万円]"],
                     marker_color="#ffb300"), row=1, col=2)
fig.update_traces(textposition="outside")
fig.update_layout(title="設計案ごとの数量とコスト", showlegend=False, height=420, margin=dict(l=0, r=0, t=60, b=0))
fig.show()
""")

md(r"""
> 💬 **考えてみよう:** 案 B（壁厚 +10cm）と案 C（2 階建て）では、コンクリート量と費用はどれくらい違う？
> 延床面積あたりの費用で比べると、どの案が有利だろう？

### スライダーで設計を動かす

下のセルの右側に表示される **スライダーを動かしてから、セルを ▶ 実行** してください（Google Colab のフォーム機能）。
建物が作り直され、3D モデル・数量・コストが更新されます。基準案（平屋 8×6m、壁厚 20cm）との比較グラフも出ます。

> Colab 以外の環境ではスライダーは出ないので、数値を直接書き換えて実行してください。
""")

code(r"""
# ===== スライダーを動かしてから、このセルを ▶ 実行してください =====
間口 = 8     #@param {type:"slider", min:4, max:16, step:1}
奥行 = 6     #@param {type:"slider", min:4, max:12, step:1}
階数 = 1     #@param {type:"slider", min:1, max:4, step:1}
壁厚 = 0.2   #@param {type:"slider", min:0.1, max:0.5, step:0.05}

import plotly.graph_objects as go
from plotly.subplots import make_subplots

base = build_house(name="基準案")                                  # 平屋 8×6m 壁厚 20cm
now = build_house(length=間口, width=奥行, floors=階数, wall_thickness=壁厚,
                  name=f"現在の案: {間口:g}×{奥行:g}m {階数}階建て 壁厚{壁厚 * 100:.0f}cm")

s0, s1 = base.concrete_summary(), now.concrete_summary()
print(f"部材数 {len(now)} / コンクリート {s1['コンクリート[m3]']} m3 / 型枠 {s1['型枠[m2]']} m2 / 概算費用 {now.total_cost():,.0f} 円")
print(f"基準案との費用差: {now.total_cost() - base.total_cost():+,.0f} 円")

now.show(height=450).show()

metrics = {"コンクリート [m3]": (s0["コンクリート[m3]"], s1["コンクリート[m3]"]),
           "型枠 [m2]": (s0["型枠[m2]"], s1["型枠[m2]"]),
           "概算費用 [万円]": (round(base.total_cost() / 1e4), round(now.total_cost() / 1e4))}
fig = make_subplots(rows=1, cols=3, subplot_titles=list(metrics))
for i, (label, (v0, v1)) in enumerate(metrics.items(), start=1):
    fig.add_trace(go.Bar(x=["基準案", "現在の案"], y=[v0, v1], text=[v0, v1], textposition="outside",
                         marker_color=["#8d9aa5", "#ffb300"]), row=1, col=i)
fig.update_layout(title="基準案との比較", showlegend=False, height=380, margin=dict(l=0, r=0, t=60, b=0))
fig.show()
""")

md(r"""
> 💬 **考えてみよう:** 2D CAD で「全部の壁を 10cm 厚くして」と言われたら、何枚の図面と何個の表を直す必要があるでしょう？
> BIM では `wall_thickness` を変えるだけです。これが **パラメトリック** の威力です。
""")

# ------------------------------------------------------------------
md(r"""
---
## 第 5 章　干渉チェック（クラッシュディテクション）

建築・構造・設備は別々の担当者が設計します。
図面を重ねて目で確認していた時代は、現場で「ダクトが梁にぶつかる！」という手戻りが頻発しました。
BIM では、モデル同士の **干渉を自動で検出** できます。

設備設計者になったつもりで、家の中に空調ダクトを通してみましょう。
""")

code(r"""
house = build_house(length=8, width=6, floors=1)

# 設備設計者がダクトを追加（西から東へ、高さ 2.3m を貫通）
duct = house.add(Duct("空調ダクト", start=(-1, 3), end=(9, 3), z=2.3, size=0.4))

clashes = house.check_clashes()
print(f"干渉 {len(clashes)} 件:")
for c in clashes:
    print("  ", c)

house.show(title="赤い箱 = 干渉している部分", clashes=clashes).show()
""")

md(r"""
ダクトが **西壁と東壁を貫通** していることが検出されました。
解決策として、壁に **スリーブ（貫通用の開口）** を設けます。これも「開口」という部材として追加します。
""")

code(r"""
# 前に入れたスリーブがあれば消してやり直す（このセルを何度も実行し直せるように）
for old in list(house.by_type("開口")):
    house.remove(old)

# ダクトの位置に合わせて壁にスリーブ（0.5m 角の開口）をあける
house.add(Opening("スリーブ（西）", house.find("1F 西壁"), offset=2.9, width=0.5, height=0.5, sill=2.05))
house.add(Opening("スリーブ（東）", house.find("1F 東壁"), offset=2.9, width=0.5, height=0.5, sill=2.05))

clashes = house.check_clashes()
print(f"干渉 {len(clashes)} 件  →  {'解決しました ✅' if not clashes else 'まだ残っています ❌'}")
for c in clashes:
    print("  ", c)
print("西壁の正味体積:", round(house.find("1F 西壁").volume, 3), "m3  （スリーブ分が差し引かれています）")

if clashes:   # 干渉が残っていれば、その部分を赤く表示
    house.show(title="赤い箱 = まだ干渉している部分", clashes=clashes).show()
""")

md(r"""
> 🧪 **やってみよう**
> - スリーブを `width=0.1, height=0.1` に小さくして再実行 → ダクト（0.4m 角）が収まらないので干渉が残り、はみ出した部分が赤く表示される
> - ダクトの高さ `z=2.3` を `z=0.5` に変えると、何と干渉する？（玄関扉の位置も確認してみよう）
> - 梁を追加して窓と干渉させてみる: `house.add(Beam("梁", start=(0, 0), end=(8, 0), z=1.5, width=0.3, depth=0.5))`
> - スリーブの位置をわざとずらして、干渉が「部分的に」残ることを確認する
""")

# ------------------------------------------------------------------
md(r"""
---
## 第 6 章　4D シミュレーション（3D + 時間）

部材に「いつ施工するか」という情報を付けると、**建物が建っていく様子をアニメーション** で確認できます。
施工順序の検討・工程説明・安全計画などに使われます。
""")

code(r"""
house = build_house(length=8, width=6, floors=2)
house.add(Duct("1F 空調ダクト", start=(0.5, 3), end=(7.5, 3), z=2.6, size=0.3))

schedule = house.plan_schedule(start_date="2026-04-01")   # 階ごと・種別ごとに順番に施工すると仮定
print(f"工期: {schedule['終了'].max() - schedule['開始'].min()}")
house.show_gantt().show()
""")

code(r"""
# セルを実行すると自動で再生されます。▶ 再生ボタンでもう一度見たり、スライダーで好きな日に止めたりできます
# （黄色 = 施工中、薄いグレー = 未着手）
house.show_4d().show()
""")

md(r"""
> 🧪 **やってみよう**
> - `plan_schedule(days={"壁": 10, "床": 5, "屋根": 4, "窓": 2, "扉": 1, "ダクト": 3})` のように日数を変えて工期がどう変わるか見る
> - 施工順序を変える: `plan_schedule(order=("床", "壁", "ダクト", "窓", "扉", "屋根"))` → ダクトを先に入れると何が起きる？
""")

# ------------------------------------------------------------------
md(r"""
---
## 第 7 章　IFC で書き出す — BIM の共通言語

BIM ソフトはメーカーごとに違いますが、**IFC（Industry Foundation Classes）** という国際標準（ISO 16739）の
ファイル形式でモデルを交換できます。私たちのミニ BIM モデルも IFC に書き出してみましょう。

IFC はテキストファイルなので、中身を人間が読むこともできます。
""")

code(r"""
house = build_house(length=8, width=6, floors=1)
house.add(Duct("空調ダクト", start=(0.5, 3), end=(7.5, 3), z=2.3, size=0.4))

path = house.to_ifc("bim_taiken_house.ifc")
print("書き出しました:", path)

print("\n■ IFC ファイルの先頭 25 行（STEP 形式のテキスト）")
with open(path, encoding="utf-8") as fh:
    for i, line in enumerate(fh):
        if i >= 25:
            break
        print(line.rstrip())
""")

md(r"""
### IFC を読み戻して、情報が保たれていることを確認する

書き出した IFC を IfcOpenShell で開き直します。壁の属性（プロパティセット）や、どの階に属するかという情報が
ファイルの中に残っています。**別の BIM ソフトで開いても同じ情報が読める** のが相互運用性です。
""")

code(r"""
import ifcopenshell
import ifcopenshell.util.element as ue

ifc = ifcopenshell.open("bim_taiken_house.ifc")
print("スキーマ:", ifc.schema)
print("プロジェクト:", ifc.by_type("IfcProject")[0].Name)
for cls in ["IfcWall", "IfcSlab", "IfcWindow", "IfcDoor", "IfcDuctSegment", "IfcOpeningElement"]:
    print(f"  {cls:<20}: {len(ifc.by_type(cls))} 個")

w = ifc.by_type("IfcWall")[0]
print("\n■", w.Name, "の情報")
print("  GlobalId :", w.GlobalId)
print("  所属する階:", ue.get_container(w).Name)
for pset_name, props in ue.get_psets(w).items():
    print(f"  {pset_name}:", {k: v for k, v in props.items() if k != "id"})
""")

code(r"""
# Google Colab なら、IFC ファイルを自分の PC にダウンロードできます
try:
    from google.colab import files
    files.download("bim_taiken_house.ifc")
except ImportError:
    print("（Colab 以外の環境ではこのセルはスキップされます）")
""")

md(r"""
### ダウンロードした IFC を BIM ビューアで開いてみよう

- **ブラウザで開く:** [3dviewer.net](https://3dviewer.net/) に .ifc ファイルをドラッグ＆ドロップ
- **無料ソフト:** [Bonsai (BlenderBIM)](https://bonsaibim.org/)、BIMvision、Solibri Anywhere など
- Revit / ArchiCAD などの商用 BIM ソフトでも「IFC を開く」で読み込めます

自分がコードで作った家が、本物の BIM ソフトで表示され、壁をクリックすると「耐火: 1時間」「メーカー: A社」といった
属性が出てくることを確認してみてください。
""")

# ------------------------------------------------------------------
md(r"""
---
## 演習課題

以下の課題に取り組んでみましょう。下のテンプレートをコピーして使ってください。

1. **自分の家をつくる:** `Wall / Slab / Roof / Column / Beam / Window / Door` を使って、間取りを自分で決めた家をつくる（2 階建て以上）
2. **情報を付ける:** 各部材に `耐火`、`仕上げ`、`メーカー`、`施工業者` などの属性を付け、`query()` で検索できることを確認する
3. **コストを比較:** 壁の材料を「コンクリート」と「木材」で作り分け、概算費用の差を求める
4. **干渉をつくって直す:** わざとダクトや梁が干渉するように配置し、`check_clashes()` で検出 → スリーブや位置変更で解消する
5. **4D:** 施工順序を考えて `plan_schedule()` の `order` と `days` を設定し、工期を見積もる
6. **IFC:** `to_ifc()` で書き出し、ビューアで開いてスクリーンショットを提出する

> 発展: `MATERIALS` に新しい材料（例: `"CLT"`）を追加して使ってみる／`Element` を継承して新しい部材（例: 階段）を作ってみる
""")

code(r"""
# ===== 演習テンプレート =====
my = Building("わたしの家")
t = 0.2   # 壁厚

my.add(Slab("基礎", (-t/2, -t/2), (10 + t, 7 + t), z=-0.2, thickness=0.2))
s = my.add(Wall("南壁", (-t/2, 0), (10 + t/2, 0), height=3.0, thickness=t, 方位="南"))
n = my.add(Wall("北壁", (-t/2, 7), (10 + t/2, 7), height=3.0, thickness=t, 方位="北"))
w = my.add(Wall("西壁", (0, t/2), (0, 7 - t/2), height=3.0, thickness=t, 方位="西"))
e = my.add(Wall("東壁", (10, t/2), (10, 7 - t/2), height=3.0, thickness=t, 方位="東"))
my.add(Window("南窓", s, offset=3, width=2.0, height=1.5, sill=0.8))
my.add(Door("玄関", s, offset=8, width=0.9, height=2.1))
my.add(Roof("屋根", (-t/2, -t/2), (10 + t, 7 + t), z=3.0, thickness=0.2))
# ここに部材を追加していく ...

print(f"部材数 {len(my)} / 概算費用 {my.total_cost():,.0f} 円 / 干渉 {len(my.check_clashes())} 件")
my.show().show()
""")

# ------------------------------------------------------------------
md(r"""
---
## まとめ

| 体験したこと | 本物の BIM では |
|---|---|
| 壁 = 直方体 + 属性 | 複雑な形状 + 数百の属性（Pset）、ファミリ／タイプの概念 |
| `to_dataframe()` で一覧表 | 集計表（スケジュール）、BIM データベース連携 |
| `check_clashes()` | Navisworks や Solibri などの干渉チェックツール |
| `plan_schedule()` + `show_4d()` | 4D シミュレーション（Synchro、Navisworks TimeLiner） |
| `to_ifc()` | IFC エクスポート、CDE（共通データ環境）での共有 |

**BIM の本質は「3D で描くこと」ではなく、「建物を情報のかたまりとして扱うこと」** です。
形だけでなく情報を持たせることで、数量・コスト・工程・干渉・維持管理まで、
同じモデルから引き出せるようになります。
""")

nb = new_notebook(cells=cells, metadata={
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python"},
    "colab": {"name": "bim_taiken.ipynb", "provenance": [], "toc_visible": True},
})
nbformat.write(nb, OUT)
print("wrote", OUT, "cells:", len(cells))
