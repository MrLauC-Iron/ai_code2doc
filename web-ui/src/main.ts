import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import './style.css'
import Overview from './views/Overview.vue'
import Modules from './views/Modules.vue'
import Graph from './views/Graph.vue'
import Ask from './views/Ask.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: Overview },
    { path: '/modules', component: Modules },
    { path: '/modules/:path+', component: Modules },
    { path: '/graph', component: Graph },
    { path: '/ask', component: Ask },
  ],
})

createApp(App).use(router).mount('#app')
