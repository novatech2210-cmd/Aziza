import { describe, it, expect } from 'vitest'
import { generateUUID } from '../utils/uuid.js'

describe('generateUUID', () => {
  it('returns a string', () => {
    expect(typeof generateUUID()).toBe('string')
  })

  it('returns a valid UUID v4 format', () => {
    const uuid = generateUUID()
    expect(uuid).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/)
  })

  it('generates unique values', () => {
    const ids = new Set(Array.from({ length: 100 }, () => generateUUID()))
    expect(ids.size).toBe(100)
  })
})
