"""Public catalog metadata only; no credentials, discovery or inference."""
import math
import re


TEXT_FIELDS = ('model', 'display_name', 'checked_at', 'vendor_for_rates', 'availability')
PRICE_FIELDS = ('input_per_million', 'output_per_million',
                'cache_read_per_million', 'cache_write_per_million')


def public_provider_info(supplied: object = None) -> dict:
    """Copy only typed scalar metadata, never arbitrary nested receipt values."""
    supplied = supplied if isinstance(supplied, dict) else {}
    public = {}
    for key in TEXT_FIELDS:
        value = supplied.get(key)
        if isinstance(value, str) and value.strip() and len(value) <= 512:
            if not any(ord(char) < 32 or ord(char) == 127 for char in value):
                public[key] = value
    streaming = supplied.get('advertised_streaming')
    if type(streaming) is bool:
        public['advertised_streaming'] = streaming
    supplied_price = supplied.get('pricing')
    supplied_price = supplied_price if isinstance(supplied_price, dict) else {}
    price = {}
    currency = supplied_price.get('currency')
    if isinstance(currency, str) and re.fullmatch('[A-Z]{3}', currency):
        price['currency'] = currency
    for key in PRICE_FIELDS:
        value = supplied_price.get(key)
        if type(value) not in (int, float):
            continue
        try:
            valid = math.isfinite(value) and value >= 0
        except OverflowError:
            valid = False
        if valid:
            price[key] = value
    public.update(pricing=price, status='Catalog metadata only', inference_calls=0,
                  cache_hits_measured=False, generation_enabled=False)
    return public
