from django.test import TestCase

from accounts.models import User
from clients.models import Client
from employee_requests.models import PortalNotification
from orders.models import Order
from orders.notifications import notify_order_closed, notify_order_created


class OrderAlertTests(TestCase):
    def setUp(self):
        self.director = self._user('director', 'DIRECTOR')
        self.operations = self._user('ops', 'OPERATIONS')
        self.creator = self._user('maker', 'PROJECT_MANAGER')
        self.client_obj = Client.objects.create(
            name='Harbour Site',
            company_type='TELECOM',
            address='Kochi',
            contact_person='A',
            phone='9999999999',
        )

    def _user(self, username, role):
        return User.objects.create_user(
            username=username,
            password='test-pass',
            role=role,
            is_active_employee=True,
            approval_status=User.APPROVAL_APPROVED,
        )

    def _order(self):
        return Order.objects.create(
            client=self.client_obj,
            site_address='Jetty',
            order_type='INSTALLATION',
            description='Lay the cable',
            created_by=self.creator,
        )

    def test_creating_an_order_alerts_director_and_operations(self):
        order = self._order()
        notify_order_created(order, self.creator)
        titles = set(
            PortalNotification.objects.values_list('user__username', 'title')
        )
        self.assertIn(('director', f'Order created: {order.order_no}'), titles)
        self.assertIn(('ops', f'Order created: {order.order_no}'), titles)
        self.assertNotIn(('maker', f'Order created: {order.order_no}'), titles)
        note = PortalNotification.objects.get(user=self.director)
        self.assertIn(f'/orders/{order.pk}/', note.link)
        self.assertIn('Harbour Site', note.message)

    def test_closing_an_order_alerts_the_creator(self):
        order = self._order()
        notify_order_closed(order, self.director)
        self.assertTrue(
            PortalNotification.objects.filter(
                user=self.creator,
                title=f'Order closed: {order.order_no}',
            ).exists()
        )
        self.assertFalse(
            PortalNotification.objects.filter(user=self.director, title__startswith='Order closed').exists()
        )
