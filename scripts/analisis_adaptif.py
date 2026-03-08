# scripts/analisis_adaptif.py
import logging
import sqlite3
import pandas as pd
import ta
from scripts.ai_validator_v2 import validate_signal_with_ai
from scripts.market_regime import detect_regime
from scripts.strategy_selector import get_signal
from scripts.notifier import kirim_notifikasi_sinkron
from scripts.signal_scorer import SignalScorer
from scripts.trade_executor import TradeExecutor
from scripts.watchlist import load_watchlist
from scripts.data_utils import ambil_data_dari_db, tambah_indikator
import scripts.fundamental as f
from scripts.cluster_tracker import get_cluster_sentiment_for_symbol
from scripts.ml_predictor_advanced import get_predictor
from scripts.regime_classifier import get_regime_classifier
from scripts.multi_agent_selector import get_multi_agent

# Inisialisasi executor
executor = TradeExecutor(account_balance=100_000_000, risk_per_trade=1.5)

logger = logging.getLogger(__name__)

def sinyal_dasar(df):
    """Menghasilkan sinyal dasar berdasarkan RSI dan EMA."""
    df = df.copy()
    df['Sinyal'] = 0
    beli = (df['RSI'] < 30) & (df['Close'] > df['EMA20'])
    jual = (df['RSI'] > 70) & (df['Close'] < df['EMA20'])
    df.loc[beli, 'Sinyal'] = 1
    df.loc[jual, 'Sinyal'] = -1
    return df

def analisis_saham_adaptif(symbol):
    logger.info(f"analisis_saham_adaptif({symbol}) dipanggil")
    logger.info(f"\n{'='*60}")
    logger.info(f" ANALISIS ADAPTIF {symbol} ")
    logger.info('='*60)

    df = ambil_data_dari_db(symbol)
    if df is None or len(df) < 30:
        logger.error(f"❌ Data tidak cukup untuk {symbol}")
        return

    df = tambah_indikator(df)

    latest = df.iloc[-1]
    logger.info(f"\n📈 DATA TERKINI ({latest['Date'].strftime('%Y-%m-%d')}):")
    logger.info(f"Harga: {latest['Close']:.2f} | RSI: {latest['RSI']:.2f} | ADX: {latest['ADX']:.2f}")
    logger.info(f"EMA20: {latest['EMA20']:.2f} | EMA50: {latest['EMA50']:.2f} | EMA200: {latest['EMA200']:.2f}")

    # Deteksi regime dengan ADX (dari market_regime)
    regime_adx = detect_regime(df)
    logger.info(f"\n🎯 Regime pasar (ADX): {regime_adx}")

    # Deteksi regime dengan GMM
    classifier = get_regime_classifier()
    gmm_regime = classifier.predict_regime(df)
    logger.info(f"🎯 GMM Regime: {gmm_regime}")
    logger.info(f"   {classifier.get_regime_description(gmm_regime)}")

    # Sinyal adaptif dari strategi utama
    sig, reason, strategy = get_signal(symbol, df)
    if sig == 1:
        sinyal_text = "BELI"
    elif sig == -1:
        sinyal_text = "JUAL"
    else:
        sinyal_text = "TIDAK ADA"

    logger.info(f"Strategi: {strategy}")
    logger.info(f"Sinyal adaptif: {sinyal_text} — {reason}")

    # Sinyal dasar
    df_dasar = sinyal_dasar(df)
    sig_dasar = df_dasar.iloc[-1]['Sinyal']
    if sig_dasar == 1:
        logger.info(f"Sinyal dasar: BELI (RSI<30 & harga>EMA20)")
    elif sig_dasar == -1:
        logger.info(f"Sinyal dasar: JUAL (RSI>70 & harga<EMA20)")
    else:
        logger.info(f"Sinyal dasar: TIDAK ADA")

    # AI Validator
    logger.info("\n🤖 Meminta opini AI...")
    df_10 = df.iloc[-10:]
    ai_result = validate_signal_with_ai(symbol, df_10)
    if ai_result:
        logger.info(f"AI: {ai_result.get('recommendation')} (conf {ai_result.get('confidence')}%)")
        logger.info(f"    {ai_result.get('reason')}")
    else:
        logger.error("AI gagal.")

    # Data fundamental
    fundamental = f.enrich_with_fundamental(symbol, df)
    if fundamental:
        fund_score, fund_reason = f.fundamental_score(fundamental)
        logger.info(f"\n📊 *Data Fundamental:*")
        logger.info(f"  PER: {fundamental.get('per', 0):.1f}x | PBV: {fundamental.get('pbv', 0):.2f}x")
        logger.info(f"  ROE: {fundamental.get('roe', 0):.1f}% | DER: {fundamental.get('der', 0):.2f}x")
        logger.info(f"  Dividen: {fundamental.get('dividend_yield', 0):.1f}%")
        logger.info(f"  Skor Fundamental: {fund_score} — {fund_reason}")
    else:
        fund_score = 50
        fund_reason = "Data fundamental tidak tersedia (skor netral)"

    # Sentimen klaster
    cluster_sent = get_cluster_sentiment_for_symbol(symbol)
    logger.info(f"\n📊 Sentimen Klaster: {cluster_sent:.2f} (dari -1 s/d 1)")

    # Prediksi ML
    ml_direction = None
    ml_confidence = 0
    predictor = get_predictor(symbol, target_days=5)
    if predictor:
        ml_direction, ml_confidence = predictor.predict()
        dir_text = "NAIK" if ml_direction == 1 else "TURUN"
        logger.info(f"🤖 ML Prediction (tuned): {dir_text} (conf {ml_confidence:.1f}%)")
    else:
        logger.warning("⚠️ Model ML tidak tersedia untuk saham ini")

    # ========== AGENT-ANALYST FRAMEWORK ==========
    logger.info("\n📊 *Agent-Analyst Framework*")
    multi_agent = get_multi_agent()
    multi_agent.update_regime(gmm_regime)
    agent_signal, agent_confidence, agent_details = multi_agent.get_consensus_signal(symbol, df)

    if agent_signal != 0:
        agent_dir = "BELI" if agent_signal == 1 else "JUAL"
        logger.info(f"\n🤖 Multi-Agent Consensus: {agent_dir} (conf {agent_confidence:.1f}%)")
        for detail in agent_details:
            dir_text = "BELI" if detail['prob_up'] > detail['prob_down'] else "JUAL"
            logger.info(f"   - {detail['name']}: {dir_text} (conf {detail['confidence']:.1f}%, reason: {detail['reason'][:50]})")
    else:
        logger.info("\n🤖 Multi-Agent Consensus: TIDAK ADA SINYAL")

    # ========== WEIGHTED SIGNAL SCORE ==========
    scorer = SignalScorer()
    data_for_score = {
        'rsi': latest['RSI'],
        'macd': latest['MACD'],
        'macd_signal': latest['MACD_signal'],
        'macd_hist': latest['MACD_diff'],
        'price': latest['Close'],
        'ema20': latest['EMA20'],
        'ema50': latest['EMA50'],
        'volume': latest['Volume'],
        'avg_volume': latest['Volume_MA20'],
        'adx': latest['ADX'],
        'di_plus': latest['DI_plus'],
        'di_minus': latest['DI_minus']
    }
    score = scorer.calculate_score(
        data_for_score,
        ai_result,
        fundamental_score=fund_score,
        cluster_sentiment=cluster_sent,
        ml_prediction=ml_direction,
        ml_confidence=ml_confidence,
        target_direction='buy'
    )
    logger.info(f"\n📊 Weighted Signal Score: {score}/100")

    # ========== KESIMPULAN ==========
    logger.info("\n📊 KESIMPULAN:")
    if sig != 0 and ai_result and ai_result.get('recommendation') in ['buy', 'sell']:
        if (sig == 1 and ai_result['recommendation'] == 'buy') or (sig == -1 and ai_result['recommendation'] == 'sell'):
            logger.info("✅ KONFIRMASI: Sinyal adaptif dan AI searah.")
        else:
            logger.warning("⚠️ BERTENTANGAN: Sinyal adaptif dan AI berbeda.")
    else:
        logger.info("ℹ️ NETRAL / TIDAK ADA SINYAL KUAT.")
    logger.info('='*60)

    # ========== EKSEKUSI TRADING ==========
    if sig != 0 and score > 40:
        allowed, msg = executor.check_pre_trade(symbol, df, sig)
        if allowed:
            executor.execute_entry(symbol, df, sig, reason, strategy, regime_adx, agent_name='Konsensus')
            notif = f"🚀 *EKSEKUSI {sinyal_text}* untuk {symbol}\n"
            notif += f"Harga: {latest['Close']:.2f}\n"
            notif += f"Alasan: {reason}\n"
            notif += f"Skor: {score}/100"
            kirim_notifikasi_sinkron(notif)
        else:
            logger.warning(f"⏸️ Trading diblokir: {msg}")
    elif sig != 0:
        logger.info(f"⏸️ Sinyal ada tetapi skor {score} < 40, tidak dieksekusi.")
    # AI Watchdog
    elif sig == 0 and ai_result and ai_result.get('confidence', 0) >= 80 and score > 70:
        watchlist = load_watchlist()['symbols']
        is_watched = symbol in watchlist
        is_volatile = latest['ADX'] > 30
        if is_watched or is_volatile:
            allowed, msg = executor.check_pre_trade(symbol, df, None)
            if allowed:
                ai_signal = 1 if ai_result['recommendation'] == 'buy' else -1
                executor.execute_entry(symbol, df, ai_signal, f"AI: {ai_result['reason'][:50]}", 'ai_only', regime_adx, agent_name='AI_Watchdog')
                notif = f"🤖 *AI EKSEKUSI {ai_result['recommendation'].upper()}* untuk {symbol}\n"
                notif += f"Harga: {latest['Close']:.2f}\n"
                notif += f"Confidence: {ai_result['confidence']}%\n"
                notif += f"Skor: {score}/100"
                kirim_notifikasi_sinkron(notif)
            else:
                logger.warning(f"⏸️ AI trading diblokir: {msg}")
        else:
            logger.info(f"⏸️ AI kuat tapi saham tidak di watchlist dan ADX < 30, tidak dieksekusi.")