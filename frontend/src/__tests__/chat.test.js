import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

vi.mock('vue-router', () => ({
  createRouter: vi.fn(() => ({ push: vi.fn(), beforeEach: vi.fn() })),
  createWebHistory: vi.fn(),
  useRouter: () => ({ push: vi.fn() }),
}))

const mockAxios = vi.hoisted(() => ({
  create: vi.fn(() => ({
    interceptors: { request: { use: vi.fn() }, response: { use: vi.fn() } },
    post: vi.fn(),
    get: vi.fn(),
  })),
  interceptors: { request: { use: vi.fn() }, response: { use: vi.fn() } },
}))

vi.mock('axios', () => ({ default: mockAxios }))

import { useChatStore } from '../stores/chat.js'

describe('chat store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('initializes with default state', () => {
    const chat = useChatStore()
    expect(chat.messages).toEqual([])
    expect(chat.connectionState).toBe('disconnected')
    expect(chat.isStreaming).toBe(false)
    expect(chat.selectedLanguage).toBe('auto')
    expect(chat.selectedMode).toBe('text')
  })

  it('isConnected getter reflects connection state', () => {
    const chat = useChatStore()
    expect(chat.isConnected).toBe(false)
    chat.connectionState = 'connected'
    expect(chat.isConnected).toBe(true)
  })

  it('sendMessage returns false when disconnected', () => {
    const chat = useChatStore()
    const result = chat.sendMessage('hello')
    expect(result).toBe(false)
    expect(chat.messages).toHaveLength(0)
  })

  it('sendMessage returns false when ws not open', () => {
    const chat = useChatStore()
    chat.wsConnection = { readyState: 0 } // CONNECTING, not OPEN
    const result = chat.sendMessage('hello')
    expect(result).toBe(false)
  })

  it('stopGeneration sends stop message and resets streaming', () => {
    const chat = useChatStore()
    const mockSend = vi.fn()
    chat.wsConnection = { readyState: 1, send: mockSend }
    chat.isStreaming = true
    chat.stopGeneration()
    expect(mockSend).toHaveBeenCalledWith(JSON.stringify({ type: 'stop' }))
    expect(chat.isStreaming).toBe(false)
  })

  it('retryLastMessage removes messages and re-sends', () => {
    const chat = useChatStore()
    chat.messages = [
      { id: '1', role: 'user', content: 'hi' },
      { id: '2', role: 'assistant', content: 'hello' },
      { id: '3', role: 'user', content: 'bye' },
      { id: '4', role: 'assistant', content: 'goodbye' },
    ]
    // WS not connected, so sendMessage will fail — messages 3+4 removed, message 3 removed, send fails
    chat.retryLastMessage()
    expect(chat.messages).toHaveLength(2)
    expect(chat.messages[0].content).toBe('hi')
    expect(chat.messages[1].content).toBe('hello')
  })
})
