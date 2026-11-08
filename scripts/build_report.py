"""Builds report/SkyRoute_Task3_Report.docx and prints the main-body word count
(headings, figure/table captions, table cells, references and appendices are not counted)."""
from pathlib import Path

from docx import Document
from docx.enum.section import WD_ORIENT  # noqa: F401
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
DG, EV = ROOT / "diagrams", ROOT / "evidence"
OUT = ROOT / "report" / "SkyRoute_Task3_Report.docx"

doc = Document()
WORDS = 0
FIG = 0

for s in doc.sections:
    s.top_margin = s.bottom_margin = Cm(2.2)
    s.left_margin = s.right_margin = Cm(2.4)
st = doc.styles["Normal"]
st.font.name = "Calibri"
st.font.size = Pt(11)
st.paragraph_format.space_after = Pt(6)
st.paragraph_format.line_spacing = 1.15
for name, size, colour in (("Heading 1", 15, "1B3A8C"), ("Heading 2", 12.5, "1B3A8C"), ("Title", 24, "1B3A8C")):
    h = doc.styles[name]
    h.font.name = "Calibri"
    h.font.size = Pt(size)
    h.font.color.rgb = RGBColor.from_string(colour)
    h.element.rPr.rFonts.set(qn("w:asciiTheme"), "") if h.element.rPr is not None and h.element.rPr.rFonts is not None else None


def para(text, count=True, bold_lead=None):
    """Body paragraph. 'bold_lead' is a short bold run-in heading."""
    global WORDS
    p = doc.add_paragraph()
    p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    if bold_lead:
        p.add_run(bold_lead + " ").bold = True
        if count:
            WORDS += len(bold_lead.split())
    p.add_run(text)
    if count:
        WORDS += len(text.split())
    return p


def figure(path, caption, width=16):
    global FIG
    FIG += 1
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.keep_with_next = True
    p.add_run().add_picture(str(path), width=Cm(width))
    c = doc.add_paragraph()
    c.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = c.add_run(f"Figure {FIG}: {caption}")
    r.italic = True
    r.font.size = Pt(9.5)
    return FIG


def shade(cell, hex_fill):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_fill)
    tcPr.append(shd)


def table(rows, caption, widths=None):
    c = doc.add_paragraph()
    c.alignment = WD_ALIGN_PARAGRAPH.CENTER
    c.paragraph_format.keep_with_next = True
    r = c.add_run(caption)
    r.italic = True
    r.font.size = Pt(9.5)
    t = doc.add_table(rows=len(rows), cols=len(rows[0]))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, row in enumerate(rows):
        for j, val in enumerate(row):
            cell = t.cell(i, j)
            cell.text = ""
            run = cell.paragraphs[0].add_run(val)
            run.font.size = Pt(9.5)
            if i == 0 or j == 0:
                run.bold = True
            if i == 0:
                shade(cell, "DAE3F3")
            if widths:
                cell.width = Cm(widths[j])
    doc.add_paragraph()


def page_number_footer():
    p = doc.sections[0].footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run()
    for tag, text in (("begin", None), (None, "PAGE"), ("end", None)):
        if tag:
            el = OxmlElement("w:fldChar")
            el.set(qn("w:fldCharType"), tag)
        else:
            el = OxmlElement("w:instrText")
            el.set(qn("xml:space"), "preserve")
            el.text = text
        run._r.append(el)


def page_break():
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


# ====================================================================== cover
page_number_footer()
for _ in range(5):
    doc.add_paragraph()
t = doc.add_paragraph(style="Title")
t.alignment = WD_ALIGN_PARAGRAPH.CENTER
t.add_run("Deployment Methods for Data Pipelines and Automated Processes")
sub = doc.add_paragraph()
sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
sub.add_run("Task 3 (LO3) – P4, P5, P6 and M2").font.size = Pt(14)
sub2 = doc.add_paragraph()
sub2.alignment = WD_ALIGN_PARAGRAPH.CENTER
sub2.add_run("Case study: SkyRoute Logistics Ltd").font.size = Pt(13)
for _ in range(6):
    doc.add_paragraph()
info = [("Student", "Valerica Stoica"), ("Unit", "Data Pipelines – Learning Outcome 3"),
        ("Submission date", "November 2026"), ("Word count (main body)", "WORDCOUNT")]
it = doc.add_table(rows=len(info), cols=2)
it.style = "Table Grid"
it.alignment = WD_TABLE_ALIGNMENT.CENTER
for i, (k, v) in enumerate(info):
    it.cell(i, 0).text, it.cell(i, 1).text = k, v
    it.cell(i, 0).paragraphs[0].runs[0].bold = True
    shade(it.cell(i, 0), "DAE3F3")
page_break()

# ====================================================================== contents
doc.add_heading("Contents", level=1)
for line in ["1. Introduction", "2. Deployment processes for new data pipelines (P4)",
             "3. Functions and features of the pipeline (P5)",
             "4. Identifying and troubleshooting pipeline issues (P6)",
             "5. Version control and rollback planning (M2)", "6. Conclusion",
             "References", "Appendix A – Project files and how to run them",
             "Appendix B – Dataset sample", "Appendix C – Pipeline source code"]:
    doc.add_paragraph(line, style="List Paragraph" if False else None).paragraph_format.space_after = Pt(2)
page_break()

# ====================================================================== 1
doc.add_heading("1. Introduction", level=1)
para("SkyRoute Logistics Ltd wants to automate its daily shipment reporting. To compare deployment options, I built a small Python pipeline that reads 241 shipment records, checks them, "
     "enriches them and publishes regional KPIs to a dashboard. Eight faulty rows were added to the "
     "dataset on purpose, so monitoring and troubleshooting could be tried on realistic problems.")

# ====================================================================== 2  P4
doc.add_heading("2. Deployment processes for new data pipelines (P4)", level=1)
para("Figure 1 compares the three approaches I prepared.")
f_dep = figure(DG / "fig2_deployment_methods.png", "Manual, scheduled and serverless deployment of the SkyRoute pipeline (draw.io)")
para("an engineer runs the pipeline on demand with run_pipeline.bat. It needs no infrastructure and suits "
     "testing or one-off backfills, but depends on someone running it on a correctly configured machine, so results are hard to repeat (Densmore, 2021).", bold_lead="Manual deployment:")
para("the job runs at fixed times. The render.yaml blueprint (Figure 2) defines a Render Cron Job that installs the "
     "dependencies, runs the unit tests during the build and starts the pipeline at 02:00 UTC every day "
     "(Render, 2025). This fits SkyRoute's daily data batches, although "
     "a run happens even when no new data has arrived.", bold_lead="Scheduled deployment:")
para("the pipeline is packaged as a Vercel Function (api/run.py) started by Vercel Cron or an authenticated "
     "HTTPS request (Vercel, 2025a). There are no servers to manage, but functions have "
     "time limits and only /tmp is writable (Eismann et al., 2021). Figure 3 shows the function refusing a "
     "request without a token (HTTP 401) and completing a run with one.", bold_lead="Serverless deployment:")
figure(EV / "12_deployment_config.png", "Deployment configuration: Render Cron Job (render.yaml) and Vercel Function with cron (vercel.json)", 14.5)
figure(EV / "10_serverless_function_test.png", "Local test of the serverless endpoint /api/run with and without the secret token", 14.5)
table([
    ["", "Manual", "Scheduled (Render Cron)", "Serverless (Vercel)"],
    ["Trigger", "A person", "Cron expression (UTC)", "Cron, HTTP call or event"],
    ["Set-up effort", "Very low", "Low", "Medium"],
    ["Reliability", "Depends on the person", "High", "High, but time-limited"],
    ["Cost model", "Staff time", "Per run (container)", "Per invocation"],
    ["Best SkyRoute use", "Testing, backfills", "Nightly reporting", "On-demand reports"],
], "Table 1: Comparison of deployment approaches", widths=[3.2, 3.6, 4.4, 4.4])

# ====================================================================== 3  P5
doc.add_heading("3. Functions and features of the pipeline (P5)", level=1)
para("Figure 4 shows the six stages. Extract reads the CSV and retries three times if the file has not yet "
     "arrived. Validate applies nine rules covering dates, regions, statuses, numeric ranges and delivery days, "
     "and removes duplicate order IDs. Failed rows are kept in rejected_orders.csv with a reason instead of "
     "being silently dropped. Transform adds value per item and an on-time flag, Aggregate builds regional "
     "KPIs, and Load writes atomically (temporary file, then rename) so readers never see a half-written file.")
figure(DG / "fig1_pipeline_architecture.png", "SkyRoute pipeline architecture and data flow (draw.io)")
para("These features keep the data flow reliable, secure and efficient. Reliability comes from retries, "
     "a quality gate that blocks publication when over 10% of rows fail, and exit codes a scheduler can act on. Security comes from keeping the CRON_SECRET token in platform environment variables rather "
     "than in code, and from authenticating the serverless endpoint. Efficiency comes from automation and "
     "scheduling, which remove manual effort, and from parallel transformation. "
     "Every run records its timings, row counts and status for monitoring "
     "(Raj et al., 2020; Reis and Housley, 2022).")

# ====================================================================== 4  P6
doc.add_heading("4. Identifying and troubleshooting pipeline issues (P6)", level=1)
para("I followed the workflow in Figure 5: detect, locate, classify, fix and verify.")
figure(DG / "fig4_troubleshooting_workflow.png", "Troubleshooting workflow used for pipeline issues (draw.io)")
para("each log line holds a timestamp, level, run ID and stage name (Figure 7), so a fault can be traced to "
     "the exact step. The dashboard (Figure 6) "
     "shows status, rejections by reason, stage timings and run history. In my runs, eight rows were "
     "rejected, including a negative order value, a UK-style date and an unknown region. Each was listed in "
     "rejected_orders.csv with its reason. Data problems like these are among the most common causes "
     "of pipeline faults (Munappy, Bosch and Olsson, 2020; Foidl et al., 2024). When the input file was "
     "missing, the extract stage retried three times and then stopped with exit code 1 (Figure 8).",
     bold_lead="Monitoring and logging:")
figure(EV / "11_dashboard.png", "Operations dashboard (index.html) built from run_summary.json, region_kpis.json and run_history.json", 13.5)
figure(EV / "01_pipeline_run_log.png", "Structured log output of a manual run, showing each rejected row and the run result", 16)
figure(EV / "09_missing_input_retry.png", "Missing input file: three retries, then a clear error and exit code 1", 16)
para("eighteen pytest tests cover every validation rule, the transformation, duplicate handling, the quality "
     "gate and a full end-to-end run (Figure 9). For a new fault, I first write a test that "
     "reproduces it, then fix the code until it passes; the test then guards against the bug returning (Okken, 2022).", bold_lead="Debugging with unit tests:")
figure(EV / "03_unit_tests_pass.png", "pytest run: all 18 unit and integration tests passing", 15)
para("the stage timings showed that transform became the slowest stage once a per-record carrier lookup was "
     "simulated. As this work waits on I/O, I used a thread pool (Python Software Foundation, 2025). With "
     "20 ms of latency per row, going from one to eight workers cut the stage from 4.98 s to 0.63 s "
     "(Figure 10). A test confirms parallel and sequential results are identical. "
     "CPU-heavy work would need processes instead of threads (Gorelick and Ozsvald, 2020).",
     bold_lead="Performance tuning:")
figure(EV / "04_parallel_benchmark_chart.png", "Effect of parallel processing on the transform stage", 13.5)

# ====================================================================== 5  M2
doc.add_heading("5. Version control and rollback planning (M2)", level=1)
para("Git recorded the whole development history (Figure 11). New work was done on a feature branch and merged "
     "through a reviewed pull request. This supports collaboration, because developers can work in parallel "
     "without overwriting each other, and tracking, because every commit shows what changed and why. Releases were tagged (v1.0.0, v1.1.0, v1.2.1), so the last "
     "known good version is always easy to find.")
figure(EV / "08_git_history.png", "Git branch, merge and release-tag history", 15)
para("Automated testing connects version control to deployment. The GitHub Actions workflow runs the tests and "
     "a smoke run on every push and pull request, and Render repeats the tests during its build, so a change "
     "that fails cannot be merged or deployed (GitHub, 2025; Kim et al., 2021).")
para("To test the rollback plan, I released a faulty change on purpose: v1.2.0 switched the date format to UK "
     "style. Eleven tests failed (Figure 12), and against real data the quality gate rejected 99.6% of rows and "
     "refused to publish (exit code 2, Figure 16). I rolled back with git revert, which adds a new commit that undoes the "
     "change instead of rewriting shared history. All tests passed again and the fix was tagged v1.2.1 "
     "(Figure 13).")
figure(EV / "05_bad_release_tests_fail.png", "Faulty release v1.2.0: the code change and the failing tests", 15)
figure(EV / "07_rollback_revert_tests_pass.png", "Rollback with git revert: all tests pass again", 13)
para("The rollback plan (Figure 14 and ROLLBACK_PLAN.md) sets out triggers, steps and an owner: pause the "
     "schedule, use the platform's instant rollback to restore the previous deployment, revert the code, then "
     "restore data from the last good run, because rolling back code does not undo data already written "
     "(Vercel, 2025b). DORA (2024) links fast recovery from failed changes with stronger delivery performance. "
     "Version control makes failures traceable and reversible, and a rehearsed plan turns a bad release into a "
     "short, controlled event.")
figure(DG / "fig3_version_control_rollback.png", "Version control, CI testing and rollback process (draw.io)")

# ====================================================================== 6
doc.add_heading("6. Conclusion", level=1)
para("For SkyRoute, a scheduled Render cron job best suits nightly reporting, with a serverless function for "
     "on-demand runs and manual runs kept for testing. Logging, unit tests and parallel processing made faults "
     "quick to find and fix, while Git, automated testing and a rehearsed rollback plan made each deployment "
     "safer.")

# ====================================================================== references
page_break()
doc.add_heading("References", level=1)
refs = [
    "Densmore, J. (2021) Data pipelines pocket reference: moving and processing data for analytics. Sebastopol, CA: O'Reilly Media.",
    "DORA (2024) Accelerate State of DevOps Report 2024. Mountain View, CA: Google Cloud. Available at: https://dora.dev/research/2024/dora-report/ (Accessed: 8 November 2026).",
    "Eismann, S., Scheuner, J., van Eyk, E., Schwinger, M., Grohmann, J., Herbst, N., Abad, C.L. and Iosup, A. (2021) 'Serverless applications: why, when, and how?', IEEE Software, 38(1), pp. 32–39.",
    "Foidl, H., Golendukhina, V., Ramler, R. and Felderer, M. (2024) 'Data pipeline quality: influencing factors, root causes of data-related issues, and processing problem areas for developers', Journal of Systems and Software, 207, 111855.",
    "GitHub (2025) GitHub Actions documentation. Available at: https://docs.github.com/en/actions (Accessed: 8 November 2026).",
    "Gorelick, M. and Ozsvald, I. (2020) High performance Python. 2nd edn. Sebastopol, CA: O'Reilly Media.",
    "Kim, G., Humble, J., Debois, P., Willis, J. and Forsgren, N. (2021) The DevOps handbook. 2nd edn. Portland, OR: IT Revolution Press.",
    "Munappy, A.R., Bosch, J. and Olsson, H.H. (2020) 'Data pipeline management in practice: challenges and opportunities', in Product-Focused Software Process Improvement (PROFES 2020). Cham: Springer, pp. 168–184.",
    "Okken, B. (2022) Python testing with pytest. 2nd edn. Raleigh, NC: The Pragmatic Bookshelf.",
    "Python Software Foundation (2025) concurrent.futures – launching parallel tasks. Available at: https://docs.python.org/3/library/concurrent.futures.html (Accessed: 8 November 2026).",
    "Raj, A., Bosch, J., Olsson, H.H. and Wang, T.J. (2020) 'Modelling data pipelines', in 46th Euromicro Conference on Software Engineering and Advanced Applications (SEAA). Portorož: IEEE, pp. 13–20.",
    "Reis, J. and Housley, M. (2022) Fundamentals of data engineering. Sebastopol, CA: O'Reilly Media.",
    "Render (2025) Cron jobs. Available at: https://render.com/docs/cronjobs (Accessed: 8 November 2026).",
    "Vercel (2025a) Cron jobs. Available at: https://vercel.com/docs/cron-jobs (Accessed: 8 November 2026).",
    "Vercel (2025b) Instant Rollback. Available at: https://vercel.com/docs/instant-rollback (Accessed: 8 November 2026).",
]
for r in refs:
    p = doc.add_paragraph(r)
    p.paragraph_format.left_indent = Cm(1)
    p.paragraph_format.first_line_indent = Cm(-1)

# ====================================================================== appendices
page_break()
doc.add_heading("Appendix A – Project files and how to run them", level=1)
table([
    ["File / folder", "Purpose"],
    ["data/orders.csv", "Synthetic SkyRoute dataset: 241 shipments, 8 faulty rows added on purpose"],
    ["scripts/generate_dataset.py", "Rebuilds the dataset with a fixed random seed"],
    ["src/pipeline.py", "Pipeline: extract, validate, parallel transform, aggregate, load, logging"],
    ["tests/test_pipeline.py", "18 pytest unit and integration tests"],
    ["run_pipeline.bat / .sh", "Manual deployment"],
    ["render.yaml", "Render Blueprint: web service (dashboard) and Cron Job (02:00 UTC)"],
    ["server.py", "Render web server: dashboard, /healthz and token-protected /api/run"],
    ["api/run.py, vercel.json", "Serverless deployment – Vercel Function and Vercel Cron"],
    [".github/workflows/ci.yml", "GitHub Actions: tests and smoke run on every push / pull request"],
    ["index.html", "Operations dashboard reading output/*.json"],
    ["ROLLBACK_PLAN.md", "Rollback triggers, steps and safeguards"],
    ["diagrams/*.drawio", "Editable draw.io source for Figures 1, 4, 5 and 14"],
    ["evidence/", "Terminal captures and screenshots used in this report"],
], "Table A1: Project contents", widths=[5.2, 10.8])
for cmd in ["pip install -r requirements.txt", "python src/pipeline.py --workers 4",
            "python src/pipeline.py --benchmark --simulate-latency 20", "pytest -v",
            "python -m http.server 8000   (then open http://localhost:8000)"]:
    p = doc.add_paragraph()
    r = p.add_run(cmd)
    r.font.name = "Consolas"
    r.font.size = Pt(9.5)
    p.paragraph_format.space_after = Pt(1)
doc.add_paragraph()
figure(EV / "02_run_summary.png", "run_summary.json produced by every run (monitoring data)", 13)
figure(EV / "06_quality_gate_blocks_release.png", "Quality gate stopping the faulty v1.2.0 release from publishing output", 16)

page_break()
doc.add_heading("Appendix B – Dataset sample", level=1)
import csv  # noqa: E402
with (ROOT / "data" / "orders.csv").open(encoding="utf-8") as f:
    data = list(csv.reader(f))
sample = [data[0]] + data[1:9] + [data[18], data[43], data[64]]
table(sample, "Table B1: First eight rows plus three of the faulty rows (SR10018, SR10043, SR10064)")
for row in doc.tables[-1].rows:
    for cell in row.cells:
        for r in cell.paragraphs[0].runs:
            r.font.size = Pt(7)
            r.bold = False

page_break()
doc.add_heading("Appendix C – Pipeline source code (src/pipeline.py)", level=1)
for line in (ROOT / "src" / "pipeline.py").read_text(encoding="utf-8").splitlines():
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.line_spacing = 1.0
    r = p.add_run(line if line else " ")
    r.font.name = "Consolas"
    r.font.size = Pt(7.5)

# word count on cover
for cell in doc.tables[0].columns[1].cells:
    if cell.text == "WORDCOUNT":
        cell.text = f"{WORDS} words (excluding headings, captions, tables, references and appendices)"

OUT.parent.mkdir(exist_ok=True)
doc.save(OUT)
print("saved", OUT)
print("main body words:", WORDS, "| figures:", FIG)
