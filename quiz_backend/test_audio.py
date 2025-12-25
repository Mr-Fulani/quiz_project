#!/usr/bin/env python3
"""
Тестовый скрипт для проверки загрузки аудио файлов.
"""
import os
import sys
import django

# Настройка Django
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from tasks.services.video_generation_service import _get_background_audio_path, _get_keyboard_audio_path
from moviepy.editor import AudioFileClip

def test_audio_loading():
    """Тестируем загрузку аудио файлов."""

    print("=" * 60)
    print("Тест загрузки аудио файлов")
    print("=" * 60)

    # Тестируем поиск файлов
    bg_path = _get_background_audio_path()
    kb_path = _get_keyboard_audio_path()

    print(f"Путь к фоновой музыке: {bg_path}")
    print(f"Путь к аудио клавиатуры: {kb_path}")

    # Тестируем загрузку фоновой музыки
    if bg_path:
        print(f"\nТестирую загрузку фоновой музыки: {bg_path}")
        try:
            audio = AudioFileClip(bg_path)
            print("✅ Фоновая музыка загружена успешно!"            print(f"   Длительность: {audio.duration:.1f} сек")
            print(f"   FPS: {getattr(audio, 'fps', 'неизвестно')}")
            audio.close()
        except Exception as e:
            print(f"❌ Ошибка загрузки фоновой музыки: {e}")
    else:
        print("❌ Файл фоновой музыки не найден")

    # Тестируем загрузку аудио клавиатуры
    if kb_path:
        print(f"\nТестирую загрузку аудио клавиатуры: {kb_path}")
        try:
            audio = AudioFileClip(kb_path)
            print("✅ Аудио клавиатуры загружено успешно!"            print(f"   Длительность: {audio.duration:.1f} сек")
            print(f"   FPS: {getattr(audio, 'fps', 'неизвестно')}")
            audio.close()
        except Exception as e:
            print(f"❌ Ошибка загрузки аудио клавиатуры: {e}")
    else:
        print("❌ Файл аудио клавиатуры не найден")

if __name__ == '__main__':
    test_audio_loading()
