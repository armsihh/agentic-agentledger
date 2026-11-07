"""phase 2 status diagram: same layout as doc/make_diagram.py, with each box marked
built (green) vs still pending (gray/dashed), for the paper's methodology section."""
from PIL import Image, ImageDraw, ImageFont

W, H = 1700, 800
BG = "white"
INK = (20, 20, 20)
GRAY = (235, 235, 235)
GRAY_BORDER = (120, 120, 120)
ACCENT = (31, 58, 95)
GREEN = (30, 120, 70)
GREEN_FILL = (223, 240, 230)
PENDING_FILL = (245, 238, 220)
PENDING_BORDER = (170, 130, 40)

img = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(img)

F_TITLE = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 30)
F_BOX_TITLE = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 17)
F_BODY = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 14)
F_SMALL = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 13)
F_NUM = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 14)
F_STATUS = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 13)


def box(xy, title=None, lines=None, status=None, fill=GRAY, outline=GRAY_BORDER, dashed=False, width=1.5):
    x0, y0, x1, y1 = xy
    if status == "done":
        fill, outline = GREEN_FILL, GREEN
    elif status == "pending":
        fill, outline = PENDING_FILL, PENDING_BORDER
    if dashed:
        step = 10
        x = x0
        while x < x1:
            d.line([(x, y0), (min(x + step, x1), y0)], fill=outline, width=2)
            d.line([(x, y1), (min(x + step, x1), y1)], fill=outline, width=2)
            x += step * 2
        y = y0
        while y < y1:
            d.line([(x0, y), (x0, min(y + step, y1))], fill=outline, width=2)
            d.line([(x1, y), (x1, min(y + step, y1))], fill=outline, width=2)
            y += step * 2
    else:
        d.rounded_rectangle(xy, radius=8, fill=fill, outline=outline, width=2)
    ty = y0 + 10
    if title:
        d.text((x0 + 12, ty), title, font=F_BOX_TITLE, fill=INK)
        ty += 24
    if lines:
        for line in lines:
            d.text((x0 + 12, ty), line, font=F_BODY, fill=INK)
            ty += 19
    if status:
        label = "DONE" if status == "done" else "PENDING"
        color = GREEN if status == "done" else PENDING_BORDER
        tw = d.textlength(label, font=F_STATUS)
        d.text((x1 - tw - 10, y1 - 20), label, font=F_STATUS, fill=color)


def arrow(p0, p1, width=2, color=INK):
    d.line([p0, p1], fill=color, width=width)
    import math

    ang = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
    size = 8
    for a in (ang + 2.7, ang - 2.7):
        d.line([p1, (p1[0] - size * math.cos(a), p1[1] - size * math.sin(a))], fill=color, width=width)


def gap_marker(center, num):
    r = 12
    x, y = center
    d.ellipse([x - r, y - r, x + r, y + r], fill=ACCENT, outline=ACCENT)
    tw = d.textlength(str(num), font=F_NUM)
    d.text((x - tw / 2, y - 9), str(num), font=F_NUM, fill="white")


d.text((W / 2 - 320, 20), "AgentLedger: Phase 2 Implementation Status", font=F_TITLE, fill=INK)

box(
    (40, 90, 330, 330),
    "Data & control sources",
    [
        "Who&When logs (184 real)",
        "",
        "Injected-violation suite",
        "(30 cases, CTRL-03/07/11)",
        "",
        "Control catalogue:",
        "5/12 predicates implemented",
    ],
    status="done",
)

core = (370, 90, 1660, 500)
box(core, dashed=True)
d.text((core[0] + 14, core[1] - 26), "Agentic audit core", font=F_BOX_TITLE, fill=INK)

bw, bh, gap = 300, 110, 25
row1_y = 120
row2_y = 260
cols = [400, 400 + (bw + gap), 400 + 2 * (bw + gap), 400 + 3 * (bw + gap)]

b_ingest = (cols[0], row1_y, cols[0] + bw, row1_y + bh)
b_ledger = (cols[1], row1_y, cols[1] + bw, row1_y + bh)
b_auditor = (cols[2], row1_y, cols[2] + bw, row1_y + bh)
b_retriever = (cols[3], row1_y, cols[3] + bw, row1_y + bh)

b_report = (cols[3], row2_y, cols[3] + bw, row2_y + bh)
b_verifier = (cols[2], row2_y, cols[2] + bw, row2_y + bh)
b_policy = (cols[1], row2_y, cols[1] + bw, row2_y + bh)
b_reviewer = (cols[0], row2_y, cols[0] + bw, row2_y + bh)

box(b_ingest, "1. Ingestor", ["Normalise logs to the", "RunLog/Event schema"], status="done")
box(b_ledger, "2. Integrity Ledger", ["SHA-256 hash chain.", "Provenance links: pending (Areej)"], status="done")
box(b_auditor, "3. Auditor agent", ["Proposes agent/step,", "cites record ids"], status="done")
box(b_retriever, "4. Retriever", ["Keyword shortlist,", "not whole-log reading"], status="done")
box(b_policy, "5. Policy Checker", ["5/12 predicates;", "7 declared, not yet built"], status="done")
box(b_verifier, "6. Verifier agent", ["Re-reads cited records,", "rejects + 1 revision"], status="done")
box(b_report, "7. Audit report", ["JSON results per run;", "reviewer UI: pending (Areej)"], status="pending")
box(b_reviewer, "8. Human reviewer", ["Approve / reject /", "escalate each finding"], status="pending")

arrow((b_ingest[2], row1_y + bh / 2), (b_ledger[0], row1_y + bh / 2))
arrow((b_ledger[2], row1_y + bh / 2), (b_auditor[0], row1_y + bh / 2))
arrow((b_auditor[2], row1_y + bh / 2), (b_retriever[0], row1_y + bh / 2))
arrow((cols[3] + bw / 2, row1_y + bh), (cols[3] + bw / 2, row2_y))
arrow((b_report[0], row2_y + bh / 2), (b_verifier[2], row2_y + bh / 2))
arrow((b_verifier[0], row2_y + bh / 2), (b_policy[2], row2_y + bh / 2))
arrow((b_policy[0], row2_y + bh / 2), (b_reviewer[2], row2_y + bh / 2))
arrow((cols[2] + bw / 2, row2_y), (cols[2] + bw / 2, row1_y + bh), color=GRAY_BORDER)
d.text((cols[2] + bw / 2 + 6, row2_y - 18), "reject", font=F_SMALL, fill=GRAY_BORDER)

gap_marker((b_verifier[2] - 14, b_verifier[1] + 14), 1)
gap_marker((b_ledger[2] - 14, b_ledger[1] + 14), 2)
gap_marker((b_policy[2] - 14, b_policy[1] + 14), 3)

d.text((400, 400), "Shared state: AuditFinding (agent, step, cited record ids, verified, control_id, passed)", font=F_SMALL, fill=GRAY_BORDER)

ly = 520
d.text((40, ly), "Gap markers:", font=F_BOX_TITLE, fill=INK)
gap_marker((160, ly + 10), 1)
d.text((180, ly + 2), "evidence-bound findings", font=F_BODY, fill=INK)
gap_marker((440, ly + 10), 2)
d.text((460, ly + 2), "tamper-evident provenance", font=F_BODY, fill=INK)
gap_marker((730, ly + 10), 3)
d.text((750, ly + 2), "control-level compliance", font=F_BODY, fill=INK)

by0 = 570
d.text((40, by0 - 30), "What the proposed system is compared against (E1/E2/E3):", font=F_BOX_TITLE, fill=INK)
box((40, by0, 560, by0 + 110), "E1 / B0 - single LLM call", ["Whole log -> one verdict.", "No tools, no citations, no ledger."], status="done")
box((590, by0, 1110, by0 + 110), "E2 / B1 - base paper (Who&When)", ["all_at_once / step_by_step /", "binary_search attribution"], status="done")
box((1140, by0, 1660, by0 + 110), "E3 - proposed system", ["Auditor+Retriever+Verifier", "+Policy Checker, this diagram"], status="done")

ly2 = by0 + 140
d.text((40, ly2 + 3), "Legend:", font=F_BOX_TITLE, fill=INK)
d.rounded_rectangle((150, ly2 - 5, 340, ly2 + 25), radius=6, fill=GREEN_FILL, outline=GREEN, width=2)
d.text((160, ly2 + 2), "implemented", font=F_BODY, fill=INK)
d.rounded_rectangle((420, ly2 - 5, 650, ly2 + 25), radius=6, fill=PENDING_FILL, outline=PENDING_BORDER, width=2)
d.text((430, ly2 + 2), "planned, not yet built", font=F_BODY, fill=INK)

img.save("doc/figure2_phase2_status.png")
print("saved doc/figure2_phase2_status.png", img.size)
