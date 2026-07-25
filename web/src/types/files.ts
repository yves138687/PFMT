export type FileType = 'text' | 'image' | 'video' | 'pdf' | 'audio' | 'other'
export type VisibilityType = 'normal' | 'private'

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
  visibility_type: VisibilityType
  status?: string
  created_at?: string
  updated_at?: string
  last_accessed_at?: string | null
}

export interface FileTag {
  tag_id: string
  tag_name: string
  tag_color?: string | null
}

export interface FileDetail extends FileInfo {
  logical_path: string
}

export interface FilePathNode {
  path_id: string
  parent_path_id: string | null
  path_name: string
  path_type: VisibilityType
  path_level: number
  full_path: string
  description?: string | null
  is_hidden: boolean
  children: FilePathNode[]
}

export interface PathCreatePayload {
  path_name: string
  parent_path_id: string
  path_type: VisibilityType
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

export interface UploadFilePayload {
  file: File
  pathId: string
  relativePath?: string
  encryptionEnabled: boolean
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
