export type FileType = 'text' | 'image' | 'video' | 'pdf' | 'audio' | 'other'
export type VisibilityType = 'normal' | 'private'

export interface FileInfo {
  file_id: string
  path_id: string
  original_name: string
  storage_object_name: string
  storage_provider?: string
  mime_type?: string | null
  file_ext?: string | null
  file_type: FileType
  size_bytes: number
  checksum_sha256?: string | null
  encryption_enabled: boolean
  key_wrap_version?: string | null
  summary_content?: string | null
  is_hidden: boolean
  visibility_type: VisibilityType
  status?: string
  created_at?: string
  updated_at?: string
  last_accessed_at?: string | null
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

export interface UploadFilePayload {
  file: File
  pathId: string
  relativePath?: string
  encryptionEnabled: boolean
}

export interface UploadFileResult {
  file: FileInfo
  storage_object_name?: string
}

export interface MarkdownFileContent {
  file_id: string
  original_name: string
  content: string
  updated_at?: string
}
