"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { formatPrice } from "@/lib/format";
import {
  CURRENCY_COOKIE,
  DEFAULT_CURRENCY_MODE,
  parseCurrencyMode,
  persistCurrencyPreference,
  pushCurrencyPreferenceRemote,
  readStoredCurrencyMode,
  type CurrencyMode,
} from "@/lib/currency-mode";
import { useAuth } from "./auth-provider";

export type { CurrencyMode };

export interface ConvertedPriceResult {
  /** 格式化后的主展示文本，如 "¥258" 或 "$35.88" */
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

function convertPrice(
  price: number,
  currency: string,
  mode: CurrencyMode,
  rates: Record<string, number>,
): ConvertedPriceResult {
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
}

const CurrencyContext = createContext<CurrencyContextType>({
  mode: DEFAULT_CURRENCY_MODE,
  setMode: () => {},
  rates: DEFAULT_RATES,
  convert: (price, currency) => convertPrice(price, currency, DEFAULT_CURRENCY_MODE, DEFAULT_RATES),
});

export function CurrencyProvider({
  children,
  initialRates,
  initialMode = DEFAULT_CURRENCY_MODE,
}: {
  children: React.ReactNode;
  initialRates?: Record<string, number>;
  initialMode?: CurrencyMode;
}) {
  const { user } = useAuth();
  const [mode, setModeState] = useState<CurrencyMode>(initialMode);
  const [rates, setRates] = useState<Record<string, number>>(initialRates || DEFAULT_RATES);

  // 无 cookie 的访客：用 localStorage 补一次并写 cookie，之后 SSR 与展示一致
  useEffect(() => {
    try {
      const hasCookie = document.cookie.split("; ").some((c) => c.startsWith(`${CURRENCY_COOKIE}=`));
      const stored = readStoredCurrencyMode();
      if (!hasCookie && stored && stored !== initialMode) {
        setModeState(stored);
        persistCurrencyPreference(stored);
        return;
      }
      persistCurrencyPreference(mode);
    } catch {
      // 忽略
    }
    // 只在挂载时迁移
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 登录后：本机已有选择就保留并异步推到服务器；本机没有才用云端
  useEffect(() => {
    if (!user) return;
    const local = readStoredCurrencyMode();
    if (local) {
      if (local !== mode) setModeState(local);
      persistCurrencyPreference(local);
      if (user.currency_mode !== local) pushCurrencyPreferenceRemote(local);
      return;
    }
    const remote = parseCurrencyMode(user.currency_mode);
    setModeState(remote);
    persistCurrencyPreference(remote);
    // user 对象在登录/拉 /me 时才会换，不要把 mode 放进依赖以免覆盖刚点的选择
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

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
    persistCurrencyPreference(newMode);
    if (user) pushCurrencyPreferenceRemote(newMode);
  };

  const convert = (price: number, currency: string): ConvertedPriceResult =>
    convertPrice(price, currency, mode, rates);

  return (
    <CurrencyContext.Provider value={{ mode, setMode, rates, convert }}>
      {children}
    </CurrencyContext.Provider>
  );
}

export function useCurrency() {
  return useContext(CurrencyContext);
}
