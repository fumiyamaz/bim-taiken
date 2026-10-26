# ===== 断面表示機能（このセルを実行すると show_section / show_plan / show_section_3d が使えます） =====
import numpy as np
import plotly.graph_objects as go

_AXIS = {"x": 0, "y": 1, "z": 2}
_AXIS_LABEL = {0: "X [m]", 1: "Y [m]", 2: "Z [m]"}
_SEC_EDGES = [(0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4), (0, 4), (1, 5), (2, 6), (3, 7)]


def _sec_box_mesh(origin, size, inflate=0.0):
    """直方体 → (頂点, 三角形インデックス)。Plotly Mesh3d 用"""
    o = np.asarray(origin, float) - inflate
    x0, y0, z0 = o
    x1, y1, z1 = o + np.asarray(size, float) + 2 * inflate
    verts = np.array([[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0],
                      [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]])
    i = [0, 0, 4, 4, 0, 0, 1, 1, 2, 2, 3, 3]
    j = [1, 2, 5, 6, 1, 5, 2, 6, 3, 7, 0, 4]
    k = [2, 3, 6, 7, 5, 4, 6, 5, 7, 6, 4, 7]
    return verts, (i, j, k)


def _clip_box(e, ax, pos, keep):
    """部材 e を切断面 (座標 ax = pos) で切り、残す側の直方体 (origin, size) を返す。残らなければ None"""
    lo, hi = e.origin.copy(), e.end.copy()
    if keep == "+":          # 座標が大きい側（奥）を残す
        lo[ax] = max(lo[ax], pos)
    else:                    # 座標が小さい側（手前・下）を残す
        hi[ax] = min(hi[ax], pos)
    if hi[ax] - lo[ax] <= 1e-9:
        return None
    return lo, hi - lo


def show_section(building, axis="y", position=3.0, keep="+", title=None, height=500):
    """2D の断面図を描く。axis="y" なら Y=position で切って X-Z 面を見る。
    切られた部材は濃く塗りつぶし（切り口）、奥に見える部材は薄く描く（見え掛かり）。
    keep="+" で座標の大きい側を残す（奥を見る）、"-" で小さい側を残す。"""
    ax = _AXIS[axis]
    h, v = [a for a in (0, 1, 2) if a != ax]          # 横軸・縦軸にする座標
    fig = go.Figure()

    def rect(o, s, color, line, width, name, opacity=1.0, dash=None):
        x0, x1, y0, y1 = o[h], o[h] + s[h], o[v], o[v] + s[v]
        fig.add_trace(go.Scatter(x=[x0, x1, x1, x0, x0], y=[y0, y0, y1, y1, y0], fill="toself", fillcolor=color,
                                 line=dict(color=line, width=width, dash=dash), opacity=opacity,
                                 mode="lines", name=name, hoverinfo="name", showlegend=False))

    cut, behind = [], []
    for e in building:
        if e.origin[ax] < position < e.end[ax]:
            cut.append(e)
        elif _clip_box(e, ax, position, keep) is not None:
            behind.append(e)

    # 1) 奥に見える部材（薄く）
    for e in behind:
        if e.type_name == "開口":
            continue
        rect(e.origin, e.size, e.color, "#999999", 1, e.name, opacity=0.35)
    # 2) 切られた部材（濃く）。壁 → 窓・扉・開口の順に描き、開口は白で抜く
    for e in sorted(cut, key=lambda e: 1 if e.host is not None else 0):
        if e.type_name == "開口":
            rect(e.origin, e.size, "white", "#333333", 1.5, e.name, dash="dot")
        else:
            rect(e.origin, e.size, e.color, "#222222", 2.5, e.name)

    fig.update_layout(title=title or f"断面図（{axis.upper()} = {position} m で切断）", height=height,
                      xaxis=dict(title=_AXIS_LABEL[h], showgrid=True, zeroline=False),
                      yaxis=dict(title=_AXIS_LABEL[v], scaleanchor="x", scaleratio=1, showgrid=True, zeroline=False),
                      plot_bgcolor="white", margin=dict(l=0, r=0, t=40, b=0))
    return fig


def show_plan(building, z=1.2, title=None, height=500):
    """平面図：高さ z で水平に切り、下側を見下ろす（建築図面の平面図と同じ考え方）"""
    return show_section(building, axis="z", position=z, keep="-", title=title or f"平面図（Z = {z} m で切断）", height=height)


def show_section_3d(building, axis="y", position=3.0, keep="+", title=None, height=600):
    """3D モデルを切断面で切り、手前側を取り除いた状態で表示する。切り口は赤で示す"""
    ax = _AXIS[axis]
    traces, ex, ey, ez = [], [], [], []
    for e in building:
        if e.type_name == "開口":
            continue
        clipped = _clip_box(e, ax, position, keep)
        if clipped is None:
            continue
        o, s = clipped
        verts, (i, j, k) = _sec_box_mesh(o, s, 0.015 if e.host is not None else 0.0)
        traces.append(go.Mesh3d(x=verts[:, 0], y=verts[:, 1], z=verts[:, 2], i=i, j=j, k=k, color=e.color,
                                flatshading=True, opacity=0.6 if e.type_name == "窓" else 1.0,
                                name=e.type_name, hovertext=e.name, hoverinfo="text", showlegend=False))
        for a, b in _SEC_EDGES:
            ex += [verts[a, 0], verts[b, 0], None]; ey += [verts[a, 1], verts[b, 1], None]; ez += [verts[a, 2], verts[b, 2], None]
        if e.origin[ax] < position < e.end[ax]:      # 切られた部材 → 切り口を赤い面で描く
            face = o.copy(); fsize = s.copy()
            face[ax] = position + (-0.01 if keep == "+" else 0.01); fsize[ax] = 0.0
            fv, (fi, fj, fk) = _sec_box_mesh(face, fsize)
            traces.append(go.Mesh3d(x=fv[:, 0], y=fv[:, 1], z=fv[:, 2], i=fi, j=fj, k=fk, color="#d32f2f",
                                    flatshading=True, name="切り口", hovertext=f"切り口: {e.name}", hoverinfo="text", showlegend=False))
    traces.append(go.Scatter3d(x=ex, y=ey, z=ez, mode="lines", line=dict(color="#333", width=2), hoverinfo="skip", showlegend=False))
    fig = go.Figure(data=traces)
    fig.update_layout(title=title or f"3D 断面（{axis.upper()} = {position} m で切断、赤 = 切り口）", height=height,
                      margin=dict(l=0, r=0, t=40, b=0),
                      scene=dict(aspectmode="data", xaxis_title="X [m]", yaxis_title="Y [m]", zaxis_title="Z [m]",
                                 camera=dict(eye=dict(x=1.6, y=-1.6, z=1.0))))
    return fig


print("断面表示機能を読み込みました ✅  使い方: show_section(house, 'y', 3.0).show() / show_plan(house, 1.2).show() / show_section_3d(house, 'y', 3.0).show()")
