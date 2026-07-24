import { http } from './http'
import type { FilePathNode } from '@/types/files'

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
  }
}

export function getPathTreeApi(showHidden = false) {
  return pathsApi.getPathTree(showHidden)
}
