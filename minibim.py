# =============================================================
#  minibim : 授業用のミニ BIM ライブラリ（教材用・簡略版）
#  - すべての部材を「直方体 + 属性情報」として扱います
#  - 本物の BIM ソフト(Revit, ArchiCAD など)の仕組みを体験するための模型です
# =============================================================
import itertools
import math
import uuid

import numpy as np
import pandas as pd
import plotly.graph_objects as go

# ---------- 材料マスタ（教材用の仮の値。実際の単価ではありません） ----------
MATERIALS = {
    "コンクリート": dict(color="#b5b5b5", unit_price=35_000,    density=2400),   # 円/m3, kg/m3
    "鉄骨":         dict(color="#5c7080", unit_price=1_800_000, density=7850),
    "木材":         dict(color="#c9a46a", unit_price=120_000,   density=500),
    "ガラス":       dict(color="#7fc8f8", unit_price=450_000,   density=2500),
    "鋼板":         dict(color="#ff8a65", unit_price=900_000,   density=7850),
}

# 種別ごとの表示色
TYPE_COLORS = {
    "壁": "#c2c2c2", "床": "#8d9aa5", "屋根": "#7a6e66", "柱": "#9c8c7a", "梁": "#a08f7f",
    "窓": "#7fc8f8", "扉": "#c9a46a", "ダクト": "#ff8a65", "開口": "#ffffff", "要素": "#dddddd",
}


# ============================================================
#  幾何ユーティリティ
# ============================================================
def _box_overlap(origin_a, size_a, origin_b, size_b, tol=1e-6):
    """2つの直方体の重なり部分を (origin, size) で返す。重ならなければ None。"""
    lo = np.maximum(origin_a, origin_b)
    hi = np.minimum(origin_a + size_a, origin_b + size_b)
    if np.all(hi - lo > tol):
        return lo, hi - lo
    return None


def _box_mesh(origin, size, inflate=0.0):
    """直方体 → (頂点座標, 三角形インデックス)。Plotly Mesh3d 用。"""
    o = np.asarray(origin, float) - inflate
    s = np.asarray(size, float) + 2 * inflate
    x0, y0, z0 = o
    x1, y1, z1 = o + s
    verts = np.array([
        [x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0],
        [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1],
    ])
    i = [0, 0, 4, 4, 0, 0, 1, 1, 2, 2, 3, 3]
    j = [1, 2, 5, 6, 1, 5, 2, 6, 3, 7, 0, 4]
    k = [2, 3, 6, 7, 5, 4, 6, 5, 7, 6, 4, 7]
    return verts, np.array([i, j, k])


_EDGES = [(0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4), (0, 4), (1, 5), (2, 6), (3, 7)]


# ============================================================
#  部材（Element）クラス
# ============================================================
class Element:
    """すべての部材の基本クラス: 『形(直方体)』+『情報(属性)』"""
    _ids = itertools.count(1)
    type_name = "要素"
    ifc_class = "IfcBuildingElementProxy"
    ifc_predefined = None

    def __init__(self, name, origin, size, material="コンクリート", **props):
        if material not in MATERIALS:
            raise ValueError(f"未登録の材料です: {material}  登録済み: {list(MATERIALS)}")
        self.id = next(Element._ids)
        self.guid = str(uuid.uuid4())
        self.name = name
        self.origin = np.asarray(origin, dtype=float)   # 最小コーナー (x, y, z)
        self.size = np.asarray(size, dtype=float)       # (幅dx, 奥行dy, 高さdz)
        self.material = material
        self.props = dict(props)                        # 自由に追加できる属性（耐火, 方位, メーカー...）
        self.level = int(props.get("階", 1))
        self.host = None        # 窓・扉・開口が取り付く壁
        self.openings = []      # この部材に開いた開口
        self.start_day = None   # 4D 用: 施工開始日（日数）
        self.duration = 1       # 4D 用: 施工日数

    # ---------- 幾何 ----------
    @property
    def end(self):
        return self.origin + self.size

    @property
    def center(self):
        return self.origin + self.size / 2

    @property
    def gross_volume(self):
        return float(np.prod(self.size))

    @property
    def volume(self):
        """開口を差し引いた正味体積 [m3]"""
        v = self.gross_volume
        for o in self.openings:
            ov = _box_overlap(self.origin, self.size, o.origin, o.size)
            if ov is not None:
                v -= float(np.prod(ov[1]))
        return v

    @property
    def weight(self):
        """重量 [kg]"""
        return self.volume * MATERIALS[self.material]["density"]

    @property
    def cost(self):
        """概算費用 [円]（教材用の仮単価）"""
        return self.volume * MATERIALS[self.material]["unit_price"]

    @property
    def color(self):
        return TYPE_COLORS.get(self.type_name, MATERIALS[self.material]["color"])

    # ---------- 情報 ----------
    def to_dict(self):
        d = {
            "ID": self.id, "名前": self.name, "種別": self.type_name, "材料": self.material, "階": self.level,
            "X": round(float(self.origin[0]), 3), "Y": round(float(self.origin[1]), 3), "Z": round(float(self.origin[2]), 3),
            "幅[m]": round(float(self.size[0]), 3), "奥行[m]": round(float(self.size[1]), 3), "高さ[m]": round(float(self.size[2]), 3),
            "体積[m3]": round(self.volume, 3), "重量[t]": round(self.weight / 1000, 2), "概算費用[円]": int(round(self.cost)),
        }
        for k, v in self.props.items():
            if k != "階":
                d[k] = v
        return d

    def info(self):
        """この部材が持っている『情報』を一覧表示"""
        print(f"■ {self.name}  ({self.type_name} / {self.ifc_class})")
        for k, v in self.to_dict().items():
            if k in ("名前", "種別"):
                continue
            print(f"   {k:<12}: {v}")
        if self.openings:
            print(f"   開口          : {[o.name for o in self.openings]}")
        if self.host is not None:
            print(f"   取付先の壁    : {self.host.name}")

    def __repr__(self):
        return f"<{self.type_name} '{self.name}' {self.size.round(2).tolist()} @ {self.origin.round(2).tolist()}>"


class Wall(Element):
    """壁: 平面上の始点・終点・高さ・厚さから定義（この教材では X 方向か Y 方向のみ）"""
    type_name = "壁"
    ifc_class = "IfcWall"

    def __init__(self, name, start, end, height=3.0, thickness=0.2, z=0.0, material="コンクリート", **props):
        (x1, y1), (x2, y2) = start, end
        if abs(y1 - y2) < 1e-9:      # X 方向の壁
            origin = (min(x1, x2), y1 - thickness / 2, z)
            size = (abs(x2 - x1), thickness, height)
            self.direction = "X"
        elif abs(x1 - x2) < 1e-9:    # Y 方向の壁
            origin = (x1 - thickness / 2, min(y1, y2), z)
            size = (thickness, abs(y2 - y1), height)
            self.direction = "Y"
        else:
            raise ValueError("この教材では X 方向または Y 方向の壁だけを扱います")
        super().__init__(name, origin, size, material, **props)
        self.start, self.end_pt = tuple(map(float, start)), tuple(map(float, end))
        self.height, self.thickness = float(height), float(thickness)

    @property
    def length(self):
        return math.dist(self.start, self.end_pt)

    @property
    def area(self):
        """壁の見付面積（開口控除後） [m2]"""
        return self.length * self.height - sum(o.face_area for o in self.openings)

    @property
    def formwork_area(self):
        """型枠面積（両面） [m2]"""
        return 2 * self.area

    def to_dict(self):
        d = super().to_dict()
        d["長さ[m]"] = round(self.length, 3)
        d["面積[m2]"] = round(self.area, 3)
        return d


class Slab(Element):
    """床スラブ: 平面の原点 (x, y)・大きさ (dx, dy)・底面の高さ z・厚さ"""
    type_name = "床"
    ifc_class = "IfcSlab"
    ifc_predefined = "FLOOR"

    def __init__(self, name, origin_xy, size_xy, z=0.0, thickness=0.2, material="コンクリート", **props):
        super().__init__(name, (origin_xy[0], origin_xy[1], z), (size_xy[0], size_xy[1], thickness), material, **props)

    @property
    def area(self):
        return float(self.size[0] * self.size[1])

    def to_dict(self):
        d = super().to_dict()
        d["面積[m2]"] = round(self.area, 3)
        return d


class Roof(Slab):
    type_name = "屋根"
    ifc_class = "IfcSlab"
    ifc_predefined = "ROOF"


class Column(Element):
    type_name = "柱"
    ifc_class = "IfcColumn"

    def __init__(self, name, x, y, z=0.0, height=3.0, width=0.4, depth=None, material="コンクリート", **props):
        depth = width if depth is None else depth
        super().__init__(name, (x - width / 2, y - depth / 2, z), (width, depth, height), material, **props)


class Beam(Element):
    """梁: 始点・終点(平面)・底面の高さ z・幅・せい"""
    type_name = "梁"
    ifc_class = "IfcBeam"

    def __init__(self, name, start, end, z=2.5, width=0.3, depth=0.5, material="コンクリート", **props):
        (x1, y1), (x2, y2) = start, end
        if abs(y1 - y2) < 1e-9:
            origin, size = (min(x1, x2), y1 - width / 2, z), (abs(x2 - x1), width, depth)
        elif abs(x1 - x2) < 1e-9:
            origin, size = (x1 - width / 2, min(y1, y2), z), (width, abs(y2 - y1), depth)
        else:
            raise ValueError("この教材では X 方向または Y 方向の梁だけを扱います")
        super().__init__(name, origin, size, material, **props)


class Duct(Element):
    """空調ダクト（設備）: 始点・終点(平面)・中心高さ z・一辺 size の角ダクト"""
    type_name = "ダクト"
    ifc_class = "IfcDuctSegment"

    def __init__(self, name, start, end, z=2.3, size=0.4, material="鋼板", **props):
        (x1, y1), (x2, y2) = start, end
        if abs(y1 - y2) < 1e-9:
            origin, sz = (min(x1, x2), y1 - size / 2, z - size / 2), (abs(x2 - x1), size, size)
        elif abs(x1 - x2) < 1e-9:
            origin, sz = (x1 - size / 2, min(y1, y2), z - size / 2), (size, abs(y2 - y1), size)
        else:
            raise ValueError("この教材では X 方向または Y 方向のダクトだけを扱います")
        super().__init__(name, origin, sz, material, **props)
        self.length = math.dist(start, end)

    @property
    def cost(self):
        return self.length * 15_000     # 円/m（教材用の仮単価）

    @property
    def weight(self):
        # 板厚 1mm の角ダクトとして概算
        return 4 * float(self.size[1]) * self.length * 0.001 * MATERIALS[self.material]["density"]


class _WallOpening(Element):
    """壁に取り付く要素（窓・扉・開口）の共通クラス"""
    def __init__(self, name, wall, offset, width, height, sill, material, **props):
        if not isinstance(wall, Wall):
            raise TypeError("窓・扉・開口は Wall に取り付けてください")
        if wall.direction == "X":
            x0 = min(wall.start[0], wall.end_pt[0]) + offset - width / 2
            origin, size = (x0, wall.origin[1], wall.origin[2] + sill), (width, wall.thickness, height)
        else:
            y0 = min(wall.start[1], wall.end_pt[1]) + offset - width / 2
            origin, size = (wall.origin[0], y0, wall.origin[2] + sill), (wall.thickness, width, height)
        props.setdefault("階", wall.level)
        if "方位" in wall.props:
            props.setdefault("方位", wall.props["方位"])
        super().__init__(name, origin, size, material, **props)
        self.host = wall
        self.width, self.height, self.sill, self.offset = float(width), float(height), float(sill), float(offset)
        wall.openings.append(self)

    @property
    def face_area(self):
        return self.width * self.height

    def to_dict(self):
        d = super().to_dict()
        d["面積[m2]"] = round(self.face_area, 3)
        d["取付先"] = self.host.name
        return d


class Window(_WallOpening):
    type_name = "窓"
    ifc_class = "IfcWindow"

    def __init__(self, name, wall, offset, width=1.5, height=1.2, sill=0.9, material="ガラス", **props):
        super().__init__(name, wall, offset, width, height, sill, material, **props)


class Door(_WallOpening):
    type_name = "扉"
    ifc_class = "IfcDoor"

    def __init__(self, name, wall, offset, width=0.9, height=2.1, material="木材", **props):
        super().__init__(name, wall, offset, width, height, 0.0, material, **props)


class Opening(_WallOpening):
    """壁の貫通開口（ダクトのスリーブなど）。材料は持たない扱い。"""
    type_name = "開口"
    ifc_class = "IfcOpeningElement"

    def __init__(self, name, wall, offset, width=0.5, height=0.5, sill=2.0, **props):
        super().__init__(name, wall, offset, width, height, sill, "コンクリート", **props)

    @property
    def cost(self):
        return 0.0

    @property
    def weight(self):
        return 0.0


# ============================================================
#  建物モデル（部材の入れ物 + BIM らしい機能）
# ============================================================
class Clash:
    def __init__(self, a, b, origin, size, net_volume=None):
        self.a, self.b, self.origin, self.size = a, b, origin, size
        self._net = net_volume

    @property
    def volume(self):
        """干渉体積 [m3]（開口で逃げている分は差し引いた正味）"""
        return float(np.prod(self.size)) if self._net is None else self._net

    def __repr__(self):
        return f"<干渉 {self.a.name} × {self.b.name} : {self.volume:.4f} m3>"


class Building:
    def __init__(self, name="BIM体験ハウス"):
        self.name = name
        self.elements = []
        self.start_date = pd.Timestamp("2026-04-01")

    # ---------- 部材の追加・検索 ----------
    def add(self, *elements):
        for e in elements:
            if not isinstance(e, Element):
                raise TypeError(f"Element ではありません: {e!r}")
            self.elements.append(e)
        return elements[0] if len(elements) == 1 else elements

    def remove(self, element):
        self.elements.remove(element)
        if element.host is not None and element in element.host.openings:
            element.host.openings.remove(element)

    def by_type(self, type_name):
        return [e for e in self.elements if e.type_name == type_name]

    def find(self, name):
        for e in self.elements:
            if e.name == name:
                return e
        raise KeyError(f"'{name}' という部材はありません")

    def __len__(self):
        return len(self.elements)

    def __iter__(self):
        return iter(self.elements)

    # ---------- 情報の取り出し ----------
    def to_dataframe(self):
        return pd.DataFrame([e.to_dict() for e in self.elements]).set_index("ID")

    def quantity_takeoff(self):
        """数量拾い: 種別・材料ごとの個数・体積・重量・費用"""
        rows = [e for e in self.elements if e.type_name != "開口"]
        df = pd.DataFrame({
            "種別": [e.type_name for e in rows], "材料": [e.material for e in rows],
            "個数": 1, "体積[m3]": [e.volume for e in rows],
            "重量[t]": [e.weight / 1000 for e in rows], "概算費用[円]": [e.cost for e in rows],
        })
        out = df.groupby(["種別", "材料"]).sum(numeric_only=True)
        out["概算費用[円]"] = out["概算費用[円]"].round().astype(int)
        return out.round(3)

    def concrete_summary(self):
        """コンクリート工事の概算数量（型枠・鉄筋は原単位による概算）"""
        conc = [e for e in self.elements if e.material == "コンクリート" and e.type_name != "開口"]
        vol = sum(e.volume for e in conc)
        formwork = sum(getattr(e, "formwork_area", 0.0) for e in conc)
        for e in conc:
            if isinstance(e, Slab):
                formwork += e.area   # スラブは下面のみ型枠
        rebar = vol * 120            # 鉄筋量 120 kg/m3 の概算原単位
        return pd.Series({"コンクリート[m3]": round(vol, 2), "型枠[m2]": round(formwork, 1), "鉄筋[t]": round(rebar / 1000, 2)})

    def total_cost(self):
        return sum(e.cost for e in self.elements)

    # ---------- 3D 表示 ----------
    def _traces(self, color_by="種別", opacity=1.0, hide=()):
        traces, seen = [], set()
        ex, ey, ez = [], [], []
        for e in self.elements:
            if e in hide or e.type_name == "開口":
                continue
            inflate = 0.015 if isinstance(e, _WallOpening) else 0.0
            verts, (i, j, k) = _box_mesh(e.origin, e.size, inflate)
            key = e.type_name if color_by == "種別" else e.material
            color = e.color if color_by == "種別" else MATERIALS[e.material]["color"]
            hover = "<br>".join(f"{kk}: {vv}" for kk, vv in e.to_dict().items()
                                if kk in ("名前", "種別", "材料", "階", "体積[m3]", "概算費用[円]", "方位", "面積[m2]"))
            traces.append(go.Mesh3d(
                x=verts[:, 0], y=verts[:, 1], z=verts[:, 2], i=i, j=j, k=k,
                color=color, opacity=0.6 if e.type_name == "窓" else opacity, flatshading=True,
                name=key, legendgroup=key, showlegend=key not in seen,
                hovertext=hover, hoverinfo="text",
            ))
            seen.add(key)
            for a, b in _EDGES:
                ex += [verts[a, 0], verts[b, 0], None]
                ey += [verts[a, 1], verts[b, 1], None]
                ez += [verts[a, 2], verts[b, 2], None]
        traces.append(go.Scatter3d(x=ex, y=ey, z=ez, mode="lines", line=dict(color="#333", width=2),
                                   hoverinfo="skip", showlegend=False))
        return traces

    def show(self, title=None, color_by="種別", clashes=None, highlight=(), height=600):
        """3D 表示（マウスで回転・ズームできます）"""
        traces = self._traces(color_by=color_by, opacity=0.25 if highlight else 1.0, hide=set(highlight))
        for e in highlight:
            verts, (i, j, k) = _box_mesh(e.origin, e.size)
            traces.append(go.Mesh3d(x=verts[:, 0], y=verts[:, 1], z=verts[:, 2], i=i, j=j, k=k, color="#ffb300",
                                    opacity=1.0, flatshading=True, name=e.name, hovertext=e.name, hoverinfo="text"))
        for c in (clashes or []):
            verts, (i, j, k) = _box_mesh(c.origin, c.size, inflate=0.02)
            traces.append(go.Mesh3d(x=verts[:, 0], y=verts[:, 1], z=verts[:, 2], i=i, j=j, k=k, color="red",
                                    opacity=1.0, flatshading=True, name="干渉", legendgroup="干渉",
                                    hovertext=repr(c), hoverinfo="text"))
        fig = go.Figure(data=traces)
        fig.update_layout(title=title or self.name, height=height, margin=dict(l=0, r=0, t=40, b=0),
                          scene=dict(aspectmode="data", xaxis_title="X [m]", yaxis_title="Y [m]", zaxis_title="Z [m]",
                                     camera=dict(eye=dict(x=1.6, y=-1.6, z=1.0))),
                          legend=dict(orientation="h", yanchor="bottom", y=0.0))
        return fig

    # ---------- 干渉チェック ----------
    def check_clashes(self, tol=1e-6):
        """すべての部材ペアについて直方体の重なりを調べ、開口分を差し引いて干渉を返す"""
        clashes = []
        els = [e for e in self.elements if e.type_name != "開口"]
        for a, b in itertools.combinations(els, 2):
            if a.host is b or b.host is a:
                continue   # 窓・扉とその取付先の壁は干渉ではない
            ov = _box_overlap(a.origin, a.size, b.origin, b.size, tol)
            if ov is None:
                continue
            net = float(np.prod(ov[1]))
            for o in a.openings + b.openings:
                sub = _box_overlap(ov[0], ov[1], o.origin, o.size, tol)
                if sub is not None:
                    net -= float(np.prod(sub[1]))
            if net > tol:
                clashes.append(Clash(a, b, ov[0], ov[1], net))
        return clashes

    # ---------- 4D（工程） ----------
    DEFAULT_ORDER = ("床", "柱", "梁", "壁", "屋根", "窓", "扉", "ダクト")
    DEFAULT_DAYS = {"床": 5, "柱": 3, "梁": 3, "壁": 6, "屋根": 4, "窓": 2, "扉": 1, "ダクト": 3}

    def plan_schedule(self, start_date="2026-04-01", order=DEFAULT_ORDER, days=DEFAULT_DAYS):
        """階ごと・種別ごとに順番に施工するとして、各部材に開始日と日数を割り当てる"""
        day = 0
        for lv in sorted({e.level for e in self.elements}):
            for t in order:
                group = [e for e in self.elements if e.level == lv and e.type_name == t]
                if not group:
                    continue
                for e in group:
                    e.start_day, e.duration = day, days.get(t, 2)
                day += days.get(t, 2)
        self.start_date = pd.Timestamp(start_date)
        return self.schedule_table()

    def schedule_table(self):
        rows = []
        for e in self.elements:
            if e.start_day is None or e.type_name == "開口":
                continue
            s = self.start_date + pd.Timedelta(days=e.start_day)
            rows.append({"部材": e.name, "種別": e.type_name, "階": e.level, "開始": s,
                         "終了": s + pd.Timedelta(days=e.duration), "日数": e.duration})
        return pd.DataFrame(rows)

    def show_gantt(self):
        import plotly.express as px
        df = self.schedule_table()
        fig = px.timeline(df, x_start="開始", x_end="終了", y="部材", color="種別", title="工程表（ガントチャート）")
        fig.update_yaxes(autorange="reversed")
        fig.update_layout(height=max(400, 18 * len(df)), margin=dict(l=0, r=0, t=40, b=0))
        return fig

    def show_4d(self, height=600):
        """工程に合わせて建物が建っていくアニメーション"""
        els = [e for e in self.elements if e.start_day is not None and e.type_name != "開口"]
        if not els:
            raise RuntimeError("先に plan_schedule() を実行してください")
        last = max(e.start_day + e.duration for e in els)

        def merged(subset, color_fn):
            xs, ys, zs, ii, jj, kk, fc = [], [], [], [], [], [], []
            for e in subset:
                verts, (i, j, k) = _box_mesh(e.origin, e.size, 0.015 if isinstance(e, _WallOpening) else 0.0)
                n = len(xs)
                xs += verts[:, 0].tolist(); ys += verts[:, 1].tolist(); zs += verts[:, 2].tolist()
                ii += (np.array(i) + n).tolist(); jj += (np.array(j) + n).tolist(); kk += (np.array(k) + n).tolist()
                fc += [color_fn(e)] * 12
            return xs, ys, zs, ii, jj, kk, fc

        def frame_traces(day):
            done = [e for e in els if e.start_day + e.duration <= day]
            doing = [e for e in els if e.start_day <= day < e.start_day + e.duration]
            todo = [e for e in els if e.start_day > day]
            x, y, z, i, j, k, fc = merged(done + doing, lambda e: "#ffb300" if e in doing else e.color)
            t1 = go.Mesh3d(x=x, y=y, z=z, i=i, j=j, k=k, facecolor=fc, flatshading=True, opacity=1.0,
                           name="完了 / 施工中(黄)", hoverinfo="skip", visible=bool(done + doing))
            x, y, z, i, j, k, fc = merged(todo, lambda e: "#999999")
            t2 = go.Mesh3d(x=x, y=y, z=z, i=i, j=j, k=k, color="#999999", flatshading=True, opacity=0.08,
                           name="未着手", hoverinfo="skip", visible=bool(todo))
            return [t1, t2]

        days = list(range(0, last + 1))
        frames = [go.Frame(data=frame_traces(d), name=str(d),
                           layout=go.Layout(title=f"{self.name}  工程 {d} 日目 / {last} 日")) for d in days]
        fig = go.Figure(data=frame_traces(0), frames=frames)
        lo = np.min([e.origin for e in els], axis=0) - 0.5
        hi = np.max([e.end for e in els], axis=0) + 0.5
        fig.update_layout(
            title=f"{self.name}  工程 0 日目 / {last} 日", height=height, margin=dict(l=0, r=0, t=40, b=0),
            scene=dict(aspectmode="data", xaxis=dict(range=[lo[0], hi[0]]), yaxis=dict(range=[lo[1], hi[1]]),
                       zaxis=dict(range=[lo[2], hi[2]]), camera=dict(eye=dict(x=1.6, y=-1.6, z=1.0))),
            updatemenus=[dict(type="buttons", showactive=False, x=0.05, y=0.05,
                              buttons=[dict(label="▶ 再生", method="animate",
                                            args=[None, dict(frame=dict(duration=250, redraw=True), fromcurrent=True)]),
                                       dict(label="■ 停止", method="animate",
                                            args=[[None], dict(frame=dict(duration=0, redraw=False), mode="immediate")])])],
            sliders=[dict(steps=[dict(method="animate", label=str(d),
                                      args=[[str(d)], dict(mode="immediate", frame=dict(duration=0, redraw=True))])
                                 for d in days],
                          currentvalue=dict(prefix="日目: "), x=0.1, len=0.85)],
        )
        return fig

    # ---------- IFC 書き出し ----------
    def to_ifc(self, path="minibim.ifc"):
        """モデルを IFC4 ファイル（BIM の国際標準フォーマット）として保存"""
        import ifcopenshell
        import ifcopenshell.guid

        f = ifcopenshell.file(schema="IFC4")
        G = ifcopenshell.guid.new

        def pt(x, y, z=None):
            return f.createIfcCartesianPoint((float(x), float(y)) if z is None else (float(x), float(y), float(z)))

        def placement(x, y, z, parent=None):
            return f.createIfcLocalPlacement(parent, f.createIfcAxis2Placement3D(pt(x, y, z), None, None))

        # 単位・座標系・プロジェクト
        units = f.createIfcUnitAssignment([
            f.createIfcSIUnit(None, "LENGTHUNIT", None, "METRE"),
            f.createIfcSIUnit(None, "AREAUNIT", None, "SQUARE_METRE"),
            f.createIfcSIUnit(None, "VOLUMEUNIT", None, "CUBIC_METRE"),
        ])
        wcs = f.createIfcAxis2Placement3D(pt(0, 0, 0), f.createIfcDirection((0.0, 0.0, 1.0)), f.createIfcDirection((1.0, 0.0, 0.0)))
        ctx = f.createIfcGeometricRepresentationContext(None, "Model", 3, 1e-5, wcs, None)
        body = f.createIfcGeometricRepresentationSubContext("Body", "Model", None, None, None, None, ctx, None, "MODEL_VIEW", None)
        project = f.create_entity("IfcProject", GlobalId=G(), Name=self.name, RepresentationContexts=[ctx], UnitsInContext=units)

        # 空間構造: 敷地 → 建物 → 階
        site_pl = placement(0, 0, 0)
        site = f.create_entity("IfcSite", GlobalId=G(), Name="敷地", ObjectPlacement=site_pl, CompositionType="ELEMENT")
        bldg_pl = placement(0, 0, 0, site_pl)
        building = f.create_entity("IfcBuilding", GlobalId=G(), Name=self.name, ObjectPlacement=bldg_pl, CompositionType="ELEMENT")
        f.createIfcRelAggregates(G(), None, None, None, project, [site])
        f.createIfcRelAggregates(G(), None, None, None, site, [building])

        storeys = {}
        for lv in sorted({e.level for e in self.elements}):
            elev = min((e.origin[2] for e in self.elements if e.level == lv and e.type_name == "壁"), default=0.0)
            st_pl = placement(0, 0, 0, bldg_pl)
            storeys[lv] = (f.create_entity("IfcBuildingStorey", GlobalId=G(), Name=f"{lv}F", ObjectPlacement=st_pl,
                                           CompositionType="ELEMENT", Elevation=float(elev)), st_pl)
        f.createIfcRelAggregates(G(), None, None, None, building, [s for s, _ in storeys.values()])

        materials = {}

        def material(name):
            if name not in materials:
                materials[name] = f.createIfcMaterial(name)
            return materials[name]

        def box_shape(size, color_hex, transparency=0.0):
            dx, dy, dz = map(float, size)
            prof = f.createIfcRectangleProfileDef("AREA", None, f.createIfcAxis2Placement2D(pt(dx / 2, dy / 2), None), dx, dy)
            solid = f.createIfcExtrudedAreaSolid(prof, f.createIfcAxis2Placement3D(pt(0, 0, 0), None, None),
                                                 f.createIfcDirection((0.0, 0.0, 1.0)), dz)
            try:   # 表示色（ビューアで色が付くように）。失敗しても形状は書き出す
                r, g, b = (int(color_hex[i:i + 2], 16) / 255 for i in (1, 3, 5))
                style = f.createIfcSurfaceStyle(None, "BOTH", [f.createIfcSurfaceStyleShading(f.createIfcColourRgb(None, r, g, b), transparency)])
                f.createIfcStyledItem(solid, [style], None)
            except Exception:
                pass
            shape = f.createIfcShapeRepresentation(body, "Body", "SweptSolid", [solid])
            return f.createIfcProductDefinitionShape(None, None, [shape])

        def ifc_value(v):
            if isinstance(v, bool):
                return f.createIfcBoolean(v)
            if isinstance(v, (int, float, np.integer, np.floating)):
                return f.createIfcReal(float(v))
            return f.createIfcLabel(str(v))

        def add_pset(product, name, props):
            vals = [f.createIfcPropertySingleValue(str(k), None, ifc_value(v), None) for k, v in props.items() if v is not None]
            pset = f.createIfcPropertySet(G(), None, name, None, vals)
            f.createIfcRelDefinesByProperties(G(), None, None, None, [product], pset)

        common_pset = {"壁": "Pset_WallCommon", "床": "Pset_SlabCommon", "屋根": "Pset_SlabCommon", "柱": "Pset_ColumnCommon",
                       "梁": "Pset_BeamCommon", "窓": "Pset_WindowCommon", "扉": "Pset_DoorCommon"}
        ifc_of = {}
        for e in self.elements:
            if e.type_name == "開口":
                continue
            storey, st_pl = storeys[e.level]
            kwargs = dict(GlobalId=G(), Name=e.name, ObjectPlacement=placement(*e.origin, parent=st_pl),
                          Representation=box_shape(e.size, e.color, 0.4 if e.type_name == "窓" else 0.0))
            if e.ifc_predefined:
                kwargs["PredefinedType"] = e.ifc_predefined
            prod = f.create_entity(e.ifc_class, **kwargs)
            ifc_of[e] = prod
            f.createIfcRelContainedInSpatialStructure(G(), None, None, None, [prod], storey)
            f.createIfcRelAssociatesMaterial(G(), None, None, None, [prod], material(e.material))
            if e.type_name in common_pset:
                add_pset(prod, common_pset[e.type_name], {"IsExternal": True, "FireRating": e.props.get("耐火")})
            add_pset(prod, "Pset_授業用", {"材料": e.material, "体積_m3": round(e.volume, 3), "概算費用_円": int(round(e.cost)),
                                         **{k: v for k, v in e.props.items() if k != "階"}})
            add_pset(prod, "Qto_授業用", {"体積[m3]": round(e.volume, 3), "重量[kg]": round(e.weight, 1)})

        # 窓・扉・開口 → IfcOpeningElement で壁をくり抜き、窓・扉をはめ込む
        for e in self.elements:
            if e.host is None or e.host not in ifc_of:
                continue
            storey, st_pl = storeys[e.level]
            op = f.create_entity("IfcOpeningElement", GlobalId=G(), Name=f"開口 ({e.name})",
                                 ObjectPlacement=placement(*e.origin, parent=st_pl), Representation=box_shape(e.size, "#ffffff"))
            f.createIfcRelVoidsElement(G(), None, None, None, ifc_of[e.host], op)
            if e in ifc_of:
                f.createIfcRelFillsElement(G(), None, None, None, op, ifc_of[e])

        f.write(path)
        return path


# ============================================================
#  複数モデルの比較表示
# ============================================================
def show_side_by_side(models, cols=2, height=750, title="設計案の比較（同じ縮尺で表示）"):
    """{名前: Building} の辞書を受け取り、同じ縮尺で 3D を並べて表示する"""
    from plotly.subplots import make_subplots

    names = list(models)
    rows = -(-len(names) // cols)
    fig = make_subplots(rows=rows, cols=cols, specs=[[{"type": "scene"}] * cols] * rows,
                        subplot_titles=names, horizontal_spacing=0.02, vertical_spacing=0.06)
    # 全モデルを含む共通の表示範囲（縮尺を揃えるため）
    lo = np.min([e.origin for b in models.values() for e in b], axis=0) - 0.5
    hi = np.max([e.end for b in models.values() for e in b], axis=0) + 0.5
    span = hi - lo
    ratio = span / float(np.max(span))
    for idx, name in enumerate(names):
        r, c = divmod(idx, cols)
        for tr in models[name]._traces():
            tr.showlegend = False
            fig.add_trace(tr, row=r + 1, col=c + 1)
    fig.update_scenes(aspectmode="manual", aspectratio=dict(x=ratio[0], y=ratio[1], z=ratio[2]),
                      xaxis=dict(range=[lo[0], hi[0]], title="X"),
                      yaxis=dict(range=[lo[1], hi[1]], title="Y"),
                      zaxis=dict(range=[lo[2], hi[2]], title="Z"),
                      camera=dict(eye=dict(x=1.5, y=-1.5, z=0.9)))
    fig.update_layout(title=title, height=height, margin=dict(l=0, r=0, t=60, b=0))
    return fig


# ============================================================
#  サンプル建物のビルダー
# ============================================================
def build_house(length=8.0, width=6.0, floors=1, story_height=3.0, wall_thickness=0.2,
                slab_thickness=0.2, window_width=1.5, name="BIM体験ハウス"):
    """パラメータから簡単な箱型住宅を自動生成する（BIM の『パラメトリック』を体験する関数）"""
    b = Building(name)
    t, L, W = wall_thickness, length, width
    b.add(Slab("基礎スラブ", (-t / 2, -t / 2), (L + t, W + t), z=-slab_thickness, thickness=slab_thickness, 階=1))
    for fl in range(1, floors + 1):
        z0 = (fl - 1) * (story_height + slab_thickness)
        h = story_height
        fire = "1時間" if fl == 1 else "30分"
        s = b.add(Wall(f"{fl}F 南壁", (-t / 2, 0), (L + t / 2, 0), height=h, thickness=t, z=z0, 階=fl, 方位="南", 耐火=fire))
        n = b.add(Wall(f"{fl}F 北壁", (-t / 2, W), (L + t / 2, W), height=h, thickness=t, z=z0, 階=fl, 方位="北", 耐火=fire))
        w = b.add(Wall(f"{fl}F 西壁", (0, t / 2), (0, W - t / 2), height=h, thickness=t, z=z0, 階=fl, 方位="西", 耐火=fire))
        e = b.add(Wall(f"{fl}F 東壁", (L, t / 2), (L, W - t / 2), height=h, thickness=t, z=z0, 階=fl, 方位="東", 耐火=fire))
        wh = min(1.2, h - 1.2)
        b.add(Window(f"{fl}F 南窓1", s, offset=L * 0.2 + t / 2, width=window_width, height=wh, sill=0.9, メーカー="A社"))
        b.add(Window(f"{fl}F 南窓2", s, offset=L * 0.5 + t / 2, width=window_width, height=wh, sill=0.9, メーカー="A社"))
        b.add(Window(f"{fl}F 北窓", n, offset=L * 0.5 + t / 2, width=window_width, height=wh, sill=0.9, メーカー="B社"))
        b.add(Window(f"{fl}F 東窓", e, offset=W * 0.5 - t / 2, width=min(window_width, W * 0.4), height=wh, sill=0.9, メーカー="B社"))
        if fl == 1:
            b.add(Door("玄関扉", s, offset=L * 0.8 + t / 2, width=0.9, height=min(2.1, h - 0.3), 耐火="防火戸"))
        if fl < floors:
            b.add(Slab(f"{fl + 1}F 床", (-t / 2, -t / 2), (L + t, W + t), z=z0 + h, thickness=slab_thickness, 階=fl + 1))
        else:
            b.add(Roof("屋根", (-t / 2, -t / 2), (L + t, W + t), z=z0 + h, thickness=slab_thickness, 階=fl))
    return b
