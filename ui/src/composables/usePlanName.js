import { useI18n } from 'vue-i18n'

/**
 * Plan names come out of the database in English ("Pro Plan"), so the UI
 * translates the tiers we ship by their stable slug and falls back to
 * whatever the server said for anything an operator added later.
 */
const SLUG_KEYS = {
  free: 'billing.plans.names.free',
  starter: 'billing.plans.names.starter',
  standard: 'billing.plans.names.standard',
  pro: 'billing.plans.names.pro',
  internal: 'billing.plans.names.internal'
}

export function usePlanName() {
  const { t, te } = useI18n()

  function planName(slug, fallback = '') {
    const key = SLUG_KEYS[String(slug || '').toLowerCase()]
    return key && te(key) ? t(key) : fallback
  }

  return { planName }
}
