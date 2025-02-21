from django.db import models
from accounts.models import CustomUser


class Poll(models.Model):
    """
    Модель для хранения информации об опросе.

    Содержит вопрос, дату создания и автора опроса.
    """
    question = models.CharField(max_length=255, verbose_name='Вопрос')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    author = models.ForeignKey(CustomUser, on_delete=models.CASCADE, null=True, verbose_name='Автор')

    def __str__(self):
        """Возвращает строковое представление опроса (вопрос)."""
        return self.question

    class Meta:
        verbose_name = 'Опрос'
        verbose_name_plural = 'Опросы'


class Choice(models.Model):
    """
    Модель для хранения вариантов ответа на опрос.

    Связана с опросом, содержит текст варианта, флаг правильности и количество голосов.
    """
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name='choices', verbose_name='Опрос')
    text = models.CharField(max_length=255, verbose_name='Текст варианта')
    is_correct = models.BooleanField(default=False, verbose_name='Правильный ответ')
    votes = models.IntegerField(default=0, verbose_name='Количество голосов')

    def __str__(self):
        """Возвращает строковое представление варианта (текст)."""
        return self.text

    class Meta:
        verbose_name = 'Вариант ответа'
        verbose_name_plural = 'Варианты ответа'


class UserResponse(models.Model):
    """
    Модель для хранения ответов пользователей на опросы.

    Связывает опрос, выбранный вариант и пользователя, фиксирует дату ответа.
    """
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, verbose_name='Опрос')
    choice = models.ForeignKey(Choice, on_delete=models.CASCADE, verbose_name='Выбранный вариант')
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, verbose_name='Пользователь')
    responded_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата ответа')

    class Meta:
        verbose_name = 'Ответ пользователя'
        verbose_name_plural = 'Ответы пользователей'
        unique_together = ('poll', 'user')

    def __str__(self):
        """Возвращает строковое представление ответа (опрос и пользователь)."""
        return f"{self.poll.question} - {self.user.username}"