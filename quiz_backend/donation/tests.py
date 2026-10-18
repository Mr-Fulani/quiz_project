from unittest.mock import patch

from django.test import RequestFactory, TestCase

from donation.models import Donation
from donation.views import coingate_callback


class CoinGateCallbackVerificationTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.donation = Donation.objects.create(
            name='Donor', amount='10.00', payment_type='crypto', coingate_order_id='cg-123', status='pending'
        )

    def call_callback(self, status):
        request = self.factory.post('/donation/crypto/callback/', {'id': 'cg-123', 'status': status, 'token': 'x'})
        return coingate_callback(request)

    @patch('donation.views.send_donation_email_task')
    @patch('donation.coingate_service.CoinGateService.get_order')
    def test_forged_paid_status_is_ignored(self, get_order, email_task):
        get_order.return_value = {'success': True, 'status': 'pending'}
        response = self.call_callback('paid')
        self.assertEqual(response.status_code, 200)
        self.donation.refresh_from_db()
        self.assertEqual(self.donation.status, 'pending')
        email_task.delay.assert_not_called()

    @patch('donation.views.send_donation_email_task')
    @patch('donation.coingate_service.CoinGateService.get_order')
    def test_unverifiable_callback_is_rejected(self, get_order, email_task):
        get_order.return_value = {'success': False, 'error': 'not found'}
        response = self.call_callback('paid')
        self.assertEqual(response.status_code, 403)
        self.donation.refresh_from_db()
        self.assertEqual(self.donation.status, 'pending')
        email_task.delay.assert_not_called()

    @patch('donation.views.send_donation_email_task')
    @patch('donation.coingate_service.CoinGateService.get_order')
    def test_paid_status_confirmed_by_api_completes_donation(self, get_order, email_task):
        get_order.return_value = {'success': True, 'status': 'paid'}
        response = self.call_callback('paid')
        self.assertEqual(response.status_code, 200)
        self.donation.refresh_from_db()
        self.assertEqual(self.donation.status, 'completed')
        get_order.assert_called_once_with('cg-123')
