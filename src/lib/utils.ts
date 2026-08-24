import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** Tailwind 类合并：shadcn/ui 与业务组件统一使用，禁止手工拼接 className。 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
