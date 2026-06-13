"""Minutes of Meeting PDF export."""
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from config.company import COMPANY

MARGIN = 14 * mm


def _p(text, style):
    return Paragraph(str(text or '—').replace('\n', '<br/>'), style)


def build_mom_pdf(context):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN,
                            topMargin=MARGIN, bottomMargin=MARGIN)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=14, alignment=TA_CENTER)
    h2 = ParagraphStyle('H2', parent=styles['Heading2'], fontSize=11, spaceBefore=10)
    body = ParagraphStyle('Body', parent=styles['Normal'], fontSize=9, leading=12)
    meeting = context['meeting']
    elements = []

    elements.append(_p(COMPANY.get('name', 'Infomates Techno Solutions'), title_style))
    elements.append(_p('Minutes of Meeting (MOM)', title_style))
    elements.append(Spacer(1, 8))
    elements.append(_p(
        f'<b>Meeting:</b> {meeting.meeting_number} &nbsp;|&nbsp; '
        f'<b>Date:</b> {meeting.meeting_date} &nbsp;|&nbsp; '
        f'<b>Time:</b> {meeting.meeting_time} &nbsp;|&nbsp; '
        f'<b>Type:</b> {meeting.get_meeting_type_display()}',
        body,
    ))
    if meeting.topic_of_day:
        elements.append(_p(f'<b>Topic of the Day:</b> {meeting.topic_of_day}', body))
    if meeting.conducted_by:
        elements.append(_p(f'<b>Conducted By:</b> {meeting.conducted_by.get_full_name() or meeting.conducted_by.username}', body))
    elements.append(Spacer(1, 6))

    att = context['attendance_stats']
    elements.append(_p(
        f'<b>Attendance:</b> Present {att.get("present", 0)} | Late {att.get("late", 0)} | '
        f'Absent {att.get("absent", 0)} ({att.get("present_pct", 0)}% present)',
        body,
    ))

    elements.append(_p('Attendance Register', h2))
    att_rows = [['Employee', 'Role', 'Status', 'Join Time']]
    for a in context['attendees']:
        att_rows.append([
            a.employee.get_full_name() or a.employee.username,
            a.role_snapshot or a.employee.role,
            a.get_status_display(),
            str(a.join_time or '—'),
        ])
    t = Table(att_rows, repeatRows=1)
    t.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e8e8e8')),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
    ]))
    elements.append(t)

    elements.append(_p('Agenda', h2))
    for item in context['agenda']:
        elements.append(_p(f'{item.sort_order}. {item.title}', body))

    if context['discussions']:
        elements.append(_p('Discussions & Decisions', h2))
        for d in context['discussions']:
            elements.append(_p(f'<b>{d.agenda_title}</b>', body))
            if d.discussion_notes:
                elements.append(_p(f'Notes: {d.discussion_notes}', body))
            if d.decisions_taken:
                elements.append(_p(f'Decisions: {d.decisions_taken}', body))
            if d.key_learnings:
                elements.append(_p(f'Learnings: {d.key_learnings}', body))

    if context['actions']:
        elements.append(_p('Action Items', h2))
        act_rows = [['#', 'Description', 'Assigned To', 'Target', 'Status']]
        for a in context['actions']:
            act_rows.append([
                a.action_number,
                a.description[:80],
                (a.assigned_to.get_full_name() or a.assigned_to.username) if a.assigned_to else '—',
                str(a.target_date or '—'),
                a.get_status_display(),
            ])
        t2 = Table(act_rows, repeatRows=1, colWidths=[50, 200, 80, 60, 60])
        t2.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e8e8e8')),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        elements.append(t2)

    if context['messages']:
        elements.append(_p('Management Messages', h2))
        for m in context['messages']:
            elements.append(_p(f'<b>{m.get_category_display()}:</b> {m.message}', body))

    if meeting.closing_message:
        elements.append(_p('Closing Message', h2))
        elements.append(_p(meeting.closing_message, body))

    elements.append(Spacer(1, 12))
    elements.append(_p(f'Generated: {context["generated_at"].strftime("%d-%b-%Y %H:%M")}', body))

    doc.build(elements)
    buffer.seek(0)
    return buffer
