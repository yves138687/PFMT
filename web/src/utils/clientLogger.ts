type ClientLogLevel = 'debug' | 'info' | 'warn' | 'error'

type ClientLogContext = Record<string, unknown>

const SENSITIVE_KEY_PATTERN = /(^|_)(password|token|authorization|secret|content|body)($|_)/i
const clientLogsEnabled = (import.meta.env.DEV && import.meta.env.MODE !== 'test') || import.meta.env.VITE_CLIENT_LOGS === 'true'

function sanitizeContext(context: ClientLogContext = {}) {
  return Object.fromEntries(
    Object.entries(context).map(([key, value]) => [
      key,
      SENSITIVE_KEY_PATTERN.test(key) ? '[redacted]' : value
    ])
  )
}

function emit(level: ClientLogLevel, event: string, context?: ClientLogContext) {
  if (!clientLogsEnabled) {
    return
  }

  // 仅记录诊断元数据，避免把密码、Token、正文内容等用户数据写入浏览器控制台。
  const payload = {
    ts: new Date().toISOString(),
    event,
    ...sanitizeContext(context)
  }
  const writer = level === 'debug' ? console.debug : level === 'info' ? console.info : level === 'warn' ? console.warn : console.error
  writer('[PFMT]', payload)
}

export const clientLogger = {
  debug: (event: string, context?: ClientLogContext) => emit('debug', event, context),
  info: (event: string, context?: ClientLogContext) => emit('info', event, context),
  warn: (event: string, context?: ClientLogContext) => emit('warn', event, context),
  error: (event: string, context?: ClientLogContext) => emit('error', event, context)
}
