import { computed, ref } from 'vue'
import { billingApi } from '@/api/billing'

/**
 * Plan name and credit balance for the app shell.
 *
 * Every page mounts its own layout, so this is cached at module scope and
 * fetched once per session; `refresh()` is there for callers that just changed
 * the subscription.
 */

const credits = ref(null)
const subscription = ref(null)
let loadPromise = null

const unwrap = (response) => response?.data?.data ?? response?.data ?? null

async function load() {
  const [subscriptionRes, creditsRes] = await Promise.allSettled([
    billingApi.getCurrentSubscription(),
    billingApi.getUserCredits()
  ])

  if (subscriptionRes.status === 'fulfilled') {
    subscription.value = unwrap(subscriptionRes.value)
  }
  if (creditsRes.status === 'fulfilled') {
    credits.value = unwrap(creditsRes.value)
  }
}

export function useAccountSummary() {
  const ensureLoaded = () => {
    if (!loadPromise) {
      loadPromise = load().catch((error) => {
        // The shell stays usable without billing data; let it retry later.
        console.error('Failed to load account summary:', error)
        loadPromise = null
      })
    }
    return loadPromise
  }

  const refresh = () => {
    loadPromise = null
    return ensureLoaded()
  }

  const availableCredits = computed(() => credits.value?.available_credits ?? 0)
  const totalCredits = computed(() => credits.value?.total_credits ?? 0)
  const creditsPercentage = computed(() => {
    if (!totalCredits.value) return 0
    return Math.min(
      100,
      Math.round((availableCredits.value / totalCredits.value) * 100)
    )
  })
  const planName = computed(() => subscription.value?.plan_name || '')

  return {
    credits,
    subscription,
    planName,
    availableCredits,
    totalCredits,
    creditsPercentage,
    ensureLoaded,
    refresh
  }
}
