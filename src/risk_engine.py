"""
Cross-Asset Macro Risk Simulation & Econometric Factor Attribution Engine
Author: Quantitative Finance Research Framework
Description: Multi-variable OLS regression engine with Newey-West HAC adjustments
             simulating systematic risk transmission under macro regime shocks.
"""

import os
import numpy as np
import pandas as pd
import yfinance as yf
import statsmodels.api as sm
from statsmodels.stats.sandwich_covariance import cov_hac

def fetch_and_prepare_data():
    print("[*] Downloading financial time-series data via API...")
    # Tickers: Tech, Financials, Long Bonds, 10Y Yield, Dollar Index
    tickers = {
        'XLK': 'XLK', 'XLF': 'XLF', 'TLT': 'TLT',
        'TNX': '^TNX', 'DXY': 'DX-Y.NYB'
    }
    
    # Fetch 3 years of daily trailing historical data
    data = yf.download(list(tickers.values()), period="3y", interval="1d", auto_adjust=False)['Adj Close']
    data = data.rename(columns={v: k for k, v in tickers.items()}).dropna()
    
    # Compute continuous log returns for assets to ensure structural variance scaling
    returns_df = pd.DataFrame()
    for asset in ['XLK', 'XLF', 'TLT']:
        returns_df[asset] = np.log(data[asset] / data[asset].shift(1))
        
    # Capture macro factor shifts as absolute daily differences (basis points/index units)
    returns_df['dTNX'] = data['TNX'].diff() / 100.0  # Convert to absolute percentage scale
    returns_df['dDXY'] = data['DXY'].diff()
    
    return returns_df.dropna()

def run_econometric_engine(df):
    print("[*] Running multi-variable OLS engine with Newey-West HAC adjustments...")
    assets = ['XLK', 'XLF', 'TLT']
    X = df[['dTNX', 'dDXY']]
    X = sm.add_constant(X)  # Isolate intercept (Alpha)
    
    results = {}
    
    for asset in assets:
        y = df[asset]
        model = sm.OLS(y, X).fit()
        
        # Apply Newey-West Heteroskedasticity and Autocorrelation Consistent standard errors (5 lags)
        nw_cov = cov_hac(model, nlags=5)
        nw_stderr = np.sqrt(np.diag(nw_cov))
        t_stats = model.params / nw_stderr
        
        results[asset] = {
            'alpha': model.params['const'],
            'beta_tnx': model.params['dTNX'],
            'beta_dxy': model.params['dDXY'],
            'adj_r2': model.rsquared_adj,
            't_stat_tnx': t_stats['dTNX'],
            't_stat_dxy': t_stats['dDXY']
        }
        
        print(f"\n[+] Empirical Factor Matrix: Matrix Output for {asset}")
        print(f"    Alpha (Intercept): {results[asset]['alpha']:.6f}")
        print(f"    Beta (Yield Curve Shift): {results[asset]['beta_tnx']:.4f} (t-stat: {results[asset]['t_stat_tnx']:.2f})")
        print(f"    Beta (USD Shift): {results[asset]['beta_dxy']:.4f} (t-stat: {results[asset]['t_stat_dxy']:.2f})")
        print(f"    Adjusted R-squared: {results[asset]['adj_r2']*100:.2f}%")
        
    return results

def simulate_regime_shock(matrix):
    print("\n[*] Simulating Shock: +75bps Yield Spike & +4.0 Unit DXY Surge...")
    # Define macro coordinate vector
    delta_tnx = 0.75 / 100.0  # 75 basis points
    delta_dxy = 4.0
    
    portfolio_weights = {'XLK': 0.40, 'XLF': 0.30, 'TLT': 0.30}
    net_pure_shock_return = 0.0
    net_integrated_return = 0.0
    
    print("\n--- Out-of-Sample Vector Projection ---")
    for asset, weight in portfolio_weights.items():
        betas = matrix[asset]
        
        # Scenario A: Pure macro factor shock transmission (Beta-only)
        pure_shock = (betas['beta_tnx'] * delta_tnx) + (betas['beta_dxy'] * delta_dxy)
        # Scenario B: Fully integrated multi-factor shift (Alpha baseline + Beta shocks)
        integrated_shock = betas['alpha'] + pure_shock
        
        net_pure_shock_return += pure_shock * weight
        net_integrated_return += integrated_shock * weight
        
        print(f"{asset} Alloc: {weight*100}% | Pure Factor Return: {pure_shock*100:.2f}% | Integrated Return: {integrated_shock*100:.2f}%")
        
    print("\n--- Aggregate Allocation Impact Analysis ---")
    print(f"Target Pure Portfolio Downside: {net_pure_shock_return*100:.2f}%")
    print(f"Target Fully Integrated Net Drawdown: {net_integrated_return*100:.2f}%")

if __name__ == "__main__":
    df = fetch_and_prepare_data()
    factor_matrix = run_econometric_engine(df)
    simulate_regime_shock(factor_matrix)
