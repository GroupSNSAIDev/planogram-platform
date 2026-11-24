// Golden parity: the same cases run in pytest (services/api/tests/test_golden.py).
import { describe, expect, it } from 'vitest'
import golden from '../../../../packages/contracts/golden/fit_cases.json'
import { checkSurface, clearHeights, eyeBand, type FitPosition, type FitProduct } from './geometry'

const products = golden.products as Record<string, FitProduct>

describe('golden surface cases', () => {
  for (const c of golden.surface_cases) {
    it(c.name, () => {
      const r = checkSurface(c.surface, c.clear_height_mm, c.has_door, c.fixture_temperature,
        c.positions as FitPosition[], products)
      expect(r.x_mm).toEqual(c.expected.x_mm)
      expect(r.used_width_mm).toBe(c.expected.used_width_mm)
      expect(r.issues.map(i => `${i.code}:${i.target}`).sort()).toEqual([...c.expected.issues].sort())
    })
  }
})

describe('golden clear heights and eye bands', () => {
  for (const c of golden.clear_height_cases) {
    it(c.name, () => expect(clearHeights(c.heights, c.bay_height_mm)).toEqual(c.expected))
  }
  for (const c of golden.eye_band_cases) {
    it(`${c.height_mm} mm is ${c.band}`, () => expect(eyeBand(c.height_mm)).toBe(c.band))
  }
})
