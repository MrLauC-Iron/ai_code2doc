import axios from 'axios'

const http = axios.create({ baseURL: '/api/v1' })

export const api = {
  getProject() {
    return http.get('/project').then(r => r.data)
  },
  getOverview() {
    return http.get('/project/overview').then(r => r.data)
  },
  getModules() {
    return http.get('/modules').then(r => r.data)
  },
  getModule(path: string) {
    return http.get(`/modules/${path}`).then(r => r.data)
  },
  getGraph() {
    return http.get('/graph').then(r => r.data)
  },
  getMermaid() {
    return http.get('/graph/mermaid').then(r => r.data)
  },
  search(query: string, nResults = 5) {
    return http.post('/search', { query, n_results: nResults }).then(r => r.data)
  },
  ask(question: string) {
    return http.post('/ask', { question }).then(r => r.data)
  },
}
