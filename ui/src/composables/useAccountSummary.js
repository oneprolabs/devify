import { computed, ref } from 'vue'
import { usePlanName } from '@/composables/usePlanName'
import { billingApi } from '@/api/billing'
import { chatApi } from '@/api/chat'
import { todosApi } from '@/api/todos'
import { expenseApi } from '@/api/expense'

/**
 * Plan name, credit balance and the two nav counts for the app shell.
 *
 * Every page mounts its own layout, so this is cached at module scope and
 * fetched once per session; `refresh()` is there for callers that just changed
 * the subscription.
 */

const credits = ref(null)
const subscription = ref(null)
const chatStats = ref(null)
const todoStats = ref(null)
const expenseStats = ref(null)
let loadPromise = null

const unwrap = (response) => response?.data?.data ?? response?.data ?? null

async function load() {
  const [subscriptionRes, creditsRes, chatRes, todoRes, expenseRes] =
    await Promise.allSettled([
      billingApi.getCurrentSubscription(),
      billingApi.getUserCredits(),
      chatApi.getThreadlineStats(),
      todosApi.getTodoStats(),
      expenseApi.getStats()
    ])

  if (subscriptionRes.status === 'fulfilled') {
    subscription.value = unwrap(subscriptionRes.value)
  }
  if (creditsRes.status === 'fulfilled') {
    credits.value = unwrap(creditsRes.value)
  }
  if (chatRes.status === 'fulfilled') {
    chatStats.value = unwrap(chatRes.value)
  }
  if (todoRes.status === 'fulfilled') {
    todoStats.value = unwrap(todoRes.value)
  }
  // The app is switched off for most accounts, in which case this 404s and
  // the badge simply does not appear.
  // expenseApi already unwraps; the others hand back the axios response,
  // so putting this one through unwrap() again would null it out.
  if (expenseRes.status === 'fulfilled') {
    expenseStats.value = expenseRes.value
  }
}

export function useAccountSummary() {
  const { planName: planLabel } = usePlanName()

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
  // The server names plans in English; the sidebar shows the localised tier.
  const planName = computed(() =>
    planLabel(
      subscription.value?.plan_slug,
      subscription.value?.plan_name || ''
    )
  )
  // The sidebar badges: conversations still waiting, and todos still open.
  const pendingChats = computed(() => chatStats.value?.pending ?? 0)
  const openTodos = computed(() => todoStats.value?.incomplete ?? 0)
  const unfiledInvoices = computed(() => expenseStats.value?.unfiled ?? 0)

  return {
    credits,
    subscription,
    planName,
    pendingChats,
    openTodos,
    unfiledInvoices,
    availableCredits,
    totalCredits,
    creditsPercentage,
    ensureLoaded,
    refresh
  }
}
