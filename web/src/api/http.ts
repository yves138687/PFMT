import { ElMessage } from 'element-plus'

import type { ApiEnvelope, ApiErrorBody, QueryParams } from '@/types/api'
import { clearAuthSnapshot, getAccessToken } from '@/utils/authStorage'

export class ApiError extends Error {
  status: number
  body: ApiErrorBody | unknown

  constructor(message: string, status: number, body?: ApiErrorBody | unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.body = body
  }
}

export interface RequestOptions extends Omit<RequestInit, 'body'> {
  body?: unknown
  query?: QueryParams
  skipAuth?: boolean
  skipErrorMessage?: boolean
}

type UnauthorizedHandler = (() => void) | null

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '/api').replace(/\/$/, '')
let unauthorizedHandler: UnauthorizedHandler = null

export function registerUnauthorizedHandler(handler: UnauthorizedHandler) {
  unauthorizedHandler = handler
}

function buildUrl(path: string, query?: QueryParams) {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  const url = new URL(`${API_BASE_URL}${normalizedPath}`, window.location.origin)

  Object.entries(query ?? {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      url.searchParams.set(key, String(value))
    }
  })

  return url.toString()
}

function getMessage(body: ApiErrorBody | unknown, fallback: string) {
  if (!body || typeof body !== 'object') {
    return fallback
  }

  const errorBody = body as ApiErrorBody
  if (typeof errorBody.message === 'string') {
    return errorBody.message
  }

  if (typeof errorBody.error === 'string') {
    return errorBody.error
  }

  if (typeof errorBody.detail === 'string') {
    return errorBody.detail
  }

  if (Array.isArray(errorBody.detail)) {
    return errorBody.detail.map((item) => item.msg).join('；') || fallback
  }

  return fallback
}

async function parseBody(response: Response) {
  if (response.status === 204) {
    return null
  }

  const contentType = response.headers.get('content-type') ?? ''
  if (contentType.includes('application/json')) {
    return response.json()
  }

  const text = await response.text()
  return text || null
}

function normalizeData<T>(payload: unknown): T {
  if (payload && typeof payload === 'object' && ('data' in payload || 'success' in payload || 'code' in payload)) {
    const envelope = payload as ApiEnvelope<T>
    const failedBySuccess = envelope.success === false
    const failedByCode = typeof envelope.code === 'number' && envelope.code >= 400

    if (failedBySuccess || failedByCode) {
      throw new ApiError(envelope.message ?? '请求处理失败', envelope.code ?? 500, payload)
    }

    return envelope.data as T
  }

  return payload as T
}

function notifyError(message: string, skipErrorMessage?: boolean) {
  if (!skipErrorMessage) {
    ElMessage.error(message)
  }
}

export async function request<T>(path: string, options: RequestOptions = {}) {
  const { body, query, skipAuth, skipErrorMessage, headers: initHeaders, ...init } = options
  const headers = new Headers(initHeaders)

  let requestBody: BodyInit | undefined
  if (body instanceof FormData) {
    requestBody = body
  } else if (body !== undefined) {
    requestBody = JSON.stringify(body)
    headers.set('Content-Type', headers.get('Content-Type') ?? 'application/json')
  }

  const token = getAccessToken()
  if (token && !skipAuth) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  let response: Response
  try {
    response = await fetch(buildUrl(path, query), {
      ...init,
      headers,
      body: requestBody
    })
  } catch (error) {
    const message = error instanceof Error ? error.message : '网络请求失败'
    notifyError(message, skipErrorMessage)
    throw new ApiError(message, 0, error)
  }

  const payload = await parseBody(response)

  if (response.status === 401) {
    // 401 表示登录态失效：清理本地 token，并交给路由层统一跳回登录页。
    clearAuthSnapshot()
    notifyError('登录已过期，请重新登录', skipErrorMessage)
    unauthorizedHandler?.()
    throw new ApiError('登录已过期，请重新登录', response.status, payload)
  }

  if (!response.ok) {
    const message = getMessage(payload, `请求失败：${response.status}`)
    notifyError(message, skipErrorMessage)
    throw new ApiError(message, response.status, payload)
  }

  try {
    return normalizeData<T>(payload)
  } catch (error) {
    if (error instanceof ApiError) {
      notifyError(error.message, skipErrorMessage)
    }
    throw error
  }
}

export const http = {
  get: <T>(path: string, options?: RequestOptions) => request<T>(path, { ...options, method: 'GET' }),
  post: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>(path, { ...options, body, method: 'POST' }),
  put: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>(path, { ...options, body, method: 'PUT' }),
  delete: <T>(path: string, options?: RequestOptions) => request<T>(path, { ...options, method: 'DELETE' })
}
