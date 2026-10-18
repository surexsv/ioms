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

from .models import MaterialRateCard, PurchaseMarginSettings, PurchaseRate, PurchaseRateLog
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
            self.assertContains(response, 'Profit margin')
        for user in (self.operations, self.technician):
            self.client.force_login(user)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302, user.username)
            self.assertIn('access-denied', response.url)

    def test_accounts_purchase_rate_adds_thirty_percent_and_updates_material_master(self):
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
            'is_active': 'on',
        })
        self.assertEqual(response.status_code, 302)
        row = PurchaseRate.objects.get(item_code='CAB-01')
        self.assertEqual(row.purchase_rate, Decimal('100.00'))
        self.assertEqual(row.margin_percent, Decimal('30.00'))
        self.assertEqual(row.margin_amount, Decimal('30.00'))
        self.assertEqual(row.supply_rate, Decimal('130.00'))
        card = MaterialRateCard.objects.get(item_code='CAB-01')
        self.assertEqual(card.rate, Decimal('130.00'))
        self.assertEqual(card.item_name, 'Copper Cable')
        self.assertEqual(card.brand, 'Finolex')
        self.assertEqual(card.unit, 'Mtr')
        self.assertEqual(card.gst_percent, Decimal('18.00'))
        self.assertTrue(card.is_active)
        self.assertIsNotNone(card.rate_revision_date)

        self.client.force_login(self.director)
        api = self.client.get(reverse('rate_card_api'), {'kind': 'material', 'id': card.pk})
        self.assertEqual(api.status_code, 200)
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
        self.assertEqual(MaterialRateCard.objects.get().rate, Decimal('130.00'))

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
        card = MaterialRateCard.objects.get()
        self.assertEqual(card.rate, Decimal('195.00'))
        self.assertEqual(card.brand, 'Polycab')

    def test_only_director_can_change_margin_and_material_master_follows(self):
        apply_purchase_rate(
            user=self.accounts,
            item_code='LED-1',
            item_name='LED Panel',
            purchase_rate='200',
        )
        self.client.force_login(self.accounts)
        denied = self.client.post(reverse('purchase_rate_list'), {
            'action': 'update_margin',
            'row_id': PurchaseRate.objects.get().pk,
            'margin_percent': '40',
        })
        self.assertEqual(denied.status_code, 302)
        self.assertIn('access-denied', denied.url)
        self.assertEqual(PurchaseRate.objects.get().margin_percent, Decimal('30.00'))

        self.client.force_login(self.director)
        saved = self.client.post(reverse('purchase_rate_list'), {
            'action': 'save_margin',
            'default_margin_percent': '25',
        })
        self.assertEqual(saved.status_code, 302)
        self.assertEqual(PurchaseMarginSettings.get_solo().default_margin_percent, Decimal('25.00'))
        self.assertEqual(PurchaseRate.objects.get().margin_percent, Decimal('30.00'))

        updated = self.client.post(reverse('purchase_rate_list'), {
            'action': 'update_margin',
            'row_id': PurchaseRate.objects.get().pk,
            'margin_percent': '40',
        })
        self.assertEqual(updated.status_code, 302)
        row = PurchaseRate.objects.get()
        self.assertEqual(row.margin_percent, Decimal('40.00'))
        self.assertEqual(row.supply_rate, Decimal('280.00'))
        self.assertEqual(MaterialRateCard.objects.get().rate, Decimal('280.00'))

        applied = self.client.post(reverse('purchase_rate_list'), {
            'action': 'save_margin',
            'default_margin_percent': '10',
            'apply_to_all': '1',
        })
        self.assertEqual(applied.status_code, 302)
        row.refresh_from_db()
        self.assertEqual(row.margin_percent, Decimal('10.00'))
        self.assertEqual(row.supply_rate, Decimal('220.00'))
        self.assertEqual(MaterialRateCard.objects.get().rate, Decimal('220.00'))

    def test_director_can_apply_margin_to_existing_material_master_rates(self):
        MaterialRateCard.objects.create(
            item_code='OLD-1',
            item_name='Existing Item',
            brand='Brand',
            unit='Nos',
            rate=Decimal('50.00'),
            gst_percent=Decimal('18'),
        )
        self.client.force_login(self.director)
        response = self.client.post(reverse('purchase_rate_list'), {'action': 'seed_material_master'})
        self.assertEqual(response.status_code, 302)
        row = PurchaseRate.objects.get(item_code='OLD-1')
        self.assertEqual(row.purchase_rate, Decimal('50.00'))
        self.assertEqual(row.supply_rate, Decimal('65.00'))
        self.assertEqual(MaterialRateCard.objects.get(item_code='OLD-1').rate, Decimal('65.00'))

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
        self.assertContains(preview, '91.00')
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
        self.assertEqual(MaterialRateCard.objects.get(item_code='XL-1').rate, Decimal('91.00'))
