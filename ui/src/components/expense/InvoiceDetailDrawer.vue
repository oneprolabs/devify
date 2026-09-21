<template>
  <!-- The canvas draws this as a column beside the list, not a sheet over
       it: checking an invoice means reading the row it came from, and a
       scrim puts that behind glass. Clicking another row swaps the panel.
       Below the breakpoint the two cannot share the width, so there it
       falls back to the overlay it used to be.

       576px is the artboard's number at its own 1440 width, which is 48%
       of the content area. Past that the panel keeps the proportion rather
       than the pixel count, or it would shrink to a strip on a wide screen;
       it stops growing at 860 so the fields do not stretch. -->
  <div
    :class="
      variant === 'panel'
        ? 'flex min-h-0 w-[576px] flex-none flex-col border-l border-line bg-panel 2xl:w-[48%] 2xl:max-w-[860px]'
        : // z-50, not z-40: the phone's tab bar is z-40 too and would
          // otherwise paint over this sheet's save button.
          'fixed inset-0 z-50 flex justify-end'
    "
    @click.self="variant !== 'panel' && $emit('close')"
  >
    <div
      v-if="variant !== 'panel'"
      class="absolute inset-0 bg-ink-3 bg-opacity-50"
    ></div>

    <aside
      :class="[
        'flex flex-col overflow-y-auto bg-panel',
        variant === 'panel'
          ? 'min-h-0 flex-1'
          : 'relative z-10 h-full w-full max-w-xl shadow-xl'
      ]"
    >
      <header
        class="flex items-start justify-between gap-3 border-b border-line px-5 pb-[13px] pt-4"
      >
        <div class="min-w-0">
          <h2
            class="truncate text-[calc(15px*var(--fs))] font-semibold -tracking-[0.01em] text-ink"
          >
            {{ form.seller_name || t('expense.invoices.untitled') }}
          </h2>
          <p class="mt-1 truncate text-[calc(11.5px*var(--fs))] text-ink-3">
            {{ invoice.email_subject }}
          </p>
        </div>
        <button
          type="button"
          class="flex h-7 w-7 flex-none items-center justify-center rounded-md text-ink-3 hover:bg-chip hover:text-ink-2"
          :aria-label="t('common.close')"
          @click="$emit('close')"
        >
          <svg
            class="h-[15px] w-[15px]"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </button>
      </header>

      <div class="flex flex-1 flex-col gap-[17px] px-5 py-[18px]">
        <p
          v-if="invoice.needs_review"
          class="rounded-lg border border-warn bg-warn-soft px-[13px] py-[11px] text-[calc(11.5px*var(--fs))] leading-[1.6] text-warn"
        >
          {{ t('expense.invoices.reviewHint') }}
        </p>

        <p
          v-if="error"
          class="rounded-lg border border-bad bg-bad-soft p-3 text-sm text-bad"
        >
          {{ error }}
        </p>

        <div class="grid grid-cols-1 gap-[13px] sm:grid-cols-2">
          <label
            v-for="field in textFields"
            :key="field.key"
            class="block"
            :class="field.wide ? 'sm:col-span-2' : ''"
          >
            <!-- An empty field on a recognised invoice is something the
                 reader has to fill in, so it is coloured like the work it
                 is rather than left to be spotted. -->
            <span
              class="mb-[5px] block text-[calc(10.5px*var(--fs))]"
              :class="isBlank(field.key) ? 'text-warn' : 'text-ink-3'"
            >
              {{ t(`expense.invoices.fields.${field.key}`) }}
            </span>
            <input
              v-model="form[field.key]"
              :type="field.type || 'text'"
              class="h-[34px] w-full rounded-md border bg-panel px-[11px] text-[calc(12.5px*var(--fs))] text-ink focus:border-accent focus:outline-none focus:ring-0"
              :class="isBlank(field.key) ? 'border-warn' : 'border-line'"
            />
            <span
              v-if="field.hint"
              class="mt-[5px] block text-[calc(10.5px*var(--fs))] text-ink-4"
            >
              {{ t(`expense.invoices.${field.hint}`) }}
            </span>
          </label>

          <label class="block">
            <span
              class="mb-[5px] block text-[calc(10.5px*var(--fs))] text-ink-3"
            >
              {{ t('expense.invoices.category') }}
            </span>
            <select
              v-model="form.category"
              class="h-[34px] w-full rounded-md border border-line bg-panel px-[11px] text-[calc(12.5px*var(--fs))] text-ink focus:border-accent focus:outline-none focus:ring-0"
            >
              <option v-for="key in categories" :key="key" :value="key">
                {{ t(`expense.categories.${key}`) }}
              </option>
            </select>
            <span
              class="mt-[5px] block text-[calc(10.5px*var(--fs))] text-ink-4"
            >
              {{
                t(
                  `expense.invoices.sources.${invoice.category_source || 'model'}`
                )
              }}
            </span>
          </label>
        </div>

        <div v-if="invoice.summary_line" class="space-y-[5px]">
          <span class="block text-[calc(10.5px*var(--fs))] text-ink-3">
            {{ t('expense.invoices.fields.summary_line') }}
          </span>
          <p class="text-[calc(12.5px*var(--fs))] leading-[1.6] text-ink-2">
            {{ invoice.summary_line }}
          </p>
        </div>

        <p class="text-[calc(11px*var(--fs))] leading-[1.7] text-ink-3">
          {{ t('expense.invoices.learnHint') }}
        </p>

        <!-- Filed invoices say so on the row; without this the drawer was
             silent about it, so opening one to ask why it is not in a
             group answered nothing. -->
        <div v-if="invoice.disposition === 'filed'" class="space-y-2">
          <p class="text-[calc(12.5px*var(--fs))] font-semibold text-ink">
            {{ t('expense.invoices.filedTitle') }}
          </p>
          <div
            class="flex items-center gap-[9px] rounded-lg border border-line bg-panel-sub px-[13px] py-3"
          >
            <span
              class="flex-none rounded-full bg-chip px-[9px] py-0.5 text-[calc(10.5px*var(--fs))] text-ink-2"
            >
              {{
                t(
                  `expense.invoices.filedReasons.${
                    invoice.filed_reason || 'other'
                  }`
                )
              }}
            </span>
            <span class="text-[calc(11.5px*var(--fs))] text-ink-3">
              {{ t('expense.invoices.filedNote') }}
            </span>
            <button
              type="button"
              class="ml-auto flex-none text-[calc(11.5px*var(--fs))] text-accent hover:underline"
              @click="$emit('unfile', invoice)"
            >
              {{ t('expense.invoices.unfile') }}
            </button>
          </div>
        </div>

        <div
          v-if="invoice.status === 'failed' && invoice.error_message"
          class="space-y-1 rounded-lg border border-bad bg-bad-soft p-3"
        >
          <p class="text-xs font-medium text-bad">
            {{ t('expense.invoices.failedTitle') }}
          </p>
          <p class="text-xs leading-relaxed text-bad">
            {{ invoice.error_message }}
          </p>
          <p class="text-xs leading-relaxed text-bad">
            {{ t('expense.invoices.failedHint') }}
          </p>
        </div>

        <div class="space-y-2">
          <h3 class="text-[calc(12.5px*var(--fs))] font-semibold text-ink">
            {{ t('expense.invoices.original') }}
          </h3>

          <p
            v-if="!invoice.has_file"
            class="rounded-lg border border-line bg-panel-sub px-[13px] py-3 text-[calc(11.5px*var(--fs))] text-ink-3"
          >
            {{ t('expense.invoices.originalMissing') }}
          </p>

          <div
            v-else-if="fileLoading"
            class="h-64 animate-pulse rounded-lg bg-chip"
          ></div>

          <p
            v-else-if="fileError"
            class="rounded-lg border border-bad bg-bad-soft p-3 text-xs text-bad"
          >
            {{ fileError }}
          </p>

          <img
            v-else-if="fileUrl && previewKind === 'image'"
            :src="fileUrl"
            :alt="t('expense.invoices.original')"
            class="w-full rounded-lg border border-line"
          />

          <iframe
            v-else-if="fileUrl && previewKind === 'pdf'"
            :src="fileUrl"
            class="h-[32rem] w-full rounded-lg border border-line"
            :title="t('expense.invoices.original')"
          ></iframe>

          <div
            v-else
            class="space-y-[5px] rounded-lg border border-line bg-panel-sub px-[13px] py-3"
          >
            <p class="text-[calc(11.5px*var(--fs))] text-ink-3">
              {{ t('expense.invoices.originalNotViewable') }}
            </p>
            <a
              v-if="fileUrl"
              :href="fileUrl"
              :download="invoice.filename || 'invoice'"
              class="text-[calc(11.5px*var(--fs))] text-accent hover:underline"
            >
              {{ t('expense.invoices.originalDownload') }}
            </a>
          </div>
        </div>

        <!-- What else the email carried about this expense. The invoice is
             the subject and stays above; these explain it and would
             otherwise be thrown away by the duplicate collapse. -->
        <div v-if="relatedDocuments.length" class="space-y-2">
          <h3 class="text-[calc(12.5px*var(--fs))] font-semibold text-ink">
            {{ t('expense.invoices.relatedTitle') }}
          </h3>
          <div class="overflow-hidden rounded-lg border border-line">
            <button
              v-for="doc in relatedDocuments"
              :key="doc.uuid"
              type="button"
              class="flex w-full items-center gap-2.5 border-b border-line-soft px-[13px] py-2.5 text-left last:border-b-0 hover:bg-chip disabled:cursor-default disabled:hover:bg-transparent"
              :disabled="!doc.has_file"
              @click="openRelated(doc)"
            >
              <span
                class="min-w-0 flex-1 truncate text-[calc(11.5px*var(--fs))] text-ink-2"
              >
                {{ doc.filename || t('expense.invoices.untitled') }}
              </span>
              <span
                v-if="doc.disposition === 'supporting'"
                class="font-mono flex-none rounded-sm bg-panel-sub px-1.5 py-0.5 text-[calc(9.5px*var(--fs))] text-ink-3"
              >
                {{ t('expense.invoices.notClaimable') }}
              </span>
              <span
                v-if="doc.has_file"
                class="flex-none text-[calc(11px*var(--fs))] text-accent"
              >
                {{ t('expense.invoices.originalDownload') }}
              </span>
            </button>
          </div>
        </div>

        <div
          v-if="invoice.ticket_details && hasTicketDetails"
          class="space-y-2"
        >
          <h3 class="text-[calc(12.5px*var(--fs))] font-semibold text-ink">
            {{ t('expense.invoices.ticketDetails') }}
          </h3>
          <dl
            class="grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-[7px] rounded-lg bg-panel-sub px-[13px] py-3 text-[calc(11.5px*var(--fs))] sm:grid-cols-[auto_minmax(0,1fr)_auto_minmax(0,1fr)]"
          >
            <template v-for="(value, key) in invoice.ticket_details" :key="key">
              <dt class="text-ink-3">{{ ticketLabel(key) }}</dt>
              <dd class="truncate text-ink">{{ value }}</dd>
            </template>
          </dl>
        </div>
      </div>

      <footer
        class="flex flex-wrap items-center justify-between gap-[10px] border-t border-line px-5 py-[14px]"
      >
        <BaseButton
          size="sm"
          variant="outline"
          :loading="reextracting"
          @click="$emit('reextract', invoice)"
        >
          {{
            t('expense.invoices.reextractWithCost', {
              credits: costPerEmail
            })
          }}
        </BaseButton>

        <BaseButton
          size="sm"
          :loading="saving"
          @click="$emit('save', buildPayload())"
        >
          {{ t('common.save') }}
        </BaseButton>
      </footer>
    </aside>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseButton from '@/components/ui/BaseButton.vue'
import { expenseApi } from '@/api/expense'

const props = defineProps({
  invoice: {
    type: Object,
    required: true
  },
  // 'panel' sits in the page flow beside the list; 'overlay' is the sheet
  // used below the breakpoint where both cannot fit.
  variant: {
    type: String,
    default: 'overlay'
  },
  // The canvas puts the price on the button rather than in a toast
  // after the fact: spending is the decision, and it is made before
  // the click.
  costPerEmail: {
    type: Number,
    default: 1
  },
  saving: {
    type: Boolean,
    default: false
  },
  reextracting: {
    type: Boolean,
    default: false
  },
  error: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['close', 'save', 'reextract', 'unfile'])

const { t, te } = useI18n()

// A sheet over the page should close on Escape; the inline panel should
// not, because there Escape would dismiss something nothing covers.
const onKeydown = (event) => {
  if (event.key === 'Escape' && props.variant !== 'panel') emit('close')
}
onMounted(() => document.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => document.removeEventListener('keydown', onKeydown))

// Ordered as the design canvas draws it — who issued it, who it is for,
// when, how much, what for — rather than the order the fields happened to
// be declared in. `wide` spans both columns for the two long names.
//
// expense_date is here because the list shows it and the drawer did not,
// and it is the worse thing to be missing: trip grouping runs on it, so a
// misread date puts a receipt on the wrong trip with no way to correct it
// from here. summary_line is shown too, below the grid rather than in it —
// the server derives it from items and ticket_details, so an input would
// take an edit and quietly drop it.
const textFields = [
  { key: 'seller_name', wide: true },
  { key: 'seller_tax_id' },
  { key: 'invoice_no' },
  { key: 'buyer_name', wide: true },
  { key: 'buyer_tax_id' },
  { key: 'city' },
  { key: 'expense_date', type: 'date', hint: 'expenseDateHint' },
  { key: 'issue_date', type: 'date' },
  { key: 'total_amount' },
  { key: 'tax_amount' },
  { key: 'amount_excl_tax' }
]

// Blank on a recognised invoice means the model found nothing there, which
// is a field to fill rather than a field that is simply empty.
// ticket_details keys come straight off the model's JSON, so the block
// was printing "passenger" and "train_no" at the reader. Anything not in
// the table falls back to the raw key rather than disappearing.
const ticketLabel = (key) => {
  const path = `expense.invoices.ticketFields.${key}`
  return te(path) ? t(path) : key
}

const isBlank = (key) => !String(form[key] ?? '').trim()

// An empty date input holds '', which the API rejects outright ("Date has
// wrong format") - so an invoice missing a date could not be saved at all,
// not even to correct a different field. Blank means "unknown", which is
// null.
function buildPayload() {
  const payload = { ...form }
  textFields.forEach((field) => {
    if (field.type === 'date' && isBlank(field.key)) payload[field.key] = null
  })
  return payload
}

const categories = [
  'transport_long',
  'transport_local',
  'accommodation',
  'meals',
  'entertainment',
  'office',
  'communication',
  'training',
  'other'
]

const form = reactive({})

function load(invoice) {
  textFields.forEach((field) => {
    form[field.key] = invoice[field.key] ?? ''
  })
  form.category = invoice.category || 'other'
}

watch(() => props.invoice, load, { immediate: true })

const relatedDocuments = computed(() => props.invoice.related_documents || [])

// Opened in a tab rather than inlined: these are secondary, and the panel
// already carries one preview.
async function openRelated(doc) {
  if (!doc.has_file) return
  try {
    const blob = await expenseApi.getInvoiceFile(doc.uuid)
    const url = URL.createObjectURL(blob)
    window.open(url, '_blank', 'noopener')
    setTimeout(() => URL.revokeObjectURL(url), 60000)
  } catch (err) {
    fileError.value =
      err?.response?.data?.message || t('expense.invoices.originalFailed')
  }
}

const hasTicketDetails = computed(
  () => Object.keys(props.invoice.ticket_details || {}).length > 0
)

const fileUrl = ref('')
const fileLoading = ref(false)
const fileError = ref('')

const previewKind = computed(() => {
  const type = (props.invoice.file_content_type || '').toLowerCase()
  if (type.startsWith('image/')) return 'image'
  if (type.includes('pdf')) return 'pdf'
  // OFD and anything else has no browser renderer; offer the file instead
  // of an empty frame.
  return 'other'
})

function releaseFile() {
  if (fileUrl.value) {
    URL.revokeObjectURL(fileUrl.value)
    fileUrl.value = ''
  }
}

async function loadFile(invoice) {
  releaseFile()
  fileError.value = ''
  if (!invoice?.has_file) return

  fileLoading.value = true
  try {
    const blob = await expenseApi.getInvoiceFile(invoice.uuid)
    fileUrl.value = URL.createObjectURL(blob)
  } catch (err) {
    fileError.value =
      err?.response?.data?.message || t('expense.invoices.originalFailed')
  } finally {
    fileLoading.value = false
  }
}

watch(
  () => props.invoice?.uuid,
  () => loadFile(props.invoice),
  {
    immediate: true
  }
)

onBeforeUnmount(releaseFile)
</script>
