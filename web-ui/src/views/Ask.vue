<template>
  <div>
    <h2 class="text-2xl font-bold mb-4">Ask about the codebase</h2>
    <div class="bg-white rounded-lg shadow p-6 mb-4">
      <div class="flex gap-2">
        <input v-model="question" @keyup.enter="askQuestion"
               class="flex-1 border rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
               placeholder="Ask a question about the codebase..." />
        <button @click="askQuestion" :disabled="loading"
                class="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50">
          Ask
        </button>
      </div>
    </div>
    <div v-if="loading" class="text-gray-500">Thinking...</div>
    <div v-if="answer" class="space-y-4">
      <div class="bg-white rounded-lg shadow p-6">
        <h3 class="font-semibold mb-2">Answer</h3>
        <div class="prose max-w-none" v-html="renderedAnswer"></div>
      </div>
      <div v-if="sources.length" class="bg-white rounded-lg shadow p-6">
        <h3 class="font-semibold mb-2">Sources</h3>
        <div v-for="source in sources" :key="source.id" class="text-sm text-gray-600 border-b py-2 last:border-0">
          <span class="font-mono">{{ source.id }}</span>
          <span class="ml-2 text-gray-400">(score: {{ source.score?.toFixed(3) }})</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { api } from '../api/client'
import { marked } from 'marked'

const question = ref('')
const answer = ref('')
const sources = ref<any[]>([])
const loading = ref(false)

const renderedAnswer = computed(() => marked.parse(answer.value || ''))

async function askQuestion() {
  if (!question.value.trim()) return
  loading.value = true
  answer.value = ''
  sources.value = []
  try {
    const result = await api.ask(question.value)
    answer.value = result.answer
    sources.value = result.sources || []
  } catch (e: any) {
    answer.value = `Error: ${e.message}`
  } finally {
    loading.value = false
  }
}
</script>
