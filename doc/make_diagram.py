"""redraws figure 1 (agentledger architecture) - simpler, one accent color only."""
from PIL import Image, ImageDraw, ImageFont

W, H = 1700, 1000
BG = "white"
INK = (20, 20, 20)
GRAY = (235, 235, 235)
GRAY_BORDER = (120, 120, 120)
ACCENT = (31, 58, 95)  # matches the doc's own heading blue (1f3a5f)

img = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(img)

F_TITLE = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 30)
F_BOX_TITLE = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 17)
F_BODY = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 14)
F_SMALL = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 13)
F_NUM = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 14)


def box(xy, title=None, lines=None, fill=GRAY, outline=GRAY_BORDER, dashed=False, width=1.5):
    x0, y0, x1, y1 = xy
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


# title
d.text((W / 2 - 260, 20), "AgentLedger: System Architecture", font=F_TITLE, fill=INK)

# data sources (left column)
box(
    (40, 90, 330, 330),
    "Data & control sources",
    [
        "Who&When logs",
        "(127 annotated failures)",
        "",
        "TRAIL / MAST-Data traces",
        "",
        "Injected-violation logs",
        "",
        "Control catalogue:",
        "ISO/IEC 42001 + NIST AI RMF",
    ],
    fill=GRAY,
)

# agentic audit core (dashed outer box)
core = (370, 90, 1660, 500)
box(core, dashed=True)
d.text((core[0] + 14, core[1] - 26), "Agentic audit core", font=F_BOX_TITLE, fill=INK)

# pipeline boxes - two rows
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

box(b_ingest, "1. Ingestor", ["Normalise logs to the", "RunLog/Event schema"])
box(b_ledger, "2. Integrity Ledger", ["SHA-256 hash chain", "per run, verify_chain()"])
box(b_auditor, "3. Auditor agent", ["Plans the investigation,", "calls tools (ReAct-style)"])
box(b_retriever, "4. Evidence Retriever", ["read_span / search_log", "get_provenance"])
box(b_policy, "5. Policy Checker", ["Evaluates control", "predicates (check_control)"])
box(b_verifier, "6. Verifier agent", ["Rejects claims the", "cited records don't support"])
box(b_report, "7. Audit report", ["finding -> record ->", "control -> hash"])
box(b_reviewer, "8. Human reviewer", ["Approve / reject /", "escalate each finding"])

# flow arrows
arrow((b_ingest[2], row1_y + bh / 2), (b_ledger[0], row1_y + bh / 2))
arrow((b_ledger[2], row1_y + bh / 2), (b_auditor[0], row1_y + bh / 2))
arrow((b_auditor[2], row1_y + bh / 2), (b_retriever[0], row1_y + bh / 2))
arrow((cols[3] + bw / 2, row1_y + bh), (cols[3] + bw / 2, row2_y))
arrow((b_report[0], row2_y + bh / 2), (b_verifier[2], row2_y + bh / 2))
arrow((b_verifier[0], row2_y + bh / 2), (b_policy[2], row2_y + bh / 2))
arrow((b_policy[0], row2_y + bh / 2), (b_reviewer[2], row2_y + bh / 2))
# verifier -> auditor feedback (rejected claims)
arrow((cols[2] + bw / 2, row2_y), (cols[2] + bw / 2, row1_y + bh), color=GRAY_BORDER)
d.text((cols[2] + bw / 2 + 6, row2_y - 18), "reject", font=F_SMALL, fill=GRAY_BORDER)

# gap markers - same colour, just numbered
gap_marker((b_verifier[2] - 14, b_verifier[1] + 14), 1)
gap_marker((b_ledger[2] - 14, b_ledger[1] + 14), 2)
gap_marker((b_policy[2] - 14, b_policy[1] + 14), 3)

# shared state note
d.text((400, 400), "Shared state: claims, cited record IDs, ledger hashes, control IDs, verification status", font=F_SMALL, fill=GRAY_BORDER)

# legend
ly = 520
d.text((40, ly), "Gap markers:", font=F_BOX_TITLE, fill=INK)
gap_marker((160, ly + 10), 1)
d.text((180, ly + 2), "evidence-bound findings", font=F_BODY, fill=INK)
gap_marker((440, ly + 10), 2)
d.text((460, ly + 2), "tamper-evident provenance", font=F_BODY, fill=INK)
gap_marker((730, ly + 10), 3)
d.text((750, ly + 2), "control-level compliance", font=F_BODY, fill=INK)

# baselines row
by0 = 570
d.text((40, by0 - 30), "What the proposed system is compared against:", font=F_BOX_TITLE, fill=INK)
box((40, by0, 560, by0 + 110), "B0 - single LLM call", ["Whole log -> one verdict.", "No tools, no citations, no ledger."])
box((590, by0, 1110, by0 + 110), "B1 - base paper (Who&When)", ["all_at_once / step_by_step /", "binary_search attribution"])
box((1140, by0, 1660, by0 + 110), "B2 - non-agentic RAG audit", ["Retrieve spans, summarise once.", "No verifier, no policy checker."])

img.save("doc/figure1_architecture.png")
print("saved doc/figure1_architecture.png", img.size)
