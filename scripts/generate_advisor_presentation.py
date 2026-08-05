from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Iterable

from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = (
    PROJECT_ROOT / "output" / "pdf" / "phish_radar_ai_advisor_presentation_th.pdf"
)
RISK_REPORT_PATH = PROJECT_ROOT / "backend" / "data" / "risk_model_evaluation.json"
MANIFEST_PATH = PROJECT_ROOT / "backend" / "data" / "training_urls.manifest.json"
ICON_PATH = PROJECT_ROOT / "icons" / "icon128.png"

PAGE_W = 960
PAGE_H = 540
MARGIN_X = 54
CONTENT_TOP = 430
CONTENT_BOTTOM = 44

FONT_REGULAR = "LeelaUI"
FONT_BOLD = "LeelaUI-Bold"

BG = HexColor("#0D0D0E")
SURFACE = HexColor("#171719")
SURFACE_2 = HexColor("#202024")
BORDER = HexColor("#323238")
TEXT = HexColor("#F4F3F2")
MUTED = HexColor("#AAA7AA")
ROSE = HexColor("#D76D77")
ROSE_DARK = HexColor("#7E303A")
BLUE = HexColor("#35A9E0")
BLUE_DARK = HexColor("#163E50")
AMBER = HexColor("#F1B653")
GREEN = HexColor("#58C598")
RED = HexColor("#F0646B")
WHITE = HexColor("#FFFFFF")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


RISK_REPORT = load_json(RISK_REPORT_PATH)
MANIFEST = load_json(MANIFEST_PATH)


def register_fonts() -> None:
    regular = Path(r"C:\Windows\Fonts\LeelawUI.ttf")
    bold = Path(r"C:\Windows\Fonts\LeelaUIb.ttf")
    if not regular.exists() or not bold.exists():
        regular = Path(r"C:\Windows\Fonts\tahoma.ttf")
        bold = Path(r"C:\Windows\Fonts\tahomabd.ttf")
    pdfmetrics.registerFont(TTFont(FONT_REGULAR, str(regular), shapable=True))
    pdfmetrics.registerFont(TTFont(FONT_BOLD, str(bold), shapable=True))


def text_width(text: str, font: str, size: float) -> float:
    return pdfmetrics.stringWidth(text, font, size)


def wrap_text(text: str, font: str, size: float, max_width: float) -> list[str]:
    lines: list[str] = []
    for paragraph in text.splitlines() or [""]:
        words = paragraph.split()
        if not words:
            lines.append("")
            continue
        line = words[0]
        for word in words[1:]:
            candidate = f"{line} {word}"
            if text_width(candidate, font, size) <= max_width:
                line = candidate
            else:
                lines.append(line)
                line = word
        lines.append(line)
    return lines


def draw_text(
    c: canvas.Canvas,
    x: float,
    y: float,
    text: str,
    *,
    font: str = FONT_REGULAR,
    size: float = 12,
    color=TEXT,
    max_width: float | None = None,
    leading: float | None = None,
    max_lines: int | None = None,
) -> float:
    leading = leading or size * 1.45
    lines = [text] if max_width is None else wrap_text(text, font, size, max_width)
    if max_lines is not None:
        lines = lines[:max_lines]
    c.setFont(font, size)
    c.setFillColor(color)
    current_y = y
    for line in lines:
        c.drawString(x, current_y, line, shaping=True)
        current_y -= leading
    return current_y


def draw_centered(
    c: canvas.Canvas,
    x: float,
    y: float,
    text: str,
    *,
    font: str = FONT_REGULAR,
    size: float = 12,
    color=TEXT,
) -> None:
    c.setFont(font, size)
    c.setFillColor(color)
    c.drawCentredString(x, y, text, shaping=True)


def rounded_card(
    c: canvas.Canvas,
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    fill=SURFACE,
    stroke=BORDER,
    radius: float = 14,
    line_width: float = 1,
) -> None:
    c.setFillColor(fill)
    c.setStrokeColor(stroke)
    c.setLineWidth(line_width)
    c.roundRect(x, y, w, h, radius, stroke=1, fill=1)


def line(c: canvas.Canvas, x1: float, y1: float, x2: float, y2: float, color=BORDER) -> None:
    c.setStrokeColor(color)
    c.setLineWidth(1)
    c.line(x1, y1, x2, y2)


def arrow(
    c: canvas.Canvas,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    *,
    color=ROSE,
    width: float = 2,
) -> None:
    c.setStrokeColor(color)
    c.setFillColor(color)
    c.setLineWidth(width)
    c.line(x1, y1, x2, y2)
    angle = math.atan2(y2 - y1, x2 - x1)
    head = 8
    for offset in (2.6, -2.6):
        hx = x2 - head * math.cos(angle) + offset * math.sin(angle)
        hy = y2 - head * math.sin(angle) - offset * math.cos(angle)
        c.line(x2, y2, hx, hy)


def badge(
    c: canvas.Canvas,
    x: float,
    y: float,
    text: str,
    *,
    fill=ROSE_DARK,
    color=TEXT,
    size: float = 9,
) -> float:
    w = text_width(text, FONT_BOLD, size) + 20
    c.setFillColor(fill)
    c.roundRect(x, y, w, 22, 11, stroke=0, fill=1)
    draw_centered(c, x + w / 2, y + 6.2, text, font=FONT_BOLD, size=size, color=color)
    return w


def bullet_list(
    c: canvas.Canvas,
    x: float,
    y: float,
    items: Iterable[str],
    *,
    width: float,
    size: float = 12,
    leading: float = 18,
    color=TEXT,
    marker=ROSE,
    gap: float = 9,
) -> float:
    current_y = y
    for item in items:
        lines = wrap_text(item, FONT_REGULAR, size, width - 25)
        c.setFillColor(marker)
        c.circle(x + 5, current_y + 3, 3.3, stroke=0, fill=1)
        for index, wrapped in enumerate(lines):
            draw_text(
                c,
                x + 18,
                current_y - index * leading,
                wrapped,
                font=FONT_REGULAR,
                size=size,
                color=color,
            )
        current_y -= len(lines) * leading + gap
    return current_y


def metric_card(
    c: canvas.Canvas,
    x: float,
    y: float,
    w: float,
    label: str,
    value: str,
    *,
    accent=ROSE,
) -> None:
    rounded_card(c, x, y, w, 82, fill=SURFACE, stroke=BORDER)
    c.setFillColor(accent)
    c.roundRect(x + 14, y + 16, 4, 50, 2, stroke=0, fill=1)
    draw_text(c, x + 30, y + 49, value, font=FONT_BOLD, size=24, color=TEXT)
    draw_text(c, x + 30, y + 23, label, font=FONT_REGULAR, size=10, color=MUTED)


def footer(c: canvas.Canvas, page: int, section: str) -> None:
    line(c, MARGIN_X, 27, PAGE_W - MARGIN_X, 27, HexColor("#27272B"))
    draw_text(
        c,
        MARGIN_X,
        12,
        f"PHISH RADAR AI  /  {section}",
        font=FONT_BOLD,
        size=7.8,
        color=HexColor("#747178"),
    )
    draw_text(
        c,
        PAGE_W - MARGIN_X - 22,
        12,
        f"{page:02d}",
        font=FONT_BOLD,
        size=8,
        color=HexColor("#747178"),
    )


def page_header(
    c: canvas.Canvas,
    page: int,
    section: str,
    title: str,
    subtitle: str | None = None,
) -> None:
    c.setFillColor(BG)
    c.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)
    c.setFillColor(ROSE)
    c.roundRect(MARGIN_X, 489, 35, 4, 2, stroke=0, fill=1)
    draw_text(c, MARGIN_X, 466, section.upper(), font=FONT_BOLD, size=8.5, color=ROSE)
    draw_text(c, MARGIN_X, 425, title, font=FONT_BOLD, size=27, color=TEXT)
    if subtitle:
        draw_text(
            c,
            MARGIN_X,
            398,
            subtitle,
            font=FONT_REGULAR,
            size=11.5,
            color=MUTED,
            max_width=PAGE_W - 2 * MARGIN_X,
            leading=17,
        )
    footer(c, page, section)


def draw_logo(c: canvas.Canvas, x: float, y: float, size: float) -> None:
    if ICON_PATH.exists():
        c.drawImage(
            ImageReader(str(ICON_PATH)),
            x,
            y,
            width=size,
            height=size,
            mask="auto",
            preserveAspectRatio=True,
        )
    else:
        c.setFillColor(BLUE_DARK)
        c.circle(x + size / 2, y + size / 2, size / 2, stroke=0, fill=1)
        c.setFillColor(ROSE)
        c.circle(x + size / 2, y + size / 2, size / 6, stroke=0, fill=1)


def slide_cover(c: canvas.Canvas, page: int) -> None:
    c.setFillColor(BG)
    c.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)

    radar_x, radar_y = 760, 286
    for radius, alpha_color in (
        (185, HexColor("#25171A")),
        (145, HexColor("#382024")),
        (105, HexColor("#51272F")),
        (65, HexColor("#71313C")),
    ):
        c.setStrokeColor(alpha_color)
        c.setLineWidth(1.2)
        c.circle(radar_x, radar_y, radius, stroke=1, fill=0)
    c.setStrokeColor(ROSE)
    c.setLineWidth(2)
    c.line(radar_x, radar_y, radar_x + 122, radar_y + 72)
    for px, py, radius in (
        (radar_x + 122, radar_y + 72, 5),
        (radar_x - 65, radar_y + 92, 4),
        (radar_x + 45, radar_y - 126, 4),
        (radar_x - 115, radar_y - 46, 3),
    ):
        c.setFillColor(ROSE)
        c.circle(px, py, radius, stroke=0, fill=1)

    rounded_card(c, 58, 425, 190, 54, fill=SURFACE, stroke=BORDER, radius=12)
    draw_logo(c, 70, 435, 34)
    draw_text(c, 114, 455, "PHISH RADAR AI", font=FONT_BOLD, size=13, color=TEXT)
    draw_text(c, 114, 438, "SECURE ACCESS", font=FONT_BOLD, size=7.5, color=ROSE)

    draw_text(
        c,
        58,
        345,
        "ระบบคัดกรอง URL และเว็บไซต์เสี่ยง",
        font=FONT_BOLD,
        size=34,
        color=TEXT,
    )
    draw_text(
        c,
        58,
        298,
        "ด้วย Layered Evidence + L1 Logistic Risk Model",
        font=FONT_BOLD,
        size=24,
        color=ROSE,
    )
    draw_text(
        c,
        58,
        253,
        "Chrome Extension / Web App / FastAPI / MySQL / Qwen",
        font=FONT_REGULAR,
        size=13,
        color=MUTED,
    )

    rounded_card(c, 58, 125, 525, 88, fill=SURFACE, stroke=BORDER, radius=16)
    draw_text(
        c,
        82,
        181,
        "แนวคิดหลัก",
        font=FONT_BOLD,
        size=10,
        color=ROSE,
    )
    draw_text(
        c,
        82,
        152,
        "ตรวจจับก่อนผู้ใช้กรอก Password หรือ OTP พร้อมอธิบายเหตุผล",
        font=FONT_BOLD,
        size=17,
        color=TEXT,
    )
    draw_text(
        c,
        82,
        131,
        "ออกแบบให้ทำงานแบบ local ได้ และต่อยอดสู่ระบบ AI ที่วัดผลได้",
        font=FONT_REGULAR,
        size=10.5,
        color=MUTED,
    )

    draw_text(
        c,
        58,
        70,
        "เอกสารนำเสนออาจารย์  /  24 กรกฎาคม 2026",
        font=FONT_REGULAR,
        size=10,
        color=HexColor("#7D797F"),
    )
    footer(c, page, "PROJECT OVERVIEW")
    c.showPage()


def slide_problem(c: canvas.Canvas, page: int) -> None:
    page_header(
        c,
        page,
        "01 / Problem",
        "ปัญหาและวัตถุประสงค์",
        "ผู้ใช้มักตัดสินใจจากหน้าตาและข้อความลิงก์ ก่อนเห็นโดเมนปลายทางจริง",
    )

    rounded_card(c, 54, 80, 405, 282, fill=SURFACE, stroke=BORDER)
    badge(c, 76, 320, "ปัญหาที่ต้องแก้", fill=ROSE_DARK)
    bullet_list(
        c,
        76,
        282,
        [
            "Phishing ใช้โดเมนคล้ายแบรนด์ คำว่า login/verify และหน้าเก็บรหัสผ่านเพื่อสร้างความน่าเชื่อถือ",
            "การเตือนหลังผู้ใช้เข้าเว็บแล้วอาจช้าเกินไป โดยเฉพาะเมื่อมีการขอ Password หรือ OTP",
            "ระบบที่บล็อกอย่างเดียวอธิบายไม่ได้ ทำให้ผู้ใช้ไม่เข้าใจและเกิด False Positive ได้ง่าย",
        ],
        width=355,
        size=12,
        leading=18,
    )

    rounded_card(c, 483, 80, 423, 282, fill=SURFACE_2, stroke=BORDER)
    badge(c, 506, 320, "วัตถุประสงค์", fill=BLUE_DARK, color=TEXT)
    objectives = [
        ("01", "ตรวจลิงก์และบริบทหน้าเว็บก่อนเข้าถึง"),
        ("02", "ผสม RuleScore 40% กับ MLScore 60% และคุม FPR"),
        ("03", "เก็บบัญชี อุปกรณ์ Session และประวัติอย่างปลอดภัย"),
        ("04", "ให้ LLM อธิบายผล แต่ไม่อนุญาตให้เปลี่ยนคำตัดสิน"),
    ]
    for index, (number, text) in enumerate(objectives):
        y = 276 - index * 54
        c.setFillColor(BG)
        c.circle(526, y + 3, 17, stroke=0, fill=1)
        draw_centered(c, 526, y - 1, number, font=FONT_BOLD, size=9, color=ROSE)
        draw_text(c, 555, y + 7, text, font=FONT_REGULAR, size=11.5, color=TEXT)
        if index < len(objectives) - 1:
            line(c, 506, y - 24, 880, y - 24, BORDER)
    c.showPage()


def slide_architecture(c: canvas.Canvas, page: int) -> None:
    page_header(
        c,
        page,
        "02 / Architecture",
        "สถาปัตยกรรมระบบแบบหลายชั้น",
        "Extension ยังตรวจแบบ local ได้เมื่อ Backend หรือ LLM ไม่พร้อม",
    )

    layers = [
        (70, 274, 165, 116, "Chrome Extension", "สแกน URL / DOM / Form\nดัก navigation ก่อนเปิดเว็บ", ROSE_DARK),
        (278, 274, 165, 116, "Web App", "Login / Dashboard\nHistory / Settings / Report", BLUE_DARK),
        (486, 274, 165, 116, "FastAPI Backend", "Predict / Auth / History\nLLM explanation / Feedback", HexColor("#433024")),
        (694, 274, 196, 116, "MySQL + Model", "Users / Devices / Sessions\nSearchHistory / model.pkl", HexColor("#27352F")),
    ]
    for x, y, w, h, heading, body, accent in layers:
        rounded_card(c, x, y, w, h, fill=SURFACE, stroke=BORDER)
        c.setFillColor(accent)
        c.roundRect(x, y + h - 8, w, 8, 4, stroke=0, fill=1)
        draw_text(c, x + 16, y + 77, heading, font=FONT_BOLD, size=13, color=TEXT)
        draw_text(
            c,
            x + 16,
            y + 50,
            body,
            font=FONT_REGULAR,
            size=9.8,
            color=MUTED,
            max_width=w - 30,
            leading=15,
        )
    for left, right in ((235, 278), (443, 486), (651, 694)):
        arrow(c, left + 7, 332, right - 7, 332, color=ROSE, width=1.8)

    rounded_card(c, 70, 105, 820, 112, fill=HexColor("#111214"), stroke=BORDER)
    draw_text(c, 92, 185, "เส้นทางข้อมูลที่ออกแบบให้ลดความเสียหาย", font=FONT_BOLD, size=12, color=ROSE)
    safeguards = [
        ("Rule-based local", "ใช้ได้ทันทีโดยไม่ต้องส่ง URL ออกนอกเครื่อง"),
        ("Risk Model API", "L1 Logistic model และ policy ถูกโหลดจาก Backend"),
        ("LLM optional", "สร้างคำอธิบายเท่านั้น หากไม่พร้อมใช้ข้อความสำรอง"),
        ("SQL security", "เก็บ PasswordHash และ TokenHash ไม่เก็บ secret ดิบ"),
    ]
    for index, (label, body) in enumerate(safeguards):
        x = 92 + index * 198
        draw_text(c, x, 151, label, font=FONT_BOLD, size=10.2, color=TEXT)
        draw_text(
            c,
            x,
            128,
            body,
            font=FONT_REGULAR,
            size=8.6,
            color=MUTED,
            max_width=174,
            leading=12,
        )
    c.showPage()


def slide_flow(c: canvas.Canvas, page: int) -> None:
    page_header(
        c,
        page,
        "03 / Detection Flow",
        "ตรวจจับก่อนเข้าถึง และอธิบายได้",
        "ระบบรวมสัญญาณจาก URL หน้าเว็บ และนโยบายที่ผ่านการประเมิน",
    )

    flow = [
        ("1", "รับ URL / หน้าเว็บ", "navigation, link, form,\nclipboard หรือ QR"),
        ("2", "คำนวณ RuleScore", "URL structure, brand,\nredirect, DOM context"),
        ("3", "คำนวณ MLScore", "sigmoid probability\nจาก L1 Logistic"),
        ("4", "คำนวณ FinalScore", "Rule 40% + ML 60%\nแล้วกำหนด decision"),
        ("5", "ตอบสนอง", "อนุญาต / เตือน / บันทึก\nและอธิบายเหตุผล"),
    ]
    for index, (number, heading, body) in enumerate(flow):
        x = 52 + index * 180
        rounded_card(c, x, 240, 154, 142, fill=SURFACE, stroke=BORDER)
        c.setFillColor(ROSE if index in (1, 3) else BLUE)
        c.circle(x + 25, 350, 14, stroke=0, fill=1)
        draw_centered(c, x + 25, 345, number, font=FONT_BOLD, size=9, color=BG)
        draw_text(c, x + 18, 316, heading, font=FONT_BOLD, size=11.5, color=TEXT)
        draw_text(
            c,
            x + 18,
            286,
            body,
            font=FONT_REGULAR,
            size=9,
            color=MUTED,
            max_width=120,
            leading=13,
        )
        if index < len(flow) - 1:
            arrow(c, x + 158, 311, x + 174, 311, color=HexColor("#68646B"), width=1.5)

    rounded_card(c, 52, 82, 856, 105, fill=SURFACE_2, stroke=BORDER)
    draw_text(c, 76, 151, "ตัวอย่างสัญญาณที่อธิบายให้ผู้ใช้เห็นได้", font=FONT_BOLD, size=11.5, color=ROSE)
    signals = [
        "HTTP บนหน้า Login",
        "Subdomain ซ้อน",
        "Brand impersonation",
        "Punycode / Homoglyph",
        "Redirect ซ่อนปลายทาง",
        "Password / OTP form",
        "ลิงก์ย่อ / ไฟล์เสี่ยง",
        "ข้อความลิงก์ไม่ตรง URL",
    ]
    x, y = 76, 112
    for signal in signals:
        width = badge(c, x, y, signal, fill=HexColor("#2B292E"), color=TEXT, size=8.5)
        x += width + 8
        if x > 820:
            x = 76
            y -= 30
    c.showPage()


def slide_dataset(c: canvas.Canvas, page: int) -> None:
    page_header(
        c,
        page,
        "04 / Dataset",
        "ชุดข้อมูลสมดุลและป้องกันข้อมูลรั่วไหล",
        "ข้อมูลถูก parse เป็นข้อความเท่านั้น ระบบสร้าง Dataset ไม่เข้าเยี่ยมชม URL ใน feed",
    )

    row_count = int(RISK_REPORT["dataset"]["row_count"])
    unique_hosts = int(RISK_REPORT["dataset"]["unique_hostname_groups"])
    labels = RISK_REPORT["dataset"]["labels"]
    sources = RISK_REPORT["dataset"]["sources"]

    metric_card(c, 54, 303, 190, "URL ทั้งหมด", f"{row_count:,}", accent=ROSE)
    metric_card(c, 260, 303, 190, "Phishing / Legitimate", f"{labels['1']:,} / {labels['0']:,}", accent=BLUE)
    metric_card(c, 466, 303, 190, "Unique hostnames", f"{unique_hosts:,}", accent=AMBER)
    metric_card(c, 672, 303, 234, "Random seed", "42", accent=GREEN)

    rounded_card(c, 54, 85, 405, 185, fill=SURFACE, stroke=BORDER)
    draw_text(c, 76, 237, "แหล่งข้อมูล", font=FONT_BOLD, size=13, color=TEXT)
    source_rows = [
        ("PhishTank", int(sources["phishtank"]), ROSE),
        ("OpenPhish", int(sources["openphish"]), AMBER),
        ("Tranco", int(sources["tranco"]), BLUE),
        ("Project seed", int(sources["seed"]), GREEN),
    ]
    max_source = max(value for _, value, _ in source_rows)
    for index, (name, value, color) in enumerate(source_rows):
        y = 201 - index * 34
        draw_text(c, 76, y + 5, name, font=FONT_REGULAR, size=9.5, color=MUTED)
        c.setFillColor(HexColor("#2A292D"))
        c.roundRect(160, y, 220, 10, 5, stroke=0, fill=1)
        c.setFillColor(color)
        c.roundRect(160, y, 220 * value / max_source, 10, 5, stroke=0, fill=1)
        draw_text(c, 393, y + 1, f"{value:,}", font=FONT_BOLD, size=8.5, color=TEXT)

    rounded_card(c, 483, 85, 423, 185, fill=SURFACE_2, stroke=BORDER)
    draw_text(c, 505, 237, "หลักการเตรียมข้อมูล", font=FONT_BOLD, size=13, color=TEXT)
    bullet_list(
        c,
        505,
        205,
        [
            "Normalize และลบ URL ซ้ำแบบ case-insensitive",
            "ตัด hostname ที่มี label conflict ออกจากฝั่ง legitimate",
            "Group ตาม hostname เพื่อไม่ให้โดเมนเดียวกันรั่วข้าม fold",
            "บันทึก SHA-256 ของ Dataset, feed และ analyzer เพื่อทำซ้ำได้",
        ],
        width=372,
        size=10,
        leading=15,
        gap=5,
        marker=BLUE,
    )
    c.showPage()


def slide_experiment(c: canvas.Canvas, page: int) -> None:
    page_header(
        c,
        page,
        "05 / Experiment",
        "Grouped Evaluation และ FPR-controlled Policy",
        "แยก grouped holdout ก่อนเลือกโมเดลและ threshold เพื่อลดข้อมูลรั่วไหล",
    )

    stages = [
        ("A", "Grouped holdout", "กันข้อมูลทดสอบก่อน\nGroup = hostname"),
        ("B", "StratifiedGroupKFold", "5 folds บน development\nสร้าง OOF probability"),
        ("C", "L1 Logistic", "เลือก C จาก Log loss\nBrier และ ROC-AUC"),
        ("D", "Two thresholds", "warn FPR <= 1%\nblock FPR <= 0.1%"),
    ]
    for index, (code, title, body) in enumerate(stages):
        x = 55 + index * 222
        rounded_card(c, x, 250, 196, 130, fill=SURFACE, stroke=BORDER)
        draw_text(c, x + 16, 349, code, font=FONT_BOLD, size=10, color=ROSE)
        draw_text(c, x + 16, 318, title, font=FONT_BOLD, size=12, color=TEXT)
        draw_text(
            c,
            x + 16,
            286,
            body,
            font=FONT_REGULAR,
            size=9.5,
            color=MUTED,
            max_width=164,
            leading=14,
        )
        if index < len(stages) - 1:
            arrow(c, x + 198, 315, x + 219, 315, color=ROSE, width=1.5)

    rounded_card(c, 55, 83, 850, 112, fill=SURFACE_2, stroke=BORDER)
    draw_text(c, 77, 161, "กติกาเลือก Policy", font=FONT_BOLD, size=12, color=ROSE)
    draw_text(
        c,
        77,
        130,
        "บังคับ Wilson upper bound 95% ของ FPR ไม่เกินเพดาน แล้วเลือก Recall สูงสุด",
        font=FONT_BOLD,
        size=15,
        color=TEXT,
    )
    draw_text(
        c,
        77,
        104,
        "Threshold ใช้ development OOF เท่านั้น ส่วน grouped holdout ใช้รายงานผลอิสระ",
        font=FONT_REGULAR,
        size=10.5,
        color=MUTED,
    )
    c.showPage()


def slide_policy(c: canvas.Canvas, page: int) -> None:
    page_header(
        c,
        page,
        "06 / Learned Risk",
        "FinalScore = 0.40(RuleScore) + 0.60(MLScore)",
        "MLScore เรียนจากข้อมูล ส่วน RuleScore มาจากกฎและบริบทใน browser",
    )

    warning = RISK_REPORT["policy"]["warning"]
    blocking = RISK_REPORT["policy"]["blocking"]
    rounded_card(c, 54, 245, 552, 137, fill=SURFACE, stroke=BORDER)
    draw_text(c, 78, 344, "FinalScore", font=FONT_BOLD, size=13, color=ROSE)
    draw_text(
        c,
        78,
        299,
        "0.40 x RuleScore + 0.60 x MLScore",
        font=FONT_BOLD,
        size=24,
        color=TEXT,
    )
    draw_text(
        c,
        78,
        270,
        "L1 Logistic Regression จาก URL features",
        font=FONT_REGULAR,
        size=12,
        color=MUTED,
    )

    rounded_card(c, 630, 245, 276, 137, fill=SURFACE_2, stroke=BORDER)
    draw_text(c, 654, 344, "Decision policy", font=FONT_BOLD, size=12, color=BLUE)
    draw_text(c, 654, 306, f"warn >= {warning['threshold']:.2f}", font=FONT_BOLD, size=19, color=TEXT)
    draw_text(
        c,
        654,
        273,
        f"block >= {blocking['threshold']:.2f}",
        font=FONT_BOLD,
        size=19,
        color=TEXT,
    )

    rounded_card(c, 54, 86, 852, 112, fill=HexColor("#111214"), stroke=BORDER)
    components = [
        (76, "Rule evidence", "อธิบายสัญญาณได้\nและทำงาน local"),
        (285, "URL features", "lexical และ host clues\nschema มี version"),
        (494, "FinalScore", "RuleScore 40%\nMLScore 60%"),
        (703, "Decision", "allow / warn / block\nจาก model policy"),
    ]
    for index, (x, title, body) in enumerate(components):
        draw_text(c, x, 160, title, font=FONT_BOLD, size=11, color=ROSE if index % 2 == 0 else BLUE)
        draw_text(
            c,
            x,
            132,
            body,
            font=FONT_REGULAR,
            size=9,
            color=MUTED,
            max_width=165,
            leading=13,
        )
        if index < len(components) - 1:
            arrow(c, x + 172, 138, x + 199, 138, color=HexColor("#5E5A61"), width=1.2)
    c.showPage()


def slide_results(c: canvas.Canvas, page: int) -> None:
    page_header(
        c,
        page,
        "07 / Results",
        "Development OOF เทียบ Independent Grouped Holdout",
        "รายงานผลจริงรวมข้อจำกัด ไม่ใช้ holdout เพื่อปรับค่าโมเดลหรือ threshold",
    )

    selected = RISK_REPORT["independent_holdout"]["warning"]
    metrics = [
        ("Precision", selected["precision"], ROSE),
        ("Recall", selected["recall"], BLUE),
        ("F1", selected["f1"], AMBER),
        ("ROC-AUC", selected["roc_auc"], GREEN),
        ("FPR", selected["false_positive_rate"], RED),
    ]
    for index, (label, value, color) in enumerate(metrics):
        metric_card(
            c,
            54 + index * 171,
            312,
            157,
            label,
            f"{value * 100:.2f}%",
            accent=color,
        )

    rounded_card(c, 54, 82, 410, 192, fill=SURFACE, stroke=BORDER)
    draw_text(c, 76, 241, "Confusion Matrix", font=FONT_BOLD, size=12, color=TEXT)
    cells = [
        (76, 161, "TN", int(selected["true_negative"]), BLUE_DARK),
        (224, 161, "FP", int(selected["false_positive"]), ROSE_DARK),
        (76, 95, "FN", int(selected["false_negative"]), HexColor("#493821")),
        (224, 95, "TP", int(selected["true_positive"]), HexColor("#224134")),
    ]
    for x, y, label, value, fill in cells:
        rounded_card(c, x, y, 128, 54, fill=fill, stroke=fill, radius=10)
        draw_text(c, x + 12, y + 31, label, font=FONT_BOLD, size=9, color=MUTED)
        draw_text(c, x + 45, y + 25, f"{value:,}", font=FONT_BOLD, size=17, color=TEXT)
    draw_text(c, 366, 185, "Predicted", font=FONT_REGULAR, size=8, color=MUTED)
    draw_text(c, 366, 118, "Actual", font=FONT_REGULAR, size=8, color=MUTED)

    probability = RISK_REPORT["independent_holdout"]["probability"]
    development = RISK_REPORT["probability_quality"]["development_out_of_fold"]
    rounded_card(c, 488, 82, 418, 192, fill=SURFACE_2, stroke=BORDER)
    draw_text(c, 510, 241, "Probability Quality", font=FONT_BOLD, size=12, color=TEXT)
    rows = [
        ("Brier score", development["brier_score"], probability["brier_score"]),
        ("Log loss", development["log_loss"], probability["log_loss"]),
    ]
    for index, (label, before, after) in enumerate(rows):
        y = 187 - index * 64
        draw_text(c, 510, y + 11, label, font=FONT_BOLD, size=9.5, color=MUTED)
        max_value = max(before, after)
        c.setFillColor(HexColor("#39363B"))
        c.roundRect(610, y + 19, 210, 10, 5, stroke=0, fill=1)
        c.setFillColor(ROSE)
        c.roundRect(610, y + 19, 210 * before / max_value, 10, 5, stroke=0, fill=1)
        c.setFillColor(HexColor("#39363B"))
        c.roundRect(610, y - 2, 210, 10, 5, stroke=0, fill=1)
        c.setFillColor(BLUE)
        c.roundRect(610, y - 2, 210 * after / max_value, 10, 5, stroke=0, fill=1)
        draw_text(c, 832, y + 18, f"{before:.6f}", font=FONT_REGULAR, size=8, color=ROSE)
        draw_text(c, 832, y - 3, f"{after:.6f}", font=FONT_REGULAR, size=8, color=BLUE)
    badge(c, 510, 95, "Development OOF", fill=ROSE_DARK, size=7.5)
    badge(c, 625, 95, "Grouped holdout", fill=BLUE_DARK, size=7.5)
    c.showPage()


def slide_auth(c: canvas.Canvas, page: int) -> None:
    page_header(
        c,
        page,
        "08 / Authentication",
        "ระบบสมาชิกและฐานข้อมูลที่ไม่เก็บ Secret ดิบ",
        "User และ Admin ใช้หน้า Login เดียวกัน แต่บัญชีใหม่เริ่มต้นเป็น Role = user เสมอ",
    )

    tables = [
        ("Users", ["UserID", "Username", "Email", "PasswordHash", "Role", "IsActive"], ROSE_DARK),
        ("UserDevices", ["DeviceName", "DeviceKeyHash", "Trusted", "Revoked", "LastSeenAt"], BLUE_DARK),
        ("Sessions", ["UserID", "UserDeviceID", "TokenHash", "ExpiresAt", "RevokedAt"], HexColor("#433024")),
        ("SearchHistory", ["URL ที่ sanitize", "RiskScore/Decision", "Model/Policy version", "Device", "CreatedAt"], HexColor("#27352F")),
    ]
    for index, (title, fields, accent) in enumerate(tables):
        x = 55 + (index % 2) * 426
        y = 242 if index < 2 else 82
        rounded_card(c, x, y, 405, 132, fill=SURFACE, stroke=BORDER)
        c.setFillColor(accent)
        c.roundRect(x, y + 124, 405, 8, 4, stroke=0, fill=1)
        draw_text(c, x + 18, y + 96, title, font=FONT_BOLD, size=12, color=TEXT)
        field_text = "  /  ".join(fields)
        draw_text(
            c,
            x + 18,
            y + 67,
            field_text,
            font=FONT_REGULAR,
            size=8.8,
            color=MUTED,
            max_width=366,
            leading=13,
        )
        if index == 0:
            draw_text(c, x + 18, y + 22, "Password: Argon2id hash", font=FONT_BOLD, size=9, color=ROSE)
        elif index == 1:
            draw_text(c, x + 18, y + 22, "Device token: SHA-256 hash", font=FONT_BOLD, size=9, color=BLUE)
        elif index == 2:
            draw_text(c, x + 18, y + 22, "Browser session: HttpOnly cookie", font=FONT_BOLD, size=9, color=AMBER)
        else:
            draw_text(c, x + 18, y + 22, "Default retention: 90 วัน", font=FONT_BOLD, size=9, color=GREEN)
    c.showPage()


def slide_privacy(c: canvas.Canvas, page: int) -> None:
    page_header(
        c,
        page,
        "09 / Privacy",
        "ประวัติการค้นหาแบบ Account และ Privacy Mode",
        "ระบบแยกเส้นทางข้อมูลตามความต้องการของผู้ใช้",
    )

    rounded_card(c, 54, 105, 405, 280, fill=SURFACE, stroke=BORDER)
    badge(c, 77, 340, "Account history", fill=BLUE_DARK)
    bullet_list(
        c,
        77,
        298,
        [
            "ผูกข้อมูลกับ UserID และ UserDeviceID จาก Session",
            "ตัด credentials, query string และ fragment ก่อนจัดเก็บ URL",
            "เก็บ SHA-256 ของ URL ต้นฉบับเพื่อ correlation",
            "เก็บ Rule evidence, RiskScore, decision, thresholds และ model/policy version",
            "ผู้ใช้ล้างประวัติหรือส่งออก JSON/CSV ได้",
        ],
        width=350,
        size=10.5,
        leading=16,
        gap=6,
        marker=BLUE,
    )

    rounded_card(c, 483, 105, 423, 280, fill=SURFACE_2, stroke=BORDER)
    badge(c, 506, 340, "Privacy Mode", fill=ROSE_DARK)
    bullet_list(
        c,
        506,
        298,
        [
            "วิเคราะห์ใน Browser และไม่ส่ง URL ไป Backend/LLM",
            "เก็บประวัติเฉพาะ localStorage ภายใต้บัญชีบนเครื่องนั้น",
            "ปิด Qwen explanation และ ML cloud assist โดยอัตโนมัติ",
            "Rule-based protection และคำเตือน local ยังทำงานต่อ",
        ],
        width=366,
        size=10.5,
        leading=16,
        gap=9,
        marker=ROSE,
    )
    rounded_card(c, 506, 132, 366, 58, fill=BG, stroke=BORDER, radius=11)
    draw_text(c, 526, 165, "หลักการ", font=FONT_BOLD, size=9, color=ROSE)
    draw_text(
        c,
        526,
        143,
        "ผู้ใช้เป็นผู้เลือกระดับการส่งข้อมูล ไม่ใช่ระบบเลือกแทน",
        font=FONT_REGULAR,
        size=10,
        color=TEXT,
    )
    c.showPage()


def slide_llm(c: canvas.Canvas, page: int) -> None:
    page_header(
        c,
        page,
        "10 / LLM",
        "Qwen เป็นผู้ช่วยอธิบาย ไม่ใช่ผู้ตัดสิน",
        "RiskScore และ decision ต้องให้ผลเดิม แม้ LLM ปิดหรือใช้งานไม่ได้",
    )

    rounded_card(c, 54, 242, 402, 143, fill=SURFACE, stroke=BORDER)
    draw_text(c, 78, 350, "ค่าเริ่มต้น", font=FONT_BOLD, size=10, color=ROSE)
    draw_text(c, 78, 311, "Qwen3:4b ผ่าน Ollama", font=FONT_BOLD, size=21, color=TEXT)
    draw_text(
        c,
        78,
        278,
        "ทำงาน local ลดการส่งข้อมูลออกนอกเครื่อง\nและยังใช้ข้อความ fallback ได้เมื่อโมเดลไม่พร้อม",
        font=FONT_REGULAR,
        size=10,
        color=MUTED,
        max_width=340,
        leading=15,
    )

    rounded_card(c, 480, 242, 426, 143, fill=SURFACE_2, stroke=BORDER)
    draw_text(c, 504, 350, "ตัวเลือกเปรียบเทียบ", font=FONT_BOLD, size=10, color=BLUE)
    draw_text(c, 504, 311, "OpenAI API (optional)", font=FONT_BOLD, size=21, color=TEXT)
    draw_text(
        c,
        504,
        278,
        "เหมาะสำหรับเปรียบเทียบคุณภาพและ latency\nแต่ต้องใช้อินเทอร์เน็ต ค่า API และนโยบายข้อมูลที่ชัดเจน",
        font=FONT_REGULAR,
        size=10,
        color=MUTED,
        max_width=356,
        leading=15,
    )

    rounded_card(c, 54, 86, 852, 112, fill=HexColor("#111214"), stroke=BORDER)
    draw_text(c, 77, 163, "Benchmark ที่ต้องทำต่อ", font=FONT_BOLD, size=11.5, color=ROSE)
    measures = [
        "คุณภาพคำอธิบาย 1-5",
        "JSON/schema pass rate",
        "Hallucination rate",
        "Latency p50/p95",
        "Cloud cost หรือ RAM/VRAM",
    ]
    x = 77
    for measure in measures:
        width = badge(c, x, 122, measure, fill=HexColor("#2B292E"), color=TEXT, size=8.2)
        x += width + 9
    draw_text(
        c,
        77,
        96,
        "สถานะปัจจุบัน: มีแผนทดลองแล้ว แต่ยังไม่มีผล benchmark บนเครื่องนี้",
        font=FONT_REGULAR,
        size=9.5,
        color=AMBER,
    )
    c.showPage()


def draw_toggle(c: canvas.Canvas, x: float, y: float, on: bool = True) -> None:
    c.setFillColor(ROSE if on else HexColor("#4C4A50"))
    c.roundRect(x, y, 34, 18, 9, stroke=0, fill=1)
    c.setFillColor(WHITE)
    c.circle(x + (25 if on else 9), y + 9, 6, stroke=0, fill=1)


def slide_demo(c: canvas.Canvas, page: int) -> None:
    page_header(
        c,
        page,
        "11 / Demo",
        "สิ่งที่พัฒนาเสร็จและลำดับการสาธิต",
        "รายการจากอาจารย์ถูกนำมาผูกกับโค้ดและเอกสารจริงในโปรเจกต์",
    )

    rounded_card(c, 54, 76, 280, 316, fill=HexColor("#121315"), stroke=BORDER, radius=18)
    draw_logo(c, 76, 345, 32)
    draw_text(c, 118, 365, "Phish Radar AI", font=FONT_BOLD, size=12, color=TEXT)
    draw_text(c, 118, 348, "Extension control", font=FONT_REGULAR, size=8, color=MUTED)
    rounded_card(c, 76, 262, 236, 66, fill=SURFACE_2, stroke=BORDER, radius=11)
    draw_text(c, 91, 305, "เว็บไซต์ปัจจุบัน", font=FONT_REGULAR, size=8, color=MUTED)
    draw_text(c, 91, 279, "example.com", font=FONT_BOLD, size=13, color=TEXT)
    draw_text(c, 271, 286, "16", font=FONT_BOLD, size=19, color=GREEN)
    rounded_card(c, 76, 214, 112, 34, fill=ROSE, stroke=ROSE, radius=9)
    draw_centered(c, 132, 225, "ตรวจหน้านี้", font=FONT_BOLD, size=9, color=BG)
    rounded_card(c, 200, 214, 112, 34, fill=SURFACE, stroke=BORDER, radius=9)
    draw_centered(c, 256, 225, "เชื่อถือเว็บนี้", font=FONT_BOLD, size=9, color=TEXT)
    toggles = [
        ("สแกนหน้าเว็บอัตโนมัติ", True),
        ("Privacy Mode", False),
        ("คำอธิบายจาก Qwen", True),
    ]
    for index, (label, on) in enumerate(toggles):
        y = 171 - index * 39
        draw_text(c, 78, y + 5, label, font=FONT_REGULAR, size=8.6, color=TEXT)
        draw_toggle(c, 276, y, on)

    rounded_card(c, 362, 76, 544, 316, fill=SURFACE, stroke=BORDER)
    draw_text(c, 386, 354, "สถานะงานตามรายการ", font=FONT_BOLD, size=13, color=TEXT)
    checklist = [
        ("01", "แหล่งอ้างอิงและวิธีคำนวณความเสี่ยง", "เสร็จ"),
        ("02", "User Login และการเก็บข้อมูลผู้ใช้", "เสร็จ"),
        ("03", "ประวัติการค้นหาแยกตาม User/Device", "เสร็จ"),
        ("04", "คำสั่งเริ่มระบบด้วย Git Bash", "เสร็จ"),
        ("05", "เปรียบเทียบ LLM และตั้ง Qwen เป็นค่าเริ่มต้น", "ออกแบบแล้ว"),
    ]
    for index, (number, label, status) in enumerate(checklist):
        y = 306 - index * 48
        c.setFillColor(BG)
        c.circle(399, y + 6, 15, stroke=0, fill=1)
        draw_centered(c, 399, y + 1, number, font=FONT_BOLD, size=8, color=ROSE)
        draw_text(c, 425, y + 10, label, font=FONT_REGULAR, size=10.5, color=TEXT)
        status_color = GREEN if status == "เสร็จ" else AMBER
        draw_text(c, 809, y + 10, status, font=FONT_BOLD, size=9, color=status_color)
        if index < len(checklist) - 1:
            line(c, 386, y - 15, 880, y - 15, BORDER)

    draw_text(c, 386, 93, "คำสั่ง Demo:  ./migrate-db.sh   แล้ว  ./start-demo.sh", font=FONT_BOLD, size=9.5, color=ROSE)
    c.showPage()


def slide_roadmap(c: canvas.Canvas, page: int) -> None:
    page_header(
        c,
        page,
        "12 / Roadmap",
        "ข้อจำกัดและงานที่ควรทำต่อ",
        "เน้นลดช่องว่างระหว่างผล Cross-validation กับการใช้งานจริง",
    )

    rounded_card(c, 54, 92, 405, 292, fill=SURFACE, stroke=BORDER)
    badge(c, 77, 340, "ข้อจำกัดปัจจุบัน", fill=ROSE_DARK)
    bullet_list(
        c,
        77,
        298,
        [
            "Dataset snapshot เดียวอาจไม่สะท้อนแคมเปญ phishing ในอนาคต",
            "ยังไม่มี time-split holdout และ traffic จริงที่แยกจากการเลือก policy",
            "Rule-based และ URL features อาจพลาดหน้าเว็บที่เลียนแบบด้วยภาพหรือ DOM ขั้นสูง",
            "LLM comparison ยังไม่มีผล benchmark จาก prompt และเครื่องเดียวกัน",
            "Admin role ยังควรมี API และ audit log แทนการปรับผ่าน SQL โดยตรง",
        ],
        width=350,
        size=10.2,
        leading=15,
        gap=6,
        marker=ROSE,
    )

    rounded_card(c, 483, 92, 423, 292, fill=SURFACE_2, stroke=BORDER)
    badge(c, 506, 340, "ลำดับพัฒนาต่อ", fill=BLUE_DARK)
    roadmap = [
        ("1", "External/time-split evaluation", "ยืนยัน Risk Model และ thresholds กับข้อมูลใหม่"),
        ("2", "Drift monitoring + retraining", "ติดตาม FPR/Recall และ version Dataset/Model"),
        ("3", "LLM benchmark", "วัดคุณภาพ Hallucination และ latency อย่างยุติธรรม"),
        ("4", "Admin API + audit log", "จัดการ Role, Account และเหตุการณ์สำคัญ"),
        ("5", "Controlled deployment", "HTTPS, secret management, backup และ monitoring"),
    ]
    for index, (number, title, body) in enumerate(roadmap):
        y = 300 - index * 49
        c.setFillColor(BG)
        c.circle(525, y + 4, 14, stroke=0, fill=1)
        draw_centered(c, 525, y - 1, number, font=FONT_BOLD, size=8, color=BLUE)
        draw_text(c, 550, y + 9, title, font=FONT_BOLD, size=10, color=TEXT)
        draw_text(c, 550, y - 9, body, font=FONT_REGULAR, size=8.7, color=MUTED)
    c.showPage()


def slide_qa(c: canvas.Canvas, page: int) -> None:
    page_header(
        c,
        page,
        "13 / Defense Notes",
        "คำถามที่คาดว่าจะได้รับ",
        "คำตอบสั้นควรผูกกับหลักฐานในผลทดลองและข้อจำกัดของระบบ",
    )

    questions = [
        (
            "ทำไมใช้ Rule 40% และ ML 60%?",
            "เป็น policy คงที่ของการทดลอง โดย ML มีน้ำหนักหลัก และเลือก threshold ใหม่บน FinalScore ภายใต้เพดาน FPR",
        ),
        (
            "ทำไมใช้ Logistic Regression?",
            "sigmoid ให้ probability โดยตรง, L1 ช่วยเลือก feature และยังตรวจ Brier/Log loss บน grouped holdout",
        ),
        (
            "ระบบเก็บรหัสผ่านหรือไม่?",
            "ไม่เก็บรหัสผ่านจริง เก็บ Argon2id PasswordHash และเก็บ Session/Device token เฉพาะ SHA-256 hash",
        ),
        (
            "Qwen เป็นตัวตัดสิน Phishing หรือไม่?",
            "ไม่ใช่ LLM มีหน้าที่อธิบาย RiskScore, decision และ evidence เท่านั้น ปิด LLM แล้วผลต้องไม่เปลี่ยน",
        ),
        (
            "ผลนี้พร้อมใช้ Production หรือยัง?",
            "ยัง ต้องเพิ่ม time-split holdout, traffic จริง, drift monitoring, audit log และ deployment controls",
        ),
        (
            "ถ้า Backend ล่มจะเกิดอะไรขึ้น?",
            "Extension ยังใช้ Rule evidence local และคำเตือนแบบ offline ได้ แต่ Risk Model, Login/History และ LLM จะไม่พร้อม",
        ),
    ]
    for index, (question, answer) in enumerate(questions):
        col = index % 2
        row = index // 2
        x = 54 + col * 426
        y = 286 - row * 103
        rounded_card(c, x, y, 405, 84, fill=SURFACE if col == 0 else SURFACE_2, stroke=BORDER)
        draw_text(c, x + 18, y + 57, question, font=FONT_BOLD, size=10.8, color=ROSE if col == 0 else BLUE)
        draw_text(
            c,
            x + 18,
            y + 34,
            answer,
            font=FONT_REGULAR,
            size=8.8,
            color=MUTED,
            max_width=365,
            leading=12,
            max_lines=3,
        )
    c.showPage()


def slide_references(c: canvas.Canvas, page: int) -> None:
    page_header(
        c,
        page,
        "14 / References",
        "แหล่งข้อมูลและงานอ้างอิงหลัก",
        "รายละเอียดการทดลองทั้งหมดอยู่ใน docs/RISK_MODEL_METHODOLOGY_TH.md",
    )

    refs = [
        (
            "Ma, J. et al. (2009)",
            "Beyond Blacklists: Learning to Detect Malicious Web Sites from Suspicious URLs. ACM KDD. https://doi.org/10.1145/1557019.1557153",
        ),
        (
            "Xiang, G. et al. (2011)",
            "CANTINA+: A Feature-rich Machine Learning Framework for Detecting Phishing Web Sites. ACM TISSEC. https://doi.org/10.1145/2019599.2019606",
        ),
        (
            "Le Pochat, V. et al. (2019)",
            "Tranco: A Research-Oriented Top Sites Ranking Hardened Against Manipulation. NDSS. https://doi.org/10.14722/ndss.2019.23386",
        ),
        (
            "Maneriker, P. et al. (2021)",
            "URLTran: Improving Phishing URL Detection Using Transformers. MILCOM / Microsoft Research.",
        ),
        (
            "University of Cambridge",
            "Discovering Phishing Dropboxes Using Email Metadata. Used to support multi-source contextual evidence, not the RiskScore formula.",
        ),
        (
            "Project evidence",
            "risk_model_evaluation.json, training_urls.manifest.json, SQL migrations 001-004, backend tests and project validation scripts.",
        ),
    ]
    for index, (title, body) in enumerate(refs):
        col = index % 2
        row = index // 2
        x = 54 + col * 426
        y = 291 - row * 100
        rounded_card(c, x, y, 405, 82, fill=SURFACE if col == 0 else SURFACE_2, stroke=BORDER)
        draw_text(c, x + 18, y + 55, title, font=FONT_BOLD, size=10, color=ROSE if col == 0 else BLUE)
        draw_text(
            c,
            x + 18,
            y + 32,
            body,
            font=FONT_REGULAR,
            size=7.9,
            color=MUTED,
            max_width=366,
            leading=11,
            max_lines=4,
        )
    c.showPage()


def build_pdf() -> Path:
    register_fonts()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(OUTPUT_PATH), pagesize=(PAGE_W, PAGE_H), pageCompression=1)
    c.setTitle("Phish Radar AI - เอกสารนำเสนออาจารย์")
    c.setAuthor("Phish Radar AI Project")
    c.setSubject("L1 Logistic URL Risk Model, layered evidence, authentication, privacy and LLM architecture")

    slides = [
        slide_cover,
        slide_problem,
        slide_architecture,
        slide_flow,
        slide_dataset,
        slide_experiment,
        slide_policy,
        slide_results,
        slide_auth,
        slide_privacy,
        slide_llm,
        slide_demo,
        slide_roadmap,
        slide_qa,
        slide_references,
    ]
    for page, slide in enumerate(slides, start=1):
        slide(c, page)
    c.save()
    return OUTPUT_PATH


if __name__ == "__main__":
    result = build_pdf()
    print(result)
