import json
import tempfile

from django.core.management import CommandError, call_command
from django.test import TestCase

from blog.models import Resume
from tenants.models import Tenant


class ImportResumeCommandTests(TestCase):
    """Резюме импортируется из JSON-файла для указанного тенанта, без данных в коде."""

    def setUp(self):
        self.tenant = Tenant.objects.create(slug='res-a', name='A', domain='res-a.example.com', site_name='A')

    def write_json(self, data):
        fh = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8')
        json.dump(data, fh)
        fh.close()
        return fh.name

    def test_imports_from_file(self):
        path = self.write_json({'name': 'Jane Doe', 'skills': ['Python'], 'email': 'jane@example.com'})

        call_command('import_resume', path, tenant='res-a', stdout=open('/dev/null', 'w'))

        resume = Resume.objects.get(tenant=self.tenant)
        self.assertEqual(resume.name, 'Jane Doe')
        self.assertEqual(resume.skills, ['Python'])
        self.assertTrue(resume.is_active)

    def test_rejects_unknown_fields_and_tenant(self):
        path = self.write_json({'name': 'Jane', 'salary': 1})
        with self.assertRaises(CommandError):
            call_command('import_resume', path, tenant='res-a')
        with self.assertRaises(CommandError):
            call_command('import_resume', self.write_json({'name': 'Jane'}), tenant='missing')
