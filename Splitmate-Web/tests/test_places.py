import unittest

from app import places


class PlaceNameTests(unittest.TestCase):
    def setUp(self):
        places._cache.clear()
        self.calls = []

    def fetch_returning(self, data):
        def fetch(lat, lng):
            self.calls.append((lat, lng))
            return data
        return fetch

    def test_small_towns_use_town_or_village(self):
        fetch = self.fetch_returning({'address': {'suburb': 'Old Town', 'town': 'Cobourg', 'postcode': 'K9A'}})
        self.assertEqual(places.place_name(43.96, -78.17, fetch=fetch), 'Old Town, Cobourg, K9A')
        places._cache.clear()
        fetch = self.fetch_returning({'address': {'village': 'Bala'}})
        self.assertEqual(places.place_name(45.01, -79.61, fetch=fetch), 'Bala')

    def test_repeated_parts_are_shown_once(self):
        fetch = self.fetch_returning({'address': {'quarter': 'Toronto', 'city': 'Toronto'}})
        self.assertEqual(places.place_name(43.65, -79.38, fetch=fetch), 'Toronto')

    def test_only_a_rounded_position_is_looked_up(self):
        places.place_name('43.642612', '-79.387054', fetch=self.fetch_returning({'address': {'city': 'Toronto'}}))
        self.assertEqual(self.calls, [(43.643, -79.387)])

    def test_out_of_range_or_bad_coordinates_are_rejected(self):
        fetch = self.fetch_returning({'address': {'city': 'Nowhere'}})
        for lat, lng in ((91, 0), (0, -181), ('abc', 0)):
            with self.assertRaises(ValueError):
                places.place_name(lat, lng, fetch=fetch)
        self.assertEqual(self.calls, [])

    def test_a_found_name_is_cached_for_nearby_lookups(self):
        fetch = self.fetch_returning({'address': {'city': 'Toronto'}})
        self.assertEqual(places.place_name(43.6426, -79.3871, fetch=fetch), 'Toronto')
        self.assertEqual(places.place_name(43.6429, -79.3874, fetch=fetch), 'Toronto')
        self.assertEqual(len(self.calls), 1)

    def test_no_name_is_not_cached(self):
        fetch = self.fetch_returning({'address': {'road': 'Lake Shore Blvd'}})
        self.assertIsNone(places.place_name(43.63, -79.42, fetch=fetch))
        self.assertIsNone(places.place_name(43.63, -79.42, fetch=fetch))
        self.assertEqual(len(self.calls), 2)

    def test_failed_lookup_returns_none(self):
        def broken(lat, lng):
            raise OSError('offline')
        self.assertIsNone(places.place_name(1, 1, fetch=broken))


if __name__ == '__main__':
    unittest.main()
