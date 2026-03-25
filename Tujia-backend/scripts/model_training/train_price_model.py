"""
XGBoost Model Training Script for Homestay Price Prediction.

This script:
1. Loads training data from Hive
2. Performs feature engineering
3. Trains an XGBoost regression model
4. Evaluates model performance
5. Saves the trained model

Usage:
    python scripts/model_training/train_price_model.py --output models/xgboost_price_model.json
"""
import argparse
import logging
import pickle
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GridSearchCV, train_test_split

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.db.hive import execute_query_to_df

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_training_data() -> pd.DataFrame:
    """
    Load training data from Hive.
    """
    query = """
    SELECT
        id,
        district,
        room_type,
        capacity,
        bedrooms,
        bathrooms,
        has_wifi,
        has_parking,
        has_kitchen,
        has_air_conditioning,
        is_weekend,
        is_holiday,
        distance_to_metro,
        rating,
        review_count,
        price
    FROM homestay_db.dwd_homestay_training
    WHERE price IS NOT NULL
      AND price > 0
      AND price < 5000  -- Filter outliers
    """

    logger.info("Loading training data from Hive...")
    df = execute_query_to_df(query)

    if df.empty:
        logger.warning("No data from Hive, using mock data for demonstration")
        df = _create_mock_data()

    logger.info(f"Loaded {len(df)} records")
    return df


def _create_mock_data() -> pd.DataFrame:
    """Create mock data for demonstration."""
    np.random.seed(42)
    n = 1000

    districts = ["江汉路", "光谷", "楚河汉街", "黄鹤楼", "武昌火车站"]
    room_types = ["整套房屋", "独立房间", "合住房间"]

    data = {
        'id': range(n),
        'district': np.random.choice(districts, n),
        'room_type': np.random.choice(room_types, n),
        'capacity': np.random.randint(1, 8, n),
        'bedrooms': np.random.randint(1, 4, n),
        'bathrooms': np.random.randint(1, 3, n),
        'has_wifi': np.random.choice([True, False], n, p=[0.95, 0.05]),
        'has_parking': np.random.choice([True, False], n, p=[0.3, 0.7]),
        'has_kitchen': np.random.choice([True, False], n, p=[0.7, 0.3]),
        'has_air_conditioning': np.random.choice([True, False], n, p=[0.9, 0.1]),
        'is_weekend': np.random.choice([True, False], n),
        'is_holiday': np.random.choice([True, False], n, p=[0.1, 0.9]),
        'distance_to_metro': np.random.uniform(0.1, 2.0, n),
        'rating': np.random.uniform(3.5, 5.0, n),
        'review_count': np.random.randint(0, 500, n),
    }

    df = pd.DataFrame(data)

    # Generate price based on features
    base_price = 150
    district_multipliers = {"江汉路": 1.5, "光谷": 1.2, "楚河汉街": 1.6,
                           "黄鹤楼": 1.4, "武昌火车站": 1.0}
    room_multipliers = {"整套房屋": 1.5, "独立房间": 1.0, "合住房间": 0.6}

    df['price'] = base_price
    df['price'] *= df['district'].map(district_multipliers)
    df['price'] *= df['room_type'].map(room_multipliers)
    df['price'] += (df['capacity'] - 1) * 30
    df['price'] += df['bedrooms'] * 50
    df['price'] += df['bathrooms'] * 30
    df['price'] += df['has_wifi'] * 10
    df['price'] += df['has_parking'] * 40
    df['price'] *= (1 + df['is_weekend'] * 0.2)
    df['price'] *= (1 + df['is_holiday'] * 0.5)
    df['price'] *= (1 + df['rating'] * 0.1)
    df['price'] += np.random.normal(0, 20, n)  # Add noise

    return df


def feature_engineering(df: pd.DataFrame) -> pd.DataFrame:
    """
    Perform feature engineering on raw data.
    """
    logger.info("Performing feature engineering...")

    # One-hot encode categorical variables
    df = pd.get_dummies(df, columns=['district', 'room_type'], prefix=['dist', 'room'])

    # Create interaction features
    df['capacity_bedroom_ratio'] = df['capacity'] / (df['bedrooms'] + 1)
    df['has_luxury_amenities'] = (df.get('has_parking', False) & df.get('has_wifi', False)).astype(int)

    # Log transform for skewed features
    if 'review_count' in df.columns:
        df['log_review_count'] = np.log1p(df['review_count'])

    return df


def prepare_features(df: pd.DataFrame, target_col: str = 'price') -> tuple:
    """
    Prepare features and target for training.
    """
    feature_cols = [col for col in df.columns
                    if col not in [target_col, 'id']]

    X = df[feature_cols]
    y = df[target_col]

    return X, y, feature_cols


def train_model(X_train: pd.DataFrame, y_train: pd.Series) -> xgb.XGBRegressor:
    """
    Train XGBoost model with hyperparameter tuning.
    """
    logger.info("Training XGBoost model...")

    # Define parameter grid for GridSearch
    param_grid = {
        'max_depth': [3, 5, 7],
        'learning_rate': [0.05, 0.1, 0.2],
        'n_estimators': [100, 200],
        'subsample': [0.8, 1.0],
        'colsample_bytree': [0.8, 1.0]
    }

    # Base model
    xgb_model = xgb.XGBRegressor(
        objective='reg:squarederror',
        random_state=42,
        n_jobs=-1
    )

    # Grid search with cross-validation
    logger.info("Running hyperparameter tuning...")
    grid_search = GridSearchCV(
        estimator=xgb_model,
        param_grid=param_grid,
        cv=5,
        scoring='neg_mean_absolute_error',
        n_jobs=-1,
        verbose=1
    )

    grid_search.fit(X_train, y_train)

    logger.info(f"Best parameters: {grid_search.best_params_}")
    logger.info(f"Best CV score: {-grid_search.best_score_:.2f} MAE")

    return grid_search.best_estimator_


def evaluate_model(model: xgb.XGBRegressor,
                   X_test: pd.DataFrame,
                   y_test: pd.Series,
                   feature_names: list) -> dict:
    """
    Evaluate model performance.
    """
    logger.info("Evaluating model...")

    predictions = model.predict(X_test)

    metrics = {
        'mae': mean_absolute_error(y_test, predictions),
        'rmse': np.sqrt(mean_squared_error(y_test, predictions)),
        'r2': r2_score(y_test, predictions),
        'mape': np.mean(np.abs((y_test - predictions) / y_test)) * 100
    }

    logger.info(f"MAE: {metrics['mae']:.2f}")
    logger.info(f"RMSE: {metrics['rmse']:.2f}")
    logger.info(f"R²: {metrics['r2']:.4f}")
    logger.info(f"MAPE: {metrics['mape']:.2f}%")

    # Feature importance
    importance_df = pd.DataFrame({
        'feature': feature_names,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)

    logger.info("\nTop 10 Important Features:")
    logger.info(importance_df.head(10).to_string(index=False))

    return metrics


def save_model(model: xgb.XGBRegressor,
               feature_names: list,
               output_path: str) -> None:
    """
    Save trained model and metadata.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Save model
    model.save_model(str(output_path))
    logger.info(f"Model saved to {output_path}")

    # Save feature names for inference
    metadata = {
        'feature_names': feature_names,
        'training_date': datetime.now().isoformat(),
        'model_version': '1.0'
    }

    metadata_path = output_path.with_suffix('.pkl')
    with open(metadata_path, 'wb') as f:
        pickle.dump(metadata, f)

    logger.info(f"Metadata saved to {metadata_path}")


def main():
    parser = argparse.ArgumentParser(description='Train XGBoost price prediction model')
    parser.add_argument('--output', default='models/xgboost_price_model.json',
                       help='Output path for trained model')
    parser.add_argument('--test-size', type=float, default=0.2,
                       help='Test set size ratio')
    parser.add_argument('--skip-tuning', action='store_true',
                       help='Skip hyperparameter tuning for faster training')
    args = parser.parse_args()

    # Load data
    df = load_training_data()

    # Feature engineering
    df = feature_engineering(df)

    # Prepare features
    X, y, feature_names = prepare_features(df)

    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=args.test_size, random_state=42
    )

    logger.info(f"Training set size: {len(X_train)}")
    logger.info(f"Test set size: {len(X_test)}")

    # Train model
    if args.skip_tuning:
        logger.info("Training with default parameters (no tuning)...")
        model = xgb.XGBRegressor(
            objective='reg:squarederror',
            max_depth=5,
            learning_rate=0.1,
            n_estimators=200,
            random_state=42
        )
        model.fit(X_train, y_train)
    else:
        model = train_model(X_train, y_train)

    # Evaluate
    metrics = evaluate_model(model, X_test, y_test, feature_names)

    # Save
    save_model(model, feature_names, args.output)

    logger.info("\nTraining completed successfully!")


if __name__ == '__main__':
    main()
