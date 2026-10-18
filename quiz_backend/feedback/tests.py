from unittest.mock import MagicMock

from django.contrib import admin
from django.test import RequestFactory, TestCase

from feedback.models import FeedbackMessage


class FeedbackAdminSaveFormsetTests(TestCase):
    def test_formset_is_saved_once(self):
        """Повторный formset.save() создавал вторую копию прикреплённой к ответу картинки."""
        model_admin = admin.site._registry[FeedbackMessage]
        formset = MagicMock()
        formset.save.return_value = []
        request = RequestFactory().post('/admin/')
        request.user = MagicMock()

        model_admin.save_formset(request, form=MagicMock(), formset=formset, change=True)

        committed_saves = [c for c in formset.save.call_args_list if c.kwargs.get('commit', True)]
        self.assertEqual(len(committed_saves), 1)
