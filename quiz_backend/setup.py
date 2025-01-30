from setuptools import setup, find_packages

setup(
    name='quiz_backend',
    version='1.0.0',
    packages=find_packages(),
    install_requires=[
        'Django>=4.2,<5.0',
        'djangorestframework>=3.14.0',
        'django-cors-headers>=4.3.1',
        'django-filter>=23.5',
        'drf-yasg>=1.21.7',
        'social-auth-app-django>=5.4.0',
        'social-auth-core>=4.5.1',
        'psycopg2-binary>=2.9.9',
        'requests>=2.31.0',
        'python-telegram-bot>=20.7',
        'python-dotenv>=1.0.0',
        'Pillow>=10.1.0',
    ],
    python_requires='>=3.8',
) 