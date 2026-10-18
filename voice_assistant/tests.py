import json
from datetime import date
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from clients.models import Client
from orders.models import Order
from scheduling.models import WorkSchedule
from voice_assistant.models import OrderVoiceNote
from voice_assistant.translate import VoiceTranslateError, _mostly_malayalam, malayalam_to_english


class MalayalamEnglishTests(TestCase):
    def test_ai_translation_is_used_when_a_key_is_set(self):
        with patch('voice_assistant.translate._ai_translate', return_value='The cable was replaced.') as ai:
            with self.settings(IOMS_AI_API_KEY='test-key'):
                english, engine = malayalam_to_english('കേബിൾ മാറ്റി')
        self.assertEqual(english, 'The cable was replaced.')
        self.assertEqual(engine, 'ai')
        ai.assert_called_once()

    def test_machine_translation_tidies_english_without_a_key(self):
        with patch('voice_assistant.translate._machine_translate', return_value='work finished at the site'):
            with self.settings(IOMS_AI_API_KEY=''):
                english, engine = malayalam_to_english('ജോലി കഴിഞ്ഞു')
        self.assertEqual(english, 'Work finished at the site.')
        self.assertEqual(engine, 'translation')

    def test_malayalam_left_untranslated_is_rejected(self):
        self.assertTrue(_mostly_malayalam('കേബിൾ മാറ്റി'))
        with patch('voice_assistant.translate._machine_translate', return_value='കേബിൾ മാറ്റി'):
            with self.settings(IOMS_AI_API_KEY=''):
                with self.assertRaises(VoiceTranslateError):
                    malayalam_to_english('കേബിൾ മാറ്റി')


class OrderVoiceNoteTests(TestCase):
    def setUp(self):
        self.technician = User.objects.create_user(
            username='tech-voice', password='test', role='Technician',
            is_active_employee=True, approval_status=User.APPROVAL_APPROVED,
        )
        self.other = User.objects.create_user(
            username='tech-other', password='test', role='Technician',
            is_active_employee=True, approval_status=User.APPROVAL_APPROVED,
        )
        self.client_obj = Client.objects.create(
            name='Infomates Site', company_type='CCTV', address='Kochi',
            contact_person='A', phone='9999999999',
        )
        self.order = Order.objects.create(
            client=self.client_obj,
            site_address='Ernakulam',
            order_type='INSTALLATION',
            description='Install cameras',
            status='IN_PROGRESS',
        )
        schedule = WorkSchedule.objects.create(
            order=self.order,
            scheduled_start_date=date.today(),
            scheduled_end_date=date.today(),
            status=WorkSchedule.STATUS_IN_PROGRESS,
        )
        schedule.assigned_engineers.add(self.technician)

    def test_assigned_technician_saves_malayalam_and_english_on_the_order(self):
        self.client.force_login(self.technician)
        page = self.client.get(reverse('order_detail', args=[self.order.pk]))
        self.assertContains(page, 'Speak in Malayalam')
        self.assertContains(page, 'Order Update')
        self.assertContains(page, 'Work Completion')
        self.assertContains(page, 'Closing Remarks')

        response = self.client.post(reverse('order_voice_note', args=[self.order.pk]), {
            'kind': OrderVoiceNote.KIND_COMPLETION,
            'malayalam_text': 'ക്യാമറ ഘടിപ്പിച്ചു',
            'english_text': 'The camera was installed.',
        })
        self.assertRedirects(response, reverse('order_detail', args=[self.order.pk]))
        note = OrderVoiceNote.objects.get(order=self.order)
        self.assertEqual(note.kind, OrderVoiceNote.KIND_COMPLETION)
        self.assertEqual(note.malayalam_text, 'ക്യാമറ ഘടിപ്പിച്ചു')
        self.assertEqual(note.english_text, 'The camera was installed.')
        self.assertEqual(note.created_by, self.technician)

        saved = self.client.get(reverse('order_detail', args=[self.order.pk]))
        self.assertContains(saved, 'The camera was installed.')
        self.assertContains(saved, 'ക്യാമറ ഘടിപ്പിച്ചു')

    def test_unassigned_technician_cannot_save_a_note(self):
        self.client.force_login(self.other)
        response = self.client.post(reverse('order_voice_note', args=[self.order.pk]), {
            'kind': OrderVoiceNote.KIND_UPDATE,
            'malayalam_text': 'പണി തുടങ്ങി',
            'english_text': 'Work started.',
        })
        self.assertIn(response.status_code, (302, 403))
        self.assertFalse(OrderVoiceNote.objects.filter(order=self.order).exists())

    def test_translate_endpoint_returns_english(self):
        self.client.force_login(self.technician)
        with patch('voice_assistant.views.malayalam_to_english', return_value=('Work started.', 'translation')):
            response = self.client.post(
                reverse('voice_translate'),
                data=json.dumps({'text': 'പണി തുടങ്ങി'}),
                content_type='application/json',
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['english'], 'Work started.')

    def test_confirm_requires_both_languages(self):
        self.client.force_login(self.technician)
        response = self.client.post(reverse('order_voice_note', args=[self.order.pk]), {
            'kind': OrderVoiceNote.KIND_CLOSING,
            'malayalam_text': 'അവസാനം',
            'english_text': '',
        })
        self.assertEqual(response.status_code, 302)
        self.assertFalse(OrderVoiceNote.objects.exists())
