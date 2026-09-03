"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { formatPrice } from "@/lib/format";

export type CurrencyMode = "original" | "CNY" | "USD";

export interface ConvertedPriceResult {
  /** 格式化后的主展示文本，如 "≈ ¥258" 或 "$35.88" */
  displayPrice: string;
  /** 是否经过汇率换算（用于遵守 AGENTS.md：清晰区分原价与估算价） */
  isConverted: boolean;
  /** 供应商原始币种与金额（如 "$35.88"），方便用户对照 */
  originalPrice: string;
  /** 换算汇率提示文案（如 "按 1 USD ≈ 7.24 CNY 折算"） */
  rateNotice?: string;
}

interface CurrencyContextType {
  mode: CurrencyMode;
  setMode: (mode: CurrencyMode) => void;
  rates: Record<string, number>;
  convert: (price: number, currency: string) => ConvertedPriceResult;
}

const DEFAULT_RATES: Record<string, number> = {
  USD: 1.0,
  CNY: 7.2,
  EUR: 0.86,
  CAD: 1.38,
};

const STORAGE_KEY = "govps_currency_mode";

const CurrencyContext = createContext<CurrencyContextType>({
  mode: "original",
  setMode: () => {},
  rates: DEFAULT_RATES,
  convert: (price, currency) => ({
    displayPrice: formatPrice(price, currency),
    isConverted: false,
    originalPrice: formatPrice(price, currency),
  }),
});

export function CurrencyProvider({
  children,
  initialRates,
}: {
  children: React.ReactNode;
  initialRates?: Record<string, number>;
}) {
  const [mode, setModeState] = useState<CurrencyMode>("original");
  const [rates, setRates] = useState<Record<string, number>>(initialRates || DEFAULT_RATES);

  // 初始化从 localStorage 读取用户偏好
  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY) as CurrencyMode | null;
      if (stored && (stored === "original" || stored === "CNY" || stored === "USD")) {
        setModeState(stored);
      }
    } catch {
      // 忽略隐私模式下的 localStorage 异常
    }
  }, []);

  // 客户端如果缺失 rates，拉取最新汇率
  useEffect(() => {
    if (!initialRates) {
      fetch("/api/rates")
        .then((res) => res.json())
        .then((data) => {
          if (data?.rates && Array.isArray(data.rates)) {
            const map: Record<string, number> = {};
            for (const r of data.rates) {
              map[r.code] = r.units_per_usd;
            }
            if (Object.keys(map).length > 0) setRates(map);
          }
        })
        .catch(() => {});
    }
  }, [initialRates]);

  const setMode = (newMode: CurrencyMode) => {
    setModeState(newMode);
    try {
      localStorage.setItem(STORAGE_KEY, newMode);
    } catch {
      // 忽略
    }
  };

  const convert = (price: number, currency: string): ConvertedPriceResult => {
    const rawCurrency = (currency || "USD").toUpperCase();
    const originalFormatted = formatPrice(price, rawCurrency);

    if (mode === "original" || !price || price <= 0) {
      return {
        displayPrice: originalFormatted,
        isConverted: false,
        originalPrice: originalFormatted,
      };
    }

    if (mode === "CNY") {
      if (rawCurrency === "CNY") {
        return {
          displayPrice: originalFormatted,
          isConverted: false,
          originalPrice: originalFormatted,
        };
      }
      const fromUnits = rates[rawCurrency] || (rawCurrency === "EUR" ? 0.86 : 1);
      const cnyUnits = rates["CNY"] || 7.2;
      const inUsd = price / fromUnits;
      const inCny = inUsd * cnyUnits;
      const formattedCny = inCny >= 100 ? Math.round(inCny).toString() : inCny.toFixed(1);

      return {
        displayPrice: `¥${formattedCny}`,
        isConverted: true,
        originalPrice: originalFormatted,
        rateNotice: `按 1 USD ≈ ${cnyUnits.toFixed(2)} CNY 汇率换算，实际扣款以原币为准`,
      };
    }

    if (mode === "USD") {
      if (rawCurrency === "USD") {
        return {
          displayPrice: originalFormatted,
          isConverted: false,
          originalPrice: originalFormatted,
        };
      }
      const fromUnits = rates[rawCurrency] || 1;
      const inUsd = price / fromUnits;
      const formattedUsd = inUsd >= 100 ? Math.round(inUsd).toString() : inUsd.toFixed(2);

      return {
        displayPrice: `$${formattedUsd}`,
        isConverted: true,
        originalPrice: originalFormatted,
        rateNotice: `按实时汇率折算为美元，实际扣款以原币为准`,
      };
    }

    return {
      displayPrice: originalFormatted,
      isConverted: false,
      originalPrice: originalFormatted,
    };
  };

  return (
    <CurrencyContext.Provider value={{ mode, setMode, rates, convert }}>
      {children}
    </CurrencyContext.Provider>
  );
}

export function useCurrency() {
  return useContext(CurrencyContext);
}
