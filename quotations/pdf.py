from io import BytesIO
from decimal import Decimal
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch, mm
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from company_settings.signatory import (
    closing_already_has_thanks,
    format_covering_letter_signatory_html,
    format_signatory_approval_html,
    strip_signatory_footer_paragraphs,
)
from config.company import COMPANY, LOGO_PATH
from .covering_letter_utils import covering_letter_context
from .settings_utils import quotation_document_sections

PAGE_W, PAGE_H = A4
MARGIN = 14 * mm
BORDER = 0.5
PAD = 5


def _fmt_money(value):
    return f"{Decimal(value):,.2f}"


def _p(text, style):
    return Paragraph(str(text).replace('\n', '<br/>'), style)


def _styled_table(data, col_widths, extra=None, header_row=False):
    t = Table(data, colWidths=col_widths, repeatRows=1 if header_row and len(data) > 1 else 0)
    style = [
        ('GRID', (0, 0), (-1, -1), BORDER, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), PAD),
        ('RIGHTPADDING', (0, 0), (-1, -1), PAD),
        ('TOPPADDING', (0, 0), (-1, -1), PAD),
        ('BOTTOMPADDING', (0, 0), (-1, -1), PAD),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
    ]
    if header_row:
        style.extend([
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e8e8e8')),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ])
    if extra:
        style.extend(extra)
    t.setStyle(TableStyle(style))
    return t


def _company_header_elements(content_w, center):
    elements = []
    if LOGO_PATH.exists():
        logo = Image(str(LOGO_PATH), width=2.5 * inch, height=0.9 * inch)
        logo.hAlign = 'CENTER'
        elements.append(logo)
    else:
        elements.append(_p(f"<b>{COMPANY['name']}</b>", center))

    header_info = (
        f"{COMPANY['address']}<br/>"
        f"Tel: {', '.join(COMPANY['phones'])} | E-mail: {', '.join(COMPANY['emails'])}<br/>"
        f"Website: {COMPANY['website']}<br/>"
        f"GSTIN: {COMPANY['gstin']} &nbsp;&nbsp; PAN: {COMPANY['pan']}"
    )
    elements.append(Spacer(1, 6))
    elements.append(_p(header_info, center))
    elements.append(Spacer(1, 8))
    return elements


def _image_element(image_field, max_w, max_h):
    if not image_field:
        return None
    path = Path(image_field.path)
    if not path.exists():
        return None
    img = Image(str(path))
    ratio = min(max_w / img.drawWidth, max_h / img.drawHeight, 1.0)
    img.drawWidth *= ratio
    img.drawHeight *= ratio
    return img


def _build_covering_letter_elements(quotation, content_w, styles):
    cl = covering_letter_context(quotation)
    body_style = ParagraphStyle('CLB', parent=styles['Normal'], fontSize=10, leading=14)
    label_style = ParagraphStyle('CLL', parent=styles['Normal'], fontSize=9, leading=12)
    subject_style = ParagraphStyle('CLS', fontSize=10, fontName='Helvetica-Bold', spaceAfter=8)

    elements = []
    elements.append(Spacer(1, 18))
    elements.append(Paragraph('<b>COVERING LETTER</b>', ParagraphStyle(
        'CLT', fontSize=12, fontName='Helvetica-Bold', alignment=TA_CENTER,
        spaceBefore=6, spaceAfter=12,
    )))

    ref_lines = [
        f"<b>Date:</b> {cl['quotation_date'].strftime('%d.%m.%Y')}",
        f"<b>Quotation No.:</b> {cl['quotation_number']}",
    ]
    if cl['reference_number']:
        ref_lines.append(f"<b>Reference:</b> {cl['reference_number']}")
    elements.append(_p('<br/>'.join(ref_lines), label_style))
    elements.append(Spacer(1, 8))

    client_block = (
        f"<b>To,</b><br/>"
        f"M/S {cl['client_name']}<br/>"
        f"{cl['client_address'].replace(chr(10), '<br/>')}<br/>"
        f"<b>Kind Attn:</b> {cl['contact_person']}<br/>"
        f"<b>Project:</b> {cl['project_name']}"
    )
    client_table = Table([[_p(client_block, label_style)]], colWidths=[content_w])
    client_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), BORDER, colors.black),
        ('LEFTPADDING', (0, 0), (-1, -1), PAD),
        ('TOPPADDING', (0, 0), (-1, -1), PAD),
        ('BOTTOMPADDING', (0, 0), (-1, -1), PAD),
    ]))
    elements.append(client_table)
    elements.append(Spacer(1, 10))

    elements.append(Paragraph(f"<b>Subject: {cl['subject']}</b>", subject_style))
    elements.append(Spacer(1, 4))

    if cl['company_introduction']:
        elements.append(_p(cl['company_introduction'], body_style))
        elements.append(Spacer(1, 6))

    body_paragraphs = strip_signatory_footer_paragraphs(cl['body_paragraphs'])
    for para in body_paragraphs:
        elements.append(_p(para, body_style))
        elements.append(Spacer(1, 6))

    if cl['closing_paragraph']:
        closing_lower = cl['closing_paragraph'].strip().lower()
        last_body = (body_paragraphs[-1].strip().lower() if body_paragraphs else '')
        if closing_lower and closing_lower != last_body:
            elements.append(_p(cl['closing_paragraph'], body_style))
            elements.append(Spacer(1, 6))

    sig_style = ParagraphStyle(
        'CLSIG', parent=body_style, spaceBefore=10, leading=14,
    )
    elements.append(Spacer(1, 8))
    elements.append(Paragraph(
        format_covering_letter_signatory_html(
            cl['signatory_name'],
            cl['designation'],
            COMPANY['name'],
            include_thanks=not closing_already_has_thanks(
                body_paragraphs, cl['closing_paragraph'],
            ),
        ),
        sig_style,
    ))
    elements.append(Spacer(1, 6))

    return elements


def _line_table(lines, content_w, title):
    styles = getSampleStyleSheet()
    tiny = ParagraphStyle('T', parent=styles['Normal'], fontSize=7, leading=9)

    cw = [0.35 * inch, content_w - 3.2 * inch, 0.45 * inch, 0.55 * inch, 0.65 * inch, 0.5 * inch, 0.7 * inch]
    cw[1] = content_w - sum(cw) + cw[1]

    rows = [['#', 'Description', 'Unit', 'Qty', 'Rate', 'GST%', 'Total']]
    for i, line in enumerate(lines, 1):
        rows.append([
            str(i),
            Paragraph(line.description[:350], tiny),
            line.unit,
            _fmt_money(line.quantity),
            _fmt_money(line.unit_rate),
            f"{line.gst_percent}%",
            _fmt_money(line.line_total),
        ])
    if len(rows) == 1:
        rows.append(['—', 'No items', '', '', '', '', ''])

    elements = []
    elements.append(Paragraph(f'<b>{title}</b>', ParagraphStyle(
        'LH', fontSize=9, fontName='Helvetica-Bold', spaceAfter=4,
    )))
    elements.append(_styled_table(
        rows, cw, header_row=True,
        extra=[('ALIGN', (3, 1), (-1, -1), 'RIGHT'), ('ALIGN', (0, 0), (0, -1), 'CENTER')],
    ))
    return elements


def _build_commercial_quotation_elements(quotation, content_w, styles, center, small):
    client = quotation.client
    elements = []

    qt_bar = Table(
        [[Paragraph('<b>COMMERCIAL QUOTATION</b>', ParagraphStyle(
            'QT', fontSize=11, fontName='Helvetica-Bold', alignment=TA_CENTER,
        ))]],
        colWidths=[content_w],
    )
    qt_bar.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), BORDER, colors.black),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(qt_bar)
    elements.append(Spacer(1, 6))

    label_w = 1.1 * inch
    value_w = (content_w / 2) - label_w
    meta_rows = [
        ['Quotation No:', quotation.quotation_number, 'Date:', quotation.quotation_date.strftime('%d.%m.%Y')],
        ['Valid Until:', quotation.valid_until.strftime('%d.%m.%Y'), 'Status:', quotation.get_status_display()],
        ['Subject:', Paragraph(quotation.subject[:120], small), '', ''],
    ]
    elements.append(_styled_table(
        meta_rows, [label_w, value_w, label_w, value_w],
        extra=[
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
            ('SPAN', (1, 2), (3, 2)),
        ],
    ))
    elements.append(Spacer(1, 6))

    client_addr = client.address.replace('\n', ', ')
    client_block = (
        f"<b>Client:</b> M/S {client.name}<br/>"
        f"{client_addr}<br/>"
        f"Contact: {quotation.contact_person} | {client.phone}<br/>"
        f"<b>Site:</b> {quotation.site_location.replace(chr(10), ', ')}"
    )
    site_table = Table([[_p(client_block, small)]], colWidths=[content_w])
    site_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), BORDER, colors.black),
        ('LEFTPADDING', (0, 0), (-1, -1), PAD),
        ('TOPPADDING', (0, 0), (-1, -1), PAD),
        ('BOTTOMPADDING', (0, 0), (-1, -1), PAD),
    ]))
    elements.append(site_table)
    elements.append(Spacer(1, 6))

    scope = Table(
        [[Paragraph(f'<b>Scope of Work</b><br/>{quotation.scope_of_work}', small)]],
        colWidths=[content_w],
    )
    scope.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), BORDER, colors.black),
        ('LEFTPADDING', (0, 0), (-1, -1), PAD),
        ('TOPPADDING', (0, 0), (-1, -1), PAD),
        ('BOTTOMPADDING', (0, 0), (-1, -1), PAD),
    ]))
    elements.append(scope)
    elements.append(Spacer(1, 8))

    elements.extend(_line_table(list(quotation.material_lines.all()), content_w, 'Materials'))
    elements.append(Spacer(1, 8))
    elements.extend(_line_table(list(quotation.service_lines.all()), content_w, 'Services'))
    elements.append(Spacer(1, 8))

    totals = [
        ['Subtotal:', _fmt_money(quotation.subtotal)],
        ['GST Total:', _fmt_money(quotation.gst_total)],
        ['Grand Total:', _fmt_money(quotation.grand_total)],
    ]
    tot_table = Table(totals, colWidths=[content_w - 1.5 * inch, 1.5 * inch])
    tot_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), BORDER, colors.black),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e8e8e8')),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(tot_table)
    return elements


def _build_terms_elements(quotation, content_w, small, page_break=True):
    """Terms & Conditions section only."""
    elements = []
    if page_break:
        elements.append(PageBreak())
    doc_sections = quotation_document_sections(quotation)
    terms = doc_sections['terms_text']
    terms_table = Table(
        [[Paragraph(f'<b>Terms &amp; Conditions</b><br/>{terms}', small)]],
        colWidths=[content_w],
    )
    terms_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), BORDER, colors.black),
        ('LEFTPADDING', (0, 0), (-1, -1), PAD),
        ('TOPPADDING', (0, 0), (-1, -1), PAD),
        ('BOTTOMPADDING', (0, 0), (-1, -1), PAD),
    ]))
    elements.append(terms_table)
    elements.append(Spacer(1, 8))
    return elements


def _build_bank_details_elements(quotation, content_w, small):
    """Company bank details — rendered before the final signature block."""
    doc_sections = quotation_document_sections(quotation)
    bank_details = doc_sections['bank_details']
    if not bank_details:
        return []
    bank_table = Table(
        [[Paragraph(f'<b>Company Bank Details</b><br/>{bank_details}', small)]],
        colWidths=[content_w],
    )
    bank_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), BORDER, colors.black),
        ('LEFTPADDING', (0, 0), (-1, -1), PAD),
        ('TOPPADDING', (0, 0), (-1, -1), PAD),
        ('BOTTOMPADDING', (0, 0), (-1, -1), PAD),
    ]))
    return [bank_table, Spacer(1, 8)]


def _build_final_approval_elements(quotation, content_w):
    """
    Final approval section — always last. Original two-column block:
    company signatory (left) + customer acceptance (right).
    """
    cl = covering_letter_context(quotation)
    half_w = content_w / 2
    sig_style = ParagraphStyle('SIG', fontSize=8, alignment=TA_LEFT, leading=11)
    left_rows = [[Paragraph(f'<b>For {COMPANY["name"]}</b>', sig_style)]]
    if cl['include_signature'] and cl['signature_image']:
        sig_img = _image_element(cl['signature_image'], 1.8 * inch, 0.6 * inch)
        if sig_img:
            left_rows.append([sig_img])
    else:
        left_rows.append([Spacer(1, 24)])

    left_rows.append([
        Paragraph(
            format_signatory_approval_html(cl['signatory_name'], cl['designation']),
            sig_style,
        ),
    ])

    if cl['include_company_seal'] and cl['company_seal']:
        seal_img = _image_element(cl['company_seal'], 1.0 * inch, 1.0 * inch)
        if seal_img:
            left_rows.append([seal_img])

    left_table = Table(left_rows, colWidths=[half_w - PAD * 2])

    customer_cell = Paragraph(
        '<b>Customer Acceptance</b><br/><br/><br/>'
        'Name &amp; Signature: _________________________<br/>'
        'Date: _________________________',
        ParagraphStyle('CUS', fontSize=8, alignment=TA_LEFT, leading=11),
    )

    sign_table = Table([[left_table, customer_cell]], colWidths=[half_w, half_w])
    sign_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), BORDER, colors.black),
        ('LINEBEFORE', (1, 0), (1, 0), BORDER, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), PAD),
        ('TOPPADDING', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('MINHEIGHT', (0, 0), (-1, -1), 70),
    ]))

    return [Spacer(1, 10), sign_table]


def build_proposal_pdf(quotation):
    """
    Full proposal PDF order:
    1. Covering Letter (page 1)
    2. Commercial Quotation (items + totals)
    3. Terms & Conditions
    4. Company Bank Details
    5. Final approval block — company signatory + customer acceptance (always last)
    """
    buffer = BytesIO()
    content_w = PAGE_W - 2 * MARGIN

    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=MARGIN,
    )
    styles = getSampleStyleSheet()
    center = ParagraphStyle('C', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER, leading=11)
    small = ParagraphStyle('S', parent=styles['Normal'], fontSize=8, leading=10)

    elements = _company_header_elements(content_w, center)

    if quotation.include_covering_letter:
        elements.extend(_build_covering_letter_elements(quotation, content_w, styles))
        elements.append(PageBreak())
        elements.extend(_company_header_elements(content_w, center))

    # Commercial quotation — line items and totals only (no signature here)
    elements.extend(_build_commercial_quotation_elements(
        quotation, content_w, styles, center, small,
    ))

    # Closing sections: terms → bank → signature (signature must be last)
    doc_sections = quotation_document_sections(quotation)
    needs_page_break = True

    if quotation.include_terms:
        elements.extend(_build_terms_elements(quotation, content_w, small, page_break=needs_page_break))
        needs_page_break = False

    bank_elements = _build_bank_details_elements(quotation, content_w, small)
    if bank_elements:
        if needs_page_break:
            elements.append(PageBreak())
            needs_page_break = False
        elements.extend(bank_elements)

    if doc_sections['footer_notes']:
        if needs_page_break:
            elements.append(PageBreak())
            needs_page_break = False
        elements.append(Table(
            [[Paragraph(doc_sections['footer_notes'], ParagraphStyle(
                'FN', fontSize=7, alignment=TA_CENTER, leading=9,
            ))]],
            colWidths=[content_w],
        ))
        elements.append(Spacer(1, 8))

    elements.extend(_build_final_approval_elements(quotation, content_w))

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


def build_quotation_pdf(quotation):
    """Backward-compatible alias for proposal PDF export."""
    return build_proposal_pdf(quotation)
