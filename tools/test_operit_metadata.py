"""External import-schema regressions; no Android or device is contacted."""
import json
from pathlib import Path
import re
import tempfile
import unittest
import zipfile

from operit_metadata import validate_archive, validate_contents

ROOT = Path(__file__).resolve().parents[1]


class OperitMetadataTests(unittest.TestCase):
    def setUp(self):
        from package_operit import FILES
        self.contents = {n: (ROOT/'clients/operit'/n).read_bytes() for n in FILES}
        self.entry = 'packages/companion.js'
        source = self.contents[self.entry].decode('utf-8')
        self.data = json.loads(re.search(r'/\* METADATA\s*([\s\S]*?)\*/', source)[1])

    def replace_metadata(self):
        self.contents[self.entry] = ('/* METADATA\n'+json.dumps(self.data)+'\n*/').encode()

    def test_all_current_parameters_have_required_descriptions(self):
        report = validate_contents(self.contents)
        self.assertEqual(report['version'], '2.25.0')
        self.assertGreater(report['parameters'], 0)

    def test_each_of_the_five_missing_fields_reproduces_import_rejection(self):
        for name, param in (('update_port','channel'),('update_port','mode'),('update_port','name'),
                            ('set_persona_source','source'),('set_persona_source','text')):
            with self.subTest(tool=name, parameter=param):
                tool = next(t for t in self.data['tools'] if t['name'] == name)
                parameter = next(p for p in tool['parameters'] if p['name'] == param)
                saved = parameter.pop('description')
                self.replace_metadata()
                with self.assertRaisesRegex(ValueError, r'parameters\[\d+\].description: required'):
                    validate_contents(self.contents)
                parameter['description'] = saved

    def test_actual_archive_bytes_are_checked(self):
        tool = next(t for t in self.data['tools'] if t['name']=='update_port')
        del tool['parameters'][0]['description']
        self.replace_metadata()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'invalid.toolpkg'
            with zipfile.ZipFile(path, 'w') as archive:
                for name, raw in self.contents.items():archive.writestr(name, raw)
            with self.assertRaisesRegex(ValueError, 'description: required'):
                validate_archive(path)

    def test_localized_description_is_accepted(self):
        self.data['tools'][0]['parameters'][0]['description'] = {'zh':'电脑局域网IP','en':'Computer LAN IP'}
        self.replace_metadata()
        validate_contents(self.contents)

    def test_missing_subpackage_entry_is_rejected(self):
        del self.contents[self.entry]
        with self.assertRaisesRegex(ValueError, 'entry not found'):
            validate_contents(self.contents)

    def test_wrong_parameter_shape_is_rejected(self):
        self.data['tools'][0]['parameters'][0]['required'] = 'true'
        self.replace_metadata()
        with self.assertRaisesRegex(ValueError, 'expected boolean'):
            validate_contents(self.contents)


if __name__=='__main__':unittest.main()
