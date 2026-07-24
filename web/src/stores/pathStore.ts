import { defineStore } from 'pinia'

import { pathsApi } from '@/api/paths'
import type { FilePathNode } from '@/types/files'

const ROOT_PATH: FilePathNode = {
  path_id: 'root',
  parent_path_id: null,
  path_name: '根目录',
  path_type: 'normal',
  path_level: 0,
  full_path: '/',
  is_hidden: false,
  children: []
}

export const usePathStore = defineStore('paths', {
  state: () => ({
    tree: [ROOT_PATH] as FilePathNode[],
    selectedPathId: ROOT_PATH.path_id,
    loading: false
  }),
  getters: {
    selectedPath(state) {
      const walk = (nodes: FilePathNode[]): FilePathNode | null => {
        for (const node of nodes) {
          if (node.path_id === state.selectedPathId) {
            return node
          }

          const found = walk(node.children ?? [])
          if (found) {
            return found
          }
        }

        return null
      }

      return walk(state.tree) ?? ROOT_PATH
    }
  },
  actions: {
    async loadTree(showHidden: boolean) {
      this.loading = true
      try {
        const tree = await pathsApi.getPathTree(showHidden)
        this.tree = tree.length > 0 ? tree : [ROOT_PATH]
      } catch {
        this.tree = [ROOT_PATH]
      } finally {
        this.loading = false
      }
    },
    selectPath(pathId: string) {
      this.selectedPathId = pathId
    }
  }
})
