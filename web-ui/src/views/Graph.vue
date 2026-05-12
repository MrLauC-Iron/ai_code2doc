<template>
  <div>
    <h2 class="text-2xl font-bold mb-4">Dependency Graph</h2>
    <div v-if="loading" class="text-gray-500">Loading graph...</div>
    <div v-else class="bg-white rounded-lg shadow p-6">
      <div ref="mermaidContainer" class="overflow-auto"></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '../api/client'
import mermaid from 'mermaid'

mermaid.initialize({ startOnLoad: false, theme: 'default' })

const loading = ref(true)
const mermaidContainer = ref<HTMLElement>()

onMounted(async () => {
  try {
    const graphStr = await api.getMermaid()
    if (mermaidContainer.value && graphStr) {
      const { svg } = await mermaid.render('graph-svg', graphStr)
      mermaidContainer.value.innerHTML = svg
    }
  } catch (e) {
    if (mermaidContainer.value) {
      mermaidContainer.value.innerHTML = '<p class="text-gray-500">No dependency graph available. Run analysis first.</p>'
    }
  } finally {
    loading.value = false
  }
})
</script>
