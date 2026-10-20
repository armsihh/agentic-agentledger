import copy
import docx
from docx.oxml.ns import qn

d = docx.Document("_tmp_image_swapped.docx")
children = list(d.element.body.iterchildren())


def P(idx):
    return docx.text.paragraph.Paragraph(children[idx], d)


# 1. figure caption - simplified, one-colour marker scheme
p183 = P(183)
p183.runs[1].text = (
    "Figure 1. AgentLedger pipeline. Numbered markers show where Gaps 1, 2 and 3 are "
    "addressed (6: Verifier, 2: Integrity Ledger, 5: Policy Checker). The bottom row shows "
    "the three baselines, which lack these components. "
)

# 2. status paragraph after B4 (clone its own body-text style)
p158_el = children[158]
status_b4 = copy.deepcopy(p158_el)
for r in status_b4.findall(qn("w:r")):
    status_b4.remove(r)
new_p = docx.text.paragraph.Paragraph(status_b4, d)
run = new_p.add_run(
    "Phase 1 status: the normalised schema, hash-chain ledger, the ISO/IEC 42001 + NIST AI RMF "
    "control catalogue, tool interfaces, and baselines B0 and B1 are implemented and tested "
    "locally (18 passing tests); see Deliverable C / the GitHub repository."
)
run.italic = True
p158_el.addnext(status_b4)

children = list(d.element.body.iterchildren())


def find_by_prefix(prefix):
    for i, c in enumerate(children):
        if c.tag.split("}")[-1] == "p" and docx.text.paragraph.Paragraph(c, d).text.strip().startswith(prefix):
            return i
    raise ValueError(prefix)


# 3. status paragraph after the B10 baseline bullets (after the B2 bullet)
b2_idx = find_by_prefix("• B2")
b2_el = children[b2_idx]
status_b10 = copy.deepcopy(b2_el)
for r in status_b10.findall(qn("w:r")):
    status_b10.remove(r)
new_p2 = docx.text.paragraph.Paragraph(status_b10, d)
run2 = new_p2.add_run(
    "B0 is implemented from scratch. B1 re-implements the base paper's own three methods, "
    "adapted from its public code (ag2ai/Agents_Failure_Attribution, MIT licensed, kept as a "
    "separate reference clone) onto our schema and provider interface; both run end-to-end "
    "against the synthetic sample logs and B1 has also been smoke-tested against the real "
    "Who&When benchmark."
)
run2.italic = True
b2_el.addnext(status_b10)

children = list(d.element.body.iterchildren())

# 4. B16 checklist line - repo status
idx216 = find_by_prefix("Papers: 10")
p216 = docx.text.paragraph.Paragraph(children[idx216], d)
last_run = p216.runs[-1]
last_run.text = last_run.text.replace(
    "Repository with baseline (Deliverable C) – submitted as a link in Classroom.",
    "Repository with baseline (Deliverable C) – implemented and tested locally; "
    "link submitted in Classroom once pushed.",
)

d.save("_updated.docx")
print("saved")
