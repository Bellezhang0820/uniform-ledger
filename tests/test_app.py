import os
import tempfile

import pytest

from app import create_app
from ledger.parser import normalize_category, normalize_for_reconcile, parse_text
from ledger.reconciliation import compare_items


@pytest.fixture()
def client():
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    os.unlink(path)
    app = create_app({'TESTING': True, 'DATABASE': path})
    with app.test_client() as client:
        yield client
    if os.path.exists(path):
        os.unlink(path)


def cats(result):
    return [(i['category_name'], i['size'], i['qty'], i['unit']) for i in result['items']]


def test_parse_example_one_shorthand_context():
    text = '''小学速干套装
160*5套
170短袖2件
中学速干套装
180 185 各3套
中学速干长裤170*2/175*2'''
    assert cats(parse_text(text)) == [
        ('小学速干套装', '160', 5, '套'),
        ('小学速干短袖', '170', 2, '件'),
        ('中学速干套装', '180', 3, '套'),
        ('中学速干套装', '185', 3, '套'),
        ('中学速干长裤', '170', 2, '条'),
        ('中学速干长裤', '175', 2, '条'),
    ]


def test_parse_platform_list_with_notes():
    text = '''3【120】小学同款长裤（码偏大）
2【170】小学速干长裤（正码）
3【185尺码】中学夏长裤（学校同款）'''
    result = parse_text(text)
    assert cats(result) == [
        ('小学同款长裤', '120', 3, '条'),
        ('小学速干长裤', '170', 2, '条'),
        ('中学同款夏长裤', '185', 3, '条'),
    ]
    assert result['items'][0]['note'] == '码偏大'


def test_parse_mixed_multiline_format():
    text = '''小学速干长裤
130*5
140*5
150*5
160*5
小学速干短袖
140*5
150*5
160*5
165*3
中学速干短袖6件
170*3
175*3'''
    result = parse_text(text)
    assert len(result['items']) == 10
    assert result['items'][0]['category_name'] == '小学速干长裤'
    assert result['items'][-1]['category_name'] == '中学速干短袖'
    assert sum(i['qty'] for i in result['items']) == 44


def test_parse_single_line_multiple_tokens():
    result = parse_text('小学速干短袖 170短袖2件 175短袖2件')
    assert cats(result) == [('小学速干短袖', '170', 2, '件'), ('小学速干短袖', '175', 2, '件')]


def test_school_same_style_defaults_to_short_sleeve():
    result = parse_text('小学同款短袖\n学校同款5件')
    assert result['items'][0]['category_name'] == '小学同款短袖'
    assert result['items'][0]['qty'] == 5


def test_normalize_category_ambiguous_by_context():
    ctx = type('Ctx', (), {'school_level': '中学', 'fabric_type': None, 'item_type': None})()
    normalized = normalize_category('速干短袖', ctx)
    assert normalized == {'school_level': '中学', 'fabric_type': '速干', 'item_type': '短袖'}


def test_reconcile_maps_ice_silk_to_quick_dry():
    item = {'school_level': '中学', 'fabric_type': '冰丝', 'item_type': '短袖', 'size': '170'}
    assert normalize_for_reconcile(item) == ('中学', '速干', '短袖', '170')


def test_reconciliation_diff_amount():
    ours = [{'school_level': '中学', 'fabric_type': '速干', 'item_type': '短袖', 'size': '170', 'qty': 3, 'unit_price': 40}]
    theirs = [{'school_level': '中学', 'fabric_type': '冰丝', 'item_type': '短袖', 'size': '170', 'qty': 1, 'unit_price': 40}]
    result = compare_items(ours, theirs)
    assert result['rows'][0]['status'] == '数量不符'
    assert result['rows'][0]['diff_qty'] == 2
    assert result['rows'][0]['diff_amount'] == 80


def test_price_list_seed_has_19_items(client):
    data = client.get('/api/price-list').get_json()
    assert len(data['items']) == 19
    mid_ice = next(i for i in data['items'] if i['school_level'] == '中学' and i['fabric_type'] == '冰丝' and i['item_type'] == '短袖')
    assert mid_ice['sell_price'] == 40
    assert mid_ice['cost_price'] == 28


def test_order_create_stats_and_money(client):
    parsed = client.post('/api/parse', json={'text': '小学速干短袖\n130*2'}).get_json()
    created = client.post('/api/orders', json={'source': 'manual', 'raw_text': 'x', 'items': parsed['items']}).get_json()
    assert created['total_qty'] == 2
    assert created['total_amount'] == 70
    assert created['gross_profit'] == 21
    st = client.get('/api/stats?range=day').get_json()
    assert st['totals']['qty'] == 2
    assert st['totals']['sales'] == 70
    assert st['totals']['profit'] == 21


def test_reconcile_api_parses_their_text(client):
    parsed = client.post('/api/parse', json={'text': '小学速干长裤\n130*2'}).get_json()
    client.post('/api/orders', json={'source': 'manual', 'raw_text': 'x', 'items': parsed['items']})
    result = client.post('/api/reconcile', json={'our_date': __import__('datetime').date.today().isoformat(), 'their_text': '2【130】小学速干长裤'}).get_json()
    assert result['summary']['matched'] == 1
    assert result['summary']['mismatched'] == 0


def test_export_csv_contains_order(client):
    parsed = client.post('/api/parse', json={'text': '中学冰丝长裤\n175*1'}).get_json()
    client.post('/api/orders', json={'source': 'manual', 'raw_text': 'x', 'items': parsed['items']})
    text = client.post('/api/export', json={}).data.decode('utf-8')
    assert '中学' in text
    assert '冰丝' in text
