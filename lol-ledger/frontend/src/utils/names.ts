/** 玩家名归一化：与后端 base_name 一致，忽略 #后缀、大小写和全半角差异。 */
export function nameKey(value?: string | null): string {
  return (value || '')
    .normalize('NFKC')
    .trim()
    .split('#')[0]
    .trim()
    .toLowerCase()
}
