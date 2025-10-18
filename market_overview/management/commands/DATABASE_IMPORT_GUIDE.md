# Database Import Guide

## Problem: Duplicate Key Violations After Database Import

When importing data from another database, you may encounter the following error:
```
django.db.utils.IntegrityError: duplicate key value violates unique constraint "market_overview_marketpricemodel_pkey"
DETAIL: Key (id)=(1) already exists.
```

This happens because PostgreSQL sequences (auto-increment counters) are not automatically updated when you import data, causing Django to try to insert records with IDs that already exist.

## Solutions

### 1. Reset Sequences (Recommended)

Use the custom management command to reset all sequences:

```bash
# Dry run to see what would be done
python manage.py reset_sequences --dry-run

# Actually reset the sequences
python manage.py reset_sequences
```

### 2. Manual SQL Reset

If you need to reset sequences manually:

```sql
-- Reset MarketPriceModel sequence
SELECT setval('market_overview_marketpricemodel_id_seq', (SELECT MAX(id) FROM market_overview_marketpricemodel));

-- Reset PriceUpdateLogModel sequence
SELECT setval('market_overview_priceupdatelogmodel_id_seq', (SELECT MAX(id) FROM market_overview_priceupdatelogmodel));
```

### 3. Django Shell Reset

You can also reset sequences using Django shell:

```python
from django.db import connection

cursor = connection.cursor()

# Reset MarketPriceModel sequence
cursor.execute('SELECT MAX(id) FROM market_overview_marketpricemodel;')
max_id = cursor.fetchone()[0] or 0
cursor.execute(f'ALTER SEQUENCE market_overview_marketpricemodel_id_seq RESTART WITH {max_id + 1};')

# Reset PriceUpdateLogModel sequence
cursor.execute('SELECT MAX(id) FROM market_overview_priceupdatelogmodel;')
max_log_id = cursor.fetchone()[0] or 0
cursor.execute(f'ALTER SEQUENCE market_overview_priceupdatelogmodel_id_seq RESTART WITH {max_log_id + 1};')
```

## Prevention

### Enhanced Error Handling

The codebase has been enhanced with better error handling in the `upsert_with_logs` function in `shared/services.py` to handle race conditions and duplicate key scenarios more gracefully.

### Using get_or_create Pattern

The application uses the `upsert_with_logs` function which implements a get-or-create pattern, helping to avoid duplicate entries based on the unique constraints defined in the models.

## Model Unique Constraints

The `MarketPriceModel` has a unique constraint on `(short_name, date)`, which means:
- You cannot have duplicate entries for the same asset on the same date
- The system will update existing records instead of creating duplicates

## Testing

After resetting sequences, you can test that everything is working:

```python
from market_overview.models import MarketPriceModel
from datetime import date

# This should work without duplicate key errors
test_record = MarketPriceModel.objects.create(
    date=date(2024, 1, 1),
    short_name='TEST_ASSET',
    asset_class='STOCKS',
    location='US',
    full_name='Test Asset',
    price=100.0,
    source='TEST'
)
print(f"Created record with ID: {test_record.id}")
```

## Troubleshooting

### If you still get duplicate key errors:

1. Check if the sequence was actually reset:
   ```sql
   SELECT last_value FROM market_overview_marketpricemodel_id_seq;
   ```

2. Verify the maximum ID in your table:
   ```sql
   SELECT MAX(id) FROM market_overview_marketpricemodel;
   ```

3. The sequence should be set to `MAX(id) + 1`

### If sequences are reset but you still have issues:

1. Check for any custom ID assignments in your data import
2. Verify that your import process isn't explicitly setting IDs
3. Make sure you're not using `bulk_create` with explicit IDs

## Best Practices

1. **Always reset sequences after importing data**
2. **Use the management command for consistency**
3. **Test with a small dataset first**
4. **Keep backups before making changes**
5. **Use the enhanced error handling in your views**

## Files Modified

- `shared/views.py` - Enhanced BaseAPIView with proper JSON error handling
- `shared/services.py` - Improved `upsert_with_logs` function with better error handling
- `market_overview/management/commands/reset_sequences.py` - New management command
- `requirements.txt` - Added `openpyxl` dependency for Excel file handling
