import io
import re

import anthropic
import streamlit as st
from fpdf import FPDF
from dotenv import load_dotenv

load_dotenv()

SYSTEM_PROMPT = """\
You are a senior Site Reliability Engineer writing a blameless post-mortem.
Given free-form incident notes, produce a structured post-mortem in markdown.
Use exactly these sections in this order — do not add or remove any:

# Post-Mortem: [concise incident title]

## Incident Overview
- **Date:** [date if mentioned, otherwise "Not specified"]
- **Severity:** [SEV1 / SEV2 / SEV3 — choose based on scope/impact, give one-line rationale]
- **Duration:** [if determinable from notes, otherwise "Unknown"]
- **Status:** Resolved

## Executive Summary
Two to three sentences covering what broke, why it mattered, and how it was resolved.

## Timeline
| Time | Event |
|------|-------|
| ... | ... |

Use times from the notes; infer relative order if exact times are absent.

## Root Cause Analysis
State the primary root cause in one paragraph, then list contributing factors as bullets.

### 5 Whys
1. Why did [symptom] occur?
2. Why did [cause 1] happen?
3. Why did [cause 2] happen?
4. Why did [cause 3] happen?
5. Why did [cause 4] happen?

## Impact Assessment
- **Users / Customers Affected:** [estimate or "Unknown"]
- **Services Affected:** [list]
- **Business Impact:** [describe revenue, SLA, or trust impact]

## Resolution
Describe the steps taken to mitigate and fully resolve the incident.

## Action Items
| Priority | Action | Suggested Owner | Target Date |
|----------|--------|-----------------|-------------|
| P1 | ... | ... | ... |

Include at least three action items focused on prevention and detection.

## Lessons Learned
### What Went Well
- ...

### What Could Be Improved
- ...
"""


def generate_postmortem(notes: str):
    client = anthropic.Anthropic()
    with client.messages.stream(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Incident notes:\n\n{notes}"}],
    ) as stream:
        for text in stream.text_stream:
            yield text


@st.cache_data
def build_pdf(markdown_text: str) -> bytes:
    pdf = FPDF()
    pdf.set_margins(20, 20, 20)
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=20)

    def clean(text: str) -> str:
        text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
        text = re.sub(r"\*(.+?)\*", r"\1", text)
        text = re.sub(r"`(.+?)`", r"\1", text)
        # Replace common Unicode punctuation with ASCII equivalents
        replacements = {
            "\u2014": "--", "\u2013": "-", "\u2012": "-",
            "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
            "\u2026": "...", "\u2022": "-", "\u00b7": "-",
        }
        for char, sub in replacements.items():
            text = text.replace(char, sub)
        # Drop anything still outside Latin-1
        return text.encode("latin-1", errors="ignore").decode("latin-1")

    for line in markdown_text.splitlines():
        stripped = line.strip()

        if stripped.startswith("# "):
            pdf.set_font("Helvetica", "B", 16)
            pdf.ln(2)
            pdf.multi_cell(0, 8, clean(stripped[2:]))
            pdf.ln(2)
        elif stripped.startswith("## "):
            pdf.set_font("Helvetica", "B", 13)
            pdf.ln(3)
            pdf.multi_cell(0, 7, clean(stripped[3:]))
            pdf.ln(1)
        elif stripped.startswith("### "):
            pdf.set_font("Helvetica", "B", 11)
            pdf.ln(2)
            pdf.multi_cell(0, 6, clean(stripped[4:]))
        elif stripped.startswith("|"):
            cells = [c.strip() for c in stripped.split("|") if c.strip()]
            if all(set(c) <= set("-: ") for c in cells):
                continue
            pdf.set_font("Helvetica", size=9)
            pdf.set_x(pdf.l_margin)
            row_text = "  |  ".join(clean(c) for c in cells)
            pdf.multi_cell(0, 5, row_text)
        elif stripped.startswith(("- ", "* ")):
            pdf.set_font("Helvetica", size=10)
            pdf.set_x(pdf.l_margin + 5)
            pdf.multi_cell(0, 5, "- " + clean(stripped[2:]))
        elif re.match(r"^\d+\.", stripped):
            pdf.set_font("Helvetica", size=10)
            pdf.set_x(pdf.l_margin + 5)
            pdf.multi_cell(0, 5, clean(stripped))
        elif stripped == "":
            pdf.ln(3)
        else:
            pdf.set_font("Helvetica", size=10)
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(0, 5, clean(stripped))

    return bytes(pdf.output())


# ── UI ────────────────────────────────────────────────────────────────────────

st.set_page_config(page_title="Post-Mortem Generator", page_icon="🔍", layout="wide")
st.title("Post-Mortem Generator")
st.caption("Paste raw incident notes and generate a structured, blameless post-mortem.")

notes = st.text_area(
    "Incident Notes",
    height=220,
    placeholder=(
        "Paste anything: Slack thread, alert text, on-call notes, timeline jots...\n\n"
        "Example:\n"
        "~2:14am alert fired for elevated 5xx on checkout service. On-call woke up, "
        "noticed deploy went out at 1:58am. Rolled back at 2:31am, errors dropped. "
        "Root cause: new feature flag was on by default, hit a nil-pointer on orders "
        "with empty promo codes. ~12k users affected during window."
    ),
)

generate_btn = st.button("Generate Post-Mortem", type="primary")

if generate_btn and not notes.strip():
    st.warning("Please enter some incident notes first.")

if generate_btn and notes.strip():
    st.divider()
    output_placeholder = st.empty()
    full_output = ""

    with st.spinner("Generating..."):
        for chunk in generate_postmortem(notes):
            full_output += chunk
            output_placeholder.markdown(full_output + "▌")

    output_placeholder.markdown(full_output)
    st.session_state["postmortem"] = full_output
    st.rerun()

if "postmortem" in st.session_state:
    st.divider()
    st.markdown(st.session_state["postmortem"])
    st.divider()
    col1, col2 = st.columns(2)

    with col1:
        st.download_button(
            label="Download Markdown",
            data=st.session_state["postmortem"],
            file_name="post-mortem.md",
            mime="text/markdown",
        )

    with col2:
        pdf_bytes = build_pdf(st.session_state["postmortem"])
        st.download_button(
            label="Download PDF",
            data=pdf_bytes,
            file_name="post-mortem.pdf",
            mime="application/pdf",
        )
