# Report — 成果與圖表

本目錄是給讀者看的成品：研究的圖表，以及（日後補上的）研究報告。

## 圖表

每張圖對應一個論點，收於 `figures/`。

| 圖 | 說明 |
|----|------|
| `figures/signal/quintile_spread.png` | 把股票依訊號分五等分，看各組後續報酬——**由弱到強單調遞增**。 |
| `figures/signal/rolling_ic.png` | 訊號預測力（IC）隨時間的走勢——**長期穩定為正**。 |
| `figures/_compare/factor_comparison.png` | 四種配置的淨值走勢與風險調整報酬對照。 |
| `figures/accel_top15/` | 樸素版（加速度排序、最強 15 檔）——純做多、扣成本後輸被動的負面對照。 |
| `figures/accel_top50/` | 加速度排序、分散至 50 檔。 |
| `figures/new_high_top50/` | **最終選定的最佳配置**（創新高排序、50 檔）。 |
| `figures/ensemble_top50/` | 集成（加速度＋創新高）排序、50 檔。 |
| `figures/benchmark/startdate_sensitivity.png` | 策略 vs 0050 在不同起點的報酬——**「輸 0050」高度取決於起點**。 |
| `figures/benchmark/alpha_significance.png` | 超額報酬的統計顯著性——**基準選得越公平，超額能力越明確**。 |
| `figures/holdings/holdings_tradeoff.png` | 持股檔數的取捨：越分散、風險調整報酬越好。 |
| `figures/robustness/param_heatmaps.png` | 跨參數的表現熱力圖——**鄰近參數都不錯，證明不是過擬合**。 |

上述四個配置資料夾各含三張圖：淨值曲線、回撤、逐年表現（皆含對照組與隨機投組分布帶）。

> 各圖由 `../Analysis/visualization/` 的腳本，讀取 `../Analysis/results/` 的分析結果繪製而成。
