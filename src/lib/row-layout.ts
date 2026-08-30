/**
 * 列表视图（表格形态）的列宽约定。
 *
 * 表头（app/vps/page.tsx）与内容行（components/vps/row-buy-zone.tsx）是两套
 * 独立 DOM：表头用固定宽度 div 横向排列；内容行靠 RowBuyZone 的 `sm:contents`
 * 让「价格 / 状态 / 操作」三段直接参与父级 flex。两边必须手抄同一组宽度，
 * 只改一处就会标题与内容错位——操作列就曾因内容行加宽到 176px、表头仍为
 * 144px 而错开 32px。
 *
 * 因此把宽度收在这里，两处引用同一份定义。
 *
 * 注意：Tailwind 不扫描动态拼接的类名（`w-[${n}px]` 会被清除），
 * 所以只能提供完整的类字符串，且表头列无需 sm 前缀（表头本身 hidden sm:flex）。
 */

/**
 * 「操作」列宽 = 关注胶囊 76px + 间距 8px + 右侧按钮 88px，留 4px 余量。
 * 关注按钮换回旧站 76px 胶囊后原 144px 装不下，缺货时会溢出压住状态标签。
 */
export const ROW_ACTIONS_HEAD = "w-[176px]";
export const ROW_ACTIONS_ROW = "sm:w-[176px]";
