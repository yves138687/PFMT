export type FileType = 'text' | 'image' | 'video' | 'pdf' | 'audio' | 'other'
export type DocumentFormat = 'plain_text' | 'markdown' | 'html'

export interface FileInfo {
  file_id: string
  path_id: string
  original_name: string
  mime_type?: string | null
  file_ext?: string | null
  file_type: FileType
  size_bytes: number
  checksum_sha256?: string | null
  encryption_enabled: boolean
  key_wrap_version?: string | null
  summary_content?: string | null
  remark?: string | null
  tags?: FileTag[]
  is_hidden: boolean
  status?: string
  created_at?: string
  updated_at?: string
  last_accessed_at?: string | null
}

export interface FileTag {
  tag_id: string
  tag_name: string
  tag_color?: string | null
  file_count?: number | null
}

export type TagImportDelimiter = 'newline' | 'comma_cn' | 'comma_en' | 'hash' | 'slash' | 'semicolon' | 'custom'

export interface FileTagUpdatePayload {
  tag_name?: string | null
  tag_color?: string | null
}

export interface FileTagImportPayload {
  raw_text: string
  delimiter: TagImportDelimiter
  custom_delimiter?: string | null
}

export interface FileTagImportResponse {
  created: FileTag[]
  reused: FileTag[]
  invalid: string[]
  total_created: number
  total_reused: number
  total_invalid: number
}

export type FileTagSuggestionSource = 'existing_tag_match' | 'keyword_weight'

export interface FileTagSuggestionItem {
  tag_name: string
  score: number
  source: FileTagSuggestionSource
  existing_tag_id?: string | null
  matched_count?: number | null
}

export interface FileTagSuggestionResponse {
  items: FileTagSuggestionItem[]
}

export interface FileDetail extends FileInfo {
  logical_path: string
}

export interface FilePathNode {
  path_id: string
  parent_path_id: string | null
  path_name: string
  path_level: number
  full_path: string
  description?: string | null
  is_hidden: boolean
  children: FilePathNode[]
}

export interface PathCreatePayload {
  path_name: string
  parent_path_id: string
  description?: string | null
  is_hidden: boolean
}

export interface PathUpdatePayload {
  path_name?: string | null
  description?: string | null
  is_hidden?: boolean | null
}

export interface FileUpdatePayload {
  original_name?: string | null
  remark?: string | null
  summary_content?: string | null
  is_hidden?: boolean | null
}

export interface FileSearchResponse {
  items: FileDetail[]
  total: number
}

export interface FileDashboardSummary {
  file_total: number
  path_total: number
  markdown_total: number
  recent_accessed: FileDetail[]
}

export interface UploadFilePayload {
  file: File
  pathId: string
  relativePath?: string
  encryptionEnabled: boolean
  conflictStrategy?: 'rename' | 'overwrite'
}

export interface MarkdownFileContent {
  file_id: string
  original_name: string
  mime_type?: string | null
  size_bytes: number
  encoding?: string
  content: string
  updated_at?: string
}

export interface TextFileContent {
  file_id: string
  original_name: string
  mime_type?: string | null
  size_bytes: number
  encoding?: string
  content: string
  updated_at?: string
}

export interface FilePreviewToken {
  file_id: string
  preview_url: string
  expires_at: string
}

export interface FileEmbedToken {
  file_id: string
  url: string
  expires_at: string
}

export interface DocumentContent {
  file_id: string
  original_name: string
  mime_type?: string | null
  size_bytes: number
  encoding?: string
  is_hidden?: boolean
  document_format: DocumentFormat
  content: string
  editable: boolean
  rendered_html?: string | null
}

export interface DocumentSavePayload {
  content: string
  document_format: DocumentFormat
}

export interface DocumentCreatePayload {
  path_id: string
  original_name: string
  document_format: DocumentFormat
  is_hidden?: boolean
}

export interface DocumentConvertPayload {
  target_format: DocumentFormat
  target_name?: string | null
}

export interface DocumentMergePayload {
  file_ids: string[]
  target_format: DocumentFormat
  target_name?: string | null
}

export interface FileBatchDeletePayload {
  file_ids: string[]
}
