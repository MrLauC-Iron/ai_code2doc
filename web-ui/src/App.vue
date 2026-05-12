<template>
  <div class="flex h-screen">
    <nav class="w-64 bg-gray-900 text-white flex flex-col">
      <div class="p-4 border-b border-gray-700">
        <h1 class="text-xl font-bold">ai-code2doc</h1>
        <p class="text-gray-400 text-sm mt-1">{{ projectName }}</p>
      </div>
      <div class="flex-1 py-4">
        <router-link to="/" class="nav-link" active-class="bg-gray-800">
          <span class="mr-2">📊</span> Overview
        </router-link>
        <router-link to="/modules" class="nav-link" active-class="bg-gray-800">
          <span class="mr-2">📁</span> Modules
        </router-link>
        <router-link to="/graph" class="nav-link" active-class="bg-gray-800">
          <span class="mr-2">🔗</span> Dependencies
        </router-link>
        <router-link to="/ask" class="nav-link" active-class="bg-gray-800">
          <span class="mr-2">💬</span> Ask
        </router-link>
      </div>
    </nav>
    <main class="flex-1 overflow-auto p-6">
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from './api/client'

const projectName = ref('Loading...')

onMounted(async () => {
  try {
    const data = await api.getProject()
    projectName.value = data.name
  } catch {
    projectName.value = 'Unknown Project'
  }
})
</script>

<style scoped>
.nav-link {
  @apply block px-4 py-2 text-gray-300 hover:bg-gray-800 hover:text-white transition-colors;
}
</style>
