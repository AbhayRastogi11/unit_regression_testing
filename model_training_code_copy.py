import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

class StandbyForecastingModel:
    def __init__(self, forecast_horizon=7, custom_holidays=None, custom_festivals=None, feature_list=None):
        self.forecast_horizon = forecast_horizon
        self.model = None
        self.scaler = StandardScaler()
        self.feature_names = []
        self.training_metrics = {}
        self.fixed_holidays = custom_holidays or {(1, 26), (8, 15), (10, 2), (12, 25)}
        self.festival_dates = custom_festivals or {(2023, 11, 12), (2023, 3, 8), (2023, 4, 22), (2024, 11, 1), (2024, 3, 25), (2024, 4, 11), (2025, 10, 20), (2025, 3, 14), (2025, 3, 31)}
        self.custom_feature_list = feature_list
    
    def prepare_data(self, df):
        processed_df = df.copy()
        if 'Date' in processed_df.columns:
            processed_df['Date'] = pd.to_datetime(processed_df['Date'], dayfirst=True, errors='coerce')
        if 'Date' in processed_df.columns:
            sort_cols = ['Date']
            optional_sort_cols = ['Station', 'Rank', 'Duty Window Number']
            available_sort_cols = [col for col in optional_sort_cols if col in processed_df.columns]
            if available_sort_cols:
                sort_cols = available_sort_cols + sort_cols
            processed_df = processed_df.sort_values(sort_cols)
        processed_df = self._create_time_features(processed_df)
        processed_df = self._create_lag_features(processed_df)
        processed_df = self._create_rolling_features(processed_df)
        processed_df = self._create_notebook_features(processed_df)
        processed_df = self._handle_missing_values(processed_df)
        cols_to_drop = ['Month_sin', 'Month_cos', 'DayOfWeek_sin', 'DayOfWeek_cos', 'DayOfWeek', 'DayOfMonth', 'WeekOfYear', 'Quarter', 'Activation_Rate_Lag1']
        cols_to_drop_existing = [c for c in cols_to_drop if c in processed_df.columns]
        if cols_to_drop_existing:
            processed_df = processed_df.drop(columns=cols_to_drop_existing)
        return processed_df
    
    def _create_time_features(self, df):
        df = df.copy()
        if 'Date' in df.columns:
            df['Year'] = df['Date'].dt.year
            df['Month Number'] = df['Date'].dt.month
            df['DayOfWeek'] = df['Date'].dt.dayofweek
            df['Weekday Number'] = df['Date'].dt.weekday
            df['DayOfMonth'] = df['Date'].dt.day
            df['WeekOfYear'] = df['Date'].dt.isocalendar().week
            df['Quarter'] = df['Date'].dt.quarter
            df['Month_sin'] = np.sin(2 * np.pi * df['Month Number'] / 12) if 'Month Number' in df.columns else 0
            df['Month_cos'] = np.cos(2 * np.pi * df['Month Number'] / 12) if 'Month Number' in df.columns else 0
            df['DayOfWeek_sin'] = np.sin(2 * np.pi * df['DayOfWeek'] / 7)
            df['DayOfWeek_cos'] = np.cos(2 * np.pi * df['DayOfWeek'] / 7)
            df['is_weekend'] = (df['DayOfWeek'] >= 5).astype(int)
        return df

    def _create_lag_features(self, df):
        return df.copy()

    def _create_rolling_features(self, df):
        df = df.copy()
        required_group_cols = ['Station', 'Rank', 'Duty Window Number']
        if not all(col in df.columns for col in required_group_cols):
            return df
        if 'Activation Rate' in df.columns:
            df['Activation Rate MA7'] = df.groupby(['Station', 'Rank', 'Duty Window Number'])['Activation Rate'].transform(lambda x: x.rolling(7, min_periods=3).mean().shift(1))
            df['Activation Rate Vol7'] = df.groupby(['Station', 'Rank', 'Duty Window Number'])['Activation Rate'].transform(lambda x: x.rolling(7, min_periods=3).std().shift(1))
        if 'Pairing Start Count' in df.columns:
            df['Pairing Start Count MA7'] = df.groupby(['Station', 'Rank', 'Duty Window Number'])['Pairing Start Count'].transform(lambda x: x.rolling(7, min_periods=3).mean().shift(1))
            df['Pairing Start Count Vol7'] = df.groupby(['Station', 'Rank', 'Duty Window Number'])['Pairing Start Count'].transform(lambda x: x.rolling(7, min_periods=3).std().shift(1))
        return df
    
    def _create_notebook_features(self, df):
        df = df.copy()
        required_group_cols = ['Station', 'Rank', 'Duty Window Number']
        if all(col in df.columns for col in required_group_cols):
            if 'Activation Rate MA7' in df.columns and 'Activation Rate' in df.columns:
                df['Activation_Rate_Lag1'] = df.groupby(['Station', 'Rank', 'Duty Window Number'])['Activation Rate'].shift(1)
                df['AR_AboveMean_Flag'] = ((df['Activation Rate MA7'].notna()) & (df['Activation_Rate_Lag1'].notna()) & (df['Activation_Rate_Lag1'] > df['Activation Rate MA7'])).astype(int)
        if 'Date' in df.columns:
            df['is_fixed_holiday'] = df['Date'].apply(lambda d: (d.month, d.day) in self.fixed_holidays if pd.notna(d) else False).astype(int)
            df['is_festival'] = df['Date'].apply(lambda d: (d.year, d.month, d.day) in self.festival_dates if pd.notna(d) else False).astype(int)
            df['is_payday_proximity'] = df['Date'].apply(lambda d: ((d + pd.offsets.MonthEnd(0)).date() == d.date()) or (1 <= d.day <= 7) if pd.notna(d) else False).astype(int)
            df['is_fy_end_proximity'] = df['Date'].apply(lambda d: (d.month == 3 and d.day >= 24) if pd.notna(d) else False).astype(int)
        return df

    def add_holiday(self, month, day):
        self.fixed_holidays.add((month, day))

    def add_festival(self, year, month, day):
        self.festival_dates.add((year, month, day))

    def set_custom_features(self, feature_list):
        self.custom_feature_list = feature_list

    def get_current_config(self):
        return {'holidays': list(self.fixed_holidays), 'festivals': list(self.festival_dates), 'custom_features': self.custom_feature_list, 'forecast_horizon': self.forecast_horizon}
    
    def _handle_missing_values(self, df):
        df = df.copy()
        required_group_cols = ['Station', 'Rank', 'Duty Window Number']
        available_group_cols = [col for col in required_group_cols if col in df.columns]
        if len(available_group_cols) == 0:
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            for col in numeric_cols:
                if col != 'Activation Rate':
                    df[col] = df[col].ffill().bfill().fillna(0)
        else:
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            for col in numeric_cols:
                if col != 'Activation Rate':
                    try:
                        df[col] = df.groupby(available_group_cols)[col].transform(lambda x: x.ffill().bfill().fillna(0))
                    except Exception:
                        df[col] = df[col].ffill().bfill().fillna(0)
        return df

    def _select_features(self, df):
        if self.custom_feature_list is not None:
            exact_features = self.custom_feature_list
        else:
            exact_features = ['AR_AboveMean_Flag', 'Standby Activation Count', 'Activation Rate MA7', 'Pairing Start Count Vol7', 'Activation Rate Vol7', 'IrOps', 'Month Number', 'Multi-Day Pairing Ratio', 'Duty Window Number', 'Season', 'is_fy_end_proximity', 'Pairing Start Count MA7', 'Pairing Start Count', 'INT Pairing Ratio', 'Year', 'is_weekend', 'INT Pairing Count', 'Multi-Day Pairing Count', 'is_festival', 'is_fixed_holiday', 'Weekday Number', 'is_payday_proximity']
        available_features = [f for f in exact_features if f in df.columns]
        return available_features
    
    def train(self, df):
        if 'Activation Rate' not in df.columns:
            raise ValueError("Target column 'Activation Rate' not found in data")
        try:
            processed_df = self.prepare_data(df)
        except KeyError as e:
            raise ValueError(f"Required column missing: {e}") from e
        if 'Date' not in processed_df.columns:
            feature_columns = self._select_features(processed_df)
            if 'Activation Rate' not in processed_df.columns:
                raise ValueError("Target column 'Activation Rate' not found in data")
            X = processed_df[feature_columns]
            y = processed_df['Activation Rate']
            valid_mask = ~y.isna()
            X = X[valid_mask]
            y = y[valid_mask]
            self.feature_names = list(X.columns)
            tscv = TimeSeriesSplit(n_splits=3)
            cv_scores = {'mae': [], 'rmse': [], 'r2': []}
            for fold, (train_idx, val_idx) in enumerate(tscv.split(X)):
                X_train_fold = X.iloc[train_idx]
                X_val_fold = X.iloc[val_idx]
                y_train_fold = y.iloc[train_idx]
                y_val_fold = y.iloc[val_idx]
                fold_scaler = StandardScaler()
                X_train_scaled = fold_scaler.fit_transform(X_train_fold)
                X_val_scaled = fold_scaler.transform(X_val_fold)
                fold_model = RandomForestRegressor(n_estimators=200, max_depth=10, random_state=42, n_jobs=-1)
                fold_model.fit(X_train_scaled, y_train_fold)
                y_pred = fold_model.predict(X_val_scaled)
                cv_scores['mae'].append(mean_absolute_error(y_val_fold, y_pred))
                cv_scores['rmse'].append(np.sqrt(mean_squared_error(y_val_fold, y_pred)))
                cv_scores['r2'].append(r2_score(y_val_fold, y_pred))
            self.scaler = StandardScaler()
            X_scaled = self.scaler.fit_transform(X)
            self.model = RandomForestRegressor(n_estimators=200, max_depth=10, random_state=42, n_jobs=-1)
            self.model.fit(X_scaled, y)
            self.training_metrics = {'cv_mae': np.mean(cv_scores['mae']), 'cv_rmse': np.mean(cv_scores['rmse']), 'cv_r2': np.mean(cv_scores['r2']), 'cv_mae_std': np.std(cv_scores['mae']), 'cv_rmse_std': np.std(cv_scores['rmse']), 'cv_r2_std': np.std(cv_scores['r2']), 'oot_mae': None, 'oot_r2': None}
            return self.training_metrics
        sort_cols = ['Date']
        optional_sort_cols = ['Station', 'Rank', 'Duty Window Number']
        available_sort_cols = [col for col in optional_sort_cols if col in processed_df.columns]
        if available_sort_cols:
            sort_cols = available_sort_cols + sort_cols
        processed_df = processed_df.sort_values(sort_cols)
        unique_dates = sorted(processed_df['Date'].dropna().unique())
        oot_cutoff = unique_dates[int(0.9 * len(unique_dates))]
        oot_mask = processed_df['Date'] >= oot_cutoff
        trainval_data = processed_df[~oot_mask].copy()
        oot_test_data = processed_df[oot_mask].copy()
        feature_columns = self._select_features(trainval_data)
        if 'Activation Rate' not in trainval_data.columns:
            raise ValueError("Target column 'Activation Rate' not found in data")
        X_trainval = trainval_data[feature_columns]
        y_trainval = trainval_data['Activation Rate']
        valid_mask = ~y_trainval.isna()
        X_trainval = X_trainval[valid_mask]
        y_trainval = y_trainval[valid_mask]
        self.feature_names = list(X_trainval.columns)
        tscv = TimeSeriesSplit(n_splits=3)
        cv_scores = {'mae': [], 'rmse': [], 'r2': []}
        for fold, (train_idx, val_idx) in enumerate(tscv.split(X_trainval)):
            X_train_fold = X_trainval.iloc[train_idx]
            X_val_fold = X_trainval.iloc[val_idx]
            y_train_fold = y_trainval.iloc[train_idx]
            y_val_fold = y_trainval.iloc[val_idx]
            fold_scaler = StandardScaler()
            X_train_scaled = fold_scaler.fit_transform(X_train_fold)
            X_val_scaled = fold_scaler.transform(X_val_fold)
            fold_model = RandomForestRegressor(n_estimators=200, max_depth=10, random_state=42, n_jobs=-1)
            fold_model.fit(X_train_scaled, y_train_fold)
            y_pred = fold_model.predict(X_val_scaled)
            cv_scores['mae'].append(mean_absolute_error(y_val_fold, y_pred))
            cv_scores['rmse'].append(np.sqrt(mean_squared_error(y_val_fold, y_pred)))
            cv_scores['r2'].append(r2_score(y_val_fold, y_pred))
        self.scaler = StandardScaler()
        X_trainval_scaled = self.scaler.fit_transform(X_trainval)
        self.model = RandomForestRegressor(n_estimators=200, max_depth=10, random_state=42, n_jobs=-1)
        self.model.fit(X_trainval_scaled, y_trainval)
        oot_mae, oot_r2 = None, None
        if len(oot_test_data) > 0:
            X_oot = oot_test_data[feature_columns]
            y_oot = oot_test_data['Activation Rate']
            oot_valid = ~y_oot.isna()
            if oot_valid.sum() > 0:
                X_oot_scaled = self.scaler.transform(X_oot[oot_valid])
                y_oot_pred = self.model.predict(X_oot_scaled)
                oot_mae = mean_absolute_error(y_oot[oot_valid], y_oot_pred)
                oot_r2 = r2_score(y_oot[oot_valid], y_oot_pred)
        self.training_metrics = {'cv_mae': np.mean(cv_scores['mae']), 'cv_rmse': np.mean(cv_scores['rmse']), 'cv_r2': np.mean(cv_scores['r2']), 'cv_mae_std': np.std(cv_scores['mae']), 'cv_rmse_std': np.std(cv_scores['rmse']), 'cv_r2_std': np.std(cv_scores['r2']), 'oot_mae': oot_mae, 'oot_r2': oot_r2}
        return self.training_metrics
    
    def predict(self, df):
        if self.model is None:
            raise ValueError("Model not trained")
        processed_df = self.prepare_data(df)
        X = processed_df[self.feature_names]
        X_scaled = self.scaler.transform(X)
        predictions = self.model.predict(X_scaled)
        result_df = df.copy()
        result_df['Predicted_Activation_Rate'] = predictions
        return result_df
    
    def generate_forecasts_for_dates(self, df, target_date, days_back=0):
        """
        Generate forecasts for target_date and previous `days_back` days.
        Example: target_date='31/12/2025', days_back=2 -> forecasts for 31/12, 30/12, 29/12
        
        Args:
            df: Training data
            target_date: Target date (string like '31/12/2025' or datetime)
            days_back: Number of previous days to include (0 = only target date)
        
        Returns: 
            DataFrame with forecasts per Station/Rank/Duty Window
        """
        if self.model is None:
            raise ValueError("Model not trained")
        if isinstance(target_date, str):
            # Try DD/MM/YYYY format first (dayfirst=True)
            target_dt = pd.to_datetime(target_date, dayfirst=True, errors='coerce')
            if pd.isna(target_dt):
                # Try other formats
                target_dt = pd.to_datetime(target_date, errors='coerce')
        else:
            target_dt = pd.to_datetime(target_date)
        
        if pd.isna(target_dt):
            raise ValueError(f"Invalid target_date: {target_date}")
        
        # Create list of dates to forecast (target_date going backwards)
        forecast_dates = [target_dt - timedelta(days=i) for i in range(0, days_back+1)]
        processed_df = self.prepare_data(df)
        
        # Check if required columns exist for forecasting
        if 'Date' not in processed_df.columns:
            raise ValueError("Forecasting requires 'Date' column in the dataset")
            
        required_group_cols = ['Station', 'Rank', 'Duty Window Number']
        if not all(col in processed_df.columns for col in required_group_cols):
            raise ValueError(f"Forecasting requires grouping columns: {required_group_cols}")
            
        processed_df = processed_df.sort_values(['Station', 'Rank', 'Duty Window Number', 'Date'])
        
        # Get latest data per group
        group_keys = ['Station', 'Rank', 'Duty Window Number']
        latest_data = processed_df.groupby(group_keys).last().reset_index()
        
        forecasts = []
        
        for _, base_row in latest_data.iterrows():
            # Get historical data for this group (for lag/rolling features)
            mask = ((processed_df['Station'] == base_row['Station']) & 
                   (processed_df['Rank'] == base_row['Rank']) & 
                   (processed_df['Duty Window Number'] == base_row['Duty Window Number']))
            group_history = processed_df[mask].sort_values('Date')
            
            for forecast_date in forecast_dates:
                # Create forecast row based on latest data
                forecast_row = base_row.copy()
                forecast_row['Date'] = forecast_date
                
                # Update time-based features for forecast date
                forecast_row = self._update_time_features(forecast_row, forecast_date)
                
                # Update rolling features based on history up to (forecast_date - 1)
                history_cutoff = forecast_date - timedelta(days=1)
                relevant_history = group_history[group_history['Date'] <= history_cutoff]
                
                # Update rolling averages from historical data
                if len(relevant_history) > 0 and 'Activation Rate' in relevant_history.columns:
                    recent_ar = relevant_history['Activation Rate'].dropna().tail(7)
                    forecast_row['Activation Rate MA7'] = recent_ar.mean() if len(recent_ar) > 0 else forecast_row['Activation Rate MA7']
                    forecast_row['Activation Rate Vol7'] = recent_ar.std() if len(recent_ar) > 1 else forecast_row['Activation Rate Vol7']
                    
                    # Update AR_AboveMean_Flag based on recent MA
                    if not pd.isna(forecast_row['Activation Rate MA7']):
                        # Use last known activation rate for comparison
                        last_ar = recent_ar.iloc[-1] if len(recent_ar) > 0 else 0
                        forecast_row['AR_AboveMean_Flag'] = 1 if last_ar > forecast_row['Activation Rate MA7'] else 0
                
                if len(relevant_history) > 0 and 'Pairing Start Count' in relevant_history.columns:
                    recent_psc = relevant_history['Pairing Start Count'].dropna().tail(7)
                    forecast_row['Pairing Start Count MA7'] = recent_psc.mean() if len(recent_psc) > 0 else forecast_row['Pairing Start Count MA7']
                    forecast_row['Pairing Start Count Vol7'] = recent_psc.std() if len(recent_psc) > 1 else forecast_row['Pairing Start Count Vol7']
                
                # Make prediction
                try:
                    X_forecast = pd.DataFrame([forecast_row])[self.feature_names]
                    X_forecast_scaled = self.scaler.transform(X_forecast)
                    prediction = self.model.predict(X_forecast_scaled)[0]
                    
                    forecasts.append({
                        'Date': forecast_date.strftime('%d/%m/%Y'),
                        'Station': base_row['Station'],
                        'Rank': base_row['Rank'], 
                        'Duty_Window_Number': base_row['Duty Window Number'],
                        'Forecasted_Activation_Rate': round(prediction, 4),
                        'Days_Back': (target_dt - forecast_date).days
                    })
                    
                except Exception as e:
                    continue
        
        result_df = pd.DataFrame(forecasts)
        result_df = result_df.sort_values(['Station', 'Rank', 'Duty_Window_Number', 'Days_Back'])
        return result_df
    
    def generate_forecasts(self, df):
        if self.model is None:
            raise ValueError("Model not trained")
        processed_df = self.prepare_data(df)
        if 'Date' not in processed_df.columns:
            raise ValueError("Forecasting requires 'Date' column")
        required_group_cols = ['Station', 'Rank', 'Duty Window Number']
        if not all(col in processed_df.columns for col in required_group_cols):
            raise ValueError(f"Forecasting requires columns: {required_group_cols}")
        latest_data = processed_df.groupby(['Station', 'Rank', 'Duty Window Number']).last().reset_index()
        if len(latest_data) == 0:
            return pd.DataFrame()
        forecasts = []
        for _, row in latest_data.iterrows():
            last_date = row['Date']
            forecast_dates = [last_date + timedelta(days=i+1) for i in range(self.forecast_horizon)]
            for i, forecast_date in enumerate(forecast_dates):
                forecast_row = row.copy()
                forecast_row['Date'] = forecast_date
                forecast_row = self._update_time_features(forecast_row, forecast_date)
                forecast_row = self._create_forecast_features(forecast_row, row)
                try:
                    missing_features = [f for f in self.feature_names if f not in forecast_row or pd.isna(forecast_row[f])]
                    if missing_features:
                        for feature in missing_features:
                            if feature in ['AR_AboveMean_Flag', 'is_weekend', 'is_festival', 'is_fixed_holiday', 'is_payday_proximity', 'is_fy_end_proximity']:
                                forecast_row[feature] = 0
                            elif feature in ['Season']:
                                forecast_row[feature] = 1 if forecast_date.month in [11, 12, 1, 2, 3] else 0
                            else:
                                forecast_row[feature] = 0
                    for feature in self.feature_names:
                        if feature in forecast_row:
                            try:
                                if callable(forecast_row[feature]):
                                    forecast_row[feature] = 0
                                else:
                                    forecast_row[feature] = float(forecast_row[feature])
                            except (ValueError, TypeError):
                                forecast_row[feature] = 0
                    X_forecast = pd.DataFrame([forecast_row])[self.feature_names]
                    if X_forecast.isna().any().any():
                        X_forecast = X_forecast.fillna(0)
                    X_forecast_scaled = self.scaler.transform(X_forecast)
                    prediction = self.model.predict(X_forecast_scaled)[0]
                    forecast_record = {'Date': forecast_date, 'Station': row['Station'], 'Rank': row['Rank'], 'Duty_Window_Number': row['Duty Window Number'], 'Forecasted_Activation_Rate': prediction, 'Forecast_Horizon': i + 1}
                    forecasts.append(forecast_record)
                except Exception as e:
                    continue
        return pd.DataFrame(forecasts)
    
    def _update_time_features(self, row, forecast_date):
        row['Year'] = forecast_date.year
        row['Month Number'] = forecast_date.month
        row['DayOfWeek'] = forecast_date.dayofweek
        row['DayOfMonth'] = forecast_date.day
        row['WeekOfYear'] = forecast_date.isocalendar().week
        row['Quarter'] = forecast_date.quarter
        row['Weekday Number'] = forecast_date.weekday()
        row['Month_sin'] = np.sin(2 * np.pi * forecast_date.month / 12)
        row['Month_cos'] = np.cos(2 * np.pi * forecast_date.month / 12)
        row['DayOfWeek_sin'] = np.sin(2 * np.pi * forecast_date.dayofweek / 7)
        row['DayOfWeek_cos'] = np.cos(2 * np.pi * forecast_date.dayofweek / 7)
        row['is_weekend'] = 1 if forecast_date.dayofweek >= 5 else 0
        row['Season'] = 1 if forecast_date.month in [11, 12, 1, 2, 3] else 0
        row['is_fixed_holiday'] = 1 if (forecast_date.month, forecast_date.day) in self.fixed_holidays else 0
        row['is_festival'] = 1 if (forecast_date.year, forecast_date.month, forecast_date.day) in self.festival_dates else 0
        row['is_payday_proximity'] = 1 if ((forecast_date + pd.offsets.MonthEnd(0)).date() == forecast_date.date()) or (1 <= forecast_date.day <= 7) else 0
        row['is_fy_end_proximity'] = 1 if (forecast_date.month == 3 and forecast_date.day >= 24) else 0
        return row
    
    def _create_forecast_features(self, forecast_row, original_row):
        numerical_features = ['Standby Activation Count', 'Pairing Start Count', 'Multi-Day Pairing Count', 'INT Pairing Count', 'Multi-Day Pairing Ratio', 'INT Pairing Ratio']
        for feature in numerical_features:
            if feature in original_row:
                try:
                    forecast_row[feature] = float(original_row[feature]) if pd.notna(original_row[feature]) else 0.0
                except (ValueError, TypeError):
                    forecast_row[feature] = 0.0
        rolling_features = ['Activation Rate MA7', 'Activation Rate Vol7', 'Pairing Start Count MA7', 'Pairing Start Count Vol7']
        for feature in rolling_features:
            if feature in original_row:
                try:
                    forecast_row[feature] = float(original_row[feature]) if pd.notna(original_row[feature]) else 0.0
                except (ValueError, TypeError):
                    forecast_row[feature] = 0.0
            else:
                forecast_row[feature] = 0.0
        if 'AR_AboveMean_Flag' in original_row:
            try:
                forecast_row['AR_AboveMean_Flag'] = int(original_row['AR_AboveMean_Flag']) if pd.notna(original_row['AR_AboveMean_Flag']) else 0
            except (ValueError, TypeError):
                forecast_row['AR_AboveMean_Flag'] = 0
        else:
            ar_ma7 = forecast_row.get('Activation Rate MA7', 0)
            last_ar = original_row.get('Activation Rate', 0) if 'Activation Rate' in original_row else 0
            try:
                if ar_ma7 > 0 and last_ar > ar_ma7:
                    forecast_row['AR_AboveMean_Flag'] = 1
                else:
                    forecast_row['AR_AboveMean_Flag'] = 0
            except:
                forecast_row['AR_AboveMean_Flag'] = 0
        default_features = {'Standby Activation Count': 0.0, 'Pairing Start Count': 0.0, 'Multi-Day Pairing Count': 0.0, 'INT Pairing Count': 0.0, 'Multi-Day Pairing Ratio': 0.0, 'INT Pairing Ratio': 0.0, 'Activation Rate MA7': 0.0, 'Activation Rate Vol7': 0.0, 'Pairing Start Count MA7': 0.0, 'Pairing Start Count Vol7': 0.0, 'AR_AboveMean_Flag': 0}
        for feature, default_value in default_features.items():
            if feature not in forecast_row or pd.isna(forecast_row[feature]):
                forecast_row[feature] = default_value
        return forecast_row
    
    def get_feature_importance(self):
        if self.model is None:
            return {}
        importance_dict = {}
        feature_importance = self.model.feature_importances_
        for i, feature in enumerate(self.feature_names):
            importance_dict[feature] = float(feature_importance[i])
        return dict(sorted(importance_dict.items(), key=lambda x: x[1], reverse=True))
    
    def predict_from_csv(self, csv_path, output_path=None):
        if self.model is None:
            raise ValueError("Model not trained")
        df = pd.read_csv(csv_path)
        if 'Date' in df.columns:
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')  # US format MM/DD/YYYY
        missing_features = [f for f in self.feature_names if f not in df.columns]
        if missing_features:
            processed_df = self.prepare_data(df)
            still_missing = [f for f in self.feature_names if f not in processed_df.columns]
            if still_missing:
                for feature in still_missing:
                    processed_df[feature] = 0
            df = processed_df
        X = df[self.feature_names]
        X_scaled = self.scaler.transform(X)
        predictions = self.model.predict(X_scaled)
        result_df = df.copy()
        result_df['Predicted_Activation_Rate'] = predictions
        result_df['Prediction_Timestamp'] = pd.Timestamp.now()
        if output_path:
            result_df.to_csv(output_path, index=False)
        return result_df
    
    def predict_row_by_row(self, csv_path, output_path=None):
        """Process CSV line by line and generate predictions (streaming mode)"""
        if self.model is None:
            raise ValueError("Model not trained")
        df = pd.read_csv(csv_path)
        if 'Date' in df.columns:
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')  # US format MM/DD/YYYY
        try:
            processed_df = self.prepare_data(df)
            df = processed_df
        except Exception as e:
            pass
        results = []
        
        for idx, row in df.iterrows():
            try:
                # Check if required features exist
                row_features = {}
                for feature in self.feature_names:
                    if feature in row:
                        row_features[feature] = row[feature]
                    else:
                        row_features[feature] = 0  # Default value for missing features
                
                # Make prediction
                X = pd.DataFrame([row_features])
                X_scaled = self.scaler.transform(X)
                prediction = float(self.model.predict(X_scaled)[0])
                
                # Store result
                result = {
                    'Row_Index': idx,
                    'Date': row.get('Date', 'Unknown'),
                    'Station': row.get('Station', 'Unknown'),
                    'Rank': row.get('Rank', 'Unknown'), 
                    'Duty_Window_Number': row.get('Duty Window Number', 'Unknown'),
                    'Predicted_Activation_Rate': round(prediction, 4),
                    'Processing_Timestamp': pd.Timestamp.now()
                }
                results.append(result)
            except Exception as e:
                results.append({
                    'Row_Index': idx,
                    'Date': row.get('Date', 'Unknown'),
                    'Station': row.get('Station', 'Unknown'),
                    'Rank': row.get('Rank', 'Unknown'),
                    'Duty_Window_Number': row.get('Duty Window Number', 'Unknown'),
                    'Predicted_Activation_Rate': np.nan,
                    'Processing_Timestamp': pd.Timestamp.now(),
                    'Error': str(e)
                })
        
        result_df = pd.DataFrame(results)
        if output_path:
            result_df.to_csv(output_path, index=False)
        return result_df


# Example usage function
def main():
    csv_path = r"C:\Users\Abhay.x.Rastogi1\Downloads\ml_feature_engineering\DEL_SBY_12month_data_new_logic.csv"
    df = pd.read_csv(csv_path)
    
    print("DYNAMIC CONFIGURATION EXAMPLES:")
    print("="*50)
    
    ## Method 1: Configure during initialization
    print("\n1. Method 1: Configure during initialization")
    model1 = StandbyForecastingModel(
        custom_holidays={(1, 1), (12, 25), (8, 15)},  # New Year, Christmas, Independence Day
        custom_festivals={(2025, 3, 15), (2025, 10, 20)},  # Custom festival dates
        forecast_horizon=7  # 7-day forecasts
    )
    print("   Model created with custom holidays and festivals")
    
    ## Method 2: Add configuration after creating model
    print("\n2. Method 2: Add configuration after creating model")
    model2 = StandbyForecastingModel()
    
    # Add holidays dynamically
    model2.add_holiday(1, 26)   # Republic Day 
    model2.add_holiday(10, 2)   # Gandhi Jayanti
    model2.add_holiday(12, 31)  # New Year Eve
    
    # Add festivals dynamically
    model2.add_festival(2025, 4, 14)  # Baisakhi
    model2.add_festival(2025, 11, 5)  # Diwali
    
    # Set custom features (if you want different from notebook)
    custom_features = ['AR_AboveMean_Flag', 'Activation Rate MA7', 'is_weekend']
    model2.set_custom_features(custom_features)
    
    # Check current configuration
    config = model2.get_current_config()
    print(f"   Current Configuration:")
    print(f"   Holidays: {config['holidays']}")
    print(f"   Festivals: {config['festivals']}")
    print(f"   Feature count: {len(config['custom_features']) if config['custom_features'] else 'Using default (22 features)'}")
    
    ## Different seasonal model configurations
    print("\n3. Configuration Examples for Different Scenarios:")
    
    # Festival season model (Diwali period)
    festival_model = StandbyForecastingModel(
        custom_holidays={(10, 2), (12, 25)},
        custom_festivals={(2025, 11, 3), (2025, 11, 4), (2025, 11, 5)},  # Diwali week
        forecast_horizon=3
    )
    print(f"   Festival model: {len(festival_model.get_current_config()['festivals'])} festivals, 3-day horizon")
    
    # Summer season model (with Independence Day)
    summer_model = StandbyForecastingModel(
        custom_holidays={(8, 15), (1, 26)},
        custom_festivals={(2025, 8, 19)},  # Raksha Bandhan
        forecast_horizon=10
    )
    print(f"   Summer model: Independence Day + Raksha Bandhan, 10-day horizon")
    
    # Minimal configuration (just major holidays)
    minimal_model = StandbyForecastingModel(
        custom_holidays={(1, 1), (8, 15), (10, 2), (12, 25)},
        forecast_horizon=5
    )
    print(f"   Minimal model: 4 major holidays, 5-day horizon")
    
    print("\n" + "="*50)
    print("TRAINING AND FORECASTING:")
    print("="*50)
    
    # Use default model for training and forecasting
    model = StandbyForecastingModel(forecast_horizon=7)
    
    # Train the model
    metrics = model.train(df)
    print("\nTraining Metrics:")
    for metric, value in metrics.items():
        if value is not None:
            print(f"  {metric}: {value:.4f}")
        else:
            print(f"  {metric}: N/A")
    
    # Make predictions on existing data
    predictions = model.predict(df.tail(100))  # Predict on last 100 rows
    print(f"\nPredictions made on {len(predictions)} samples")
    print(f"Mean predicted activation rate: {predictions['Predicted_Activation_Rate'].mean():.4f}")
    
    # Generate forecasts
    forecasts = model.generate_forecasts(df)
    print(f"\nGenerated {len(forecasts)} forecast points")
    
    if len(forecasts) > 0:
        print(f"Forecast date range: {forecasts['Date'].min()} to {forecasts['Date'].max()}")
    else:
        print("⚠️  No forecasts generated. Check data and model requirements.")
    
    # 🎯 NEW: Date-specific forecasting (example user requested)
    print(f"\n🎯 DATE-SPECIFIC FORECASTING DEMO:")
    try:
        date_forecasts = model.generate_forecasts_for_dates(df, '31/12/2025', days_back=2)
        print(f"Requested: 31/12/2025 + last 2 days (31, 30, 29 Dec)")
        print(f"Generated forecasts for {len(date_forecasts)} combinations")
        
        # Show sample results
        if len(date_forecasts) > 0:
            print(f"\nSample results:")
            sample = date_forecasts.head(6)
            for _, row in sample.iterrows():
                print(f"  📅 {row['Date']} | {row['Station']}-{row['Rank']}-Window{row['Duty_Window_Number']} | Rate: {row['Forecasted_Activation_Rate']:.4f}")
        else:
            print("⚠️ No date-specific forecasts generated.")
    except Exception as e:
        print(f"⚠️ Date-specific forecasting failed: {e}")
    # Show feature importance
    try:
        importance = model.get_feature_importance()
        if importance:
            print("\nTop 10 Important Features:")
            for i, (feature, imp) in enumerate(list(importance.items())[:10]):
                print(f"  {i+1:2d}. {feature:<25}: {imp:.4f}")
        else:
            print("\n⚠️ No feature importance available.")
    except Exception as e:
        print(f"\n⚠️ Feature importance extraction failed: {e}")
    
    print("\n✅ Dynamic configuration examples complete!")
    
    # 🎯 NEW: Dynamic CSV Prediction Demo
    print("\n" + "="*50)
    print("🎯 DYNAMIC CSV PREDICTION DEMO:")
    print("="*50)
    
    # Check if the updated prediction file exists
    new_data_file = r"C:\Users\Abhay.x.Rastogi1\Downloads\ml_feature_engineering\DEL_SBY_12month_data_new_logic_UPDATED_feb_prediction.csv"
    if pd.io.common.file_exists(new_data_file):
        print(f"\n📂 Found new data file: {new_data_file}")
        
        # Method 1: Batch prediction (Latest 3 dates only)
        print("\n1️⃣ Batch Prediction (Latest 3 dates only):")
        
        # Load and filter to latest 3 dates
        temp_df = pd.read_csv(new_data_file)
        if 'Date' in temp_df.columns:
            temp_df['Date'] = pd.to_datetime(temp_df['Date'], errors='coerce')  # US format MM/DD/YYYY
            unique_dates = sorted(temp_df['Date'].dropna().unique())
            latest_3_dates = unique_dates[-3:] if len(unique_dates) >= 3 else unique_dates
            filtered_df = temp_df[temp_df['Date'].isin(latest_3_dates)]
            
            # Save filtered data temporarily
            filtered_file = "temp_latest_3_dates.csv" 
            filtered_df.to_csv(filtered_file, index=False)
            
            batch_results = model.predict_from_csv(
                csv_path=filtered_file,
                output_path="batch_predictions.csv"
            )
            print(f"   ✅ Batch processing: {len(batch_results)} predictions on latest 3 dates")
            print(f"   📅 Date range: {min(latest_3_dates).strftime('%d/%m/%Y')} to {max(latest_3_dates).strftime('%d/%m/%Y')}")
            print(f"   📊 Mean predicted rate: {batch_results['Predicted_Activation_Rate'].mean():.4f}")
        else:
            # Fallback if no Date column
            batch_results = model.predict_from_csv(
                csv_path=new_data_file,
                output_path="batch_predictions.csv"
            )
            print(f"   ✅ Batch processing: {len(batch_results)} predictions (no date filtering)")
            print(f"   📊 Mean predicted rate: {batch_results['Predicted_Activation_Rate'].mean():.4f}")
        
        # Method 2: Row-by-row prediction  
        print("\n2️⃣ Row-by-Row Prediction:")
        streaming_results = model.predict_row_by_row(
            csv_path=new_data_file,
            output_path="streaming_predictions.csv"
        )
        print(f"   ✅ Streaming processing: {len(streaming_results)} predictions")
        
        # Show sample results
        print("\n📋 Sample Batch Results:")
        sample = batch_results[['Date', 'Station', 'Rank', 'Duty Window Number', 'Predicted_Activation_Rate']].head()
        for _, row in sample.iterrows():
            print(f"   📅 {row['Date'].strftime('%d/%m/%Y') if pd.notna(row['Date']) else 'N/A'} | {row['Station']}-{row['Rank']}-Window{row['Duty Window Number']} | Rate: {row['Predicted_Activation_Rate']:.4f}")
        
        print("\n💾 Output Files Created:")
        print("   📄 batch_predictions.csv - Complete predictions with all original columns")
        print("   📄 streaming_predictions.csv - Row-by-row processing results")
        
    else:
        print(f"\n⚠️  File '{new_data_file}' not found. Place your CSV file in the same directory.")
        print("\n📋 To use dynamic CSV prediction:")
        print("   1. Place your CSV file (with features) in the project directory")
        print("   2. Use: model.predict_from_csv('your_file.csv', 'output.csv')")
        print("   3. Or: model.predict_row_by_row('your_file.csv', 'output.csv')")
    
    return model, predictions, forecasts


if __name__ == "__main__":
    model, predictions, forecasts = main()