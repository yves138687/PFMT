import { http } from './http'
import type { FilePathNode, PathCreatePayload } from '@/types/files'

function normalizeNode(node: FilePathNode): FilePathNode {
  return {
    ...node,
    parent_path_id: node.parent_path_id ?? null,
    children: (node.children ?? []).map(normalizeNode)
  }
}

export const pathsApi = {
  async getPathTree(showHidden: boolean) {
    const response = await http.get<FilePathNode[] | { nodes: FilePathNode[] }>('/paths/tree', {
      query: {
        show_hidden: showHidden
      }
    })

    const nodes = Array.isArray(response) ? response : response.nodes
    return nodes.map(normalizeNode)
  },
  async createPath(payload: PathCreatePayload) {
    const response = await http.post<FilePathNode>('/paths', payload)
    return normalizeNode(response)
  },
  async movePath(pathId: string, parentPathId: string) {
    const response = await http.patch<FilePathNode>(`/paths/${encodeURIComponent(pathId)}/move`, {
      parent_path_id: parentPathId
    })
    return normalizeNode(response)
  },
  deletePath(pathId: string) {
    return http.delete<void>(`/paths/${encodeURIComponent(pathId)}`)
  }
}

export function getPathTreeApi(showHidden = false) {
  return pathsApi.getPathTree(showHidden)
}
