"""Задачи без картинки: разбор вопроса, пост в Telegram текстом, картинки только для английских задач."""
from unittest.mock import patch

from django.template.loader import render_to_string
from django.test import TestCase

from platforms.models import TelegramGroup
from tasks.models import Task, TaskTranslation
from tasks.question_format import question_display
from tasks.services import social_image
from tasks.services.telegram_service import publish_task_to_telegram
from tenants.models import Tenant
from topics.models import Subtopic, Topic

PY_CODE = "class Book:\n    def __str__(self):\n        return 'Book'\n\nprint(Book())"
SERVICE = 'tasks.services.telegram_service'


class QuestionTestCase(TestCase):
    def make_task(self, question=PY_CODE, theme='code', topic='Python', language='ru'):
        tenant = Tenant.objects.create(
            slug=f't-{Tenant.objects.count()}', name='T', domain=f't{Tenant.objects.count()}.example.com',
            image_theme=theme,
        )
        topic_obj = Topic.objects.create(name=topic, description='', tenant=tenant)
        subtopic = Subtopic.objects.create(name='Basics', topic=topic_obj)
        task = Task.objects.create(topic=topic_obj, subtopic=subtopic, difficulty='easy', tenant=tenant)
        translation = TaskTranslation.objects.create(
            task=task, language=language, question=question,
            answers=['A', 'B', 'C'], correct_answer='C', explanation='Потому что C',
        )
        group = TelegramGroup.objects.create(
            group_name='Канал', group_id=-100123 - Tenant.objects.count(), topic_id=topic_obj, language=language, tenant=tenant,
        )
        return task, translation, group


class QuestionDisplayTest(QuestionTestCase):
    def test_kinds(self):
        task, translation, _ = self.make_task()
        view = question_display(task, translation.question)
        self.assertEqual((view['kind'], view['language'], view['prompt']), ('code', 'python', None))

        task, translation, _ = self.make_task('@app.get("/")\ndef root():\n    return 1\n\nЧто вернёт endpoint?', topic='FastAPI')
        view = question_display(task, translation.question)
        self.assertEqual((view['kind'], view['prompt']), ('code', 'Что вернёт endpoint?'))
        self.assertNotIn('Что вернёт', view['body'])

        task, translation, _ = self.make_task('Какая команда создаёт репозиторий?', topic='Git')
        self.assertEqual(question_display(task, translation.question)['kind'], 'text')

        task, translation, _ = self.make_task('x = 1', theme='islamic', topic='Fiqh')
        self.assertEqual(question_display(task, translation.question)['kind'], 'text')

    def test_site_markup_has_question_text(self):
        task, translation, _ = self.make_task()
        task.question_view = question_display(task, translation.question)
        html = render_to_string('blog/includes/task_question.html', {'task': task})
        self.assertIn('data-kind="code"', html)
        self.assertIn('data-language="python"', html)
        self.assertIn("return &#x27;Book&#x27;", html)

        task, translation, _ = self.make_task('Какой перевод у «البيت كبير»?', theme='islamic', topic='Arabic')
        task.question_view = question_display(task, translation.question)
        html = render_to_string('blog/includes/task_question.html', {'task': task})
        self.assertIn('tq-theme--islamic', html)
        self.assertIn('البيت كبير', html)


@patch(f'{SERVICE}.time.sleep')
class TelegramPostTest(QuestionTestCase):
    def test_code_post_without_image(self, _sleep):
        task, translation, group = self.make_task()
        self.assertFalse(task.image_url)
        with patch(f'{SERVICE}.send_message_with_button', return_value={'message_id': 10}) as send_text, \
                patch(f'{SERVICE}.send_poll', return_value={'message_id': 11}) as send_poll:
            result = publish_task_to_telegram(task, translation, group)

        self.assertTrue(result['success'], result['errors'])
        text = send_text.call_args.args[1]
        self.assertIn('<pre><code class="language-python">', text)
        self.assertIn("return &#x27;Book&#x27;", text)
        self.assertEqual(send_text.call_args.kwargs['parse_mode'], 'HTML')
        poll = send_poll.call_args.kwargs
        self.assertEqual(poll['question'], 'Какой будет вывод?')
        self.assertEqual(poll['explanation'], '💡 Потому что C')
        self.assertEqual(poll['options'][-1], 'Я не знаю, но хочу узнать')
        task.refresh_from_db()
        self.assertEqual(task.telegram_message_ids, [10, 11])
        self.assertEqual(task.message_id, 11)
        self.assertEqual(task.telegram_post_message_ids(), [10, 11])

    def test_text_post_puts_question_into_poll(self, _sleep):
        task, translation, group = self.make_task('Какое действие нарушает пост?', theme='islamic', topic='Fiqh')
        with patch(f'{SERVICE}.send_message_with_button', return_value={'message_id': 20}) as send_text, \
                patch(f'{SERVICE}.send_poll', return_value={'message_id': 21}) as send_poll:
            result = publish_task_to_telegram(task, translation, group)
        self.assertTrue(result['success'], result['errors'])
        self.assertNotIn('<pre>', send_text.call_args.args[1])
        self.assertIn('📚', send_text.call_args.args[1])
        self.assertEqual(send_poll.call_args.kwargs['question'], 'Какое действие нарушает пост?')

    def test_no_link_publishes_without_button(self, _sleep):
        task, translation, group = self.make_task()
        with patch(f'{SERVICE}._task_link', return_value=(None, 'нет ссылки')), \
                patch(f'{SERVICE}.send_message', return_value={'message_id': 30}) as send_text, \
                patch(f'{SERVICE}.send_poll', return_value={'message_id': 31}):
            result = publish_task_to_telegram(task, translation, group)
        self.assertTrue(result['success'])
        self.assertFalse(result['button_sent'])
        send_text.assert_called_once()

    def test_legacy_post_ids(self, _sleep):
        task, _, _ = self.make_task()
        task.message_id = 100
        self.assertEqual(task.telegram_post_message_ids(), [98, 99, 100, 101])


class SocialImageTest(QuestionTestCase):
    def test_only_english_tasks(self):
        task, translation, _ = self.make_task(language='ru')
        self.assertEqual(social_image.ensure_social_image(task, translation), (None, social_image.NOT_ENGLISH_REASON))

        task, translation, _ = self.make_task(language='en')
        with patch.object(social_image, 'generate_task_image', return_value=None) as generate:
            task.image_url = None
            social_image.ensure_social_image(task, translation)
        generate.assert_called_once()

    def test_task_saves_without_image_in_admin_form(self):
        from tasks.admin import TaskAdminForm
        self.assertFalse(TaskAdminForm.base_fields['image_url'].required)
