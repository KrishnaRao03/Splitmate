import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app import create_app, db, grocery_compare
from app.models import User
from app.routes.mobile_api import mobile_token_for
from config import Config


class GroceryTestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    MAIL_PASSWORD = None
    BREVO_API_KEY = None
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False


def flyer_catalogs():
    """Weekly flyer data without apples, like the real TrimCart feed."""
    return [
        {'store_id': 'nofrills', 'store_name': 'No Frills', 'items': [
            {'name': 'Bananas (per lb)', 'generic_name': 'bananas', 'size': 'per lb', 'price': '0.69',
             'in_stock': True, 'aliases': ['banana', 'bananas']},
        ]},
        {'store_id': 'walmart', 'store_name': 'Walmart', 'items': [
            {'name': 'Bananas (per lb)', 'generic_name': 'bananas', 'size': 'per lb', 'price': '0.62',
             'in_stock': True, 'aliases': ['banana', 'bananas']},
        ]},
    ], {'name': 'TrimCart', 'label': 'TrimCart weekly prices.', 'status': 'live_weekly'}


class FakeGemini:
    def __init__(self, text):
        self.calls = 0
        self.models = SimpleNamespace(generate_content=self.generate_content)
        self.text = text

    def generate_content(self, **kwargs):
        self.calls += 1
        self.last_prompt = kwargs.get('contents')
        return SimpleNamespace(text=self.text)


WEB_REPLY = '```json\n' + json.dumps({'prices': [
    {'item': 'apple', 'store_id': 'nofrills', 'product': 'Gala Apples', 'size': 'per lb', 'price': 1.49,
     'url': 'https://www.nofrills.ca/gala-apples'},
    {'item': 'apple', 'store_id': 'walmart', 'product': 'Gala Apples', 'size': 'per lb', 'price': 1.97,
     'url': 'https://www.walmart.ca/gala-apples'},
    {'item': 'apple', 'store_id': 'not-a-store', 'product': 'Apple', 'price': 0.01},
    {'item': 'apple', 'store_id': 'walmart', 'product': 'Free apple', 'price': 0},
]}) + '\n```'


class GroceryPriceTests(unittest.TestCase):
    def setUp(self):
        grocery_compare._web_price_cache.clear()
        self.scheduler_patch = patch('app.scheduler.start_inactivity_scheduler', return_value=None)
        self.scheduler_patch.start()
        self.app = create_app(GroceryTestConfig)
        self.client = self.app.test_client()
        with self.app.app_context():
            user = User(email='shopper@example.com', name='Shopper', is_email_verified=True)
            user.set_password('Shopper-pass-1')
            db.session.add(user)
            db.session.commit()
            self.headers = {'Authorization': f'Bearer {mobile_token_for(user)}'}

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        self.scheduler_patch.stop()

    def test_items_missing_from_the_flyer_get_real_web_prices_and_stores_are_sorted(self):
        fake = FakeGemini(WEB_REPLY)
        with patch('app.grocery_compare.live_grocery_catalogs', side_effect=flyer_catalogs):
            result = grocery_compare.compare_grocery_list(
                grocery_compare.parse_grocery_items_from_text('apple, banana'), client=fake)

        self.assertEqual(fake.calls, 1)
        self.assertTrue(result['catalog_source_meta']['web_lookup'])
        self.assertEqual([store['store_name'] for store in result['stores']], ['No Frills', 'Walmart'])
        cheapest = result['stores'][0]
        self.assertEqual(cheapest['total'], 2.18)
        apple = next(line for line in cheapest['items'] if line['requested']['name'] == 'apple')
        self.assertEqual(apple['source'], 'web')
        self.assertEqual(apple['source_url'], 'https://www.nofrills.ca/gala-apples')
        banana = next(line for line in cheapest['items'] if line['requested']['name'] == 'banana')
        self.assertEqual(banana['source'], 'trimcart')

        # The web result is cached, so a second search costs nothing.
        with patch('app.grocery_compare.live_grocery_catalogs', side_effect=flyer_catalogs):
            grocery_compare.compare_grocery_list(grocery_compare.parse_grocery_items_from_text('apple'), client=fake)
        self.assertEqual(fake.calls, 1)

    def test_location_is_searched_and_shown_and_items_missing_at_one_store_are_looked_up(self):
        def catalogs_missing_walmart_milk():
            catalogs, meta = flyer_catalogs()
            catalogs[0]['items'].append({'name': 'Milk 2% 4L', 'generic_name': 'milk', 'size': '4L', 'price': '6.49',
                                         'in_stock': True, 'aliases': ['milk']})
            return catalogs, meta

        reply = json.dumps({
            'branches': [{'store_id': 'walmart', 'branch': 'Walmart Supercentre, 900 Dufferin St'}],
            'prices': [{'item': 'milk', 'store_id': 'walmart', 'product': 'Great Value 2% Milk', 'size': '4 L',
                        'price': 6.27, 'url': 'https://www.walmart.ca/milk'}],
        })
        fake = FakeGemini(reply)
        with patch('app.grocery_compare.live_grocery_catalogs', side_effect=catalogs_missing_walmart_milk):
            result = grocery_compare.compare_grocery_list(
                grocery_compare.parse_grocery_items_from_text('milk'), location='M6H 4M5', client=fake)

        self.assertEqual(fake.calls, 1)
        self.assertIn('M6H 4M5', fake.last_prompt)
        self.assertIn('closest similar product', fake.last_prompt)
        self.assertEqual(result['location'], 'M6H 4M5')
        by_store = {store['store_id']: store for store in result['stores']}
        self.assertEqual(by_store['walmart']['location'], 'Walmart Supercentre, 900 Dufferin St')
        self.assertEqual(by_store['nofrills']['location'], 'M6H 4M5')
        self.assertEqual(by_store['walmart']['total'], 6.27)

    def test_failed_online_lookup_is_reported(self):
        class BrokenGemini(FakeGemini):
            def generate_content(self, **kwargs):
                raise RuntimeError('quota exceeded')

        with patch('app.grocery_compare.live_grocery_catalogs', side_effect=flyer_catalogs), \
                patch.dict(os.environ, {'GEMINI_API_KEY': 'test-key'}):
            result = grocery_compare.compare_grocery_list(
                grocery_compare.parse_grocery_items_from_text('apple'), client=BrokenGemini(''))
        self.assertIn('quota exceeded', grocery_compare.last_web_price_error)
        self.assertIn('online price lookup failed', result['catalog_source'])
        health = self.client.get('/api/mobile/health').get_json()
        self.assertIn('quota exceeded', health['last_grocery_price_error'])

    def test_no_made_up_prices_when_the_flyer_feed_is_down(self):
        with patch.dict(os.environ, {'GROCERY_PRICE_SOURCE': 'trimcart'}), \
                patch('app.grocery_compare.fetch_trimcart_catalogs', side_effect=OSError('offline')):
            grocery_compare._catalog_cache['catalogs'] = None
            result = grocery_compare.compare_grocery_list(grocery_compare.parse_grocery_items_from_text('milk, bread'),
                                                          client=FakeGemini('not json'))
        self.assertEqual(result['catalog_source_meta']['status'], 'unavailable')
        self.assertIsNone(result['top_store'])
        self.assertTrue(all(store['available_count'] == 0 for store in result['stores']))

    def test_app_endpoint_compares_a_typed_list(self):
        with patch('app.grocery_compare.live_grocery_catalogs', side_effect=flyer_catalogs):
            response = self.client.post('/api/mobile/grocery/compare', json={'items': 'banana\n2 bananas'},
                                        headers=self.headers)
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(len(data['requested_items']), 2)
        self.assertEqual(data['top_store']['store_name'], 'Walmart')

        self.assertEqual(self.client.post('/api/mobile/grocery/compare', json={'items': '  '},
                                          headers=self.headers).status_code, 400)
        self.assertEqual(self.client.post('/api/mobile/grocery/compare', json={'items': 'milk'}).status_code, 401)

    def test_website_compares_a_typed_list(self):
        self.client.post('/login', data={'email': 'shopper@example.com', 'password': 'Shopper-pass-1'})
        page = self.client.get('/notes/').get_data(as_text=True)
        self.assertIn('Compare grocery prices', page)
        with patch('app.grocery_compare.live_grocery_catalogs', side_effect=flyer_catalogs):
            response = self.client.post('/notes/api/grocery-compare', json={'items': 'banana'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['top_store']['store_name'], 'Walmart')
        self.assertEqual(self.client.post('/notes/api/grocery-compare', json={'items': ''}).status_code, 400)


if __name__ == '__main__':
    unittest.main()
