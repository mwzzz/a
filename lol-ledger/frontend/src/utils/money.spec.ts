import { describe, expect, it } from 'vitest'

import { formatCents, formatChange, parseYuan } from './money'

describe('parseYuan', () => {
  it('整数元', () => {
    expect(parseYuan('12')).toBe(1200)
  })

  it('一位小数补零', () => {
    expect(parseYuan('0.1')).toBe(10)
  })

  it('两位小数不出现浮点误差', () => {
    expect(parseYuan('10.05')).toBe(1005)
    expect(parseYuan('0.07')).toBe(7)
    expect(parseYuan('19.99')).toBe(1999)
  })

  it('千分位逗号', () => {
    expect(parseYuan('1,234.50')).toBe(123450)
  })

  it('超过两位小数拒绝', () => {
    expect(parseYuan('1.001')).toBeNull()
  })

  it('负数、空串、字母拒绝', () => {
    expect(parseYuan('-1')).toBeNull()
    expect(parseYuan('')).toBeNull()
    expect(parseYuan('abc')).toBeNull()
    expect(parseYuan('1e3')).toBeNull()
  })

  it('整数返回数字而不是字符串', () => {
    expect(typeof parseYuan('5')).toBe('number')
  })
})

describe('formatCents', () => {
  it('负数带符号', () => {
    expect(formatCents(-1230)).toBe('-12.30')
  })

  it('零和一位', () => {
    expect(formatCents(0)).toBe('0.00')
    expect(formatCents(5)).toBe('0.05')
  })

  it('大额', () => {
    expect(formatCents(123456789)).toBe('1234567.89')
  })
})

describe('formatChange', () => {
  it('正数带加号', () => {
    expect(formatChange(500)).toBe('+5.00')
  })

  it('负数不加号', () => {
    expect(formatChange(-500)).toBe('-5.00')
  })

  it('零', () => {
    expect(formatChange(0)).toBe('0.00')
  })
})
