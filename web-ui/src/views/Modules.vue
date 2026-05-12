<template>
  <div>
    <h2 class="text-2xl font-bold mb-4">Modules</h2>
    <div v-if="loading" class="text-gray-500">Loading...</div>
    <div v-else>
      <div class="grid grid-cols-4 gap-4" v-if="!selectedModule">
        <div v-for="mod in modules" :key="mod.name"
             class="bg-white rounded-lg shadow p-4 cursor-pointer hover:shadow-lg transition-shadow"
             @click="selectedModule = mod">
          <h3 class="font-semibold text-blue-600">{{ mod.name }}</h3>
          <p class="text-sm text-gray-500 mt-1">{{ mod.file_count }} files</p>
        </div>
      </div>
      <div v-else>
        <button @click="selectedModule = null" class="mb-4 text-blue-600 hover:underline">&larr; Back to modules</button>
        <div class="bg-white rounded-lg shadow p-6">
          <div class="prose max-w-none" v-html="renderedModule"></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { api } from '../api/client'
import { marked } from 'marked'

const loading = ref(true)
const modules = ref<any[]>([])
const selectedModule = ref<any>(null)

const renderedModule = computed(() => {
  return marked.parse(selectedModule.value?.content || '')
})

onMounted(async () => {
  try {
    const data = await api.getModules()
    modules.value = data.modules
  } catch {} finally {
    loading.value = false
  }
})
</script>
