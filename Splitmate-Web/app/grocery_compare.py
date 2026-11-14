import copy
import json
import logging
import os
import re
import time
from datetime import datetime
from difflib import SequenceMatcher
from decimal import Decimal, ROUND_HALF_UP
from urllib.error import URLError
from urllib.request import Request, urlopen



CENT = Decimal('0.01')
CURRENCY_CODE = 'CAD'

DEMO_CATALOG_SOURCE = (
    'Built-in demo grocery catalog. Replace these catalog rows with a live '
    'retailer or grocery API when real-time prices are available.'
)
TRIMCART_URL = 'https://trimcart.groceryprice.workers.dev/'
TRIMCART_CACHE_SECONDS = 6 * 60 * 60
TRIMCART_CATALOG_SOURCE = (
    'TrimCart weekly Toronto grocery prices. Prices may vary by location and should be confirmed at checkout.'
)
TRIMCART_USER_AGENT = 'Splitmate grocery comparison/1.0'

_catalog_cache = {
    'expires_at': 0,
    'catalogs': None,
    'source': None,
}

STOP_WORDS = {
    'a',
    'an',
    'and',
    'bag',
    'bottle',
    'box',
    'brand',
    'buy',
    'can',
    'carton',
    'fresh',
    'for',
    'get',
    'grocery',
    'groceries',
    'item',
    'items',
    'list',
    'need',
    'of',
    'pack',
    'packet',
    'please',
    'the',
    'to',
}

UNIT_WORDS = {
    'bag',
    'bags',
    'bottle',
    'bottles',
    'box',
    'boxes',
    'bunch',
    'bunches',
    'can',
    'cans',
    'carton',
    'cartons',
    'dozen',
    'g',
    'gram',
    'grams',
    'kg',
    'kilogram',
    'kilograms',
    'l',
    'lb',
    'lbs',
    'liter',
    'liters',
    'loaf',
    'ml',
    'pack',
    'packs',
    'piece',
    'pieces',
    'pcs',
}

BRAND_WORDS = {
    'astro',
    'black',
    'burnbrae',
    'campbells',
    'country',
    'dempsters',
    'driscolls',
    'gay',
    'great',
    'heinz',
    'kelloggs',
    'kraft',
    'minute',
    'neilson',
    'no',
    'name',
    'old',
    'oikos',
    'olivieri',
    'organic',
    'pc',
    'pepsi',
    'presidents',
    'quaker',
    'selection',
    'silk',
    'simply',
    'wonder',
}

LEADING_QUANTITY_RE = re.compile(
    r'^\s*(?:(?P<count_a>\d+(?:\.\d+)?)\s*x\s*|(?P<count_b>\d+(?:\.\d+)?)\s+)?'
    r'(?:(?P<unit>kg|g|lb|lbs|l|ml|dozen|pack|packs|bag|bags|box|boxes|bottle|bottles|can|cans|loaf|bunch|pcs|pieces)\b\s*)?',
    re.IGNORECASE,
)
TRAILING_QUANTITY_RE = re.compile(r'\b(?:x\s*)?(?P<count>\d+(?:\.\d+)?)\s*$', re.IGNORECASE)

TRIMCART_STORES = [
    ('nofrills', 'No Frills'),
    ('walmart', 'Walmart'),
    ('freshco', 'FreshCo'),
    ('metro', 'Metro'),
    ('foodbasics', 'Food Basics'),
    ('sobeys', 'Sobeys'),
]

TRIMCART_ITEM_ALIASES = {
    'white bread': ['bread', 'white bread', 'loaf'],
    'eggs large 12pk': ['eggs', 'egg', 'large eggs', 'dozen eggs', '12 eggs'],
    'chicken breasts per kg': ['chicken', 'chicken breast', 'chicken breasts'],
    'ground beef per kg': ['ground beef', 'beef', 'minced beef'],
    'milk 2% 4l': ['milk', '2 percent milk', '2% milk', 'dairy milk'],
    'butter 454g': ['butter', 'salted butter', 'unsalted butter'],
    'cheddar cheese 400g': ['cheese', 'cheddar', 'cheddar cheese'],
    'bacon per 100g': ['bacon'],
    'bananas per lb': ['bananas', 'banana'],
    'carrots per kg': ['carrots', 'carrot'],
    'potatoes 4 54kg 10lb bag': ['potatoes', 'potato', '10 lb potatoes'],
    'yellow onions 1 36kg 3lb bag': ['onions', 'onion', 'yellow onions'],
    'pasta spaghetti 900g': ['pasta', 'spaghetti', 'noodles'],
    'canned tuna 170g': ['tuna', 'canned tuna', 'tuna can'],
    'frozen peas 750g': ['peas', 'frozen peas'],
}

GROCERY_COMPARISON_PHRASES = {
    'food basics',
    'food list',
    'grocery list',
    'meal prep',
    'no frills',
    'shopping list',
    'store run',
}

GROCERY_COMPARISON_KEYWORDS = {
    'buy',
    'cart',
    'costco',
    'freshco',
    'food',
    'foods',
    'groceries',
    'grocery',
    'ingredient',
    'ingredients',
    'list',
    'loblaws',
    'market',
    'metro',
    'pantry',
    'purchase',
    'shop',
    'shopping',
    'sobeys',
    'store',
    'supermarket',
    'walmart',
}


DEMO_GROCERY_CATALOGS = [
    {
        'store_id': 'walmart',
        'store_name': 'Walmart',
        'items': [
            {'name': 'Great Value 2% Milk', 'brand': 'Great Value', 'generic_name': 'milk', 'size': '4 L', 'price': '5.69', 'in_stock': True, 'aliases': ['2 percent milk', 'dairy milk']},
            {'name': 'Burnbrae Large Eggs', 'brand': 'Burnbrae', 'generic_name': 'eggs', 'size': '12 count', 'price': '3.98', 'in_stock': True, 'aliases': ['egg', 'dozen eggs']},
            {'name': 'Dempsters White Bread', 'brand': 'Dempsters', 'generic_name': 'bread', 'size': '675 g', 'price': '3.47', 'in_stock': True, 'aliases': ['loaf', 'white bread']},
            {'name': 'Great Value Long Grain Rice', 'brand': 'Great Value', 'generic_name': 'rice', 'size': '2 kg', 'price': '4.97', 'in_stock': True, 'aliases': ['white rice']},
            {'name': 'Great Value Pasta', 'brand': 'Great Value', 'generic_name': 'pasta', 'size': '900 g', 'price': '2.27', 'in_stock': True, 'aliases': ['spaghetti', 'macaroni']},
            {'name': 'Kraft Cheddar Cheese', 'brand': 'Kraft', 'generic_name': 'cheese', 'size': '400 g', 'price': '5.77', 'in_stock': True, 'aliases': ['cheddar']},
            {'name': 'Astro Plain Yogurt', 'brand': 'Astro', 'generic_name': 'yogurt', 'size': '750 g', 'price': '3.97', 'in_stock': True, 'aliases': ['plain yogurt', 'curd']},
            {'name': 'Great Value Unsalted Butter', 'brand': 'Great Value', 'generic_name': 'butter', 'size': '454 g', 'price': '5.48', 'in_stock': True, 'aliases': ['unsalted butter']},
            {'name': 'Kelloggs Corn Flakes', 'brand': 'Kelloggs', 'generic_name': 'cereal', 'size': '440 g', 'price': '4.97', 'in_stock': True, 'aliases': ['corn flakes', 'breakfast cereal']},
            {'name': 'Minute Maid Orange Juice', 'brand': 'Minute Maid', 'generic_name': 'orange juice', 'size': '1.54 L', 'price': '3.28', 'in_stock': False, 'aliases': ['juice', 'oj']},
            {'name': 'Bananas', 'brand': '', 'generic_name': 'bananas', 'size': '1 kg', 'price': '1.68', 'in_stock': True, 'aliases': ['banana']},
            {'name': 'Red Apples', 'brand': '', 'generic_name': 'apples', 'size': '1 kg', 'price': '4.39', 'in_stock': True, 'aliases': ['apple', 'red apple']},
            {'name': 'Potatoes', 'brand': '', 'generic_name': 'potatoes', 'size': '10 lb bag', 'price': '5.97', 'in_stock': True, 'aliases': ['potato']},
            {'name': 'Roma Tomatoes', 'brand': '', 'generic_name': 'tomatoes', 'size': '1 kg', 'price': '3.96', 'in_stock': True, 'aliases': ['tomato']},
            {'name': 'Yellow Onions', 'brand': '', 'generic_name': 'onions', 'size': '3 lb bag', 'price': '2.97', 'in_stock': True, 'aliases': ['onion']},
            {'name': 'Baby Carrots', 'brand': '', 'generic_name': 'carrots', 'size': '2 lb bag', 'price': '3.47', 'in_stock': True, 'aliases': ['carrot']},
            {'name': 'Romaine Lettuce', 'brand': '', 'generic_name': 'lettuce', 'size': '3 count', 'price': '4.47', 'in_stock': True, 'aliases': ['romaine']},
            {'name': 'Chicken Breast', 'brand': '', 'generic_name': 'chicken breast', 'size': '1 kg', 'price': '13.21', 'in_stock': True, 'aliases': ['chicken']},
            {'name': 'Lean Ground Beef', 'brand': '', 'generic_name': 'ground beef', 'size': '1 kg', 'price': '11.99', 'in_stock': True, 'aliases': ['beef']},
            {'name': 'Canned Tuna', 'brand': 'Great Value', 'generic_name': 'tuna', 'size': '170 g', 'price': '1.47', 'in_stock': True, 'aliases': ['tuna can']},
        ],
    },
    {
        'store_id': 'nofrills',
        'store_name': 'No Frills',
        'items': [
            {'name': 'Neilson 2% Milk', 'brand': 'Neilson', 'generic_name': 'milk', 'size': '4 L', 'price': '5.89', 'in_stock': True, 'aliases': ['2 percent milk', 'dairy milk']},
            {'name': 'No Name Large Eggs', 'brand': 'No Name', 'generic_name': 'eggs', 'size': '12 count', 'price': '4.29', 'in_stock': True, 'aliases': ['egg', 'dozen eggs']},
            {'name': 'Wonder White Bread', 'brand': 'Wonder', 'generic_name': 'bread', 'size': '675 g', 'price': '2.99', 'in_stock': True, 'aliases': ['loaf', 'white bread']},
            {'name': 'No Name Long Grain Rice', 'brand': 'No Name', 'generic_name': 'rice', 'size': '2 kg', 'price': '4.49', 'in_stock': True, 'aliases': ['white rice']},
            {'name': 'No Name Pasta', 'brand': 'No Name', 'generic_name': 'pasta', 'size': '900 g', 'price': '1.99', 'in_stock': True, 'aliases': ['spaghetti', 'macaroni']},
            {'name': 'No Name Cheddar Cheese', 'brand': 'No Name', 'generic_name': 'cheese', 'size': '400 g', 'price': '5.49', 'in_stock': False, 'aliases': ['cheddar']},
            {'name': 'PC Plain Yogurt', 'brand': 'PC', 'generic_name': 'yogurt', 'size': '750 g', 'price': '3.79', 'in_stock': True, 'aliases': ['plain yogurt', 'curd']},
            {'name': 'No Name Salted Butter', 'brand': 'No Name', 'generic_name': 'butter', 'size': '454 g', 'price': '5.29', 'in_stock': True, 'aliases': ['salted butter']},
            {'name': 'No Name Corn Flakes', 'brand': 'No Name', 'generic_name': 'cereal', 'size': '440 g', 'price': '3.99', 'in_stock': True, 'aliases': ['corn flakes', 'breakfast cereal']},
            {'name': 'PC Orange Juice', 'brand': 'PC', 'generic_name': 'orange juice', 'size': '1.54 L', 'price': '3.49', 'in_stock': True, 'aliases': ['juice', 'oj']},
            {'name': 'Bananas', 'brand': '', 'generic_name': 'bananas', 'size': '1 kg', 'price': '1.65', 'in_stock': True, 'aliases': ['banana']},
            {'name': 'Red Apples', 'brand': '', 'generic_name': 'apples', 'size': '1 kg', 'price': '3.99', 'in_stock': True, 'aliases': ['apple', 'red apple']},
            {'name': 'Potatoes', 'brand': '', 'generic_name': 'potatoes', 'size': '10 lb bag', 'price': '4.99', 'in_stock': True, 'aliases': ['potato']},
            {'name': 'Tomatoes', 'brand': '', 'generic_name': 'tomatoes', 'size': '1 kg', 'price': '3.49', 'in_stock': True, 'aliases': ['tomato']},
            {'name': 'Yellow Onions', 'brand': '', 'generic_name': 'onions', 'size': '3 lb bag', 'price': '2.49', 'in_stock': True, 'aliases': ['onion']},
            {'name': 'Carrots', 'brand': '', 'generic_name': 'carrots', 'size': '2 lb bag', 'price': '2.99', 'in_stock': True, 'aliases': ['carrot']},
            {'name': 'Romaine Lettuce', 'brand': '', 'generic_name': 'lettuce', 'size': '3 count', 'price': '4.99', 'in_stock': False, 'aliases': ['romaine']},
            {'name': 'Chicken Breast', 'brand': '', 'generic_name': 'chicken breast', 'size': '1 kg', 'price': '12.49', 'in_stock': True, 'aliases': ['chicken']},
            {'name': 'Lean Ground Beef', 'brand': '', 'generic_name': 'ground beef', 'size': '1 kg', 'price': '10.99', 'in_stock': True, 'aliases': ['beef']},
            {'name': 'No Name Canned Tuna', 'brand': 'No Name', 'generic_name': 'tuna', 'size': '170 g', 'price': '1.39', 'in_stock': True, 'aliases': ['tuna can']},
        ],
    },
    {
        'store_id': 'freshco',
        'store_name': 'FreshCo',
        'items': [
            {'name': 'Neilson 2% Milk', 'brand': 'Neilson', 'generic_name': 'milk', 'size': '4 L', 'price': '5.79', 'in_stock': True, 'aliases': ['2 percent milk', 'dairy milk']},
            {'name': 'Compliments Large Eggs', 'brand': 'Compliments', 'generic_name': 'eggs', 'size': '12 count', 'price': '4.09', 'in_stock': True, 'aliases': ['egg', 'dozen eggs']},
            {'name': 'Dempsters Whole Wheat Bread', 'brand': 'Dempsters', 'generic_name': 'bread', 'size': '675 g', 'price': '3.29', 'in_stock': True, 'aliases': ['loaf', 'whole wheat bread']},
            {'name': 'Selection Long Grain Rice', 'brand': 'Selection', 'generic_name': 'rice', 'size': '2 kg', 'price': '4.79', 'in_stock': True, 'aliases': ['white rice']},
            {'name': 'Selection Pasta', 'brand': 'Selection', 'generic_name': 'pasta', 'size': '900 g', 'price': '2.19', 'in_stock': True, 'aliases': ['spaghetti', 'macaroni']},
            {'name': 'Black Diamond Cheddar Cheese', 'brand': 'Black Diamond', 'generic_name': 'cheese', 'size': '400 g', 'price': '5.99', 'in_stock': True, 'aliases': ['cheddar']},
            {'name': 'Oikos Plain Yogurt', 'brand': 'Oikos', 'generic_name': 'yogurt', 'size': '750 g', 'price': '4.49', 'in_stock': True, 'aliases': ['plain yogurt', 'curd']},
            {'name': 'Gay Lea Butter', 'brand': 'Gay Lea', 'generic_name': 'butter', 'size': '454 g', 'price': '5.69', 'in_stock': True, 'aliases': ['salted butter', 'unsalted butter']},
            {'name': 'Kelloggs Cereal', 'brand': 'Kelloggs', 'generic_name': 'cereal', 'size': '440 g', 'price': '4.49', 'in_stock': True, 'aliases': ['corn flakes', 'breakfast cereal']},
            {'name': 'Simply Orange Juice', 'brand': 'Simply', 'generic_name': 'orange juice', 'size': '1.54 L', 'price': '4.49', 'in_stock': True, 'aliases': ['juice', 'oj']},
            {'name': 'Bananas', 'brand': '', 'generic_name': 'bananas', 'size': '1 kg', 'price': '1.72', 'in_stock': True, 'aliases': ['banana']},
            {'name': 'Red Apples', 'brand': '', 'generic_name': 'apples', 'size': '1 kg', 'price': '4.29', 'in_stock': True, 'aliases': ['apple', 'red apple']},
            {'name': 'Potatoes', 'brand': '', 'generic_name': 'potatoes', 'size': '10 lb bag', 'price': '5.49', 'in_stock': True, 'aliases': ['potato']},
            {'name': 'Roma Tomatoes', 'brand': '', 'generic_name': 'tomatoes', 'size': '1 kg', 'price': '3.79', 'in_stock': True, 'aliases': ['tomato']},
            {'name': 'Yellow Onions', 'brand': '', 'generic_name': 'onions', 'size': '3 lb bag', 'price': '2.79', 'in_stock': True, 'aliases': ['onion']},
            {'name': 'Baby Carrots', 'brand': '', 'generic_name': 'carrots', 'size': '2 lb bag', 'price': '3.29', 'in_stock': True, 'aliases': ['carrot']},
            {'name': 'Green Leaf Lettuce', 'brand': '', 'generic_name': 'lettuce', 'size': '1 count', 'price': '2.49', 'in_stock': True, 'aliases': ['romaine']},
            {'name': 'Chicken Breast', 'brand': '', 'generic_name': 'chicken breast', 'size': '1 kg', 'price': '13.99', 'in_stock': True, 'aliases': ['chicken']},
            {'name': 'Lean Ground Beef', 'brand': '', 'generic_name': 'ground beef', 'size': '1 kg', 'price': '11.49', 'in_stock': False, 'aliases': ['beef']},
            {'name': 'Canned Tuna', 'brand': 'Selection', 'generic_name': 'tuna', 'size': '170 g', 'price': '1.59', 'in_stock': True, 'aliases': ['tuna can']},
        ],
    },
    {
        'store_id': 'metro',
        'store_name': 'Metro',
        'items': [
            {'name': 'Neilson 2% Milk', 'brand': 'Neilson', 'generic_name': 'milk', 'size': '4 L', 'price': '6.19', 'in_stock': True, 'aliases': ['2 percent milk', 'dairy milk']},
            {'name': 'Burnbrae Large Eggs', 'brand': 'Burnbrae', 'generic_name': 'eggs', 'size': '12 count', 'price': '4.79', 'in_stock': True, 'aliases': ['egg', 'dozen eggs']},
            {'name': 'Dempsters White Bread', 'brand': 'Dempsters', 'generic_name': 'bread', 'size': '675 g', 'price': '3.99', 'in_stock': True, 'aliases': ['loaf', 'white bread']},
            {'name': 'Selection Rice', 'brand': 'Selection', 'generic_name': 'rice', 'size': '2 kg', 'price': '5.49', 'in_stock': True, 'aliases': ['white rice']},
            {'name': 'Olivieri Fresh Pasta', 'brand': 'Olivieri', 'generic_name': 'pasta', 'size': '750 g', 'price': '4.99', 'in_stock': True, 'aliases': ['spaghetti', 'macaroni']},
            {'name': 'Black Diamond Cheddar Cheese', 'brand': 'Black Diamond', 'generic_name': 'cheese', 'size': '400 g', 'price': '6.49', 'in_stock': True, 'aliases': ['cheddar']},
            {'name': 'Oikos Plain Yogurt', 'brand': 'Oikos', 'generic_name': 'yogurt', 'size': '750 g', 'price': '4.79', 'in_stock': True, 'aliases': ['plain yogurt', 'curd']},
            {'name': 'Gay Lea Butter', 'brand': 'Gay Lea', 'generic_name': 'butter', 'size': '454 g', 'price': '6.29', 'in_stock': True, 'aliases': ['salted butter', 'unsalted butter']},
            {'name': 'Kelloggs Corn Flakes', 'brand': 'Kelloggs', 'generic_name': 'cereal', 'size': '440 g', 'price': '5.29', 'in_stock': True, 'aliases': ['corn flakes', 'breakfast cereal']},
            {'name': 'Simply Orange Juice', 'brand': 'Simply', 'generic_name': 'orange juice', 'size': '1.54 L', 'price': '4.99', 'in_stock': True, 'aliases': ['juice', 'oj']},
            {'name': 'Bananas', 'brand': '', 'generic_name': 'bananas', 'size': '1 kg', 'price': '1.89', 'in_stock': True, 'aliases': ['banana']},
            {'name': 'Red Apples', 'brand': '', 'generic_name': 'apples', 'size': '1 kg', 'price': '4.99', 'in_stock': True, 'aliases': ['apple', 'red apple']},
            {'name': 'Potatoes', 'brand': '', 'generic_name': 'potatoes', 'size': '10 lb bag', 'price': '6.49', 'in_stock': True, 'aliases': ['potato']},
            {'name': 'Roma Tomatoes', 'brand': '', 'generic_name': 'tomatoes', 'size': '1 kg', 'price': '4.49', 'in_stock': True, 'aliases': ['tomato']},
            {'name': 'Yellow Onions', 'brand': '', 'generic_name': 'onions', 'size': '3 lb bag', 'price': '3.29', 'in_stock': True, 'aliases': ['onion']},
            {'name': 'Baby Carrots', 'brand': '', 'generic_name': 'carrots', 'size': '2 lb bag', 'price': '3.89', 'in_stock': True, 'aliases': ['carrot']},
            {'name': 'Romaine Lettuce', 'brand': '', 'generic_name': 'lettuce', 'size': '3 count', 'price': '5.49', 'in_stock': True, 'aliases': ['romaine']},
            {'name': 'Chicken Breast', 'brand': '', 'generic_name': 'chicken breast', 'size': '1 kg', 'price': '15.49', 'in_stock': True, 'aliases': ['chicken']},
            {'name': 'Lean Ground Beef', 'brand': '', 'generic_name': 'ground beef', 'size': '1 kg', 'price': '12.49', 'in_stock': True, 'aliases': ['beef']},
            {'name': 'Canned Tuna', 'brand': 'Selection', 'generic_name': 'tuna', 'size': '170 g', 'price': '1.89', 'in_stock': True, 'aliases': ['tuna can']},
        ],
    },
]


def js_array_text_after(html, marker):
    start = html.find(marker)
    if start == -1:
        raise ValueError(f'{marker} was not found.')

    array_start = html.find('[', start)
    if array_start == -1:
        raise ValueError(f'{marker} array was not found.')

    depth = 0
    quote = None
    escaped = False
    for index in range(array_start, len(html)):
        character = html[index]

        if quote:
            if escaped:
                escaped = False
            elif character == '\\':
                escaped = True
            elif character == quote:
                quote = None
            continue

        if character in ("'", '"', '`'):
            quote = character
        elif character == '[':
            depth += 1
        elif character == ']':
            depth -= 1
            if depth == 0:
                return html[array_start:index + 1]

    raise ValueError(f'{marker} array was not closed.')


def split_js_objects(array_text):
    objects = []
    object_start = None
    depth = 0
    quote = None
    escaped = False

    for index, character in enumerate(array_text):
        if quote:
            if escaped:
                escaped = False
            elif character == '\\':
                escaped = True
            elif character == quote:
                quote = None
            continue

        if character in ("'", '"', '`'):
            quote = character
        elif character == '{':
            if depth == 0:
                object_start = index
            depth += 1
        elif character == '}':
            depth -= 1
            if depth == 0 and object_start is not None:
                objects.append(array_text[object_start:index + 1])
                object_start = None

    return objects


def single_quoted_field(object_text, field):
    match = re.search(rf'\b{re.escape(field)}\s*:\s*\'((?:\\\'|[^\'])*)\'', object_text)
    if not match:
        return ''
    return match.group(1).replace("\\'", "'").strip()


def numeric_field(object_text, field):
    match = re.search(rf'\b{re.escape(field)}\s*:\s*(-?\d+(?:\.\d+)?)', object_text)
    if not match:
        return None
    return match.group(1)


def parse_js_price_object(object_text):
    match = re.search(r'\bprices\s*:\s*\{([^}]*)\}', object_text, flags=re.DOTALL)
    if not match:
        return {}

    prices = {}
    for key, value in re.findall(r'\b([a-zA-Z][a-zA-Z0-9_]*)\s*:\s*(-?\d+(?:\.\d+)?)', match.group(1)):
        prices[key.lower()] = value
    return prices


def parse_trimcart_items(html):
    array_text = js_array_text_after(html, 'const ITEMS =')
    items = []

    for object_text in split_js_objects(array_text):
        object_text = re.sub(r"\s*,?\s*img\s*:\s*'[^']*'", '', object_text, flags=re.DOTALL)
        name = single_quoted_field(object_text, 'name')
        prices = parse_js_price_object(object_text)
        if not name or not prices:
            continue

        items.append({
            'name': name,
            'category': single_quoted_field(object_text, 'cat'),
            'statcan': numeric_field(object_text, 'statcan'),
            'prices': prices,
        })

    if not items:
        raise ValueError('No TrimCart grocery items were parsed.')
    return items


def item_size_from_name(name):
    match = re.search(r'\(([^)]+)\)', name)
    return match.group(1).strip() if match else ''


def generic_name_from_trimcart_name(name):
    return re.sub(r'\([^)]*\)', '', name).strip().lower()


def trimcart_aliases_for(item):
    normalized_name = normalize_text(item['name'])
    aliases = TRIMCART_ITEM_ALIASES.get(normalized_name, [])
    generic_name = generic_name_from_trimcart_name(item['name'])
    return sorted({generic_name, item['name'], *aliases})


def trimcart_catalogs_from_items(items):
    catalogs = {
        store_id: {
            'store_id': store_id,
            'store_name': store_name,
            'items': [],
        }
        for store_id, store_name in TRIMCART_STORES
    }

    for item in items:
        aliases = trimcart_aliases_for(item)
        generic_name = generic_name_from_trimcart_name(item['name'])
        size = item_size_from_name(item['name'])
        for store_id, price in item['prices'].items():
            if store_id not in catalogs:
                continue
            catalogs[store_id]['items'].append({
                'name': item['name'],
                'brand': None,
                'generic_name': generic_name,
                'size': size,
                'price': price,
                'in_stock': True,
                'aliases': aliases,
            })

    return [catalogs[store_id] for store_id, _ in TRIMCART_STORES]


def fetch_trimcart_catalogs():
    request = Request(TRIMCART_URL, headers={'User-Agent': TRIMCART_USER_AGENT})
    with urlopen(request, timeout=8) as response:
        charset = response.headers.get_content_charset() or 'utf-8'
        html = response.read().decode(charset, errors='replace')

    items = parse_trimcart_items(html)
    fetched_at = datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'
    return trimcart_catalogs_from_items(items), {
        'name': 'TrimCart Toronto weekly prices',
        'label': TRIMCART_CATALOG_SOURCE,
        'url': TRIMCART_URL,
        'status': 'live_weekly',
        'fetched_at': fetched_at,
        'item_count': len(items),
        'store_count': len(TRIMCART_STORES),
    }


def live_grocery_catalogs():
    source = (os.environ.get('GROCERY_PRICE_SOURCE') or 'trimcart').strip().lower()
    if source == 'demo':
        return DEMO_GROCERY_CATALOGS, {
            'name': 'Demo catalog',
            'label': DEMO_CATALOG_SOURCE,
            'status': 'demo',
        }

    now = time.time()
    if _catalog_cache['catalogs'] and _catalog_cache['expires_at'] > now:
        return _catalog_cache['catalogs'], _catalog_cache['source']

    try:
        catalogs, source_meta = fetch_trimcart_catalogs()
    except (OSError, URLError, TimeoutError, ValueError) as exc:
        # Never fall back to made-up prices; web lookups can still fill in what they find.
        return [{'store_id': store_id, 'store_name': store_name, 'items': []} for store_id, store_name in TRIMCART_STORES], {
            'name': 'Weekly prices unavailable',
            'label': f'TrimCart weekly prices could not be fetched right now ({exc}).',
            'url': TRIMCART_URL,
            'status': 'unavailable',
        }

    _catalog_cache['catalogs'] = catalogs
    _catalog_cache['source'] = source_meta
    _catalog_cache['expires_at'] = now + TRIMCART_CACHE_SECONDS
    return catalogs, source_meta


def normalize_text(value):
    text = re.sub(r'[^a-z0-9% ]+', ' ', str(value or '').lower())
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def normalized_tokens(value, *, keep_brand_words=False):
    tokens = []
    for token in normalize_text(value).split():
        if len(token) <= 1 and not token.isdigit():
            continue
        if token in UNIT_WORDS or token in STOP_WORDS:
            continue
        if not keep_brand_words and token in BRAND_WORDS:
            continue
        if token.endswith('es') and len(token) > 4:
            token = token[:-2]
        elif token.endswith('s') and len(token) > 3:
            token = token[:-1]
        tokens.append(token)
    return tokens


def decimal_from(value, default='1'):
    try:
        number = Decimal(str(value))
    except Exception:
        number = Decimal(default)
    return number if number > 0 else Decimal(default)


def money(value):
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def decimal_to_float(value):
    return float(value.quantize(CENT, rounding=ROUND_HALF_UP))


def split_note_lines(text):
    cleaned = str(text or '').replace('\r', '\n')
    raw_parts = re.split(r'[\n;,]+', cleaned)
    parts = []
    for raw_part in raw_parts:
        part = raw_part.strip()
        part = re.sub(r'^\s*(?:[-*•]|\d+[.)]|\[[ xX]\])\s*', '', part)
        part = part.strip(' -:')
        if part:
            parts.append(part)
    return parts


def parse_grocery_items_from_text(text):
    items = []
    seen = set()

    for raw_item in split_note_lines(text):
        quantity = Decimal('1')
        unit = None
        name = raw_item

        leading_match = LEADING_QUANTITY_RE.match(name)
        if leading_match:
            count = leading_match.group('count_a') or leading_match.group('count_b')
            if count:
                quantity = decimal_from(count)
            if leading_match.group('unit'):
                unit = leading_match.group('unit').lower()
            name = name[leading_match.end():].strip()

        trailing_match = TRAILING_QUANTITY_RE.search(name)
        if trailing_match and not leading_match.group('count_a') and not leading_match.group('count_b'):
            quantity = decimal_from(trailing_match.group('count'))
            name = name[:trailing_match.start()].strip()

        name = re.sub(r'\([^)]*\)', '', name)
        name = re.sub(r'\b(?:x\s*)?\d+(?:\.\d+)?\s*(?:kg|g|lb|lbs|l|ml|dozen|pack|packs|bag|bags|box|boxes|bottle|bottles|can|cans|loaf|bunch|pcs|pieces)?\b', ' ', name, flags=re.IGNORECASE)
        name = re.sub(r'\s+', ' ', name).strip(' -:')

        tokens = normalized_tokens(name)
        if not tokens:
            continue

        normalized_name = ' '.join(tokens)
        key = (normalized_name, str(quantity), unit or '')
        if key in seen:
            continue
        seen.add(key)

        items.append({
            'raw': raw_item,
            'name': name,
            'normalized_name': normalized_name,
            'quantity': decimal_to_float(quantity),
            'unit': unit,
        })

    return items


def note_grocery_text(note):
    description = (getattr(note, 'description', None) or '').strip()
    if description:
        return description
    return (getattr(note, 'title', None) or getattr(note, 'content', None) or '').strip()


def grocery_comparison_enabled_for_text(title='', description=''):
    text = normalize_text(f'{title or ""} {description or ""}')
    if not text:
        return False

    if any(phrase in text for phrase in GROCERY_COMPARISON_PHRASES):
        return True

    return bool(set(text.split()) & GROCERY_COMPARISON_KEYWORDS)


def note_allows_grocery_comparison(note):
    title = getattr(note, 'title', None) or getattr(note, 'content', None) or ''
    description = getattr(note, 'description', None) or ''
    return grocery_comparison_enabled_for_text(title, description)


def parse_grocery_items_from_note(note):
    return parse_grocery_items_from_text(note_grocery_text(note))


def item_search_text(catalog_item):
    parts = [
        catalog_item.get('name'),
        catalog_item.get('generic_name'),
        catalog_item.get('brand'),
        catalog_item.get('size'),
        ' '.join(catalog_item.get('aliases') or []),
    ]
    return ' '.join(part for part in parts if part)


def product_tokens(catalog_item):
    return normalized_tokens(item_search_text(catalog_item))


def match_score(requested_item, catalog_item):
    query_tokens = set(normalized_tokens(requested_item.get('name')))
    candidate_tokens = set(product_tokens(catalog_item))

    if not query_tokens or not candidate_tokens:
        return 0

    overlap = len(query_tokens & candidate_tokens) / len(query_tokens)
    ordered_query = ' '.join(sorted(query_tokens))
    ordered_candidate = ' '.join(sorted(candidate_tokens))
    sequence = SequenceMatcher(None, ordered_query, ordered_candidate).ratio()

    generic_tokens = set(normalized_tokens(catalog_item.get('generic_name')))
    alias_tokens = set(normalized_tokens(' '.join(catalog_item.get('aliases') or [])))
    direct_generic_bonus = Decimal('0.18') if query_tokens & (generic_tokens | alias_tokens) else Decimal('0')

    score = Decimal(str((overlap * 0.68) + (sequence * 0.32))) + direct_generic_bonus
    return min(score, Decimal('1.00'))


def best_match_for_store(requested_item, store_items, threshold=Decimal('0.46')):
    scored_items = [
        (match_score(requested_item, item), item)
        for item in store_items
    ]
    scored_items.sort(key=lambda row: row[0], reverse=True)
    if not scored_items or scored_items[0][0] < threshold:
        return None, Decimal('0')
    return scored_items[0][1], scored_items[0][0]


def line_result_for(requested_item, catalog_item, score):
    quantity = Decimal(str(requested_item.get('quantity') or 1))
    unit_price = money(catalog_item['price'])
    line_total = money(unit_price * quantity)
    in_stock = bool(catalog_item.get('in_stock', True))

    return {
        'requested': requested_item,
        'status': 'available' if in_stock else 'unavailable',
        'matched_item': catalog_item['name'],
        'brand': catalog_item.get('brand') or None,
        'size': catalog_item.get('size') or '',
        'unit_price': decimal_to_float(unit_price),
        'line_total': decimal_to_float(line_total) if in_stock else 0,
        'match_score': float(score.quantize(Decimal('0.01'))),
        'source': catalog_item.get('source') or 'trimcart',
        'source_url': catalog_item.get('source_url') or None,
    }


def missing_line_result(requested_item):
    return {
        'requested': requested_item,
        'status': 'missing',
        'matched_item': None,
        'brand': None,
        'size': '',
        'unit_price': None,
        'line_total': 0,
        'match_score': 0,
    }


def compare_grocery_items(requested_items, catalogs=None):
    if catalogs is None:
        catalogs, _ = live_grocery_catalogs()
    store_results = []

    for store in catalogs:
        lines = []
        total = Decimal('0')
        score_total = Decimal('0')

        for requested_item in requested_items:
            catalog_item, score = best_match_for_store(requested_item, store['items'])
            if not catalog_item:
                lines.append(missing_line_result(requested_item))
                continue

            line = line_result_for(requested_item, catalog_item, score)
            lines.append(line)
            score_total += score
            if line['status'] == 'available':
                total += money(line['line_total'])

        available_count = sum(1 for line in lines if line['status'] == 'available')
        unavailable_count = sum(1 for line in lines if line['status'] == 'unavailable')
        missing_count = sum(1 for line in lines if line['status'] == 'missing')
        requested_count = len(requested_items)

        store_results.append({
            'store_id': store['store_id'],
            'store_name': store['store_name'],
            'currency': CURRENCY_CODE,
            'total': decimal_to_float(total),
            'all_items_available': requested_count > 0 and available_count == requested_count,
            'available_count': available_count,
            'unavailable_count': unavailable_count,
            'missing_count': missing_count,
            'requested_count': requested_count,
            'average_match_score': float((score_total / Decimal(requested_count)).quantize(Decimal('0.01'))) if requested_count else 0,
            'items': lines,
        })

    store_results.sort(key=lambda row: (
        0 if row['all_items_available'] else 1,
        row['missing_count'] + row['unavailable_count'],
        row['total'],
        -row['average_match_score'],
        row['store_name'],
    ))

    for index, store_result in enumerate(store_results, start=1):
        store_result['rank'] = index

    return store_results


# ---------------------------------------------------------------------------
# Live web prices from Gemini + Google Search, for items the weekly flyer data doesn't cover.
# ---------------------------------------------------------------------------
WEB_PRICE_MODEL = os.environ.get('GROCERY_PRICE_MODEL') or 'gemini-3.6-flash'
WEB_PRICE_CACHE_SECONDS = 6 * 60 * 60
WEB_PRICE_MAX_ITEMS = 12
_web_price_cache = {}

DEFAULT_LOCATION = 'Toronto, ON'
last_web_price_error = None  # Shown by /api/mobile/health so a failing lookup can be diagnosed without logs.

WEB_PRICE_PROMPT = """You are checking real, current grocery shelf prices for a shopper near: {location} (Canada, CAD).
Search the stores' own websites (or flyers) for each item below at each store listed.

Stores (use these exact store_id values): {stores}
Items: {items}

For each store, find the branch nearest to the shopper's location.
For each item and store, report the regular price of the most common everyday product that matches
(e.g. "apple" -> a common apple sold per lb or per bag). If the exact item isn't sold there, report the
closest similar product instead and name it in "product". Only report prices you actually found online
in the last few weeks; never estimate or invent a price.

Reply with JSON only, no prose, in exactly this shape:
{{"branches": [{{"store_id": "<store_id>", "branch": "<branch name or street, city>"}}],
"prices": [{{"item": "<item as given>", "store_id": "<store_id>", "product": "<product name as listed>",
"size": "<size or unit, e.g. per lb, 1.36 kg bag>", "price": <number in CAD>, "url": "<page where you found it>"}}]}}"""


def web_price_lookup_configured():
    return bool(os.environ.get('GEMINI_API_KEY'))


def _parse_web_price_json(text):
    """Pull the JSON object out of Gemini's reply (it may wrap it in a code fence)."""
    text = (text or '').strip()
    start, end = text.find('{'), text.rfind('}')
    if start == -1 or end <= start:
        return {}
    try:
        data = json.loads(text[start:end + 1])
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def clean_location(value):
    return re.sub(r'\s+', ' ', str(value or '')).strip()[:80] or DEFAULT_LOCATION


def fetch_web_prices(item_names, location=DEFAULT_LOCATION, client=None):
    """({store_id: [catalog items]}, {store_id: branch}) with real prices found online near `location`.

    Cached for 6 hours per item and location.
    """
    global last_web_price_error
    store_ids = {store_id for store_id, _ in TRIMCART_STORES}
    location = clean_location(location)
    now = time.time()
    found = {store_id: [] for store_id in store_ids}
    branches = {}
    to_lookup = []
    for name in item_names[:WEB_PRICE_MAX_ITEMS]:
        cached = _web_price_cache.get((name.lower(), location.lower()))
        if cached and cached['expires_at'] > now:
            for store_id, entries in cached['prices'].items():
                found[store_id].extend(entries)
            branches.update(cached['branches'])
        else:
            to_lookup.append(name)

    if not to_lookup:
        return found, branches
    if client is None:
        if not web_price_lookup_configured():
            return found, branches
        from google import genai
        client = genai.Client(api_key=os.environ['GEMINI_API_KEY'])

    from google.genai import types
    prompt = WEB_PRICE_PROMPT.format(
        location=location,
        stores=', '.join(f'{store_id} ({store_name})' for store_id, store_name in TRIMCART_STORES),
        items=', '.join(to_lookup),
    )
    try:
        response = client.models.generate_content(
            model=WEB_PRICE_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())]),
        )
        data = _parse_web_price_json(response.text)
    except Exception as exc:  # Any failure just means no web prices this time; flyer prices still show.
        last_web_price_error = f'{type(exc).__name__}: {str(exc)[:300]}'
        logging.getLogger(__name__).warning('Online grocery price lookup failed: %s', last_web_price_error)
        return found, branches
    if not data:
        last_web_price_error = 'Gemini replied without usable JSON: ' + str(getattr(response, 'text', '') or '')[:200]
        return found, branches
    last_web_price_error = None

    fresh_branches = {}
    for row in data.get('branches') or []:
        if isinstance(row, dict):
            store_id = str(row.get('store_id') or '').strip().lower()
            branch = str(row.get('branch') or '').strip()[:80]
            if store_id in store_ids and branch:
                fresh_branches[store_id] = branch

    fresh = {name.lower(): {store_id: [] for store_id in store_ids} for name in to_lookup}
    for row in data.get('prices') or []:
        if not isinstance(row, dict):
            continue
        item = str(row.get('item') or '').strip()
        store_id = str(row.get('store_id') or '').strip().lower()
        try:
            price = money(row.get('price'))
        except Exception:
            continue
        if item.lower() not in fresh or store_id not in store_ids or price <= 0:
            continue
        product = str(row.get('product') or item).strip()[:120]
        url = str(row.get('url') or '').strip()
        fresh[item.lower()][store_id].append({
            'name': product,
            'brand': None,
            'generic_name': item.lower(),
            'size': str(row.get('size') or '').strip()[:40],
            'price': str(price),
            'in_stock': True,
            'aliases': [item, item.lower(), product],
            'source': 'web',
            'source_url': url if url.startswith(('http://', 'https://')) else None,
        })

    for name, prices in fresh.items():
        _web_price_cache[(name, location.lower())] = {
            'prices': prices, 'branches': fresh_branches, 'expires_at': now + WEB_PRICE_CACHE_SECONDS,
        }
        for store_id, entries in prices.items():
            found[store_id].extend(entries)
    branches.update(fresh_branches)
    return found, branches


def compare_grocery_list(requested_items, location=None, client=None):
    """Compare requested items across stores with real prices: weekly flyer data plus a web lookup near `location`."""
    location = clean_location(location)
    catalogs, source_meta = live_grocery_catalogs()
    catalogs = copy.deepcopy(catalogs)

    # Look up online every item that some store lacks, so each store gets its own real price (or closest match).
    uncovered = [
        item['name'] for item in requested_items
        if not all(best_match_for_store(item, store['items'])[0] for store in catalogs)
    ]
    web_used = False
    branches = {}
    if uncovered and source_meta.get('status') != 'demo':
        web_prices, branches = fetch_web_prices(uncovered, location=location, client=client)
        for store in catalogs:
            extra = web_prices.get(store['store_id']) or []
            if extra:
                web_used = True
                store['items'] = list(store['items']) + extra

    stores = compare_grocery_items(requested_items, catalogs)
    for store in stores:
        store['location'] = branches.get(store['store_id']) or location
    labels = [source_meta.get('label')] if source_meta.get('label') else []
    if web_used:
        labels.append('Items not in the weekly flyer data were priced from the stores\' websites via Google Search '
                      f'on {datetime.now().strftime("%b %d, %Y")}. Prices can change; check in store.')
    elif uncovered and last_web_price_error and web_price_lookup_configured():
        labels.append('The online price lookup failed this time, so some items show no price. Try again in a minute.')
    elif uncovered and not web_price_lookup_configured() and source_meta.get('status') != 'demo':
        labels.append('Some items have no weekly price yet. Add GEMINI_API_KEY on the server to look up any item online.')

    return {
        'currency': CURRENCY_CODE,
        'catalog_source': ' '.join(labels),
        'catalog_source_meta': {**source_meta, 'web_lookup': web_used},
        'location': location,
        'requested_items': requested_items,
        'top_store': stores[0] if stores and any(store['available_count'] for store in stores) else None,
        'stores': stores,
    }


def compare_grocery_note(note, location=None):
    requested_items = parse_grocery_items_from_note(note)
    result = compare_grocery_list(requested_items, location=location)
    return {
        'note_id': note.id,
        'note_title': getattr(note, 'title', None) or getattr(note, 'content', None) or '',
        **result,
    }
