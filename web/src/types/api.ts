export interface ApiEnvelope<T> {
  code?: number
  success?: boolean
  message?: string
  data?: T
}

export interface ApiErrorBody {
  message?: string
  detail?: string | Array<{ loc?: string[]; msg: string; type?: string }>
  error?: string
}

export type QueryValue = string | number | boolean | null | undefined

export type QueryParams = Record<string, QueryValue>
