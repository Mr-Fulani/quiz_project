"""Переключатель языка запоминает выбор — при возврате «Назад» base.html переводит на выбранный язык."""
from django.conf import settings
from django.test import TestCase


class LanguageSwitchTest(TestCase):
    def test_switch_remembers_choice_and_keeps_page(self):
        response = self.client.post('/set-language/', {'language': 'en'}, HTTP_REFERER='http://testserver/ru/privacy-policy/')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/en/privacy-policy/')
        self.assertEqual(response.cookies[settings.LANGUAGE_COOKIE_NAME].value, 'en')

    def test_unknown_language_sets_no_cookie(self):
        response = self.client.post('/set-language/', {'language': 'xx'})
        self.assertNotIn(settings.LANGUAGE_COOKIE_NAME, response.cookies)
