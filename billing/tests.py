import csv
import tempfile
from datetime import date
from decimal import Decimal
from io import BytesIO, StringIO
from unittest.mock import patch
from zipfile import ZipFile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from billing.approval import ACTION_APPROVED, ACTION_CREATED, STATUS_APPROVED, STATUS_DRAFT
from billing.gst import GST_TYPE_INTER, GST_TYPE_INTRA
from billing.import_service import (
    TEMPLATE_HEADERS,
    ImportFileError,
    batch_totals,
    build_template_workbook,
    confirm_import_batch,
    creatable_items,
    parse_and_validate,
)
from billing.models import Invoice, InvoiceImportBatch, InvoiceImportItem, InvoiceLineItem
from billing.pdf import build_invoice_pdf
from clients.models import Client
from orders.models import Order

TEMPLATE_HEADER = TEMPLATE_HEADERS


def _csv_bytes(rows):
    buf = StringIO()
    writer = csv.writer(buf)
    writer.writerow(list(TEMPLATE_HEADER))
    for row in rows:
        if isinstance(row, dict):
            writer.writerow([row.get(header, '') for header in TEMPLATE_HEADER])
        else:
            writer.writerow(list(row))
    return buf.getvalue().encode('utf-8')


def _csv_upload(rows, name='invoices.csv'):
    return SimpleUploadedFile(name, _csv_bytes(rows), content_type='text/csv')


def _xlsx_upload(rows, name='invoices.xlsx'):
    workbook = build_template_workbook()
    sheet = workbook.active
    sheet.delete_rows(2, sheet.max_row)
    for row in rows:
        values = [row.get(header, '') for header in TEMPLATE_HEADER] if isinstance(row, dict) else list(row)
        sheet.append(values)
    buffer = BytesIO()
    workbook.save(buffer)
    return SimpleUploadedFile(
        name,
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )


@override_settings(MEDIA_ROOT=tempfile.gettempdir())
class InvoiceImportTestCase(TestCase):
    def setUp(self):
        self.password = 'testpass123'
        self.accounts = User.objects.create_user(
            username='accounts', password=self.password, role='ACCOUNTS',
        )
        self.technician = User.objects.create_user(
            username='technician', password=self.password, role='Technician',
        )
        self.engineer = User.objects.create_user(
            username='engineer', password=self.password, role='ENGINEER',
        )
        self.tl = User.objects.create_user(
            username='tl', password=self.password, role='SUPERVISOR',
        )
        self.manager = User.objects.create_user(
            username='manager', password=self.password, role='PROJECT_MANAGER',
        )
        self.director = User.objects.create_user(
            username='director', password=self.password, role='DIRECTOR',
        )
        self.client_a = Client.objects.create(
            name='Client A',
            company_type='TELECOM',
            gst_number='32AAAAA0000A1Z5',
            state='Kerala',
            state_code='32',
            gst_type=GST_TYPE_INTRA,
            address='Kochi, Kerala',
            contact_person='A Person',
            phone='9999990001',
        )
        self.client_b = Client.objects.create(
            name='Client B',
            company_type='IT',
            gst_number='33BBBBB0000B1Z3',
            state='Tamil Nadu',
            state_code='33',
            gst_type=GST_TYPE_INTER,
            address='Chennai, Tamil Nadu',
            contact_person='B Person',
            phone='9999990002',
        )

    def _row(self, **overrides):
        row = {
            'Invoice Number': 'INV-001',
            'Invoice Date': '15-03-2026',
            'Due Date': '14-04-2026',
            'Customer Name': self.client_a.name,
            'PO Number': 'PO-1',
            'PO Date': '01-03-2026',
            'Billing Period From': '',
            'Billing Period To': '',
            'Service Title': 'OFC Connectivity',
            'Item Description': 'Fibre work',
            'HSN/SAC': '998422',
            'Unit': 'Nos',
            'Qty': '1',
            'Rate': '100',
            'GST %': '18',
            'Remarks': '',
        }
        row.update(overrides)
        return row

    def _parse(self, rows, filename='invoices.csv', title=''):
        uploaded = _csv_upload(rows, name=filename)
        return parse_and_validate(uploaded, filename, self.accounts, title=title)

    def _make_order(self, client=None, status='APPROVED'):
        return Order.objects.create(
            client=client or self.client_a,
            site_address='Site address',
            order_type='INSTALLATION',
            description='Installation work',
            status=status,
        )

    def _create_invoice_post_data(self, order, **overrides):
        data = {
            'invoice_number_mode': 'AUTO',
            'invoice_number': '',
            'service_title': 'OFC Connectivity',
            'po_number': '',
            'due_date': date.today().isoformat(),
            'gst_type': GST_TYPE_INTRA,
            'items-TOTAL_FORMS': '1',
            'items-INITIAL_FORMS': '0',
            'items-MIN_NUM_FORMS': '0',
            'items-MAX_NUM_FORMS': '1000',
            'items-0-sl_no': '1',
            'items-0-description': 'Fibre work',
            'items-0-hsn_sac': '998422',
            'items-0-unit': 'Nos',
            'items-0-qty': '1',
            'items-0-rate': '100',
            'items-0-remarks': '',
            'items-0-DELETE': '',
        }
        if order is not None:
            data['order'] = str(order.pk)
        data.update(overrides)
        return data


class UploadValidationTests(InvoiceImportTestCase):
    def test_template_headers_match_public_api(self):
        self.assertEqual(TEMPLATE_HEADER, TEMPLATE_HEADERS)
        workbook = build_template_workbook()
        header_row = [cell.value for cell in next(workbook.active.iter_rows(min_row=1, max_row=1))]
        self.assertEqual(header_row, list(TEMPLATE_HEADERS))

    def test_rejects_unsupported_extension(self):
        uploaded = SimpleUploadedFile('notes.txt', b'hello', content_type='text/plain')
        with self.assertRaises(ImportFileError) as ctx:
            parse_and_validate(uploaded, 'notes.txt', self.accounts)
        self.assertIn('.xlsx', str(ctx.exception))

    def test_rejects_file_over_5mb(self):
        class HugeUpload:
            name = 'huge.csv'
            size = 5 * 1024 * 1024 + 1

            def read(self):
                return b'x'

            def seek(self, *args, **kwargs):
                return 0

        with self.assertRaises(ImportFileError) as ctx:
            parse_and_validate(HugeUpload(), 'huge.csv', self.accounts)
        self.assertIn('5 MB', str(ctx.exception))

    def test_rejects_more_than_500_rows(self):
        rows = [self._row(invoice_number=f'INV-{i:04d}') for i in range(501)]
        with self.assertRaises(ImportFileError) as ctx:
            parse_and_validate(_csv_upload(rows), 'too-many.csv', self.accounts)
        self.assertIn('500', str(ctx.exception))

    def test_rejects_empty_file(self):
        uploaded = SimpleUploadedFile('empty.csv', b'', content_type='text/csv')
        with self.assertRaises(ImportFileError):
            parse_and_validate(uploaded, 'empty.csv', self.accounts)

    def test_rejects_missing_required_headers(self):
        content = b'Invoice Number,Qty,Rate\nINV-1,1,100\n'
        uploaded = SimpleUploadedFile('bad.csv', content, content_type='text/csv')
        with self.assertRaises(ImportFileError) as ctx:
            parse_and_validate(uploaded, 'bad.csv', self.accounts)
        self.assertIn('Customer Name', str(ctx.exception))

    def test_unknown_customer_is_error_never_created(self):
        batch = self._parse([self._row(**{'Customer Name': 'Does Not Exist'})])
        item = batch.items.get()
        self.assertEqual(item.status, InvoiceImportItem.STATUS_ERROR)
        self.assertTrue(any('not found' in err.lower() for err in item.errors))
        self.assertIsNone(item.client)
        self.assertEqual(Client.objects.filter(name__iexact='Does Not Exist').count(), 0)
        result = confirm_import_batch(batch, self.accounts)
        self.assertFalse(result['ok'])
        self.assertEqual(Invoice.objects.count(), 0)

    def test_gst_percent_must_equal_company_rate(self):
        batch = self._parse([self._row(**{'GST %': '12'})])
        item = batch.items.get()
        self.assertEqual(item.status, InvoiceImportItem.STATUS_ERROR)
        self.assertTrue(any('18' in err for err in item.errors))

    def test_customer_matched_iexact_not_created(self):
        batch = self._parse([self._row(**{'Customer Name': 'client a'})])
        item = batch.items.get()
        self.assertEqual(item.client, self.client_a)
        self.assertIn(item.status, (
            InvoiceImportItem.STATUS_VALID,
            InvoiceImportItem.STATUS_WARNING,
        ))
        self.assertEqual(Client.objects.filter(name__iexact='Client A').count(), 1)

    def test_xlsx_upload_is_accepted(self):
        uploaded = _xlsx_upload([self._row()])
        batch = parse_and_validate(uploaded, 'invoices.xlsx', self.accounts, title='XLSX')
        self.assertEqual(batch.invoice_count, 1)
        self.assertEqual(batch.items.get().client, self.client_a)


class GroupingAndBulkTests(InvoiceImportTestCase):
    def test_three_rows_group_into_one_invoice(self):
        rows = [
            self._row(**{'Invoice Number': 'GRP-001', 'Item Description': 'Line 1', 'Rate': '100'}),
            self._row(**{'Invoice Number': 'GRP-001', 'Item Description': 'Line 2', 'Rate': '50'}),
            self._row(**{'Invoice Number': 'GRP-001', 'Item Description': 'Line 3', 'Rate': '25'}),
        ]
        batch = self._parse(rows, title='Grouped')
        self.assertEqual(batch.total_rows, 3)
        self.assertEqual(batch.invoice_count, 1)
        item = batch.items.get()
        self.assertEqual(len(item.payload['lines']), 3)
        self.assertEqual(item.payload['taxable'], '175.00')
        result = confirm_import_batch(batch, self.accounts)
        self.assertTrue(result['ok'])
        self.assertEqual(result['created'], 1)
        invoice = Invoice.objects.get()
        self.assertIsNone(invoice.order_id)
        self.assertEqual(invoice.client, self.client_a)
        self.assertEqual(invoice.source, Invoice.SOURCE_IMPORT)
        self.assertEqual(invoice.approval_status, STATUS_APPROVED)
        self.assertEqual(invoice.invoice_number, 'GRP-001')
        self.assertEqual(invoice.number_mode, Invoice.NUMBER_MODE_MANUAL)
        self.assertEqual(invoice.line_items.count(), 3)
        self.assertEqual(invoice.amount, Decimal('175.00'))
        self.assertEqual(invoice.gst, Decimal('31.50'))
        self.assertEqual(invoice.total, Decimal('206.50'))

    def test_blank_numbers_group_by_customer_po_and_dates(self):
        shared = {
            'Invoice Number': '',
            'Customer Name': self.client_a.name,
            'PO Number': 'PO-SHARED',
            'Invoice Date': '10-01-2026',
            'Due Date': '09-02-2026',
        }
        rows = [
            self._row(**{**shared, 'Item Description': 'A', 'Rate': '10'}),
            self._row(**{**shared, 'Item Description': 'B', 'Rate': '20'}),
            self._row(**{**shared, 'PO Number': 'PO-OTHER', 'Item Description': 'C', 'Rate': '30'}),
        ]
        batch = self._parse(rows)
        self.assertEqual(batch.invoice_count, 2)
        result = confirm_import_batch(batch, self.accounts)
        self.assertTrue(result['ok'])
        self.assertEqual(result['created'], 2)
        invoices = list(Invoice.objects.order_by('id'))
        self.assertEqual(invoices[0].line_items.count(), 2)
        self.assertEqual(invoices[1].line_items.count(), 1)
        self.assertTrue(all(inv.number_mode == Invoice.NUMBER_MODE_AUTO for inv in invoices))
        self.assertTrue(all(inv.invoice_number.startswith('ITSPL') for inv in invoices))

    def test_ten_invoices_created_from_ten_rows(self):
        rows = [
            self._row(
                **{
                    'Invoice Number': f'BULK-{i:02d}',
                    'Item Description': f'Service {i}',
                    'Rate': '100',
                }
            )
            for i in range(1, 11)
        ]
        batch = self._parse(rows, title='Ten invoices')
        self.assertEqual(batch.invoice_count, 10)
        self.assertEqual(creatable_items(batch).count(), 10)
        totals = batch_totals(batch)
        self.assertEqual(totals['count'], 10)
        self.assertEqual(totals['taxable'], Decimal('1000.00'))
        result = confirm_import_batch(batch, self.accounts)
        self.assertTrue(result['ok'])
        self.assertEqual(result['created'], 10)
        self.assertEqual(Invoice.objects.filter(source=Invoice.SOURCE_IMPORT).count(), 10)


class DuplicateProtectionTests(InvoiceImportTestCase):
    def test_existing_invoice_number_marked_already_exists(self):
        Invoice.objects.create(
            invoice_number='DUP-001',
            client=self.client_a,
            gst_type=GST_TYPE_INTRA,
            approval_status=STATUS_APPROVED,
        )
        batch = self._parse([self._row(**{'Invoice Number': 'DUP-001'})])
        item = batch.items.get()
        self.assertEqual(item.status, InvoiceImportItem.STATUS_ALREADY_EXISTS)
        result = confirm_import_batch(batch, self.accounts)
        self.assertFalse(result['ok'])
        self.assertEqual(result['created'], 0)
        self.assertEqual(Invoice.objects.filter(invoice_number='DUP-001').count(), 1)

    def test_duplicate_in_file_groups_as_one_invoice(self):
        rows = [
            self._row(**{'Invoice Number': 'SAME-1', 'Item Description': 'One'}),
            self._row(**{'Invoice Number': 'SAME-1', 'Item Description': 'Two'}),
        ]
        batch = self._parse(rows)
        self.assertEqual(batch.invoice_count, 1)
        confirm_import_batch(batch, self.accounts)
        self.assertEqual(Invoice.objects.filter(invoice_number='SAME-1').count(), 1)

    def test_confirm_does_not_run_twice(self):
        batch = self._parse([self._row(**{'Invoice Number': 'ONCE-1'})])
        first = confirm_import_batch(batch, self.accounts)
        self.assertTrue(first['ok'])
        second = confirm_import_batch(batch, self.accounts)
        self.assertFalse(second['ok'])
        self.assertEqual(Invoice.objects.filter(invoice_number='ONCE-1').count(), 1)


class TaxAndPdfTests(InvoiceImportTestCase):
    def test_kerala_client_uses_intra_cgst_sgst(self):
        batch = self._parse([self._row(**{'Invoice Number': 'TAX-INTRA', 'Rate': '100'})])
        result = confirm_import_batch(batch, self.accounts)
        self.assertTrue(result['ok'])
        invoice = Invoice.objects.get(invoice_number='TAX-INTRA')
        self.assertEqual(invoice.gst_type, GST_TYPE_INTRA)
        self.assertEqual(invoice.amount, Decimal('100.00'))
        self.assertEqual(invoice.gst, Decimal('18.00'))
        self.assertEqual(invoice.cgst_amount, Decimal('9.00'))
        self.assertEqual(invoice.sgst_amount, Decimal('9.00'))
        self.assertEqual(invoice.igst_amount, Decimal('0.00'))
        self.assertEqual(invoice.total, Decimal('118.00'))
        self.assertTrue(invoice.is_pdf_available)
        actions = list(invoice.approval_audit_logs.values_list('action', flat=True))
        self.assertIn(ACTION_CREATED, actions)
        self.assertIn(ACTION_APPROVED, actions)

    def test_tamil_nadu_client_uses_inter_igst(self):
        batch = self._parse([
            self._row(**{
                'Invoice Number': 'TAX-INTER',
                'Customer Name': self.client_b.name,
                'Rate': '100',
            }),
        ])
        confirm_import_batch(batch, self.accounts)
        invoice = Invoice.objects.get(invoice_number='TAX-INTER')
        self.assertEqual(invoice.client, self.client_b)
        self.assertEqual(invoice.gst_type, GST_TYPE_INTER)
        self.assertEqual(invoice.gst, Decimal('18.00'))
        self.assertEqual(invoice.igst_amount, Decimal('18.00'))
        self.assertEqual(invoice.cgst_amount, Decimal('0.00'))
        self.assertEqual(invoice.sgst_amount, Decimal('0.00'))

    def test_imported_invoice_pdf_is_available(self):
        batch = self._parse([self._row(**{'Invoice Number': 'PDF-001'})])
        confirm_import_batch(batch, self.accounts)
        invoice = Invoice.objects.select_related('client').prefetch_related('line_items').get(
            invoice_number='PDF-001',
        )
        self.assertEqual(invoice.approval_status, STATUS_APPROVED)
        pdf = build_invoice_pdf(invoice)
        self.assertTrue(pdf.getvalue().startswith(b'%PDF'))


class TransactionSafetyTests(InvoiceImportTestCase):
    def test_line_item_failure_rolls_back_all_invoices(self):
        rows = [
            self._row(**{'Invoice Number': 'TXN-1', 'Item Description': 'First'}),
            self._row(**{'Invoice Number': 'TXN-2', 'Item Description': 'Second'}),
        ]
        batch = self._parse(rows)
        original_create = InvoiceLineItem.objects.create
        calls = {'n': 0}

        def failing_create(*args, **kwargs):
            calls['n'] += 1
            if calls['n'] >= 2:
                raise IntegrityError('simulated line-item failure')
            return original_create(*args, **kwargs)

        with patch.object(InvoiceLineItem.objects, 'create', side_effect=failing_create):
            result = confirm_import_batch(batch, self.accounts)

        self.assertFalse(result['ok'])
        self.assertEqual(result['created'], 0)
        self.assertEqual(Invoice.objects.count(), 0)
        self.assertEqual(InvoiceLineItem.objects.count(), 0)
        batch.refresh_from_db()
        self.assertEqual(batch.status, InvoiceImportBatch.STATUS_FAILED)
        self.assertIn('rolled back', batch.confirm_message.lower())


class RbacAndUrlTests(InvoiceImportTestCase):
    def _denied_users(self):
        return [self.technician, self.engineer, self.tl, self.manager, self.director]

    def test_accounts_can_open_import_pages(self):
        self.client.force_login(self.accounts)
        upload = self.client.get(reverse('invoice_import_upload'))
        history = self.client.get(reverse('invoice_import_history'))
        template = self.client.get(reverse('invoice_import_template'))
        self.assertEqual(upload.status_code, 200)
        self.assertEqual(history.status_code, 200)
        self.assertEqual(template.status_code, 200)
        self.assertEqual(
            template['Content-Type'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )

    def test_other_roles_are_redirected_to_access_denied(self):
        urls = [
            reverse('invoice_import_upload'),
            reverse('invoice_import_history'),
            reverse('invoice_import_template'),
        ]
        for user in self._denied_users():
            self.client.force_login(user)
            for url in urls:
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302, msg=f'{user.username} {url}')
                self.assertIn('access-denied', response.url)

    def test_preview_item_and_confirm_follow_rbac(self):
        batch = self._parse([self._row(**{'Invoice Number': 'RBAC-1'})])
        item = batch.items.get()
        preview_url = reverse('invoice_import_preview', args=[batch.pk])
        item_url = reverse('invoice_import_item', args=[batch.pk, item.pk])
        confirm_url = reverse('invoice_import_confirm', args=[batch.pk])

        self.client.force_login(self.accounts)
        self.assertEqual(self.client.get(preview_url).status_code, 200)
        self.assertEqual(self.client.get(item_url).status_code, 200)

        for user in self._denied_users():
            self.client.force_login(user)
            self.assertEqual(self.client.get(preview_url).status_code, 302)
            self.assertIn('access-denied', self.client.get(preview_url).url)
            self.assertEqual(self.client.post(confirm_url).status_code, 302)

        self.client.force_login(self.engineer)
        self.client.post(confirm_url)
        self.assertEqual(Invoice.objects.count(), 0)

        self.client.force_login(self.accounts)
        response = self.client.post(confirm_url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Invoice.objects.filter(invoice_number='RBAC-1').count(), 1)


class ExistingBillingRegressionTests(InvoiceImportTestCase):
    def test_create_invoice_still_requires_order(self):
        self.client.force_login(self.accounts)
        data = self._create_invoice_post_data(order=None)
        try:
            self.client.post(reverse('create_invoice'), data)
        except Exception:
            pass
        self.assertFalse(Invoice.objects.exists())

        order = self._make_order()
        data = self._create_invoice_post_data(order=order)
        response = self.client.post(reverse('create_invoice'), data)
        self.assertEqual(response.status_code, 302)
        invoice = Invoice.objects.get()
        self.assertEqual(invoice.order_id, order.pk)
        self.assertEqual(invoice.source, Invoice.SOURCE_ORDER)
        self.assertEqual(invoice.approval_status, STATUS_DRAFT)

    def test_create_invoice_auto_numbering_still_works(self):
        self.client.force_login(self.accounts)
        order = self._make_order()
        response = self.client.post(reverse('create_invoice'), self._create_invoice_post_data(order=order))
        self.assertEqual(response.status_code, 302)
        invoice = Invoice.objects.get()
        self.assertTrue(invoice.invoice_number.startswith('ITSPL'))
        self.assertEqual(invoice.number_mode, Invoice.NUMBER_MODE_AUTO)

    def test_order_invoice_pdf_still_works(self):
        self.client.force_login(self.accounts)
        order = self._make_order()
        self.client.post(reverse('create_invoice'), self._create_invoice_post_data(order=order))
        invoice = Invoice.objects.get()
        invoice.approval_status = STATUS_APPROVED
        invoice.save(update_fields=['approval_status'])
        pdf = build_invoice_pdf(
            Invoice.objects.select_related('order', 'order__client').prefetch_related('line_items').get(pk=invoice.pk)
        )
        self.assertTrue(pdf.getvalue().startswith(b'%PDF'))
        response = self.client.get(reverse('invoice_pdf', args=[invoice.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')

    def test_http_csv_upload_and_confirm(self):
        self.client.force_login(self.accounts)
        uploaded = _csv_upload([self._row(**{'Invoice Number': 'HTTP-1'})], name='http.csv')
        response = self.client.post(
            reverse('invoice_import_upload'),
            {'title': 'HTTP CSV', 'file': uploaded},
        )
        self.assertEqual(response.status_code, 302)
        batch = InvoiceImportBatch.objects.get()
        self.assertIn(reverse('invoice_import_preview', args=[batch.pk]), response.url)
        confirm = self.client.post(reverse('invoice_import_confirm', args=[batch.pk]))
        self.assertEqual(confirm.status_code, 302)
        invoice = Invoice.objects.get(invoice_number='HTTP-1')
        self.assertEqual(invoice.source, Invoice.SOURCE_IMPORT)
        self.assertEqual(invoice.approval_status, STATUS_APPROVED)
        self.assertTrue(invoice.is_pdf_available)

        pdfs = self.client.get(reverse('invoice_import_pdfs', args=[batch.pk]))
        self.assertEqual(pdfs.status_code, 200)
        self.assertEqual(pdfs['Content-Type'], 'application/zip')
        with ZipFile(BytesIO(pdfs.content)) as archive:
            self.assertTrue(any(name.endswith('.pdf') for name in archive.namelist()))
