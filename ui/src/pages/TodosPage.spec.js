// @vitest-environment happy-dom

import { flushPromises, shallowMount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'

import { todosApi } from '@/api/todos'
import TodosPage from './TodosPage.vue'

vi.mock('vue-i18n', async (importOriginal) => ({
  ...(await importOriginal()),
  useI18n: () => ({ t: (key) => key, locale: ref('en-US') })
}))
vi.mock('@/store/preferences', () => ({
  usePreferencesStore: () => ({ currentTimezone: 'Asia/Shanghai' })
}))
vi.mock('@/api/todos', () => ({
  todosApi: {
    getTodos: vi.fn(),
    getTodoStats: vi.fn(),
    createTodo: vi.fn(),
    updateTodo: vi.fn()
  }
}))

describe('TodosPage undated TODOs (issue #118)', () => {
  let wrapper
  let records

  const mountPage = async () => {
    wrapper = shallowMount(TodosPage, {
      global: { renderStubDefaultSlot: true }
    })
    await flushPromises()
  }
  const rows = () => wrapper.findAllComponents({ name: 'TodoRow' })
  const rowIds = () => rows().map((row) => row.props('todo').id)
  const clickButton = async (label) => {
    const button = wrapper
      .findAll('button')
      .find((item) => item.text() === label)
    expect(button, label).toBeDefined()
    await button.trigger('click')
    await flushPromises()
  }

  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['Date', 'setTimeout', 'clearTimeout'] })
    vi.setSystemTime(new Date('2026-11-04T08:00:00Z'))
    vi.clearAllMocks()
    records = [
      { id: 1, content: 'Undated task', deadline: null, is_completed: false },
      {
        id: 2,
        content: 'November task',
        deadline: '2026-11-20T12:00:00Z',
        is_completed: false
      },
      {
        id: 3,
        content: 'October task',
        deadline: '2026-10-15T12:00:00Z',
        is_completed: false
      }
    ]
    todosApi.getTodos.mockImplementation(async (params) => ({
      data: {
        data: {
          list: records.filter((todo) => {
            if (
              params.is_completed !== undefined &&
              todo.is_completed !== params.is_completed
            )
              return false
            if (params.search && !todo.content.includes(params.search))
              return false
            if (!todo.deadline) return params.include_no_deadline === true
            return (
              new Date(todo.deadline) >= new Date(params.deadline_after) &&
              new Date(todo.deadline) <= new Date(params.deadline_before)
            )
          })
        }
      }
    }))
    todosApi.getTodoStats.mockImplementation(async () => ({
      data: {
        data: {
          total: records.length,
          incomplete: records.filter((todo) => !todo.is_completed).length
        }
      }
    }))
    todosApi.createTodo.mockImplementation(async (data) => {
      records.push({ id: 4, is_completed: false, ...data })
    })
    todosApi.updateTodo.mockImplementation(async (id, data) => {
      Object.assign(
        records.find((todo) => todo.id === id),
        data
      )
    })
  })

  afterEach(() => {
    wrapper?.unmount()
    vi.clearAllTimers()
    vi.useRealTimers()
  })

  it('requests and renders undated TODOs alongside the selected date range', async () => {
    await mountPage()
    expect(todosApi.getTodos).toHaveBeenLastCalledWith(
      expect.objectContaining({
        include_no_deadline: true,
        deadline_after: expect.any(String),
        deadline_before: expect.any(String)
      })
    )
    expect(rowIds()).toEqual([1, 2])
  })

  it('keeps a newly saved undated TODO visible after reloading the page', async () => {
    await mountPage()
    await clickButton('todos.newTodo')
    wrapper.findComponent({ name: 'TodoEditor' }).vm.$emit('save', {
      content: 'New undated task',
      deadline: null
    })
    await flushPromises()
    expect(todosApi.createTodo).toHaveBeenCalledWith({
      content: 'New undated task',
      deadline: null
    })
    expect(rowIds()).toContain(4)
    wrapper.unmount()
    await mountPage()
    expect(rowIds()).toContain(4)
  })

  it('allows an undated TODO to be edited and completed from the list', async () => {
    await mountPage()
    rows()[0].vm.$emit('edit', records[0])
    await flushPromises()
    wrapper.findComponent({ name: 'TodoEditor' }).vm.$emit('save', {
      content: 'Edited undated task',
      deadline: null
    })
    await flushPromises()
    expect(rows()[0].props('todo').content).toBe('Edited undated task')
    rows()[0].vm.$emit('toggle', 1)
    await flushPromises()
    expect(todosApi.updateTodo).toHaveBeenLastCalledWith(1, {
      is_completed: true
    })
    expect(
      rows()
        .find((row) => row.props('todo').id === 1)
        .props('todo').is_completed
    ).toBe(true)
  })

  it('continues to apply completion and search filters to undated TODOs', async () => {
    await mountPage()
    wrapper
      .findAllComponents({ name: 'FilterSelect' })[0]
      .vm.$emit('update:modelValue', true)
    await vi.advanceTimersByTimeAsync(301)
    await flushPromises()
    expect(rowIds()).toEqual([])
    wrapper
      .findAllComponents({ name: 'FilterSelect' })[0]
      .vm.$emit('update:modelValue', false)
    await wrapper.get('input').setValue('Undated')
    await vi.advanceTimersByTimeAsync(301)
    await flushPromises()
    expect(rowIds()).toEqual([1])
  })

  it('keeps calendar queries date-only and restores undated TODOs in list view', async () => {
    await mountPage()
    await clickButton('todos.view.calendar')
    expect(todosApi.getTodos.mock.lastCall[0]).not.toHaveProperty(
      'include_no_deadline'
    )
    expect(rowIds()).toEqual([2])
    wrapper
      .findComponent({ name: 'TodoCalendar' })
      .vm.$emit('select', new Date('2026-11-20T12:00:00Z'))
    await flushPromises()
    await clickButton('todos.view.list')
    expect(rowIds()).toEqual([1, 2])
  })

  it('uses the selected range without reapplying a current-month filter', async () => {
    await mountPage()
    wrapper
      .findComponent({ name: 'TodoStatStrip' })
      .vm.$emit('update:modelValue', 'quarter')
    await flushPromises()
    expect(rowIds().sort()).toEqual([1, 2, 3])
  })
})
