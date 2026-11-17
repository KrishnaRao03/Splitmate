import unittest

from app.email_validation import normalize_email


class EmailValidationTestCase(unittest.TestCase):
    def test_rejects_missing_at_and_unrealistic_domains(self):
        self.assertIsNone(normalize_email('123.com'))
        self.assertIsNone(normalize_email('person@123.com'))
        self.assertIsNone(normalize_email('person@gmail.123'))

    def test_accepts_common_real_email_domains(self):
        self.assertEqual(normalize_email('Person@Gmail.com'), 'person@gmail.com')
        self.assertEqual(normalize_email('person@hotmail.com'), 'person@hotmail.com')
        self.assertEqual(normalize_email('person@yahoo.com'), 'person@yahoo.com')
        self.assertEqual(normalize_email('person@outlook.com'), 'person@outlook.com')


if __name__ == '__main__':
    unittest.main()
