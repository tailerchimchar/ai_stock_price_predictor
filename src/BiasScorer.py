class BiasScorer:
  def __init__(self, signals):
    self.signals = signals

  def _fmt(self, value: float) -> str:
    return f"{value:.1f}"

  def _has(self, value) -> bool:
    return value is not None and value == value  # filters None and NaN
    
  def score_from_signals(self) -> tuple[float, dict]:
    # Calculates a confidence score based on provided signals and returns the score and reasoning.
    bullish_bias_score = 0.5  # Start with a neutral score
    evidence = {}
    window = self.signals.get('window', 0)
    
    # rsi indicator
    rsi = self.signals.get('rsi')
    if not self._has(rsi):
      evidence['rsi'] = 'RSI unavailable, time period is too short'
    else:
      if rsi < 30:
        bullish_bias_score += 0.2
        evidence['rsi'] = f'RSI {self._fmt(rsi)} oversold'
      elif rsi > 70:
        bullish_bias_score -= 0.2
        evidence['rsi'] = f'RSI {self._fmt(rsi)} overbought'
      else:
        evidence['rsi'] = f'RSI {self._fmt(rsi)} neutral'
      
    # directional indicators (short term) 
    percent_price_change = self.signals.get('percent_price_change')
    if not self._has(percent_price_change):
      price_change = self.signals.get('price_change')
      if self._has(price_change):
        percent_price_change = price_change / 100  # backward compat

    if not self._has(percent_price_change):
      evidence['percent_price_change'] = '5 day return unavailable'
    elif percent_price_change > 0:
      bullish_bias_score += 0.2
      evidence['percent_price_change'] = f'5 day return: {percent_price_change*100:.2f}%'
    elif percent_price_change < 0:
      bullish_bias_score -= 0.2
      evidence['percent_price_change'] = f'5 day return: {percent_price_change*100:.2f}%'
    else:
      evidence['percent_price_change'] = '5 day return unavailable (need >= 6 candles)' if window < 6 else '5 day return: 0.00%'
      
    # moving average indicators (medium term)
    ma5 = self.signals.get('ma_5')
    ma20 = self.signals.get('ma_20')
    if self._has(ma5) and self._has(ma20):
      if ma5 > ma20:
        bullish_bias_score += 0.1
        evidence['ma_short_term'] = f'Ma5 {self._fmt(ma5)} above Ma20 {self._fmt(ma20)}'
      else:
        bullish_bias_score -= 0.1
        evidence['ma_short_term'] = f'Ma5 {self._fmt(ma5)} below Ma20 {self._fmt(ma20)}'
    else:
      evidence['ma_short_term'] = 'MA5/MA20 unavailable'
    
    # moving average indicators (long term)
    ma100 = self.signals.get('ma_100')
    ma200 = self.signals.get('ma_200')
    if self._has(ma100) and self._has(ma200):
      if ma100 > ma200:
        bullish_bias_score += 0.1
        evidence['ma_long_term'] = f'Ma100 {self._fmt(ma100)} above Ma200 {self._fmt(ma200)}'
      else:
        bullish_bias_score -= 0.1
        evidence['ma_long_term'] = f'Ma100 {self._fmt(ma100)} below Ma200 {self._fmt(ma200)}'
    else:
      evidence['ma_long_term'] = 'MA100/MA200 unavailable'
    
    # Most recent price vs sma20 (medium term)
    last_close = self.signals.get('last_close')
    if self._has(last_close) and self._has(ma20):
      if last_close > ma20:
        bullish_bias_score += 0.1
        evidence['close_vs_sma20'] = f'Close {self._fmt(last_close)} above SMA20 {self._fmt(ma20)}'
      else:
        bullish_bias_score -= 0.1
        evidence['close_vs_sma20'] = f'Close {self._fmt(last_close)} below SMA20 {self._fmt(ma20)}'
    else:
      evidence['close_vs_sma20'] = 'Close/SMA20 unavailable'
      
    # todo: add volatility later 
    '''
    # Volatility indicator
    if self.signals['volatility'] < 0.02:
      bullish_bias_score += 0.1
      evidence['volatility'] = f'Volatility {self.signals["volatility"]} low'
    elif self.signals['volatility'] > 0.05:
      bullish_bias_score -= 0.1
      evidence['volatility'] = f'Volatility {self.signals["volatility"]} high'
    '''
    # Normalize score to be between 0 and 1
    
    # ADX indicator (trend strength)
    adx = self.signals.get('adx')
    if adx is None:
      evidence['adx'] = 'ADX not available (adx needs >  28 trading days)'
    else:
      if adx > 25:
        # Strong trend (bullish or bearish depends on price direction)
        if self._has(percent_price_change) and percent_price_change > 0:
          bullish_bias_score += 0.15
          evidence['adx'] = f'ADX {adx} strong uptrend'
        elif self._has(percent_price_change) and percent_price_change < 0:
          bullish_bias_score -= 0.15
          evidence['adx'] = f'ADX {adx} strong downtrend'
        else:
          evidence['adx'] = f'ADX {adx} strong trend (direction unclear)'
      elif adx < 20:
        evidence['adx'] = f'ADX {adx} weak trend'
        # pull bias scare towards 0.5
        bullish_bias_score += (0.5 - bullish_bias_score) * 0.1
        
        
        
    bullish_bias_score = max(0, min(1, bullish_bias_score))
    return bullish_bias_score, evidence
  
  def label_from_score(self, score: float) -> str:
    if score >= 0.7:
      return 'bullish'
    elif score <= 0.30:
      return 'bearish'
    else:
      return 'neutral'
    
  def full_bias_assessment(self) -> tuple[str, float, dict]:
    raw_score, evidence = self.score_from_signals()
    score = round(raw_score, 2)
    label = self.label_from_score(score)
    return (label, score, evidence)
      
      