<template>
  <div>
    <h2 class="text-2xl font-bold mb-4">Project Overview</h2>
    <div v-if="loading" class="text-gray-500">Loading...</div>
    <div v-else-if="error" class="text-red-500">{{ error }}</div>
    <div v-else>
      <div class="grid grid-cols-3 gap-4 mb-6">
        <div class="bg-white rounded-lg shadow p-4">
          <h3 class="text-sm text-gray-500">Framework</h3>
          <p class="text-xl font-semibold">{{ overview.tech_stack?.framework || 'N/A' }}</p>
        </div>
        <div class="bg-white rounded-lg shadow p-4">
          <h3 class="text-sm text-gray-500">Language</h3>
          <p class="text-xl font-semibold">{{ overview.tech_stack?.language || 'N/A' }}</p>
        </div>
        <div class="bg-white rounded-lg shadow p-4">
          <h3 class="text-sm text-gray-500">Build Tool</h3>
          <p class="text-xl font-semibold">{{ overview.tech_stack?.build_tool || 'N/A' }}</p>
        </div>
      </div>
      <div class="bg-white rounded-lg shadow p-6">
        <div class="prose max-w-none" v-html="renderedContent"></div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { api } from '../api/client'
import { marked } from 'marked'

const loading = ref(true)
const error = ref('')
const overview = ref<any>({})

const renderedContent = computed(() => {
  return marked.parse(overview.value.overview_content || '')
})

onMounted(async () => {
  try {
    overview.value = await api.getOverview()
  } catch (e: any) {
    error.value = e.message
  } finally {
    loading.value = false
  }
})
</script>
