import { http } from './http'
import type {
  DocumentContent,
  DocumentCreatePayload,
  DocumentConvertPayload,
  DocumentMergePayload,
  FileBatchDeletePayload,
  FileDashboardSummary,
  DocumentSavePayload,
  FileDetail,
  FileEmbedToken,
  FileInfo,
  FilePreviewToken,
  FileSearchResponse,
  FileTag,
  FileTagImportPayload,
  FileTagImportResponse,
  FileTagUpdatePayload,
  FileTagSuggestionResponse,
  FileUpdatePayload,
  MarkdownFileContent,
  TextFileContent,
  UploadFilePayload
} from '@/types/files'

export const filesApi = {
  listFiles(pathId = 'root') {
    return http.get<FileInfo[]>('/files', {
      query: {
        path_id: pathId
      }
    })
  },
  searchFiles(query: string, limit = 50) {
    return http.get<FileSearchResponse>('/files/search', {
      query: {
        q: query,
        limit
      }
    })
  },
  getDashboardSummary() {
    return http.get<FileDashboardSummary>('/files/dashboard')
  },
  uploadFile(payload: UploadFilePayload) {
    const formData = new FormData()
    formData.append('file', payload.file)
    formData.append('path_id', payload.pathId)
    formData.append('encryption_enabled', String(payload.encryptionEnabled))
    formData.append('conflict_strategy', payload.conflictStrategy ?? 'rename')

    if (payload.relativePath) {
      formData.append('relative_path', payload.relativePath)
    }

    return http.post<FileInfo>('/files/upload', formData)
  },
  getFileDetail(fileId: string) {
    return http.get<FileDetail>(`/files/${encodeURIComponent(fileId)}`)
  },
  updateFile(fileId: string, payload: FileUpdatePayload) {
    return http.patch<FileDetail>(`/files/${encodeURIComponent(fileId)}`, payload)
  },
  updateFileRemark(fileId: string, remark: string | null) {
    return filesApi.updateFile(fileId, { remark })
  },
  updateFileTags(fileId: string, tagNames: string[]) {
    return http.put<FileDetail>(
      `/files/${encodeURIComponent(fileId)}/tags`,
      {
        tag_names: tagNames
      }
    )
  },
  suggestFileTags(fileId: string, limit = 80) {
    return http.post<FileTagSuggestionResponse>(
      `/files/${encodeURIComponent(fileId)}/tag-suggestions`,
      undefined,
      {
        query: {
          limit
        }
      }
    )
  },
  moveFile(fileId: string, pathId: string) {
    return http.patch<FileDetail>(
      `/files/${encodeURIComponent(fileId)}/move`,
      {
        path_id: pathId
      }
    )
  },
  deleteFile(fileId: string) {
    return http.delete<void>(`/files/${encodeURIComponent(fileId)}`)
  },
  deleteFiles(fileIds: string[]) {
    const payload: FileBatchDeletePayload = {
      file_ids: fileIds
    }
    return http.post<void>('/files/delete', payload)
  },
  exportFile(fileId: string) {
    return http.blobResponse(`/files/${encodeURIComponent(fileId)}/export`, {
      method: 'GET'
    })
  },
  exportFiles(fileIds: string[]) {
    return http.blobResponse('/files/export', {
      method: 'POST',
      body: {
        file_ids: fileIds
      }
    })
  },
  getMarkdownFile(fileId: string) {
    return http.get<MarkdownFileContent>(`/files/${encodeURIComponent(fileId)}/markdown`)
  },
  getTextFile(fileId: string) {
    return http.get<TextFileContent>(`/files/${encodeURIComponent(fileId)}/text`)
  },
  getPreviewBlob(fileId: string) {
    return http.blob(`/files/${encodeURIComponent(fileId)}/preview`)
  },
  issuePreviewToken(fileId: string) {
    return http.post<FilePreviewToken>(`/files/${encodeURIComponent(fileId)}/preview-token`)
  },
  issueEmbedToken(fileId: string) {
    return http.post<FileEmbedToken>(`/files/${encodeURIComponent(fileId)}/embed-token`)
  },
  getDocument(fileId: string, options: { readSection?: number } = {}) {
    return http.get<DocumentContent>(`/files/${encodeURIComponent(fileId)}/document`, {
      query: {
        read_section: options.readSection
      }
    })
  },
  createDocument(payload: DocumentCreatePayload) {
    return http.post<FileDetail>('/files/document', payload)
  },
  saveDocument(fileId: string, payload: DocumentSavePayload) {
    return http.put<DocumentContent>(`/files/${encodeURIComponent(fileId)}/document`, payload)
  },
  convertDocument(fileId: string, payload: DocumentConvertPayload) {
    return http.post<FileDetail>(`/files/${encodeURIComponent(fileId)}/convert`, payload)
  },
  mergeDocuments(payload: DocumentMergePayload) {
    return http.post<FileDetail>('/files/merge', payload)
  }
}

export const tagsApi = {
  listTags(options: { withUsage?: boolean, includeUnused?: boolean } = {}) {
    return http.get<FileTag[]>('/tags', {
      query: {
        with_usage: options.withUsage,
        include_unused: options.includeUnused
      }
    })
  },
  createTag(tagName: string, tagColor?: string | null) {
    return http.post<FileTag>('/tags', {
      tag_name: tagName,
      tag_color: tagColor
    })
  },
  updateTag(tagId: string, payload: FileTagUpdatePayload) {
    return http.patch<FileTag>(`/tags/${encodeURIComponent(tagId)}`, payload)
  },
  deleteTag(tagId: string) {
    return http.delete<void>(`/tags/${encodeURIComponent(tagId)}`)
  },
  importTags(payload: FileTagImportPayload) {
    return http.post<FileTagImportResponse>('/tags/import', payload)
  },
  listTagFiles(tagId: string) {
    return http.get<FileSearchResponse>(`/tags/${encodeURIComponent(tagId)}/files`)
  }
}

export async function uploadFileApi(pathId: string, file: File) {
  return filesApi.uploadFile({
    file,
    pathId,
    encryptionEnabled: true
  })
}

export function readMarkdownApi(fileId: string) {
  return filesApi.getMarkdownFile(fileId)
}
