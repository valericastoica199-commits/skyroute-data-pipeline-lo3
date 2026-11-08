"""Draws the report diagrams twice from one definition:
  diagrams/<name>.drawio  - editable in draw.io / app.diagrams.net
  diagrams/<name>.png     - image placed in the Word report
"""
from pathlib import Path
from xml.sax.saxutils import escape

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Polygon, Rectangle

OUT = Path(__file__).resolve().parents[1] / "diagrams"

STYLES = {  # fill, stroke
    "data": ("#DAE8FC", "#6C8EBF"),
    "proc": ("#D5E8D4", "#82B366"),
    "store": ("#FFF2CC", "#D6B656"),
    "dec": ("#FFE6CC", "#D79B00"),
    "bad": ("#F8CECC", "#B85450"),
    "plat": ("#E1D5E7", "#9673A6"),
    "note": ("#F5F5F5", "#666666"),
}


class Diagram:
    def __init__(self, name, title, w, h):
        self.name, self.title, self.w, self.h = name, title, w, h
        self.nodes, self.edges, self.lanes = {}, [], []

    def node(self, nid, label, x, y, w=150, h=60, kind="proc"):
        self.nodes[nid] = dict(label=label, x=x, y=y, w=w, h=h, kind=kind)

    def lane(self, label, x, y, w, h):
        self.lanes.append(dict(label=label, x=x, y=y, w=w, h=h))

    def edge(self, a, b, label="", exit=None, entry=None, pts=(), dashed=False):
        self.edges.append(dict(a=a, b=b, label=label, exit=exit, entry=entry, pts=list(pts), dashed=dashed))

    # ---- anchors: side -> (fx, fy)
    SIDES = {"r": (1, .5), "l": (0, .5), "t": (.5, 0), "b": (.5, 1)}

    def _auto(self, a, b):
        na, nb = self.nodes[a], self.nodes[b]
        dx = (nb["x"] + nb["w"] / 2) - (na["x"] + na["w"] / 2)
        dy = (nb["y"] + nb["h"] / 2) - (na["y"] + na["h"] / 2)
        if abs(dx) >= abs(dy):
            return ("r", "l") if dx > 0 else ("l", "r")
        return ("b", "t") if dy > 0 else ("t", "b")

    def _pt(self, nid, side):
        n = self.nodes[nid]
        fx, fy = self.SIDES[side]
        return n["x"] + fx * n["w"], n["y"] + fy * n["h"]

    # ---- draw.io
    def drawio(self):
        cells, i = [], 2
        for ln in self.lanes:
            cells.append(f'<mxCell id="lane{i}" value="{escape(ln["label"])}" style="rounded=1;arcSize=4;dashed=1;fillColor=none;strokeColor=#999999;verticalAlign=top;align=left;spacingLeft=8;fontStyle=1;fontSize=13;" vertex="1" parent="1"><mxGeometry x="{ln["x"]}" y="{ln["y"]}" width="{ln["w"]}" height="{ln["h"]}" as="geometry"/></mxCell>')
            i += 1
        for nid, n in self.nodes.items():
            fill, stroke = STYLES[n["kind"]]
            shape = "rhombus;" if n["kind"] == "dec" else "rounded=1;"
            label = escape(n["label"]).replace("\n", "&lt;br&gt;")
            cells.append(f'<mxCell id="{nid}" value="{label}" style="{shape}whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};fontSize=12;" vertex="1" parent="1"><mxGeometry x="{n["x"]}" y="{n["y"]}" width="{n["w"]}" height="{n["h"]}" as="geometry"/></mxCell>')
        for k, e in enumerate(self.edges):
            ex, en = self._auto(e["a"], e["b"])
            ex, en = e["exit"] or ex, e["entry"] or en
            (ex_x, ex_y), (en_x, en_y) = self.SIDES[ex], self.SIDES[en]
            style = (f"edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;endArrow=block;endFill=1;fontSize=11;"
                     f"exitX={ex_x};exitY={ex_y};entryX={en_x};entryY={en_y};" + ("dashed=1;" if e["dashed"] else ""))
            pts = "".join(f'<mxPoint x="{x}" y="{y}"/>' for x, y in e["pts"])
            pts = f'<Array as="points">{pts}</Array>' if pts else ""
            cells.append(f'<mxCell id="e{k}" value="{escape(e["label"])}" style="{style}" edge="1" parent="1" source="{e["a"]}" target="{e["b"]}"><mxGeometry relative="1" as="geometry">{pts}</mxGeometry></mxCell>')
        xml = (f'<mxfile host="app.diagrams.net"><diagram name="{escape(self.title)}"><mxGraphModel dx="{self.w}" dy="{self.h}" grid="1" gridSize="10" page="1" pageWidth="{self.w}" pageHeight="{self.h}"><root>'
               '<mxCell id="0"/><mxCell id="1" parent="0"/>' + "".join(cells) + "</root></mxGraphModel></diagram></mxfile>")
        (OUT / f"{self.name}.drawio").write_text(xml, encoding="utf-8")

    # ---- PNG
    def png(self):
        fig = plt.figure(figsize=(self.w / 100, self.h / 100), dpi=200)
        ax = fig.add_axes([0, 0, 1, 1])
        ax.set_xlim(0, self.w)
        ax.set_ylim(self.h, 0)
        ax.axis("off")
        for ln in self.lanes:
            ax.add_patch(FancyBboxPatch((ln["x"], ln["y"]), ln["w"], ln["h"], boxstyle="round,pad=0,rounding_size=8",
                                        fill=False, ls="--", ec="#999999", lw=1))
            ax.text(ln["x"] + 10, ln["y"] + 8, ln["label"], va="top", fontsize=8.5, weight="bold", color="#333")
        for e in self.edges:
            ex, en = self._auto(e["a"], e["b"])
            ex, en = e["exit"] or ex, e["entry"] or en
            path = [self._pt(e["a"], ex)] + e["pts"] + [self._pt(e["b"], en)]
            path = _orthogonal(path, ex, en)
            ls = "--" if e["dashed"] else "-"
            for p, q in zip(path[:-2], path[1:-1]):
                ax.plot([p[0], q[0]], [p[1], q[1]], color="#333", lw=1.1, ls=ls)
            ax.annotate("", xy=path[-1], xytext=path[-2],
                        arrowprops=dict(arrowstyle="-|>", color="#333", lw=1.1, ls=ls, shrinkA=0, shrinkB=0))
            if e["label"]:
                mid = len(path) // 2
                p, q = path[mid - 1], path[mid]
                ax.text((p[0] + q[0]) / 2, (p[1] + q[1]) / 2, e["label"], fontsize=7, ha="center", va="center",
                        bbox=dict(fc="white", ec="none", pad=1.2), color="#222")
        for n in self.nodes.values():
            fill, stroke = STYLES[n["kind"]]
            x, y, w, h = n["x"], n["y"], n["w"], n["h"]
            if n["kind"] == "dec":
                ax.add_patch(Polygon([(x + w / 2, y), (x + w, y + h / 2), (x + w / 2, y + h), (x, y + h / 2)],
                                     fc=fill, ec=stroke, lw=1.2, zorder=3))
            else:
                ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=7",
                                            fc=fill, ec=stroke, lw=1.2, zorder=3))
            ax.text(x + w / 2, y + h / 2, n["label"], ha="center", va="center", fontsize=7.6, zorder=4, linespacing=1.25)
        fig.savefig(OUT / f"{self.name}.png", dpi=200, facecolor="white")
        plt.close(fig)

    def save(self):
        OUT.mkdir(exist_ok=True)
        self.drawio()
        self.png()


def _orthogonal(path, ex, en):
    """Insert corner points so every segment is horizontal or vertical."""
    out = [path[0]]
    for i, q in enumerate(path[1:], 1):
        p = out[-1]
        if p[0] != q[0] and p[1] != q[1]:
            first_horizontal = (ex in "lr") if i == 1 else (out[-1][1] == out[-2][1] if len(out) > 1 else True)
            if i == len(path) - 1:
                first_horizontal = en in "tb"
            out.append((q[0], p[1]) if first_horizontal else (p[0], q[1]))
        out.append(q)
    return out


# ------------------------------------------------------------------ Figure 1
def architecture():
    d = Diagram("fig1_pipeline_architecture", "SkyRoute pipeline architecture", 1240, 470)
    y = 70
    d.node("src", "Source data\norders.csv\n(241 shipments)", 20, y, 140, 70, "data")
    d.node("ext", "1. Extract\nread CSV\nretry x3", 215, y, 140, 70)
    d.node("val", "2. Validate\n9 rules +\nduplicate check", 410, y, 140, 70)
    d.node("tr", "3. Transform\nThreadPool\n(4-8 workers)", 605, y, 140, 70)
    d.node("agg", "4. Aggregate\nregional KPIs", 800, y, 140, 70)
    d.node("load", "5. Load\natomic write\n(temp -> rename)", 995, y, 140, 70)
    d.node("gate", "Quality gate\n>10% rejected?", 405, 200, 150, 90, "dec")
    d.node("rej", "rejected_orders.csv\n+ reject_reason", 215, 215, 150, 60, "bad")
    d.node("stop", "Stop: exit code 2\noutputs not published", 405, 340, 150, 60, "bad")
    d.node("outp", "processed_orders.csv\nregion_kpis.json", 995, 215, 150, 60, "store")
    d.node("obs", "6. Observe\npipeline.log (run_id, stage)\nrun_summary.json\nrun_history.json", 690, 330, 200, 90, "store")
    d.node("dash", "Operations dashboard\nindex.html", 995, 345, 150, 60, "plat")
    d.edge("src", "ext"); d.edge("ext", "val");     d.edge("tr", "agg"); d.edge("agg", "load")
    d.edge("val", "gate", "valid rows", exit="b", entry="t")
    d.edge("val", "rej", "invalid rows", exit="b", entry="t", pts=[(480, 170), (290, 170)])
    d.edge("gate", "stop", "yes", exit="b", entry="t")
    d.edge("gate", "tr", "no - continue", exit="r", entry="b", pts=[(675, 245)])
    d.edge("load", "outp", exit="b", entry="t")
    d.edge("outp", "obs", "metrics", exit="l", entry="t", pts=[(790, 245)])
    d.edge("obs", "dash", exit="r", entry="l")
    d.lane("Automated run (manual, scheduled or serverless trigger)", 5, 15, 1225, 445)
    d.save()


# ------------------------------------------------------------------ Figure 2
def deployment():
    d = Diagram("fig2_deployment_methods", "Deployment methods", 1240, 560)
    d.node("repo", "GitHub repository\n(main branch,\ntagged releases)", 20, 230, 150, 80, "data")
    d.lane("A. Manual deployment", 200, 15, 1030, 150)
    d.node("m1", "Engineer runs\nrun_pipeline.bat", 230, 65, 150, 60, "note")
    d.node("m2", "python src/pipeline.py\n--workers 4", 450, 65, 160, 60)
    d.node("m3", "Local output/ + logs/\nchecked by engineer", 680, 65, 170, 60, "store")
    d.node("m4", "Good for: tests, one-off\nbackfills, first release", 920, 65, 180, 60, "note")
    d.lane("B. Scheduled deployment - Render Cron Job (render.yaml)", 200, 190, 1030, 160)
    d.node("s1", "Cron trigger\n0 2 * * * (UTC)", 230, 245, 150, 60, "plat")
    d.node("s2", "Build: pip install\n+ pytest -q", 450, 245, 160, 60)
    d.node("s3", "Run container\npython src/pipeline.py", 680, 245, 170, 60)
    d.node("s4", "Render logs,\nevents & deploy history", 920, 245, 180, 60, "store")
    d.lane("C. Serverless deployment - Vercel Function (api/run.py)", 200, 375, 1030, 170)
    d.node("v1", "Vercel Cron 06:00 UTC\nor HTTPS GET /api/run\n+ Bearer CRON_SECRET", 230, 430, 160, 70, "plat")
    d.node("v2", "Auth check\n401 if token wrong", 450, 435, 160, 60, "dec")
    d.node("v3", "Function runs pipeline\n(/tmp, 60 s limit,\nscales to zero)", 680, 430, 170, 70)
    d.node("v4", "JSON response +\nruntime logs\n(200 / 422 / 500)", 920, 430, 180, 70, "store")
    d.edge("m1", "m2"); d.edge("m2", "m3"); d.edge("m3", "m4", dashed=True)
    d.edge("s1", "s2"); d.edge("s2", "s3", "tests pass"); d.edge("s3", "s4")
    d.edge("v1", "v2"); d.edge("v2", "v3", "valid"); d.edge("v3", "v4")
    d.edge("repo", "m1", "git pull", exit="t", entry="l", pts=[(95, 95)])
    d.edge("repo", "s1", exit="r", entry="l")
    d.edge("repo", "v1", "auto-deploy", exit="b", entry="l", pts=[(95, 465)])
    d.save()


# ------------------------------------------------------------------ Figure 3
def version_control():
    d = Diagram("fig3_version_control_rollback", "Version control, CI and rollback", 1130, 460)
    d.node("br", "Feature branch\ngit checkout -b feature/x", 20, 60, 170, 60, "data")
    d.node("pr", "Commit + pull\nrequest (review)", 230, 60, 150, 60, "data")
    d.node("ci", "GitHub Actions\npytest -v + smoke run", 420, 60, 160, 60)
    d.node("ok", "Tests\npass?", 620, 45, 110, 90, "dec")
    d.node("mg", "Merge to main\ngit tag -a vX.Y.Z", 770, 60, 150, 60, "data")
    d.node("dp", "Auto-deploy\nRender / Vercel", 960, 60, 150, 60, "plat")
    d.node("mon", "Monitor: dashboard,\nlogs, run_history", 960, 210, 150, 60, "store")
    d.node("hl", "Healthy?", 790, 195, 110, 90, "dec")
    d.node("keep", "Keep release\n(last known good)", 590, 210, 150, 60, "proc")
    d.node("rb1", "1. Instant rollback\nto previous deploy", 960, 360, 150, 60, "bad")
    d.node("rb2", "2. git revert <sha>\n(new commit, history kept)", 740, 360, 170, 60, "bad")
    d.node("rb3", "3. Restore data from\nlast good run artifact", 520, 360, 170, 60, "bad")
    d.node("fix", "Fix on branch +\nadd regression test", 230, 210, 150, 60, "note")
    d.edge("br", "pr"); d.edge("pr", "ci"); d.edge("ci", "ok")
    d.edge("ok", "mg", "yes"); d.edge("mg", "dp")
    d.edge("dp", "mon", exit="b", entry="t")
    d.edge("mon", "hl", exit="l", entry="r")
    d.edge("hl", "keep", "yes", exit="l", entry="r")
    d.edge("hl", "rb1", "no", exit="b", entry="t", pts=[(845, 320), (1035, 320)])
    d.edge("rb1", "rb2", exit="l", entry="r"); d.edge("rb2", "rb3", exit="l", entry="r")
    d.edge("rb3", "fix", exit="l", entry="b", pts=[(305, 390)])
    d.edge("ok", "fix", "no - merge blocked", exit="b", entry="r", pts=[(675, 170), (450, 170), (450, 240)])
    d.edge("fix", "pr", exit="t", entry="b")
    d.save()


# ------------------------------------------------------------------ Figure 4
def troubleshooting():
    d = Diagram("fig4_troubleshooting_workflow", "Troubleshooting workflow", 1240, 520)
    d.node("det", "Detect\nfailed run / exit code /\nalert / dashboard", 20, 215, 160, 80, "bad")
    d.node("loc", "Locate stage\nfilter pipeline.log\nby run_id + stage", 220, 215, 160, 80, "data")
    d.node("cls", "Type of\nissue?", 420, 205, 120, 100, "dec")
    d.node("t1", "Data quality\nrejected_orders.csv\n+ reject_reason", 600, 20, 180, 70, "note")
    d.node("t2", "Code bug\nreproduce with a\nfailing unit test (pytest)", 600, 135, 180, 70, "note")
    d.node("t3", "Performance\nstage_timings +\n--benchmark", 600, 250, 180, 70, "note")
    d.node("t4", "Platform / config\nRender & Vercel logs,\nenv vars, versions", 600, 365, 180, 70, "note")
    d.node("f1", "Fix source data or\nvalidation rule", 830, 20, 170, 70)
    d.node("f2", "Fix code until\ntest passes", 830, 135, 170, 70)
    d.node("f3", "Tune: more workers\n(parallel processing)", 830, 250, 170, 70)
    d.node("f4", "Fix setting /\nroll back deploy", 830, 365, 170, 70)
    d.node("ver", "Verify\nCI green, summary\nnormal, redeploy", 1050, 215, 160, 80, "proc")
    d.edge("det", "loc"); d.edge("loc", "cls")
    for t, f, y in (("t1", "f1", 55), ("t2", "f2", 170), ("t3", "f3", 285), ("t4", "f4", 400)):
        d.edge("cls", t, exit="r", entry="l", pts=[(570, y)])
        d.edge(t, f)
        d.edge(f, "ver", exit="r", entry="l", pts=[(1025, y)])
    d.edge("ver", "det", "monitor next run", exit="b", entry="b", pts=[(1130, 490), (100, 490)], dashed=True)
    d.save()


if __name__ == "__main__":
    architecture(); deployment(); version_control(); troubleshooting()
    print("diagrams written to", OUT)
