from io import BytesIO
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch, mm
from reportlab.platypus import (
    Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from company_settings.signatory import format_signatory_html, get_document_signatory
from config.company import COMPANY, LOGO_PATH
from billing.gst import GST_TYPE_INTRA, resolve_client_state_display
from billing.utils import amount_in_words_indian

PAGE_W, PAGE_H = A4
MARGIN = 14 * mm
BORDER = 0.5
PAD = 5


def _fmt_money(value):
    return f"{Decimal(value):,.2f}"


def _p(text, style):
    return Paragraph(str(text).replace('\n', '<br/>'), style)


def _base_grid_style():
    return [
        ('GRID', (0, 0), (-1, -1), BORDER, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), PAD),
        ('RIGHTPADDING', (0, 0), (-1, -1), PAD),
        ('TOPPADDING', (0, 0), (-1, -1), PAD),
        ('BOTTOMPADDING', (0, 0), (-1, -1), PAD),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
    ]


def _styled_table(data, col_widths, extra=None, header_row=False):
    t = Table(data, colWidths=col_widths, repeatRows=1 if header_row and len(data) > 1 else 0)
    style = _base_grid_style()
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


def build_invoice_pdf(invoice):
    buffer = BytesIO()
    content_w = PAGE_W - 2 * MARGIN
    half_w = content_w / 2

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=MARGIN,
    )
    styles = getSampleStyleSheet()
    center = ParagraphStyle('C', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER, leading=11)
    center_b = ParagraphStyle('CB', parent=center, fontName='Helvetica-Bold', fontSize=8)
    small = ParagraphStyle('S', parent=styles['Normal'], fontSize=8, leading=10)
    tiny = ParagraphStyle('T', parent=styles['Normal'], fontSize=7, leading=9)

    order = invoice.order
    client = invoice.billing_client
    if client is None:
        raise ValueError('Invoice has no client to print.')
    elements = []

    # --- Header: logo only (company name is in logo) ---
    if LOGO_PATH.exists():
        logo = Image(str(LOGO_PATH), width=2.5 * inch, height=0.9 * inch)
        logo.hAlign = 'CENTER'
        elements.append(logo)
    else:
        elements.append(_p(f"<b>{COMPANY['name']}</b>", center_b))

    header_info = (
        f"{COMPANY['address']}<br/>"
        f"Tel: {', '.join(COMPANY['phones'])} | E-mail: {', '.join(COMPANY['emails'])}<br/>"
        f"Website: {COMPANY['website']}<br/>"
        f"GSTIN: {COMPANY['gstin']} &nbsp;&nbsp; PAN: {COMPANY['pan']}"
    )
    elements.append(Spacer(1, 6))
    elements.append(_p(header_info, center))
    elements.append(Spacer(1, 8))

    # --- TAX INVOICE bar ---
    copy_labels = (
        '☐ Original for Recipient<br/>'
        '☐ Duplicate for Supplier/Transporter<br/>'
        '☐ Triplicate for Supplier'
    )
    tax_bar = Table(
        [[
            Paragraph('<b>TAX INVOICE</b>', ParagraphStyle(
                'TI', fontSize=11, fontName='Helvetica-Bold', alignment=TA_CENTER,
            )),
            Paragraph(copy_labels, ParagraphStyle('CP', fontSize=7, alignment=TA_RIGHT, leading=9)),
        ]],
        colWidths=[half_w, half_w],
    )
    tax_bar.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), BORDER, colors.black),
        ('LINEBEFORE', (1, 0), (1, 0), BORDER, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), PAD),
        ('RIGHTPADDING', (0, 0), (-1, -1), PAD),
    ]))
    elements.append(tax_bar)
    elements.append(Spacer(1, 6))

    # --- Invoice meta (4 equal logical columns) ---
    inv_date = invoice.invoice_date.strftime('%d.%m.%Y') if invoice.invoice_date else ''
    po_date = invoice.po_date.strftime('%d-%m-%Y') if invoice.po_date else '—'
    label_w = 0.9 * inch
    value_w = (content_w / 2 - label_w) - 1

    meta_rows = []
    meta_left = [
        ('Invoice No:', invoice.invoice_number),
        ('Date:', inv_date),
        ('State:', COMPANY['state']),
        ('State Code:', COMPANY['state_code']),
    ]
    meta_right = [
        ('PO/SO No:', invoice.po_number or '—'),
        ('PO Date:', po_date),
        ('Circle:', COMPANY['state']),
        ('Order Ref:', (order.order_no or str(order.order_id)) if order else '—'),
    ]
    for i in range(4):
        l = meta_left[i]
        r = meta_right[i]
        meta_rows.append([l[0], l[1], r[0], r[1]])

    meta_table = _styled_table(
        meta_rows,
        [label_w, value_w, label_w, value_w],
        extra=[
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('ALIGN', (3, 0), (3, -1), 'LEFT'),
        ],
    )
    elements.append(meta_table)
    elements.append(Spacer(1, 6))

    period_from = getattr(invoice, 'billing_period_from', None)
    period_to = getattr(invoice, 'billing_period_to', None)
    if period_from or period_to:
        from_s = period_from.strftime('%d.%m.%Y') if period_from else '—'
        to_s = period_to.strftime('%d.%m.%Y') if period_to else '—'
        period_table = _styled_table(
            [['Billing Period:', f'{from_s} to {to_s}']],
            [label_w, content_w - label_w],
            extra=[('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold')],
        )
        elements.append(period_table)
        elements.append(Spacer(1, 6))

    # --- Service + client ---
    service = invoice.service_title or (order.get_order_type_display() if order else 'Services')
    service_table = Table(
        [[Paragraph(
            f"<b>Service — {service}</b><br/>{client.name}",
            ParagraphStyle('SR', fontSize=9, fontName='Helvetica-Bold', alignment=TA_CENTER, leading=12),
        )]],
        colWidths=[content_w],
    )
    service_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), BORDER, colors.black),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ]))
    elements.append(service_table)
    elements.append(Spacer(1, 6))

    # --- Billed To | Shipped To ---
    client_addr = client.address.replace('\n', ', ')
    client_state, client_state_code = resolve_client_state_display(client)
    gst_line = f"GSTIN: {client.gst_number}" if client.gst_number else 'GSTIN: —'
    bill_text = (
        f"<b>Details of Receiver / Billed To:</b><br/>"
        f"M/S {client.name}<br/>{client_addr}<br/>"
        f"{gst_line}<br/>State: {client_state} | State Code: {client_state_code}<br/>"
        f"Contact: {client.contact_person} — {client.phone}"
    )
    ship_text = (
        f"<b>Details of Consignee / Shipped To:</b><br/>"
        f"M/S {client.name}<br/>{client_addr}<br/>"
        f"{gst_line}<br/>State: {client_state} | State Code: {client_state_code}"
    )
    addr_table = Table(
        [[_p(bill_text, small), _p(ship_text, small)]],
        colWidths=[half_w, half_w],
    )
    addr_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), BORDER, colors.black),
        ('LINEBEFORE', (1, 0), (1, 0), BORDER, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), PAD),
        ('RIGHTPADDING', (0, 0), (-1, -1), PAD),
        ('TOPPADDING', (0, 0), (-1, -1), PAD),
        ('BOTTOMPADDING', (0, 0), (-1, -1), PAD),
    ]))
    elements.append(addr_table)
    elements.append(Spacer(1, 6))

    # --- Line items ---
    line_items = list(invoice.line_items.all())

    cw = [
        0.4 * inch,
        content_w - 2.55 * inch,
        0.55 * inch,
        0.45 * inch,
        0.45 * inch,
        0.7 * inch,
        0.7 * inch,
    ]
    cw[1] = content_w - sum(cw) + cw[1]

    line_header = [
        'Sr No', 'Name of Product/Service', 'HSN/SAC', 'Unit', 'Qty', 'Rate', 'Amount',
    ]
    line_rows = [line_header]
    if line_items:
        for item in line_items:
            desc_text = item.description
            if item.remarks:
                desc_text += f" ({item.remarks})"
            line_rows.append([
                str(item.sl_no),
                Paragraph(desc_text[:400], tiny),
                item.hsn_sac,
                item.unit,
                str(int(item.qty)) if item.qty == int(item.qty) else _fmt_money(item.qty),
                _fmt_money(item.rate),
                _fmt_money(item.line_amount),
            ])
    else:
        desc = invoice.service_title or 'Services'
        if order:
            desc = order.description or order.get_order_type_display()
        line_rows.append([
            '1', Paragraph(desc[:400], tiny), COMPANY['default_hsn_sac'],
            'Nos', '1', _fmt_money(invoice.amount), _fmt_money(invoice.amount),
        ])

    lines_table = _styled_table(
        line_rows, cw, header_row=True,
        extra=[('ALIGN', (4, 1), (-1, -1), 'RIGHT'), ('ALIGN', (0, 0), (0, -1), 'CENTER')],
    )
    elements.append(lines_table)
    elements.append(Spacer(1, 6))

    # --- Totals ---
    words = amount_in_words_indian(invoice.total)
    summary_rows = [['Total amount Before Tax:', _fmt_money(invoice.amount)]]
    if invoice.gst_type == GST_TYPE_INTRA:
        summary_rows.extend([
            [f"CGST @ {COMPANY['cgst_percent']}%:", _fmt_money(invoice.cgst_amount)],
            [f"SGST @ {COMPANY['sgst_percent']}%:", _fmt_money(invoice.sgst_amount)],
        ])
    else:
        summary_rows.append([
            f"IGST @ {COMPANY['gst_rate_percent']}%:",
            _fmt_money(invoice.igst_amount),
        ])
    summary_rows.extend([
        ['Tax Amount (GST):', _fmt_money(invoice.gst)],
        ['Total amount After Tax:', _fmt_money(invoice.total)],
    ])
    summary_inner = Table(summary_rows, colWidths=[1.55 * inch, 0.95 * inch])
    summary_inner.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LINEABOVE', (0, -1), (-1, -1), BORDER, colors.black),
    ]))

    words_w = content_w * 0.56
    totals_w = content_w - words_w
    words_summary = Table(
        [[
            Paragraph(f"<b>Total Payable Amount in Words:</b><br/>{words}", small),
            summary_inner,
        ]],
        colWidths=[words_w, totals_w],
    )
    words_summary.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), BORDER, colors.black),
        ('LINEBEFORE', (1, 0), (1, 0), BORDER, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), PAD),
        ('RIGHTPADDING', (0, 0), (-1, -1), PAD),
        ('TOPPADDING', (0, 0), (-1, -1), PAD),
        ('BOTTOMPADDING', (0, 0), (-1, -1), PAD),
    ]))
    elements.append(words_summary)
    elements.append(Spacer(1, 6))

    # --- Bank details ---
    bank_rows = [
        ['Company Name', COMPANY['name']],
        ['Bank Name & Branch', f"{COMPANY['bank_name']}, Branch - {COMPANY['bank_branch']}"],
        ['Bank Account Number', COMPANY['bank_account']],
        ['Bank Branch IFSC', COMPANY['bank_ifsc']],
    ]
    bank_table = _styled_table(
        bank_rows, [1.45 * inch, content_w - 1.45 * inch],
        extra=[
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#fafafa')),
        ],
    )
    elements.append(bank_table)
    elements.append(Spacer(1, 6))

    # --- Terms | Declaration ---
    terms_html = '<b>Terms &amp; Conditions:</b><br/>' + '<br/>'.join(
        f"{i + 1}. {t}" for i, t in enumerate(COMPANY['terms'])
    )
    signatory = get_document_signatory(invoice)
    decl_html = (
        '<b>GST Payable on Reverse Charge:</b> No<br/><br/>'
        'Certified that the particulars given above are true and correct.<br/>'
        f'For, <b>{COMPANY["name"]}</b><br/><br/><br/>'
        f'<b>{format_signatory_html(signatory["name"], signatory["designation"])}</b>'
    )
    footer_row = Table(
        [[_p(terms_html, tiny), _p(decl_html, tiny)]],
        colWidths=[half_w, half_w],
    )
    footer_row.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), BORDER, colors.black),
        ('LINEBEFORE', (1, 0), (1, 0), BORDER, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), PAD),
        ('TOPPADDING', (0, 0), (-1, -1), PAD),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
    ]))
    elements.append(footer_row)
    elements.append(Spacer(1, 8))

    pay_status = 'PAID' if invoice.payment_status == 'RECEIVED' else 'PAYMENT PENDING'
    elements.append(_p(
        f"{COMPANY['address']} | Mob: {', '.join(COMPANY['phones'])} | "
        f"E-mail: {', '.join(COMPANY['emails'])} | {pay_status}",
        ParagraphStyle('Foot', fontSize=7, alignment=TA_CENTER, textColor=colors.grey),
    ))

    doc.build(elements)
    buffer.seek(0)
    return buffer
