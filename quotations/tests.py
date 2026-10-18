import json
from decimal import Decimal
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from openpyxl import Workbook
from reportlab.pdfgen import canvas

from accounts.models import User
from accounts.roles import ROLE_ACCOUNTS, ROLE_DIRECTOR, ROLE_OPERATIONS, ROLE_TECHNICIAN

from .models import MaterialRateCard, PurchaseRate, PurchaseRateLog
from .purchase_extract import parse_rate_text, rows_from_upload
from .purchase_rates import apply_purchase_rate


def _user(username, role, superuser=False):
    if superuser:
        return User.objects.create_superuser(username=username, password='testpass123', email=f'{username}@example.com')
    return User.objects.create_user(
        username=username,
        password='testpass123',
        role=role,
        is_active_employee=True,
        approval_status=User.APPROVAL_APPROVED,
    )


class PurchaseRateTests(TestCase):
    def setUp(self):
        self.director = _user('director', ROLE_DIRECTOR)
        self.accounts = _user('accounts', ROLE_ACCOUNTS)
        self.operations = _user('operations', ROLE_OPERATIONS)
        self.technician = _user('technician', ROLE_TECHNICIAN)
        self.superuser = _user('admin', None, superuser=True)

    def test_page_is_limited_to_director_accounts_and_superuser(self):
        url = reverse('purchase_rate_list')
        for user in (self.director, self.accounts, self.superuser):
            self.client.force_login(user)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, user.username)
            self.assertContains(response, 'Purchase Rates')
            self.assertNotContains(response, 'Profit margin %')
        for user in (self.operations, self.technician):
            self.client.force_login(user)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302, user.username)
            self.assertIn('access-denied', response.url)

        rate_card = reverse('rate_card_list')
        for user in (self.director, self.superuser):
            self.client.force_login(user)
            response = self.client.get(rate_card)
            self.assertEqual(response.status_code, 200, user.username)
            self.assertContains(response, 'Profit margin %')
            self.assertContains(response, 'Supply rate')
        for user in (self.accounts, self.operations, self.technician):
            self.client.force_login(user)
            response = self.client.get(rate_card)
            self.assertEqual(response.status_code, 302, user.username)
            self.assertIn('access-denied', response.url)

    def test_accounts_entry_waits_for_director_approval_before_material_master(self):
        self.client.force_login(self.accounts)
        response = self.client.post(reverse('purchase_rate_list'), {
            'action': 'add',
            'item_code': 'CAB-01',
            'item_name': 'Copper Cable',
            'brand': 'Finolex',
            'unit': 'Mtr',
            'gst_percent': '18',
            'purchase_rate': '100',
            'margin_percent': '50',
            'remarks': 'Vendor bill',
        })
        self.assertEqual(response.status_code, 302)
        row = PurchaseRate.objects.get(item_code='CAB-01')
        self.assertEqual(row.status, PurchaseRate.STATUS_PENDING)
        self.assertEqual(row.purchase_rate, Decimal('100.00'))
        self.assertEqual(row.margin_percent, Decimal('30.00'))
        self.assertEqual(row.supply_rate, Decimal('130.00'))
        self.assertFalse(MaterialRateCard.objects.filter(item_code='CAB-01').exists())

        self.client.force_login(self.director)
        card_page = self.client.get(reverse('rate_card_list'))
        self.assertContains(card_page, 'CAB-01')
        self.assertContains(card_page, '130.00')
        approved = self.client.post(reverse('rate_card_list'), {
            'action': 'approve_row',
            'row_id': row.pk,
            'purchase_rate': '100',
            'margin_percent': '30',
            'gst_percent': '18',
            'brand': 'Finolex',
            'unit': 'Mtr',
            'remarks': 'Vendor bill',
            'is_active': 'on',
        })
        self.assertEqual(approved.status_code, 302)
        row.refresh_from_db()
        self.assertEqual(row.status, PurchaseRate.STATUS_APPROVED)
        card = MaterialRateCard.objects.get(item_code='CAB-01')
        self.assertEqual(card.rate, Decimal('130.00'))
        self.assertEqual(card.item_name, 'Copper Cable')
        self.assertEqual(card.brand, 'Finolex')
        self.assertEqual(card.unit, 'Mtr')
        self.assertEqual(card.gst_percent, Decimal('18.00'))
        self.assertTrue(card.is_active)

        api = self.client.get(reverse('rate_card_api'), {'kind': 'material', 'id': card.pk})
        self.assertEqual(json.loads(api.content)['unit_rate'], '130.00')

    def test_lower_or_equal_purchase_rate_does_not_replace_the_saved_rate(self):
        apply_purchase_rate(
            user=self.accounts,
            item_code='CAB-01',
            item_name='Copper Cable',
            purchase_rate='100',
            gst_percent='18',
            unit='Mtr',
        )
        kept = apply_purchase_rate(
            user=self.accounts,
            item_code='CAB-01',
            item_name='Copper Cable',
            purchase_rate='90',
        )
        same = apply_purchase_rate(
            user=self.accounts,
            item_code='cab-01',
            item_name='Copper Cable',
            purchase_rate='100',
        )
        self.assertEqual(kept['outcome'], PurchaseRateLog.OUTCOME_KEPT)
        self.assertEqual(same['outcome'], PurchaseRateLog.OUTCOME_KEPT)
        row = PurchaseRate.objects.get()
        self.assertEqual(row.purchase_rate, Decimal('100.00'))
        self.assertFalse(MaterialRateCard.objects.exists())

        replaced = apply_purchase_rate(
            user=self.accounts,
            item_code='CAB-01',
            item_name='Copper Cable 2.5',
            brand='Polycab',
            purchase_rate='150',
            unit='Mtr',
            gst_percent='18',
            remarks='New bill',
        )
        self.assertEqual(replaced['outcome'], PurchaseRateLog.OUTCOME_REPLACED)
        row.refresh_from_db()
        self.assertEqual(row.purchase_rate, Decimal('150.00'))
        self.assertEqual(row.supply_rate, Decimal('195.00'))
        self.assertEqual(row.item_name, 'Copper Cable 2.5')
        self.assertEqual(row.status, PurchaseRate.STATUS_PENDING)
        self.assertFalse(MaterialRateCard.objects.exists())

    def test_a_higher_bill_does_not_change_material_master_until_approved_again(self):
        from quotations.purchase_rates import save_rate_card

        apply_purchase_rate(
            user=self.accounts,
            item_code='CAB-01',
            item_name='Copper Cable',
            purchase_rate='100',
            unit='Mtr',
            gst_percent='18',
        )
        row = PurchaseRate.objects.get()
        save_rate_card(row, self.director, approve=True)
        self.assertEqual(MaterialRateCard.objects.get().rate, Decimal('130.00'))

        apply_purchase_rate(
            user=self.accounts,
            item_code='CAB-01',
            item_name='Copper Cable',
            purchase_rate='150',
            unit='Mtr',
            gst_percent='18',
        )
        row.refresh_from_db()
        self.assertEqual(row.purchase_rate, Decimal('150.00'))
        self.assertEqual(row.status, PurchaseRate.STATUS_PENDING)
        self.assertEqual(MaterialRateCard.objects.get().rate, Decimal('130.00'))

        save_rate_card(row, self.director, approve=True)
        row.refresh_from_db()
        self.assertEqual(row.supply_rate, Decimal('195.00'))
        self.assertEqual(MaterialRateCard.objects.get().rate, Decimal('195.00'))

    def test_director_can_change_margin_and_rate_then_approve_into_material_master(self):
        apply_purchase_rate(
            user=self.accounts,
            item_code='LED-1',
            item_name='LED Panel',
            purchase_rate='200',
        )
        row = PurchaseRate.objects.get()
        self.client.force_login(self.accounts)
        denied = self.client.post(reverse('rate_card_list'), {
            'action': 'save_row',
            'row_id': row.pk,
            'purchase_rate': '200',
            'margin_percent': '40',
        })
        self.assertEqual(denied.status_code, 302)
        self.assertIn('access-denied', denied.url)
        self.assertEqual(PurchaseRate.objects.get().margin_percent, Decimal('30.00'))
        self.assertFalse(MaterialRateCard.objects.exists())

        self.client.force_login(self.director)
        saved = self.client.post(reverse('rate_card_list'), {
            'action': 'save_row',
            'row_id': row.pk,
            'purchase_rate': '180',
            'margin_percent': '40',
            'gst_percent': '18',
            'brand': '',
            'unit': 'Nos',
            'remarks': '',
            'is_active': 'on',
        })
        self.assertEqual(saved.status_code, 302)
        row.refresh_from_db()
        self.assertEqual(row.purchase_rate, Decimal('180.00'))
        self.assertEqual(row.margin_percent, Decimal('40.00'))
        self.assertEqual(row.supply_rate, Decimal('252.00'))
        self.assertEqual(row.status, PurchaseRate.STATUS_PENDING)
        self.assertFalse(MaterialRateCard.objects.exists())

        approved = self.client.post(reverse('rate_card_list'), {
            'action': 'approve_row',
            'row_id': row.pk,
            'purchase_rate': '180',
            'margin_percent': '40',
            'gst_percent': '18',
            'brand': '',
            'unit': 'Nos',
            'remarks': '',
            'is_active': 'on',
        })
        self.assertEqual(approved.status_code, 302)
        row.refresh_from_db()
        self.assertEqual(row.status, PurchaseRate.STATUS_APPROVED)
        self.assertEqual(MaterialRateCard.objects.get(item_code='LED-1').rate, Decimal('252.00'))

    def test_text_pdf_and_spreadsheet_rows_can_be_captured_and_saved(self):
        rows = parse_rate_text(
            'Code Item Brand Unit Rate GST\n'
            'CAB-01 Copper Cable Finolex Mtr 100.00 18\n'
            'PVC Conduit 45.00\n'
        )
        self.assertEqual(rows[0]['item_code'], 'CAB-01')
        self.assertEqual(rows[0]['purchase_rate'], Decimal('100.00'))
        self.assertEqual(rows[0]['gst_percent'], Decimal('18'))
        self.assertIn('Copper Cable', rows[0]['item_name'])
        self.assertEqual(rows[1]['purchase_rate'], Decimal('45.00'))

        buffer = BytesIO()
        pdf = canvas.Canvas(buffer)
        pdf.drawString(40, 800, 'CAB-02 Aluminium Cable Mtr 80.00 18')
        pdf.save()
        upload = SimpleUploadedFile('rates.pdf', buffer.getvalue(), content_type='application/pdf')
        captured = rows_from_upload(upload)
        self.assertEqual(captured[0]['item_code'], 'CAB-02')
        self.assertEqual(captured[0]['purchase_rate'], Decimal('80.00'))

        workbook = Workbook()
        sheet = workbook.active
        sheet.append(['Code', 'Item', 'Brand', 'Unit', 'Purchase Rate', 'GST'])
        sheet.append(['XL-1', 'Trunking', 'Legrand', 'Mtr', 70, 18])
        xlsx = BytesIO()
        workbook.save(xlsx)
        sheet_upload = SimpleUploadedFile(
            'rates.xlsx',
            xlsx.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        self.client.force_login(self.accounts)
        preview = self.client.post(reverse('purchase_rate_list'), {'action': 'upload', 'document': sheet_upload})
        self.assertEqual(preview.status_code, 200)
        self.assertContains(preview, 'XL-1')
        self.assertContains(preview, 'Trunking')
        saved = self.client.post(reverse('purchase_rate_list'), {
            'action': 'save_captured',
            'captured_include': '0',
            'captured_code': 'XL-1',
            'captured_name': 'Trunking',
            'captured_brand': 'Legrand',
            'captured_unit': 'Mtr',
            'captured_rate': '70',
            'captured_gst': '18',
            'captured_remarks': 'Price list',
        })
        self.assertEqual(saved.status_code, 302)
        self.assertFalse(MaterialRateCard.objects.filter(item_code='XL-1').exists())
        self.client.force_login(self.director)
        approved = self.client.post(reverse('rate_card_list'), {'action': 'approve_all'})
        self.assertEqual(approved.status_code, 302)
        self.assertEqual(MaterialRateCard.objects.get(item_code='XL-1').rate, Decimal('91.00'))
