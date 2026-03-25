"""
Data Import Scripts
Helper utilities for importing scraped data into Hive.
"""
import pandas as pd
import logging
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def preprocess_homestay_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Preprocess raw homestay data before importing to Hive.
    """
    # Remove duplicates
    df = df.drop_duplicates(subset=['id'])

    # Handle missing values
    df['rating'] = df.get('rating', 4.5).fillna(4.5)
    df['review_count'] = df.get('review_count', 0).fillna(0)

    # Price cleaning
    df['price'] = pd.to_numeric(df['price'], errors='coerce')
    df = df[(df['price'] > 0) & (df['price'] < 10000)]  # Filter outliers

    # Standardize text fields
    text_cols = ['district', 'room_type']
    for col in text_cols:
        if col in df.columns:
            df[col] = df[col].str.strip()

    # Convert boolean columns
    bool_cols = ['has_wifi', 'has_parking', 'has_kitchen', 'has_air_conditioning']
    for col in bool_cols:
        if col in df.columns:
            df[col] = df[col].astype(bool)

    logger.info(f"Preprocessed {len(df)} records")
    return df


def generate_hive_insert_statement(df: pd.DataFrame, table_name: str) -> str:
    """
    Generate Hive INSERT statement from DataFrame.
    """
    columns = ', '.join(df.columns)

    values_list = []
    for _, row in df.iterrows():
        values = []
        for val in row:
            if pd.isna(val):
                values.append('NULL')
            elif isinstance(val, str):
                values.append(f"'{val}'")
            elif isinstance(val, bool):
                values.append('TRUE' if val else 'FALSE')
            else:
                values.append(str(val))
        values_list.append(f"({', '.join(values)})")

    values_str = ',\n'.join(values_list[:100])  # Limit batch size

    insert_sql = f"""
    INSERT INTO TABLE {table_name}
    ({columns})
    VALUES
    {values_str};
    """

    return insert_sql


def validate_data_quality(df: pd.DataFrame) -> dict:
    """
    Validate data quality and return metrics.
    """
    metrics = {
        'total_records': len(df),
        'missing_values': df.isnull().sum().to_dict(),
        'duplicate_records': df.duplicated().sum(),
        'price_range': {
            'min': df['price'].min() if 'price' in df.columns else None,
            'max': df['price'].max() if 'price' in df.columns else None,
            'mean': df['price'].mean() if 'price' in df.columns else None
        }
    }

    # Check for data anomalies
    anomalies = []

    if 'price' in df.columns:
        if df['price'].min() < 10:
            anomalies.append("Found prices below 10 RMB")
        if df['price'].max() > 10000:
            anomalies.append("Found prices above 10000 RMB")

    if 'rating' in df.columns:
        if df['rating'].min() < 1 or df['rating'].max() > 5:
            anomalies.append("Rating out of range [1, 5]")

    metrics['anomalies'] = anomalies

    return metrics
