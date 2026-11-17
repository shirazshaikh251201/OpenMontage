import sys
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.lib.styles import ParagraphStyle

out = sys.argv[1]
W, H = A4
INK = colors.HexColor("#14141A"); MUTED = colors.HexColor("#6B6B76")
CREAM = colors.HexColor("#F6F0EC"); ACC = colors.HexColor("#2F6F5E"); RULE = colors.HexColor("#E2DCD6")
M = 20 * mm

body = ParagraphStyle("b", fontName="Helvetica", fontSize=10.5, leading=15.5, textColor=INK)
small = ParagraphStyle("s", parent=body, fontSize=9, leading=13, textColor=MUTED)

c = canvas.Canvas(out, pagesize=A4)
c.setTitle("Website Redesign Proposal"); c.setAuthor("Northline Studio"); c.setSubject("Proposal for Bloom & Co.")

def footer(n):
    c.setStrokeColor(RULE); c.line(M, 16 * mm, W - M, 16 * mm)
    c.setFont("Helvetica", 8.5); c.setFillColor(MUTED)
    c.drawString(M, 11 * mm, "Northline Studio  ·  Website Redesign Proposal  ·  Bloom & Co.")
    c.drawRightString(W - M, 11 * mm, f"{n} / 2")

def para(text, x, y, w, style=body):
    p = Paragraph(text, style); _, h = p.wrap(w, 1000); p.drawOn(c, x, y - h); return y - h

def heading(text, y):
    c.setFont("Helvetica-Bold", 9); c.setFillColor(ACC); c.drawString(M, y, text.upper()); return y - 7 * mm

# ---------------- page 1 ----------------
c.setFillColor(CREAM); c.rect(0, H - 118 * mm, W, 118 * mm, stroke=0, fill=1)
c.setFillColor(INK); c.setFont("Helvetica-Bold", 11); c.drawString(M, H - 22 * mm, "NORTHLINE STUDIO")
c.setFont("Helvetica", 9); c.setFillColor(MUTED); c.drawRightString(W - M, H - 22 * mm, "Proposal No. NS-2611")
c.setFillColor(INK); c.setFont("Times-Bold", 42)
c.drawString(M, H - 62 * mm, "Website Redesign")
c.drawString(M, H - 79 * mm, "Proposal")
c.setFont("Helvetica", 12); c.setFillColor(MUTED)
c.drawString(M, H - 92 * mm, "Prepared for Bloom & Co.  ·  November 2026")
c.setFillColor(ACC); c.rect(M, H - 104 * mm, 28 * mm, 1.6 * mm, stroke=0, fill=1)

y = H - 134 * mm
y = heading("Summary", y)
y = para("Bloom &amp; Co.'s current site was built in 2019 for a much smaller catalogue. It loads slowly on "
         "mobile, the checkout takes five steps, and product pages bury the details customers ask about most. "
         "We propose a focused eight-week redesign that rebuilds the storefront around mobile shoppers, cuts "
         "checkout to two steps, and gives your team a content system they can update without a developer.",
         M, y, W - 2 * M) - 9 * mm

y = heading("Goals", y)
goals = [("Faster", "Mobile pages under 2 seconds, down from 6.4s today."),
         ("Simpler", "Two-step checkout with saved addresses and UPI / card wallets."),
         ("Clearer", "Product pages that answer size, care and delivery questions up front."),
         ("Yours", "A CMS your team can edit — banners, collections and blog — without code.")]
for t, d in goals:
    c.setFillColor(ACC); c.circle(M + 1.5 * mm, y - 1.4 * mm, 1.2 * mm, stroke=0, fill=1)
    c.setFillColor(INK); c.setFont("Helvetica-Bold", 10.5); c.drawString(M + 6 * mm, y - 3 * mm, t)
    y = para(d, M + 26 * mm, y + 0.6 * mm, W - 2 * M - 26 * mm) - 4 * mm
y -= 5 * mm

y = heading("Scope", y)
para("Discovery and analytics review · information architecture · visual design for 14 key templates · "
     "responsive build on Shopify · checkout optimisation · CMS setup and team training · launch and "
     "30 days of post-launch support.", M, y, W - 2 * M)
footer(1)
c.showPage()

# ---------------- page 2 ----------------
y = H - 24 * mm
y = heading("Timeline", y)
rows = [["Phase", "Weeks", "Deliverable"],
        ["1. Discovery", "1 – 2", "Audit, user interviews, sitemap"],
        ["2. Design", "3 – 5", "Wireframes, visual design, prototype"],
        ["3. Build", "5 – 7", "Shopify theme, checkout, CMS"],
        ["4. Launch", "8", "QA, go-live, team training"]]
def table(rows, widths, y, bold_last=False):
    t = Table(rows, colWidths=widths)
    extra = [("FONT", (0, -1), (-1, -1), "Helvetica-Bold", 10.5), ("LINEABOVE", (0, -1), (-1, -1), 1, INK)] if bold_last else []
    t.setStyle(TableStyle(extra + [
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9), ("TEXTCOLOR", (0, 0), (-1, 0), MUTED),
        ("FONT", (0, 1), (-1, -1), "Helvetica", 10), ("TEXTCOLOR", (0, 1), (-1, -1), INK),
        ("LINEBELOW", (0, 0), (-1, -1), 0.6, RULE),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    _, h = t.wrap(W - 2 * M, 1000); t.drawOn(c, M, y - h); return y - h
y = table(rows, [50 * mm, 25 * mm, W - 2 * M - 75 * mm], y) - 12 * mm

y = heading("Investment", y)
rows = [["Item", "", "Amount (INR)"],
        ["Discovery & strategy", "", "60,000"],
        ["UX & visual design", "", "1,40,000"],
        ["Shopify build & checkout", "", "1,80,000"],
        ["CMS setup & training", "", "40,000"],
        ["Total (excl. GST)", "", "4,20,000"]]
t_y = y
y = table(rows, [80 * mm, W - 2 * M - 120 * mm, 40 * mm], y, bold_last=True)
c.setFont("Helvetica-Bold", 10.5); c.setFillColor(INK)
y -= 4 * mm
y = para("Payment in three parts: 40% to start, 40% at design sign-off, 20% at launch.", M, y, W - 2 * M, small) - 12 * mm

y = heading("Next steps", y)
for i, s in enumerate(["Share feedback on scope and timeline.",
                       "Confirm a kick-off date — we can start as early as 1 December.",
                       "We send the contract and first invoice."], 1):
    c.setFont("Helvetica-Bold", 10.5); c.setFillColor(ACC); c.drawString(M, y - 3 * mm, f"{i}")
    y = para(s, M + 7 * mm, y + 0.6 * mm, W - 2 * M - 7 * mm) - 3.5 * mm

y -= 12 * mm
c.setStrokeColor(RULE); c.line(M, y, M + 60 * mm, y)
c.setFont("Helvetica-Bold", 10.5); c.setFillColor(INK); c.drawString(M, y - 6 * mm, "Aman Verma")
c.setFont("Helvetica", 9.5); c.setFillColor(MUTED); c.drawString(M, y - 11 * mm, "Project Lead, Northline Studio")
footer(2)
c.save()
