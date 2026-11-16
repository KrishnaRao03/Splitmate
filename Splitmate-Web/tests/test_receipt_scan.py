"""The receipt scanner asks Gemini for a fast read and turns its answer into line items."""
import json
import unittest
from types import SimpleNamespace

import httpx

from app.receipt_scan import ReceiptScanError, scan_receipt_image


class FakeModels:
    def __init__(self, text=None, error=None):
        self.text, self.error, self.config = text, error, None

    def generate_content(self, model, contents, config):
        self.config = config
        if self.error:
            raise self.error
        return SimpleNamespace(text=self.text, candidates=[SimpleNamespace(finish_reason=None)])


class ReceiptScanTests(unittest.TestCase):
    def test_reads_items_with_minimal_thinking(self):
        models = FakeModels(json.dumps({'is_receipt': True, 'merchant': 'Shop', 'currency': 'CAD',
                                        'items': [{'name': 'Milk', 'quantity': 1, 'price': 4.5, 'taxed': True}], 'tax': 0.2, 'total': 4.7}))
        result = scan_receipt_image(b'jpg', 'image/jpeg', client=SimpleNamespace(models=models))
        self.assertEqual(result['items'], [{'name': 'Milk', 'quantity': 1, 'price': 4.5, 'taxed': True}])
        self.assertEqual(models.config.thinking_config.thinking_level.value, 'MINIMAL')

    def test_a_slow_scanner_gives_a_clear_error_instead_of_hanging(self):
        models = FakeModels(error=httpx.ReadTimeout('slow'))
        with self.assertRaises(ReceiptScanError) as caught:
            scan_receipt_image(b'jpg', 'image/jpeg', client=SimpleNamespace(models=models))
        self.assertEqual(caught.exception.status, 504)


if __name__ == '__main__':
    unittest.main()
