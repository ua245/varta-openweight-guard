from pathlib import Path
import re

from PIL import Image, ImageDraw, ImageFont
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "outputs/verta-law-firm-poc-walkthrough.md"
OUTPUT = ROOT / "outputs/verta-law-firm-poc-walkthrough.docx"
TMP = ROOT / "tmp/poc-doc"
TMP.mkdir(parents=True, exist_ok=True)

NAVY = "18314F"
PALE = "EEF3F7"
GRAY = "D9D9D9"
GREEN = "1C6B50"
RED = "A93636"


def font(size, bold=False):
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "",
    ]
    for candidate in candidates[::-1] if bold else candidates:
        if candidate and Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def box(draw, xy, text, fill="#FFFFFF", outline="#18314F", title=False):
    draw.rounded_rectangle(xy, radius=18, fill=fill, outline=outline, width=4)
    x1, y1, x2, y2 = xy
    lines = text.split("\n")
    f = font(31 if title else 27, title)
    heights = [draw.textbbox((0, 0), line, font=f)[3] for line in lines]
    y = (y1 + y2 - sum(heights) - 10 * (len(lines) - 1)) / 2
    for line, height in zip(lines, heights):
        width = draw.textbbox((0, 0), line, font=f)[2]
        draw.text(((x1 + x2 - width) / 2, y), line, fill="#111111", font=f)
        y += height + 10


def arrow(draw, start, end, color="#536170", width=5):
    draw.line([start, end], fill=color, width=width)
    import math
    angle = math.atan2(end[1] - start[1], end[0] - start[0])
    for delta in (2.55, -2.55):
        point = (end[0] + 22 * math.cos(angle + delta), end[1] + 22 * math.sin(angle + delta))
        draw.line([end, point], fill=color, width=width)


def architecture(path):
    im = Image.new("RGB", (2400, 1080), "white")
    d = ImageDraw.Draw(im)
    box(d, (60, 110, 400, 320), "External email\nText or PNG", fill="#F7F0E8")
    box(d, (510, 110, 860, 320), "Roundcube\nand GreenMail", fill="#EEF3F7")
    box(d, (970, 55, 1370, 220), "Visible text\nand local Qwen", fill="#EEF3F7")
    box(d, (970, 265, 1370, 430), "PNG LSB decoder\nand checksum", fill="#EEF3F7")
    box(d, (1480, 130, 1810, 350), "GPT OSS 20B\nagent", fill="#EAF4EF")
    box(d, (1920, 105, 2320, 375), "VARTA tool\npolicy decision", fill="#FFF5E8", title=True)
    box(d, (420, 650, 800, 865), "Approved matter\nfiles", fill="#EEF3F7")
    box(d, (920, 650, 1300, 865), "Privileged\nsettlement record", fill="#FBECEC", outline="#A93636")
    box(d, (1420, 650, 1800, 865), "Local capture\nservice", fill="#FBECEC", outline="#A93636")
    box(d, (1920, 650, 2320, 865), "Internal partner\nbrief and audit", fill="#EAF4EF", outline="#1C6B50")
    arrow(d, (400, 215), (510, 215)); arrow(d, (860, 185), (970, 135)); arrow(d, (860, 245), (970, 345))
    arrow(d, (1370, 135), (1480, 205)); arrow(d, (1370, 345), (1480, 285)); arrow(d, (1810, 240), (1920, 240))
    arrow(d, (2120, 375), (610, 650)); arrow(d, (2120, 375), (1110, 650), color="#A93636")
    arrow(d, (2120, 375), (1610, 650), color="#A93636"); arrow(d, (2120, 375), (2120, 650), color="#1C6B50")
    d.text((60, 965), "The worker has no external network. The demonstration capture endpoint is inside the isolated worker.", fill="#344150", font=font(27))
    im.save(path, quality=95)


def sequence(path):
    im = Image.new("RGB", (2400, 1050), "white")
    d = ImageDraw.Draw(im)
    cols = [(180, "Email"), (700, "Agent"), (1230, "VARTA"), (1760, "Tools"), (2220, "Evidence")]
    for x, label in cols:
        w = d.textbbox((0, 0), label, font=font(30, True))[2]
        d.text((x - w / 2, 45), label, fill="#111111", font=font(30, True))
        d.line([(x, 100), (x, 980)], fill="#C8D0D8", width=3)
    events = [
        (145, 180, 700, "Matter update and hidden instruction", NAVY),
        (275, 700, 1760, "read privileged record", RED),
        (405, 1760, 700, "Off  record contents", RED),
        (535, 700, 1230, "On  policy check with provenance", NAVY),
        (665, 1230, 700, "Deny privileged path and audit", GREEN),
        (795, 700, 1760, "read approved summary and write brief", GREEN),
        (925, 1760, 2220, "Capture result brief and audit", NAVY),
    ]
    for y, start, end, label, color in events:
        arrow(d, (start, y), (end, y), color=f"#{color}", width=5)
        f = font(25)
        tw = d.textbbox((0, 0), label, font=f)[2]
        d.rectangle((min(start, end) + 12, y - 42, min(start, end) + 30 + tw, y - 8), fill="white")
        d.text((min(start, end) + 20, y - 41), label, fill=f"#{color}", font=f)
    im.save(path, quality=95)


def shade(cell, fill):
    tcpr = cell._tc.get_or_add_tcPr()
    shd = tcpr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tcpr.append(shd)
    shd.set(qn("w:fill"), fill)


def borders(table):
    tblpr = table._tbl.tblPr
    b = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        e = OxmlElement(f"w:{edge}")
        e.set(qn("w:val"), "single"); e.set(qn("w:sz"), "6"); e.set(qn("w:color"), GRAY)
        b.append(e)
    tblpr.append(b)


def margins(cell, top=100, start=120, bottom=100, end=120):
    tc = cell._tc.get_or_add_tcPr()
    m = tc.first_child_found_in("w:tcMar")
    if m is None:
        m = OxmlElement("w:tcMar"); tc.append(m)
    for tag, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        el = OxmlElement(f"w:{tag}"); el.set(qn("w:w"), str(value)); el.set(qn("w:type"), "dxa"); m.append(el)


def add_inline(paragraph, text):
    pattern = re.compile(r"(`[^`]+`|\*\*[^*]+\*\*)")
    pos = 0
    for match in pattern.finditer(text):
        if match.start() > pos:
            paragraph.add_run(text[pos:match.start()])
        token = match.group()
        if token.startswith("`"):
            run = paragraph.add_run(token[1:-1]); run.font.name = "Courier New"; run.font.size = Pt(9)
        else:
            paragraph.add_run(token[2:-2]).bold = True
        pos = match.end()
    if pos < len(text):
        paragraph.add_run(text[pos:])


def add_table(doc, rows):
    table = doc.add_table(rows=1, cols=len(rows[0]))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    borders(table)
    for col, value in enumerate(rows[0]):
        cell = table.rows[0].cells[col]; cell.text = value.strip(); shade(cell, NAVY); margins(cell)
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        for run in cell.paragraphs[0].runs:
            run.font.color.rgb = RGBColor(255, 255, 255); run.font.bold = True; run.font.size = Pt(9.2)
    for row_index, values in enumerate(rows[1:]):
        cells = table.add_row().cells
        for col, value in enumerate(values):
            cells[col].text = value.strip(); margins(cells[col]); cells[col].vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            if row_index % 2: shade(cells[col], PALE)
            for run in cells[col].paragraphs[0].runs: run.font.size = Pt(9.2)
    widths = [1.05, 1.55, 2.55, 1.75] if len(rows[0]) == 4 else [6.7 / len(rows[0])] * len(rows[0])
    for row in table.rows:
        for idx, cell in enumerate(row.cells): cell.width = Inches(widths[idx])
    doc.add_paragraph().paragraph_format.space_after = Pt(0)


def add_page_field(paragraph):
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    paragraph.add_run("VARTA PoC Walkthrough   ")
    begin = OxmlElement("w:fldChar"); begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText"); instr.set(qn("xml:space"), "preserve"); instr.text = "PAGE"
    end = OxmlElement("w:fldChar"); end.set(qn("w:fldCharType"), "end")
    paragraph._p.append(begin); paragraph._p.append(instr); paragraph._p.append(end)


def build():
    arch = TMP / "architecture.png"; seq = TMP / "sequence.png"
    architecture(arch); sequence(seq)
    doc = Document()
    sec = doc.sections[0]
    sec.page_width = Inches(8.5); sec.page_height = Inches(11)
    sec.top_margin = Inches(.62); sec.bottom_margin = Inches(.62); sec.left_margin = Inches(.72); sec.right_margin = Inches(.72)
    styles = doc.styles
    styles["Normal"].font.name = "Arial"; styles["Normal"].font.size = Pt(10.5)
    styles["Normal"].paragraph_format.space_after = Pt(5); styles["Normal"].paragraph_format.line_spacing = 1.08
    title = styles["Title"]; title.font.name = "Arial"; title.font.color.rgb = RGBColor(0, 0, 0); title.font.size = Pt(25); title.font.bold = True
    title_ppr = title.element.get_or_add_pPr()
    title_border = title_ppr.find(qn("w:pBdr"))
    if title_border is not None:
        title_ppr.remove(title_border)
    for name, size in (("Heading 1", 16), ("Heading 2", 12)):
        s = styles[name]; s.font.name = "Arial"; s.font.color.rgb = RGBColor(0, 0, 0); s.font.size = Pt(size); s.font.bold = True
        s.paragraph_format.space_before = Pt(9); s.paragraph_format.space_after = Pt(4); s.paragraph_format.keep_with_next = True
    for section in doc.sections: add_page_field(section.footer.paragraphs[0])

    lines = SOURCE.read_text().splitlines()
    i = 0; in_code = False; code_lines = []; mermaid = False; inserted_seq = False
    page_break_heads = {"Architecture", "Attack intent technique and procedure", "Run the demonstration", "Evidence and acceptance criteria", "References"}
    while i < len(lines):
        line = lines[i]
        if line.startswith("```mermaid"):
            mermaid = True; i += 1
            while i < len(lines) and not lines[i].startswith("```"): i += 1
            p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.add_run().add_picture(str(arch), width=Inches(6.85))
            cap = doc.add_paragraph("Figure 1  PoC architecture and control points"); cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
            cap.runs[0].italic = True; cap.runs[0].font.size = Pt(8.5)
            i += 1; continue
        if line.startswith("```"):
            if not in_code:
                in_code = True; code_lines = []
            else:
                p = doc.add_paragraph(); p.style = styles["Normal"]
                p.paragraph_format.left_indent = Inches(.18); p.paragraph_format.right_indent = Inches(.1)
                p.paragraph_format.space_before = Pt(3); p.paragraph_format.space_after = Pt(7)
                shd = OxmlElement("w:shd"); shd.set(qn("w:fill"), "F2F4F6"); p._p.get_or_add_pPr().append(shd)
                run = p.add_run("\n".join(code_lines)); run.font.name = "Courier New"; run.font.size = Pt(8.3)
                in_code = False
            i += 1; continue
        if in_code:
            code_lines.append(line); i += 1; continue
        if line.startswith("# "):
            title_paragraph = doc.add_heading(line[2:], 0)
            direct_border = title_paragraph._p.get_or_add_pPr().find(qn("w:pBdr"))
            if direct_border is not None:
                title_paragraph._p.get_or_add_pPr().remove(direct_border)
            p = doc.add_paragraph("End to end demonstration guide  |  Kingsbridge Vale LLP synthetic scenario  |  15 November 2026")
            p.runs[0].font.size = Pt(9); p.runs[0].font.color.rgb = RGBColor(80, 80, 80)
            i += 1; continue
        if line.startswith("## "):
            head = line[3:]
            if head in page_break_heads and len(doc.paragraphs) > 3: doc.add_page_break()
            if head == "Attack intent technique and procedure" and not inserted_seq:
                p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.add_run().add_picture(str(seq), width=Inches(6.85))
                cap = doc.add_paragraph("Figure 2  Same input and task with the VARTA decision inserted")
                cap.alignment = WD_ALIGN_PARAGRAPH.CENTER; cap.runs[0].italic = True; cap.runs[0].font.size = Pt(8.5)
                inserted_seq = True
            doc.add_heading(head, 1); i += 1; continue
        if line.startswith("| "):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                values = [v.strip() for v in lines[i].strip().strip("|").split("|")]
                if not all(set(v) <= {"-", ":"} for v in values): rows.append(values)
                i += 1
            add_table(doc, rows); continue
        if line.startswith("- "):
            p = doc.add_paragraph(style="List Bullet"); add_inline(p, line[2:]); i += 1; continue
        if re.match(r"^\d+\. ", line):
            match = re.match(r"^(\d+)\. (.*)", line)
            p = doc.add_paragraph(); p.paragraph_format.left_indent = Inches(.24); p.paragraph_format.first_line_indent = Inches(-.24)
            p.paragraph_format.space_after = Pt(3)
            prefix = p.add_run(match.group(1) + ".  "); prefix.bold = True
            add_inline(p, match.group(2)); i += 1; continue
        if not line.strip(): i += 1; continue
        p = doc.add_paragraph(); add_inline(p, line)
        i += 1

    props = doc.core_properties
    props.title = "VARTA Law Firm Prompt Injection Proof of Concept"
    props.subject = "End to end walkthrough for the two mode VARTA demonstration"
    props.author = "VARTA Project Team"
    doc.save(OUTPUT)


if __name__ == "__main__":
    build()
